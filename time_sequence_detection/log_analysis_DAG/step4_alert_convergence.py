#!/usr/bin/env python3
"""
Step 4: 告警收敛应用
基于 DAG 的告警收敛：如果 DAG 中 DB 挂了，
那么下游的 OrderService 和 Frontend 的告警都是 DB 引起的，
只发一条根因告警
"""
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from step3_build_dag import ServiceDAG


@dataclass
class Alert:
    alert_id: str
    timestamp: str
    service: str
    level: str
    message: str
    is_root_cause: bool = False
    suppressed: bool = False
    suppress_reason: str = ""


@dataclass
class ConvergedAlertGroup:
    root_cause_alert: Alert
    suppressed_alerts: List[Alert] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    propagation_path: List[List[str]] = field(default_factory=list)
    confidence: str = "MEDIUM"
    summary: str = ""


class AlertConverger:
    """
    基于 DAG 的告警收敛器
    
    核心逻辑：
    1. 收到告警后，在 DAG 中定位该服务
    2. 沿 DAG 上游查找根因服务
    3. 如果根因服务也有告警，则下游告警全部收敛
    4. 只发出根因告警，附带影响范围
    """
    
    def __init__(self, dag: ServiceDAG):
        self.dag = dag
        self._active_alerts: Dict[str, Alert] = {}
        self._converged_groups: List[ConvergedAlertGroup] = []
        self._alert_window: List[Alert] = []
        self._window_size = 300  # 5分钟窗口
    
    def add_alert(self, alert: Alert) -> Dict[str, Any]:
        """
        添加告警并进行收敛判断
        """
        self._active_alerts[alert.service] = alert
        self._alert_window.append(alert)
        
        return self._evaluate_alert(alert)
    
    def _evaluate_alert(self, alert: Alert) -> Dict[str, Any]:
        """
        评估告警是否需要收敛
        
        DAG 边方向: A → B 表示 A 调用 B（A 依赖 B）
        故障传播方向: B 故障 → A 受影响（沿调用链反向传播）
        因此查找根因时应沿 DAG 下游（依赖方向）查找
        """
        service = alert.service
        
        if service not in self.dag.nodes:
            return {
                "action": "PASS_THROUGH",
                "alert_id": alert.alert_id,
                "reason": f"服务 {service} 不在 DAG 中，直接发送",
                "root_cause": None,
            }
        
        downstream = self.dag.get_downstream(service)
        downstream_with_alerts = [s for s in downstream if s in self._active_alerts]
        
        if not downstream_with_alerts:
            return {
                "action": "SEND",
                "alert_id": alert.alert_id,
                "reason": f"服务 {service} 的依赖服务无告警，判定为根因",
                "root_cause": service,
                "is_root_cause": True,
            }
        
        root_causes = self.dag.find_root_causes(downstream_with_alerts + [service])
        
        if root_causes:
            root_service = root_causes[0]["service"]
            
            if root_service != service:
                alert.suppressed = True
                alert.suppress_reason = f"由依赖服务 {root_service} 故障引起"
                
                upstream_of_root = self.dag.get_upstream(root_service)
                
                return {
                    "action": "SUPPRESS",
                    "alert_id": alert.alert_id,
                    "reason": f"服务 {service} 的告警由依赖 {root_service} 故障引起，已收敛",
                    "root_cause": root_service,
                    "is_root_cause": False,
                    "suppressed": True,
                    "propagation_path": self._trace_propagation_reverse(root_service, service),
                    "affected_callers": [s for s in upstream_of_root if s in self._active_alerts],
                }
        
        return {
            "action": "SEND",
            "alert_id": alert.alert_id,
            "reason": f"无法确定依赖根因，直接发送",
            "root_cause": service,
            "is_root_cause": True,
        }
    
    def _trace_propagation(self, root: str, target: str) -> List[str]:
        """追踪从根因到目标服务的传播路径（沿调用方向）"""
        from collections import deque
        
        visited = {root}
        queue = deque([(root, [root])])
        
        while queue:
            node, path = queue.popleft()
            if node == target:
                return path
            
            for neighbor in self.dag._adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return [root, target]
    
    def _trace_propagation_reverse(self, root: str, target: str) -> List[str]:
        """
        追踪故障传播路径（沿调用链反向）
        root 是依赖服务（如 DB-Master），target 是受影响的调用方（如 OrderService）
        路径: root → ... → target（沿 _rev_adj 搜索）
        """
        from collections import deque
        
        visited = {root}
        queue = deque([(root, [root])])
        
        while queue:
            node, path = queue.popleft()
            if node == target:
                return path
            
            for neighbor in self.dag._rev_adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return [root, "...", target]
    
    def converge_batch(self, alerts: List[Alert]) -> Dict[str, Any]:
        """
        批量告警收敛
        
        对一批告警进行统一收敛处理，返回收敛结果
        """
        results = []
        root_cause_alerts = []
        suppressed_alerts = []
        
        for alert in alerts:
            result = self.add_alert(alert)
            results.append(result)
            
            if result["action"] == "SUPPRESS":
                alert.suppressed = True
                alert.suppress_reason = result.get("reason", "")
                suppressed_alerts.append(alert)
            else:
                alert.is_root_cause = result.get("is_root_cause", False)
                root_cause_alerts.append(alert)
        
        # 按根因分组
        groups = self._group_by_root_cause(results, alerts)
        
        return {
            "total_input": len(alerts),
            "root_cause_count": len(root_cause_alerts),
            "suppressed_count": len(suppressed_alerts),
            "compression_ratio": round(len(root_cause_alerts) / max(len(alerts), 1) * 100, 1),
            "groups": groups,
            "root_cause_alerts": [
                {
                    "alert_id": a.alert_id,
                    "service": a.service,
                    "level": a.level,
                    "message": a.message,
                }
                for a in root_cause_alerts
            ],
            "suppressed_alerts": [
                {
                    "alert_id": a.alert_id,
                    "service": a.service,
                    "level": a.level,
                    "message": a.message,
                    "suppress_reason": a.suppress_reason,
                }
                for a in suppressed_alerts
            ],
        }
    
    def _group_by_root_cause(
        self, 
        results: List[Dict], 
        alerts: List[Alert]
    ) -> List[Dict[str, Any]]:
        """按根因分组"""
        groups: Dict[str, ConvergedAlertGroup] = {}
        
        for alert, result in zip(alerts, results):
            root_cause = result.get("root_cause", alert.service)
            
            if root_cause not in groups:
                root_alert = self._active_alerts.get(root_cause, alert)
                groups[root_cause] = ConvergedAlertGroup(
                    root_cause_alert=Alert(
                        alert_id=f"ROOT-{root_cause}",
                        timestamp=root_alert.timestamp,
                        service=root_cause,
                        level=root_alert.level,
                        message=root_alert.message,
                        is_root_cause=True,
                    ),
                    affected_services=[],
                    confidence=result.get("is_root_cause", False) and "HIGH" or "MEDIUM",
                )
            
            group = groups[root_cause]
            if alert.service != root_cause:
                group.suppressed_alerts.append(alert)
                if alert.service not in group.affected_services:
                    group.affected_services.append(alert.service)
                group.propagation_path.append(
                    result.get("propagation_path", [root_cause, alert.service])
                )
        
        result_groups = []
        for root, group in groups.items():
            upstream_callers = self.dag.get_upstream(root)
            group.summary = (
                f"根因: {root} | 影响: {len(group.affected_services)} 个调用方服务 "
                f"({', '.join(group.affected_services)}) | "
                f"全部受影响调用方: {', '.join(upstream_callers)}"
            )
            result_groups.append({
                "root_cause": root,
                "root_alert": {
                    "service": group.root_cause_alert.service,
                    "level": group.root_cause_alert.level,
                    "message": group.root_cause_alert.message,
                },
                "suppressed_count": len(group.suppressed_alerts),
                "affected_services": group.affected_services,
                "all_affected_callers": upstream_callers,
                "propagation_paths": group.propagation_path,
                "confidence": group.confidence,
                "summary": group.summary,
            })
        
        return result_groups


