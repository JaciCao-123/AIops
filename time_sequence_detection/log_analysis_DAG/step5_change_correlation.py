#!/usr/bin/env python3
"""
Step 5: 变更关联应用
基于 DAG 的变更关联分析：如果 PaymentService 变慢，
查看 DAG 上游，发现是 DB 刚刚做了变更
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from step3_build_dag import ServiceDAG


@dataclass
class ChangeRecord:
    change_id: str
    service: str
    change_type: str
    description: str
    timestamp: str
    operator: str = ""
    risk_level: str = "MEDIUM"


@dataclass
class AnomalyEvent:
    event_id: str
    service: str
    anomaly_type: str
    description: str
    timestamp: str
    severity: str = "WARN"
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorrelationResult:
    anomaly: AnomalyEvent
    related_changes: List[ChangeRecord] = field(default_factory=list)
    upstream_anomalies: List[Dict[str, Any]] = field(default_factory=list)
    root_cause_hypothesis: str = ""
    confidence: str = "LOW"
    evidence: List[str] = field(default_factory=list)
    recommendation: str = ""


class ChangeCorrelator:
    """
    基于 DAG 的变更关联分析器
    
    核心逻辑：
    1. 当服务出现异常时，沿 DAG 上游查找
    2. 检查上游服务是否有最近的变更记录
    3. 分析变更与异常的时间关系和因果链
    4. 生成变更关联分析报告
    """
    
    def __init__(self, dag: ServiceDAG):
        self.dag = dag
        self._change_records: List[ChangeRecord] = []
        self._anomaly_events: List[AnomalyEvent] = []
    
    def add_change_record(self, change: ChangeRecord):
        self._change_records.append(change)
    
    def load_change_records(self, changes: List[Dict[str, Any]]):
        for ch in changes:
            self.add_change_record(ChangeRecord(
                change_id=ch.get("change_id", f"CHG-{len(self._change_records) + 1:04d}"),
                service=ch["service"],
                change_type=ch.get("change_type", "normal"),
                description=ch.get("description", ""),
                timestamp=ch.get("timestamp", ""),
                operator=ch.get("operator", ""),
                risk_level=ch.get("risk_level", "MEDIUM"),
            ))
    
    def add_anomaly_event(self, anomaly: AnomalyEvent):
        self._anomaly_events.append(anomaly)
    
    def _find_changes_for_service(
        self, 
        service: str, 
        lookback_hours: int = 72,
    ) -> List[ChangeRecord]:
        """查找服务最近的变更记录"""
        now = datetime.now()
        cutoff = now - timedelta(hours=lookback_hours)
        
        related = []
        for change in self._change_records:
            if change.service != service:
                continue
            try:
                change_time = datetime.strptime(change.timestamp, "%Y-%m-%d %H:%M:%S")
                if change_time >= cutoff:
                    related.append(change)
            except ValueError:
                related.append(change)
        
        return sorted(related, key=lambda c: c.timestamp, reverse=True)
    
    def _find_dependency_changes(
        self,
        service: str,
        lookback_hours: int = 72,
        max_depth: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        沿 DAG 下游（依赖方向）查找变更记录
        
        DAG 边方向: A → B 表示 A 调用 B（A 依赖 B）
        当 A 出现异常时，应检查 A 的依赖（下游方向）是否有变更
        """
        dependencies = self.dag.get_downstream(service, depth=max_depth)
        dep_changes = []
        
        for dep_service in dependencies:
            changes = self._find_changes_for_service(dep_service, lookback_hours)
            for change in changes:
                dep_changes.append({
                    "service": dep_service,
                    "change_id": change.change_id,
                    "change_type": change.change_type,
                    "description": change.description,
                    "timestamp": change.timestamp,
                    "operator": change.operator,
                    "risk_level": change.risk_level,
                    "distance": self._get_distance(service, dep_service),
                    "propagation_path": self._trace_path(service, dep_service),
                })
        
        return sorted(dep_changes, key=lambda x: x.get("distance", 999))
    
    def _get_distance(self, source: str, target: str) -> int:
        """计算两个服务之间的最短距离"""
        from collections import deque
        
        visited = {source}
        queue = deque([(source, 0)])
        
        while queue:
            node, dist = queue.popleft()
            if node == target:
                return dist
            
            for neighbor in self.dag._adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        
        return -1
    
    def _trace_path(self, source: str, target: str) -> List[str]:
        """追踪从 source 到 target 的路径"""
        from collections import deque
        
        visited = {source}
        queue = deque([(source, [source])])
        
        while queue:
            node, path = queue.popleft()
            if node == target:
                return path
            
            for neighbor in self.dag._adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return [source, "...", target]
    
    def correlate(
        self,
        anomaly: AnomalyEvent,
        lookback_hours: int = 72,
    ) -> CorrelationResult:
        """
        执行变更关联分析
        
        Args:
            anomaly: 异常事件
            lookback_hours: 回溯时间（小时）
            
        Returns:
            关联分析结果
        """
        result = CorrelationResult(anomaly=anomaly)
        
        # 1. 检查异常服务自身的变更
        self_changes = self._find_changes_for_service(anomaly.service, lookback_hours)
        
        # 2. 检查依赖服务的变更（沿 DAG 下游方向）
        dep_changes = self._find_dependency_changes(anomaly.service, lookback_hours)
        
        all_changes = []
        for ch in self_changes:
            all_changes.append({
                "service": anomaly.service,
                "change_id": ch.change_id,
                "change_type": ch.change_type,
                "description": ch.description,
                "timestamp": ch.timestamp,
                "operator": ch.operator,
                "risk_level": ch.risk_level,
                "relation": "self",
                "distance": 0,
            })
        all_changes.extend(dep_changes)
        result.related_changes = all_changes
        
        # 3. 检查依赖服务的异常
        dependencies = self.dag.get_downstream(anomaly.service)
        for dep_svc in dependencies:
            if dep_svc in self.dag.nodes and self.dag.nodes[dep_svc].is_anomaly:
                result.upstream_anomalies.append({
                    "service": dep_svc,
                    "error_rate": self.dag.nodes[dep_svc].error_rate,
                    "propagation_path": self._trace_path(anomaly.service, dep_svc),
                })
        
        # 4. 生成根因假设
        result.root_cause_hypothesis, result.confidence, result.evidence = \
            self._generate_hypothesis(anomaly, all_changes, result.upstream_anomalies)
        
        # 5. 生成建议
        result.recommendation = self._generate_recommendation(anomaly, all_changes, result)
        
        return result
    
    def _generate_hypothesis(
        self,
        anomaly: AnomalyEvent,
        changes: List[Dict],
        dep_anomalies: List[Dict],
    ) -> tuple:
        """生成根因假设"""
        evidence = []
        confidence = "LOW"
        hypothesis = ""
        
        for change in changes:
            if change.get("relation") == "self":
                evidence.append(f"[自身变更] {change['service']} 在 {change['timestamp']} 执行了: {change['description']}")
                if change.get("change_type") == "emergency":
                    evidence.append("  → 紧急变更，风险较高")
        
        for change in changes:
            if change.get("relation") != "self" and change.get("distance", 999) <= 2:
                evidence.append(
                    f"[依赖变更] {change['service']} (距离={change['distance']}) "
                    f"在 {change['timestamp']} 执行了: {change['description']}"
                )
                evidence.append(f"  → 依赖路径: {' → '.join(change.get('propagation_path', []))}")
        
        for da in dep_anomalies:
            evidence.append(
                f"[依赖异常] {da['service']} 错误率 {da['error_rate']}%, "
                f"依赖路径: {' → '.join(da['propagation_path'])}"
            )
        
        dep_critical_changes = [
            c for c in changes
            if c.get("relation") != "self"
            and c.get("distance", 999) <= 2
            and c.get("risk_level") in ("HIGH", "CRITICAL")
        ]
        
        if dep_critical_changes and dep_anomalies:
            confidence = "HIGH"
            root_change = dep_critical_changes[0]
            hypothesis = (
                f"{anomaly.service} {anomaly.anomaly_type} 的根因可能是依赖服务 "
                f"{root_change['service']} 的变更: {root_change['description']}。"
                f"变更通过 {' → '.join(root_change.get('propagation_path', []))} 传播影响。"
            )
        elif dep_critical_changes:
            confidence = "MEDIUM"
            root_change = dep_critical_changes[0]
            hypothesis = (
                f"{anomaly.service} {anomaly.anomaly_type} 可能与依赖服务 "
                f"{root_change['service']} 的变更有关: {root_change['description']}。"
                f"需进一步确认因果关系。"
            )
        elif dep_anomalies:
            confidence = "MEDIUM"
            root_anomaly = dep_anomalies[0]
            hypothesis = (
                f"{anomaly.service} {anomaly.anomaly_type} 可能由依赖服务 "
                f"{root_anomaly['service']} 的异常引起 (错误率 {root_anomaly['error_rate']}%)。"
                f"未发现关联变更，可能是运行时故障。"
            )
        else:
            confidence = "LOW"
            hypothesis = (
                f"{anomaly.service} {anomaly.anomaly_type} 未找到明确的依赖变更或异常关联。"
                f"可能是自身问题或外部因素。"
            )
        
        return hypothesis, confidence, evidence
    
    def _generate_recommendation(
        self,
        anomaly: AnomalyEvent,
        changes: List[Dict],
        result: CorrelationResult,
    ) -> str:
        """生成操作建议"""
        recommendations = []
        
        if result.confidence == "HIGH":
            dep_changes = [c for c in changes if c.get("relation") != "self"]
            if dep_changes:
                root = dep_changes[0]
                recommendations.append(
                    f"1. 优先检查依赖服务 {root['service']} 的变更 {root['change_id']}: {root['description']}"
                )
                recommendations.append(
                    f"2. 联系变更执行人 {root.get('operator', '未知')} 确认变更影响范围"
                )
                recommendations.append(
                    f"3. 评估是否需要回滚变更 {root['change_id']}"
                )
        elif result.confidence == "MEDIUM":
            recommendations.append("1. 检查依赖服务的运行状态和最近变更")
            recommendations.append("2. 对比异常发生前后的指标变化")
            recommendations.append("3. 查看依赖服务的错误日志")
        else:
            recommendations.append("1. 检查服务自身的配置和资源")
            recommendations.append("2. 查看服务日志定位具体错误")
            recommendations.append("3. 检查网络连通性和外部依赖")
        
        return "\n".join(recommendations)


