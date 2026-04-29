#!/usr/bin/env python3
"""
Step 3: 构建 DAG 图
将提取的服务调用关系构建为有向无环图（DAG），
执行去环和降噪处理
"""
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple


@dataclass
class DAGNode:
    name: str
    node_type: str = "service"
    error_count: int = 0
    warn_count: int = 0
    total_logs: int = 0
    error_rate: float = 0.0
    is_anomaly: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DAGEdge:
    source: str
    target: str
    weight: int = 1
    error_count: int = 0
    trace_count: int = 0
    is_noisy: bool = False


class ServiceDAG:
    """
    服务依赖 DAG（有向无环图）
    
    核心功能：
    1. 从调用关系构建图
    2. 去环处理（DAG 不允许有环）
    3. 降噪处理（移除低频/噪声边）
    4. 拓扑排序
    5. 上下游查询
    """
    
    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.edges: Dict[Tuple[str, str], DAGEdge] = {}
        self._adj: Dict[str, List[str]] = defaultdict(list)
        self._rev_adj: Dict[str, List[str]] = defaultdict(list)
    
    def add_node(self, name: str, node_type: str = "service", **kwargs) -> DAGNode:
        if name not in self.nodes:
            self.nodes[name] = DAGNode(name=name, node_type=node_type, **kwargs)
        else:
            for k, v in kwargs.items():
                setattr(self.nodes[name], k, v)
        return self.nodes[name]
    
    def add_edge(self, source: str, target: str, **kwargs) -> Optional[DAGEdge]:
        if source == target:
            return None
        
        key = (source, target)
        if key not in self.edges:
            self.edges[key] = DAGEdge(source=source, target=target, **kwargs)
            self._adj[source].append(target)
            self._rev_adj[target].append(source)
        else:
            for k, v in kwargs.items():
                setattr(self.edges[key], k, v)
        
        return self.edges[key]
    
    def remove_edge(self, source: str, target: str):
        key = (source, target)
        if key in self.edges:
            del self.edges[key]
            if target in self._adj[source]:
                self._adj[source].remove(target)
            if source in self._rev_adj[target]:
                self._rev_adj[target].remove(source)
    
    def has_path(self, source: str, target: str) -> bool:
        """BFS 检查是否存在从 source 到 target 的路径"""
        if source == target:
            return True
        visited = set()
        queue = deque([source])
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            for neighbor in self._adj.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        return False
    
    def detect_cycles(self) -> List[List[str]]:
        """检测所有环"""
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self._adj.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
            
            path.pop()
            rec_stack.remove(node)
        
        for node in self.nodes:
            if node not in visited:
                dfs(node)
        
        return cycles
    
    def remove_cycles(self, strategy: str = "break_weakest") -> List[Tuple[str, str]]:
        """
        去环处理
        
        Args:
            strategy: 去环策略
                - "break_weakest": 断开权重最小的边（默认）
                - "break_error_heaviest": 断开错误数最少的边
                - "break_latest": 断开最后添加的边
        
        Returns:
            被移除的边列表
        """
        removed_edges = []
        max_iterations = len(self.edges)
        iteration = 0
        
        while iteration < max_iterations:
            cycles = self.detect_cycles()
            if not cycles:
                break
            
            iteration += 1
            cycle = cycles[0]
            
            cycle_edges = []
            for i in range(len(cycle) - 1):
                src, tgt = cycle[i], cycle[i + 1]
                key = (src, tgt)
                if key in self.edges:
                    cycle_edges.append(key)
            
            if not cycle_edges:
                break
            
            if strategy == "break_weakest":
                edge_to_remove = min(cycle_edges, key=lambda k: self.edges[k].weight)
            elif strategy == "break_error_heaviest":
                edge_to_remove = min(cycle_edges, key=lambda k: self.edges[k].error_count)
            else:
                edge_to_remove = cycle_edges[-1]
            
            edge = self.edges[edge_to_remove]
            removed_edges.append(edge_to_remove)
            self.remove_edge(edge_to_remove[0], edge_to_remove[1])
        
        return removed_edges
    
    def denoise(
        self,
        min_weight: int = 2,
        min_trace_count: int = 1,
        error_weight_threshold: float = 0.1,
    ) -> List[Tuple[str, str]]:
        """
        降噪处理
        
        移除低频/噪声边：
        1. 调用次数低于 min_weight 的边
        2. 无 trace 支撑且调用次数极低的边
        3. 错误率极低的边（可能是正常的偶尔调用）
        
        Args:
            min_weight: 最小调用次数阈值
            min_trace_count: 最小 trace 数量阈值
            error_weight_threshold: 错误权重阈值
        
        Returns:
            被移除的边列表
        """
        removed_edges = []
        edges_to_check = list(self.edges.keys())
        
        for key in edges_to_check:
            edge = self.edges[key]
            
            is_noisy = False
            reason = ""
            
            if edge.weight < min_weight:
                is_noisy = True
                reason = f"调用次数 {edge.weight} < {min_weight}"
            elif edge.trace_count == 0 and edge.weight <= 1:
                is_noisy = True
                reason = f"无 trace 支撑且调用次数仅 {edge.weight}"
            elif edge.error_count == 0 and edge.weight < min_weight * 2:
                if self._is_indirect_dependency(key[0], key[1]):
                    is_noisy = True
                    reason = "存在更直接的依赖路径，此边为冗余"
            
            if is_noisy:
                edge.is_noisy = True
                removed_edges.append(key)
                self.remove_edge(key[0], key[1])
        
        return removed_edges
    
    def _is_indirect_dependency(self, source: str, target: str) -> bool:
        """检查是否存在 source -> ... -> target 的间接路径（不经过直连边）"""
        visited = set()
        queue = deque()
        
        for neighbor in self._adj.get(source, []):
            if neighbor != target:
                queue.append(neighbor)
        
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            if node in visited:
                continue
            visited.add(node)
            for neighbor in self._adj.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        
        return False
    
    def topological_sort(self) -> List[str]:
        """拓扑排序"""
        in_degree = defaultdict(int)
        for node in self.nodes:
            in_degree[node] = 0
        
        for edge in self.edges.values():
            in_degree[edge.target] += 1
        
        queue = deque([n for n in self.nodes if in_degree[n] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in self._adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return result
    
    def get_upstream(self, service: str, depth: int = None) -> List[str]:
        """获取上游服务（依赖此服务的服务）"""
        visited = set()
        result = []
        queue = deque([(service, 0)])
        
        while queue:
            node, d = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            
            if node != service:
                result.append(node)
            
            if depth is not None and d >= depth:
                continue
            
            for parent in self._rev_adj.get(node, []):
                if parent not in visited:
                    queue.append((parent, d + 1))
        
        return result
    
    def get_downstream(self, service: str, depth: int = None) -> List[str]:
        """获取下游服务（此服务依赖的服务）"""
        visited = set()
        result = []
        queue = deque([(service, 0)])
        
        while queue:
            node, d = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            
            if node != service:
                result.append(node)
            
            if depth is not None and d >= depth:
                continue
            
            for child in self._adj.get(node, []):
                if child not in visited:
                    queue.append((child, d + 1))
        
        return result
    
    def find_root_causes(self, anomaly_services: List[str]) -> List[Dict[str, Any]]:
        """
        在 DAG 中查找根因服务
        
        DAG 边方向: A → B 表示 A 调用 B（A 依赖 B）
        故障传播: B 故障 → A 受影响（沿依赖方向反向传播）
        根因查找策略：对于每个异常服务，沿 DAG 下游（依赖方向）追溯，
        找到最下游的异常服务即为根因（因为它是被依赖的基础服务）
        """
        anomaly_set = set(anomaly_services)
        root_causes = []
        
        for service in anomaly_services:
            downstream = self.get_downstream(service)
            downstream_anomalies = [s for s in downstream if s in anomaly_set]
            
            if not downstream_anomalies:
                root_causes.append({
                    "service": service,
                    "reason": f"{service} 异常且其依赖服务无异常，判定为根因",
                    "upstream_impact": self.get_upstream(service),
                    "confidence": "HIGH",
                })
            else:
                furthest_downstream = None
                for down_svc in downstream_anomalies:
                    down_downstream = self.get_downstream(down_svc)
                    down_downstream_anomalies = [s for s in down_downstream if s in anomaly_set]
                    if not down_downstream_anomalies:
                        furthest_downstream = down_svc
                        break
                
                if furthest_downstream:
                    root_causes.append({
                        "service": furthest_downstream,
                        "reason": f"{service} 异常由依赖服务 {furthest_downstream} 故障引起",
                        "upstream_impact": self.get_upstream(furthest_downstream),
                        "affected_service": service,
                        "confidence": "MEDIUM",
                    })
        
        seen = set()
        unique_causes = []
        for rc in root_causes:
            if rc["service"] not in seen:
                seen.add(rc["service"])
                unique_causes.append(rc)
        
        return unique_causes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {
                name: {
                    "type": node.node_type,
                    "error_count": node.error_count,
                    "warn_count": node.warn_count,
                    "total_logs": node.total_logs,
                    "error_rate": node.error_rate,
                    "is_anomaly": node.is_anomaly,
                }
                for name, node in self.nodes.items()
            },
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "weight": edge.weight,
                    "error_count": edge.error_count,
                    "trace_count": edge.trace_count,
                }
                for edge in self.edges.values()
            ],
            "topological_order": self.topological_sort(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceDAG":
        dag = cls()
        for name, node_data in data.get("nodes", {}).items():
            dag.add_node(
                name=name,
                node_type=node_data.get("type", "service"),
                error_count=node_data.get("error_count", 0),
                warn_count=node_data.get("warn_count", 0),
                total_logs=node_data.get("total_logs", 0),
                error_rate=node_data.get("error_rate", 0.0),
                is_anomaly=node_data.get("is_anomaly", False),
            )
        for edge_data in data.get("edges", []):
            dag.add_edge(
                source=edge_data["source"],
                target=edge_data["target"],
                weight=edge_data.get("weight", 1),
                error_count=edge_data.get("error_count", 0),
                trace_count=edge_data.get("trace_count", 0),
            )
        return dag


def build_dag(
    edges_file: str = None,
    error_summary_file: str = None,
    output_dir: str = None,
) -> ServiceDAG:
    """
    构建服务依赖 DAG
    
    Args:
        edges_file: 调用关系文件路径
        error_summary_file: 错误摘要文件路径
        output_dir: 输出目录
    """
    if edges_file is None:
        edges_file = str(Path(__file__).parent / "data" / "parsed" / "call_edges.json")
    if error_summary_file is None:
        error_summary_file = str(Path(__file__).parent / "data" / "parsed" / "error_summary.json")
    if output_dir is None:
        output_dir = str(Path(__file__).parent / "data" / "dag")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 加载调用关系
    with open(edges_file, "r", encoding="utf-8") as f:
        edges_data = json.load(f)
    
    # 加载错误摘要
    error_summary = {}
    if Path(error_summary_file).exists():
        with open(error_summary_file, "r", encoding="utf-8") as f:
            error_summary = json.load(f)
    
    # 构建 DAG
    dag = ServiceDAG()
    
    # 添加节点
    all_services = set()
    for edge in edges_data:
        all_services.add(edge["source"])
        all_services.add(edge["target"])
    
    for service in all_services:
        svc_summary = error_summary.get(service, {})
        node_type = "service"
        if "DB" in service or "db" in service:
            node_type = "database"
        elif "Redis" in service or "redis" in service:
            node_type = "cache"
        elif "Kafka" in service or "kafka" in service:
            node_type = "mq"
        elif "Frontend" in service:
            node_type = "gateway"
        
        dag.add_node(
            name=service,
            node_type=node_type,
            error_count=svc_summary.get("error_count", 0),
            warn_count=svc_summary.get("warn_count", 0),
            total_logs=svc_summary.get("total_logs", 0),
            error_rate=svc_summary.get("error_rate", 0.0),
            is_anomaly=svc_summary.get("error_rate", 0.0) > 10.0,
        )
    
    # 添加边
    for edge in edges_data:
        dag.add_edge(
            source=edge["source"],
            target=edge["target"],
            weight=edge.get("call_count", 1),
            error_count=edge.get("error_count", 0),
            trace_count=edge.get("trace_count", 0),
        )
    
    print(f"初始图: {len(dag.nodes)} 个节点, {len(dag.edges)} 条边")
    
    # 去环
    print("\n[1/2] 去环处理...")
    cycles = dag.detect_cycles()
    if cycles:
        print(f"  检测到 {len(cycles)} 个环")
        removed = dag.remove_cycles(strategy="break_weakest")
        print(f"  移除 {len(removed)} 条边以消除环: {removed}")
    else:
        print("  未检测到环")
    
    # 降噪
    print("\n[2/2] 降噪处理...")
    noisy_edges = dag.denoise(min_weight=2, min_trace_count=1)
    if noisy_edges:
        print(f"  移除 {len(noisy_edges)} 条噪声边: {noisy_edges}")
    else:
        print("  未检测到噪声边")
    
    print(f"\n最终 DAG: {len(dag.nodes)} 个节点, {len(dag.edges)} 条边")
    print(f"拓扑排序: {' -> '.join(dag.topological_sort())}")
    
    # 保存 DAG
    dag_file = output_path / "service_dag.json"
    with open(dag_file, "w", encoding="utf-8") as f:
        json.dump(dag.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"DAG 保存到: {dag_file}")
    
    # 保存可视化数据
    vis_file = output_path / "dag_visualization.json"
    vis_data = {
        "nodes": [
            {
                "id": name,
                "label": name,
                "type": node.node_type,
                "errorRate": node.error_rate,
                "isAnomaly": node.is_anomaly,
            }
            for name, node in dag.nodes.items()
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "weight": edge.weight,
                "errorCount": edge.error_count,
            }
            for edge in dag.edges.values()
        ],
    }
    with open(vis_file, "w", encoding="utf-8") as f:
        json.dump(vis_data, f, ensure_ascii=False, indent=2)
    print(f"可视化数据保存到: {vis_file}")
    
    return dag


if __name__ == "__main__":
    build_dag()