def run_alert_convergence(
    dag_file: str = None,
    output_dir: str = None,
) -> Dict[str, Any]:
    """
    执行告警收敛演示
    """
    if dag_file is None:
        dag_file = str(Path(__file__).parent / "data" / "dag" / "service_dag.json")
    if output_dir is None:
        output_dir = str(Path(__file__).parent / "data" / "results")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 加载 DAG
    with open(dag_file, "r", encoding="utf-8") as f:
        dag_data = json.load(f)
    dag = ServiceDAG.from_dict(dag_data)
    
    converger = AlertConverger(dag)
    
    # ===== 场景1: DB 宕机导致级联告警 =====
    print("=" * 60)
    print("场景1: DB-Master 宕机 → 级联告警收敛")
    print("=" * 60)
    
    db_down_alerts = [
        Alert("ALT-001", "2026-04-24 12:00:01", "DB-Master", "CRITICAL",
              "Connection refused: too many connections"),
        Alert("ALT-002", "2026-04-24 12:00:02", "OrderService", "ERROR",
              "DB query timeout: SELECT * FROM orders"),
        Alert("ALT-003", "2026-04-24 12:00:03", "PaymentService", "ERROR",
              "DB write timeout: INSERT INTO payments"),
        Alert("ALT-004", "2026-04-24 12:00:04", "UserService", "ERROR",
              "DB query: SELECT * FROM users - timeout 30s"),
        Alert("ALT-005", "2026-04-24 12:00:05", "InventoryService", "ERROR",
              "DB query timeout: SELECT stock FROM inventory"),
        Alert("ALT-006", "2026-04-24 12:00:06", "Frontend", "WARN",
              "Upstream timeout: OrderService"),
        Alert("ALT-007", "2026-04-24 12:00:07", "Frontend", "WARN",
              "Upstream timeout: PaymentService"),
    ]
    
    result1 = converger.converge_batch(db_down_alerts)
    
    print(f"\n输入告警: {result1['total_input']} 条")
    print(f"根因告警: {result1['root_cause_count']} 条")
    print(f"收敛告警: {result1['suppressed_count']} 条")
    print(f"压缩率: {result1['compression_ratio']}%")
    
    for group in result1["groups"]:
        print(f"\n  根因: {group['root_cause']}")
        print(f"  根因告警: [{group['root_alert']['level']}] {group['root_alert']['message']}")
        print(f"  收敛下游: {group['suppressed_count']} 条")
        print(f"  影响服务: {', '.join(group['affected_services'])}")
        print(f"  传播路径: {group['propagation_paths']}")
        print(f"  总结: {group['summary']}")
    
    # 保存结果
    result_file = output_path / "alert_convergence_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result1, f, ensure_ascii=False, indent=2)
    print(f"\n结果保存到: {result_file}")
    
    # ===== 场景2: Redis 主从切换 =====
    print("\n" + "=" * 60)
    print("场景2: Redis 主从切换 → 缓存雪崩告警收敛")
    print("=" * 60)
    
    converger2 = AlertConverger(dag)
    redis_alerts = [
        Alert("ALT-101", "2026-04-24 14:00:01", "Redis-Cache", "WARN",
              "Master failover initiated"),
        Alert("ALT-102", "2026-04-24 14:00:02", "Redis-Cache", "ERROR",
              "Connection refused: max clients reached"),
        Alert("ALT-103", "2026-04-24 14:00:03", "PaymentService", "WARN",
              "Cache miss for payment session"),
        Alert("ALT-104", "2026-04-24 14:00:04", "UserService", "WARN",
              "Cache miss for user profile"),
        Alert("ALT-105", "2026-04-24 14:00:05", "Frontend", "WARN",
              "Upstream timeout: UserService"),
    ]
    
    result2 = converger2.converge_batch(redis_alerts)
    
    print(f"\n输入告警: {result2['total_input']} 条")
    print(f"根因告警: {result2['root_cause_count']} 条")
    print(f"收敛告警: {result2['suppressed_count']} 条")
    
    for group in result2["groups"]:
        print(f"\n  根因: {group['root_cause']}")
        print(f"  影响服务: {', '.join(group['affected_services'])}")
        print(f"  总结: {group['summary']}")
    
    return {"db_down": result1, "redis_failover": result2}


if __name__ == "__main__":
    run_alert_convergence()