def run_change_correlation(
    dag_file: str = None,
    output_dir: str = None,
) -> Dict[str, Any]:
    """
    执行变更关联分析演示
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
    
    correlator = ChangeCorrelator(dag)
    
    # 模拟变更记录
    change_records = [
        {
            "change_id": "CHG-0001",
            "service": "DB-Master",
            "change_type": "normal",
            "description": "ALTER TABLE payments ADD INDEX idx_status (status)",
            "timestamp": "2026-04-24 13:45:00",
            "operator": "DBA-Zhang",
            "risk_level": "HIGH",
        },
        {
            "change_id": "CHG-0002",
            "service": "DB-Master",
            "change_type": "normal",
            "description": "UPDATE config SET value='200' WHERE key='connection_pool'",
            "timestamp": "2026-04-24 13:30:00",
            "operator": "DBA-Zhang",
            "risk_level": "MEDIUM",
        },
        {
            "change_id": "CHG-0003",
            "service": "Redis-Cache",
            "change_type": "emergency",
            "description": "Redis 主从切换: master 从 node-1 切换到 node-2",
            "timestamp": "2026-04-24 14:00:00",
            "operator": "SRE-Li",
            "risk_level": "CRITICAL",
        },
        {
            "change_id": "CHG-0004",
            "service": "Kafka",
            "change_type": "normal",
            "description": "Topic payment-events 分区数从 6 扩展到 12",
            "timestamp": "2026-04-24 11:00:00",
            "operator": "MQ-Wang",
            "risk_level": "MEDIUM",
        },
    ]
    correlator.load_change_records(change_records)
    
    # ===== 场景1: PaymentService 变慢，关联 DB 变更 =====
    print("=" * 60)
    print("场景1: PaymentService 变慢 → 关联 DB 变更")
    print("=" * 60)
    
    anomaly1 = AnomalyEvent(
        event_id="EVT-001",
        service="PaymentService",
        anomaly_type="latency_spike",
        description="支付接口延迟从 50ms 飙升到 2450ms",
        timestamp="2026-04-24 14:00:30",
        severity="WARN",
        metrics={"p99_latency_ms": 2450, "error_rate": 0.15},
    )
    
    result1 = correlator.correlate(anomaly1)
    
    print(f"\n异常事件: [{result1.anomaly.severity}] {result1.anomaly.service} - {result1.anomaly.description}")
    print(f"\n根因假设 (置信度: {result1.confidence}):")
    print(f"  {result1.root_cause_hypothesis}")
    
    print(f"\n关联变更 ({len(result1.related_changes)} 条):")
    for ch in result1.related_changes:
        print(f"  [{ch.get('relation', '?')}] {ch['service']} | {ch['change_id']} | "
              f"{ch['description'][:60]}... | 距离={ch.get('distance', '?')}")
    
    print(f"\n上游异常 ({len(result1.upstream_anomalies)} 条):")
    for ua in result1.upstream_anomalies:
        print(f"  {ua['service']} 错误率={ua['error_rate']}% | 路径: {' → '.join(ua['propagation_path'])}")
    
    print(f"\n证据链:")
    for ev in result1.evidence:
        print(f"  {ev}")
    
    print(f"\n建议操作:")
    print(f"  {result1.recommendation}")
    
    # ===== 场景2: Frontend 超时，关联 Redis 主从切换 =====
    print("\n" + "=" * 60)
    print("场景2: Frontend 超时 → 关联 Redis 主从切换")
    print("=" * 60)
    
    anomaly2 = AnomalyEvent(
        event_id="EVT-002",
        service="Frontend",
        anomaly_type="timeout",
        description="前端请求超时率上升至 15%",
        timestamp="2026-04-24 14:01:00",
        severity="ERROR",
        metrics={"timeout_rate": 0.15, "p99_latency_ms": 5000},
    )
    
    result2 = correlator.correlate(anomaly2)
    
    print(f"\n异常事件: [{result2.anomaly.severity}] {result2.anomaly.service} - {result2.anomaly.description}")
    print(f"\n根因假设 (置信度: {result2.confidence}):")
    print(f"  {result2.root_cause_hypothesis}")
    
    print(f"\n关联变更 ({len(result2.related_changes)} 条):")
    for ch in result2.related_changes:
        print(f"  [{ch.get('relation', '?')}] {ch['service']} | {ch['change_id']} | "
              f"{ch['description'][:60]}... | 距离={ch.get('distance', '?')}")
    
    print(f"\n建议操作:")
    print(f"  {result2.recommendation}")
    
    # 保存结果
    results = {
        "payment_slow": {
            "anomaly": {
                "service": result1.anomaly.service,
                "type": result1.anomaly.anomaly_type,
                "description": result1.anomaly.description,
            },
            "root_cause_hypothesis": result1.root_cause_hypothesis,
            "confidence": result1.confidence,
            "related_changes": result1.related_changes,
            "evidence": result1.evidence,
            "recommendation": result1.recommendation,
        },
        "frontend_timeout": {
            "anomaly": {
                "service": result2.anomaly.service,
                "type": result2.anomaly.anomaly_type,
                "description": result2.anomaly.description,
            },
            "root_cause_hypothesis": result2.root_cause_hypothesis,
            "confidence": result2.confidence,
            "related_changes": result2.related_changes,
            "evidence": result2.evidence,
            "recommendation": result2.recommendation,
        },
    }
    
    result_file = output_path / "change_correlation_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果保存到: {result_file}")
    
    return results


if __name__ == "__main__":
    run_change_correlation()
