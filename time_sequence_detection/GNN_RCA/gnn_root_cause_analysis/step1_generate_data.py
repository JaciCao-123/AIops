#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 生成模拟数据 - 微服务拓扑与故障场景

生成内容：
1. 服务拓扑结构（有向图）
2. 带根因标注的告警时间序列
3. 故障传播路径
4. 节点特征和边特征

使用方法:
    python step1_generate_data.py                    # 生成默认配置
    python step1_generate_data.py --scenarios 50      # 生成50个场景
    python step1_generate_data.py --services 20       # 20个服务
"""

import os
import sys
import json
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
import networkx as nx

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    TOPOLOGY_CONFIG,
    ALERT_CONFIG,
    DATA_DIRS,
    GRAPH_CONFIG
)


class ServiceTopologyGenerator:
    """服务拓扑生成器"""
    
    def __init__(self, config: dict = None):
        self.config = config or TOPOLOGY_CONFIG
        self.graph = nx.DiGraph()
        self.service_layers = {}
        
    def generate(self) -> nx.DiGraph:
        """生成完整的服务拓扑"""
        
        topology_type = self.config.get("topology_type", "microservices")
        
        if topology_type == "microservices":
            return self._generate_microservices_topology()
        elif topology_type == "layered":
            return self._generate_layered_topology()
        elif topology_type == "mesh":
            return self._generate_mesh_topology()
        else:
            return self._generate_random_topology()
    
    def _generate_microservices_topology(self):
        """生成微服务架构拓扑（分层 + 网状混合）"""
        
        layers_config = self.config["layers"]
        service_id_counter = 0
        
        for layer_name, layer_info in layers_config.items():
            services_in_layer = []
            
            for i in range(layer_info["count"]):
                service_id = f"{layer_name}_{i+1}"
                service_name = f"{layer_name.replace('_', '-').title()}-{i+1}"
                
                self.graph.add_node(
                    service_id,
                    name=service_name,
                    layer=layer_name,
                    type=self._get_service_type(layer_name),
                    cpu_baseline=random.uniform(30, 60),
                    mem_baseline=random.uniform(40, 70),
                    is_root_cause_candidate=True
                )
                
                services_in_layer.append(service_id)
                service_id_counter += 1
            
            self.service_layers[layer_name] = services_in_layer
        
        # 建立层间依赖关系
        for layer_name, layer_info in layers_config.items():
            current_services = self.service_layers[layer_name]
            upstream_names = layer_info.get("upstream", [])
            
            for upstream_name in upstream_names:
                if upstream_name in self.service_layers:
                    upstream_services = self.service_layers[upstream_name]
                    
                    # 每个下游服务连接到上游的1-3个服务
                    for downstream in current_services:
                        num_upstream_connections = random.randint(
                            1, min(3, len(upstream_services))
                        )
                        
                        selected_upstream = random.sample(
                            upstream_services, 
                            num_upstream_connections
                        )
                        
                        for upstream in selected_upstream:
                            weight_range = self.config["edge_weights"]["medium_freq"]
                            edge_weight = random.randint(*weight_range)
                            
                            self.graph.add_edge(
                                upstream,  # 上游 -> 下游
                                downstream,
                                call_frequency=edge_weight,
                                latency_avg=random.uniform(5, 50),
                                dependency_type="synchronous",
                                reliability=0.999
                            )
        
        # 同层服务间添加少量连接
        for layer_name, services in self.service_layers.items():
            if len(services) > 1:
                num_internal_edges = max(1, len(services) // 3)
                pairs_to_connect = random.sample(
                    list(range(len(services))), 
                    min(num_internal_edges * 2, len(services))
                )
                
                for idx in range(0, len(pairs_to_connect) - 1, 2):
                    src = services[pairs_to_connect[idx]]
                    dst = services[pairs_to_connect[idx + 1]]
                    
                    if not self.graph.has_edge(src, dst):
                        weight_range = self.config["edge_weights"]["high_freq"]
                        self.graph.add_edge(
                            src, dst,
                            call_frequency=random.randint(*weight_range),
                            latency_avg=random.uniform(1, 10),
                            dependency_type="async",
                            reliability=0.995
                        )
        
        print(f"✅ 拓扑生成完成:")
        print(f"   节点数: {self.graph.number_of_nodes()}")
        print(f"   边数: {self.graph.number_of_edges()}")
        
        return self.graph
    
    def _get_service_type(self, layer: str) -> str:
        """根据层级确定服务类型"""
        type_mapping = {
            "gateway": "ingress",
            "api_services": "application",
            "core_services": "business",
            "data_services": "data",
            "infra_services": "infrastructure"
        }
        return type_mapping.get(layer, "unknown")


class FaultScenarioGenerator:
    """故障场景生成器"""
    
    def __init__(self, topology: nx.DiGraph, config: dict = None):
        self.topology = topology
        self.config = config or ALERT_CONFIG
        self.scenarios = []
    
    def generate_scenarios(self, num_scenarios: int = None) -> List[Dict]:
        """生成多个故障场景"""
        
        n = num_scenarios or self.config["num_scenarios"]
        
        for scenario_id in range(n):
            scenario = self._generate_single_scenario(scenario_id)
            self.scenarios.append(scenario)
        
        print(f"\n📊 已生成 {len(self.scenarios)} 个故障场景")
        return self.scenarios
    
    def _generate_single_scenario(self, scenario_id: int) -> Dict:
        """生成单个故障场景"""
        
        nodes = list(self.topology.nodes())
        
        # 根据分布选择根因节点
        root_cause_dist = self.config["root_cause_distribution"]
        root_cause_node = self._select_root_cause(nodes, root_cause_dist)
        
        # 故障开始时间
        base_time = datetime.now() - timedelta(hours=self.config["time_range_hours"])
        fault_start_time = base_time + timedelta(
            minutes=random.randint(0, int(self.config["time_range_hours"] * 60))
        )
        
        # 生成故障传播链
        propagation_chain = self._generate_propagation_chain(
            root_cause_node, 
            fault_start_time
        )
        
        # 为每个受影响节点生成告警
        alerts = []
        for node_info in propagation_chain:
            node_alerts = self._generate_alerts_for_node(node_info)
            alerts.extend(node_alerts)
        
        scenario = {
            "scenario_id": f"S{scenario_id+1:03d}",
            "root_cause": root_cause_node,
            "root_cause_layer": self.topology.nodes[root_cause_node].get("layer", "unknown"),
            "fault_start_time": fault_start_time.isoformat(),
            "propagation_chain": [
                {
                    "node": info["node"],
                    "timestamp": info["timestamp"].isoformat(),
                    "distance_from_root": info["distance"]
                }
                for info in propagation_chain
            ],
            "alerts": alerts,
            "affected_nodes": [info["node"] for info in propagation_chain],
            "total_alerts": len(alerts),
            "severity_distribution": {
                sev: sum(1 for a in alerts if a["severity"] == sev)
                for sev in self.config["severity_levels"]
            },
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "topology_nodes": len(nodes),
                "topology_edges": self.topology.number_of_edges(),
                "affected_ratio": len(propagation_chain) / len(nodes)
            }
        }
        
        return scenario
    
    def _select_root_cause(self, nodes: List[str], distribution: Dict[str, float]) -> str:
        """根据概率分布选择根因节点"""
        
        r = random.random()
        cumulative_prob = 0.0
        selected_layer = None
        
        for layer, prob in sorted(distribution.items(), key=lambda x: -x[1]):
            cumulative_prob += prob
            if r <= cumulative_prob:
                selected_layer = layer
                break
        
        if selected_layer is None:
            selected_layer = list(distribution.keys())[0]
        
        candidates = [n for n in nodes 
                     if self.topology.nodes[n].get("layer") == selected_layer]
        
        if not candidates:
            candidates = nodes
        
        return random.choice(candidates)
    
    def _generate_propagation_chain(
        self, 
        root_node: str, 
        start_time: datetime
    ) -> List[Dict]:
        """生成故障传播链（BFS遍历）"""
        
        chain = [{"node": root_node, "timestamp": start_time, "distance": 0}]
        visited = {root_node}
        current_level = [root_node]
        level = 1
        
        while current_level and level <= 5:  # 最多传播5跳
            
            next_level = []
            
            for node in current_level:
                successors = list(self.topology.successors(node))
                
                for successor in successors:
                    if successor not in visited and random.random() > 0.3:  # 70%概率传播
                        
                        delay_config = self.config["propagation_delay"]
                        
                        if level == 1:
                            delay = random.uniform(*delay_config["same_layer"])
                        elif level <= 2:
                            delay = random.uniform(*delay_config["adjacent_layer"])
                        else:
                            delay = random.uniform(*delay_config["cross_layer"])
                        
                        arrival_time = start_time + timedelta(seconds=delay * level)
                        
                        chain.append({
                            "node": successor,
                            "timestamp": arrival_time,
                            "distance": level
                        })
                        
                        visited.add(successor)
                        next_level.append(successor)
            
            current_level = next_level
            level += 1
        
        return sorted(chain, key=lambda x: x["timestamp"])
    
    def _generate_alerts_for_node(self, node_info: Dict) -> List[Dict]:
        """为单个节点生成告警"""
        
        node = node_info["node"]
        timestamp = node_info["timestamp"]
        distance = node_info["distance"]
        
        node_attrs = self.topology.nodes[node]
        layer = node_attrs.get("layer", "unknown")
        
        # 根因节点告警更多更严重
        if distance == 0:
            num_alerts = random.randint(*self.config["alerts_per_scenario"])
            severity_bias = [0.4, 0.35, 0.15, 0.10]  # critical, major, minor, warning
        else:
            num_alerts = random.randint(max(2, 5 - distance), max(3, 8 - distance))
            severity_bias = [0.15, 0.35, 0.30, 0.20]
        
        alerts = []
        
        for i in range(num_alerts):
            alert_offset = timedelta(seconds=random.uniform(0, 120 * (distance + 1)))
            alert_time = timestamp + alert_offset
            
            alert_type = random.choice(self.config["alert_types"])
            
            # 选择严重程度
            r = random.random()
            cumulative = 0
            severity_idx = 0
            for j, prob in enumerate(severity_bias):
                cumulative += prob
                if r <= cumulative:
                    severity_idx = j
                    break
            severity = self.config["severity_levels"][severity_idx]
            
            host = f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"
            
            message_templates = {
                "CPU使用率过高": f"{node} CPU使用率达到{random.randint(85,100)}%，持续{random.randint(5,30)}分钟",
                "内存不足": f"{node} 内存使用率{random.randint(80,98)}%(已用{random.randint(8,16)}GB/{16}GB)",
                "磁盘空间不足": f"{node} 数据盘空间使用率{random.randint(75,95)}%",
                "网络延迟过高": f"{node} 到上游服务的网络延迟从{random.uniform(0.5,2):.1f}ms升至{random.uniform(10,50):.1f}ms",
                "连接超时": f"{node} 连接超时率上升至{random.uniform(5,20):.1f}%，平均响应时间{random.randint(5000,30000)}ms",
                "连接池耗尽": f"{node} 数据库连接池已耗尽({random.randint(90,100)}/{random.randint(100,200)})，请求排队中",
                "响应时间过长": f"{node} P99延迟达到{random.randint(8000,60000)/1000:.1f}s，超过阈值3s",
                "错误率上升": f"{node} 错误率从{random.uniform(0.01,0.5):.2f}%飙升至{random.uniform(5,25):.1f}%",
                "Pod重启": f"{node} Pod在过去{random.randint(10,60)}分钟重启{random.randint(3,15)}次",
                "节点NotReady": f"主机{host}状态变为NotReady，Kubelet无响应"
            }
            
            message = message_templates.get(alert_type, f"{node} 发生异常: {alert_type}")
            
            alert = {
                "alert_id": f"ALT-{datetime.now().strftime('%Y%m%d')}-{len(alerts)+1:04d}",
                "timestamp": alert_time.isoformat(),
                "scenario_id": node_info.get("scenario_id", ""),
                "node": node,
                "service": node_attrs.get("name", node),
                "host": host,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "is_root_cause": distance == 0,
                "distance_from_root": distance,
                "layer": layer,
                "metrics": {
                    "cpu_usage": random.uniform(60, 100) if distance < 2 else random.uniform(30, 70),
                    "mem_usage": random.uniform(65, 99) if distance < 2 else random.uniform(40, 75),
                    "latency_p99": random.uniform(1000, 30000) if distance < 3 else random.uniform(100, 2000),
                    "error_rate": random.uniform(0.05, 0.3) if distance < 2 else random.uniform(0.001, 0.05)
                }
            }
            
            alerts.append(alert)
        
        return alerts


class DataExporter:
    """数据导出器"""
    
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or DATA_DIRS["raw"]
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_all(
        self, 
        topology: nx.DiGraph, 
        scenarios: List[Dict],
        prefix: str = ""
    ) -> Dict[str, str]:
        """导出所有数据"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = prefix or timestamp
        
        exported_files = {}
        
        # 1. 导出拓扑结构
        topo_file = os.path.join(self.output_dir, f"{prefix}_topology.json")
        self._export_topology(topology, topo_file)
        exported_files["topology"] = topo_file
        
        # 2. 导出所有告警为DataFrame
        all_alerts = []
        for scenario in scenarios:
            all_alerts.extend(scenario["alerts"])
        
        alerts_df = pd.DataFrame(all_alerts)
        alerts_file = os.path.join(self.output_dir, f"{prefix}_alerts.csv")
        alerts_df.to_csv(alerts_file, index=False, encoding='utf-8-sig')
        exported_files["alerts"] = alerts_file
        
        # 3. 导出场景元数据
        scenarios_meta = [{
            "scenario_id": s["scenario_id"],
            "root_cause": s["root_cause"],
            "root_cause_layer": s["root_cause_layer"],
            "fault_start_time": s["fault_start_time"],
            "total_alerts": s["total_alerts"],
            "affected_nodes_count": len(s["affected_nodes"]),
            **s["severity_distribution"]
        } for s in scenarios]
        
        scenarios_df = pd.DataFrame(scenarios_meta)
        meta_file = os.path.join(self.output_dir, f"{prefix}_scenarios.csv")
        scenarios_df.to_csv(meta_file, index=False, encoding='utf-8-sig')
        exported_files["scenarios"] = meta_file
        
        # 4. 导出带标签的训练数据（用于GNN）
        training_data = self._prepare_training_data(scenarios)
        train_file = os.path.join(self.output_dir, f"{prefix}_training_data.csv")
        training_data.to_csv(train_file, index=False, encoding='utf-8-sig')
        exported_files["training_data"] = train_file
        
        # 5. 导出边列表（用于构建图）
        edges_file = os.path.join(self.output_dir, f"{prefix}_edges.csv")
        self._export_edges(topology, edges_file)
        exported_files["edges"] = edges_file
        
        print(f"\n💾 数据导出完成:")
        for name, path in exported_files.items():
            size_mb = os.path.getsize(path) / 1024 / 1024
            print(f"   ✓ {name}: {path} ({size_mb:.2f} MB)")
        
        return exported_files
    
    def _export_topology(self, graph: nx.DiGraph, filepath: str):
        """导出拓扑为JSON"""
        
        data = {
            "nodes": [],
            "edges": []
        }
        
        for node, attrs in graph.nodes(data=True):
            data["nodes"].append({
                "id": node,
                **attrs
            })
        
        for src, dst, attrs in graph.edges(data=True):
            data["edges"].append({
                "source": src,
                "target": dst,
                **attrs
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _export_edges(self, graph: nx.DiGraph, filepath: str):
        """导出边列表"""
        
        edges_data = []
        for src, dst, attrs in graph.edges(data=True):
            edges_data.append({
                "source": src,
                "target": dst,
                **attrs
            })
        
        pd.DataFrame(edges_data).to_csv(filepath, index=False)
    
    def _prepare_training_data(self, scenarios: List[Dict]) -> pd.DataFrame:
        """准备带根因标签的训练数据"""
        
        rows = []
        
        for scenario in scenarios:
            affected_nodes = set(scenario["affected_nodes"])
            root_cause = scenario["root_cause"]
            
            for node in self.topology.nodes() if hasattr(self, 'topology') else set(affected_nodes):
                node_alerts = [a for a in scenario["alerts"] if a["node"] == node]
                
                if node_alerts:
                    row = {
                        "scenario_id": scenario["scenario_id"],
                        "node": node,
                        "service": node_alerts[0]["service"],
                        "layer": node_alerts[0].get("layer", "unknown"),
                        "is_root_cause": 1 if node == root_cause else 0,
                        "is_affected": 1 if node in affected_nodes else 0,
                        "num_alerts": len(node_alerts),
                        "first_alert_time": min(a["timestamp"] for a in node_alerts),
                        "last_alert_time": max(a["timestamp"] for a in node_alerts),
                        "max_severity_order": min([
                            ["critical", "major", "minor", "warning"].index(a["severity"])
                            for a in node_alerts
                        ]),
                        "unique_alert_types": len(set(a["alert_type"] for a in node_alerts)),
                        "avg_cpu": np.mean([a["metrics"]["cpu_usage"] for a in node_alerts]),
                        "avg_mem": np.mean([a["metrics"]["mem_usage"] for a in node_alerts]),
                        "avg_latency": np.mean([a["metrics"]["latency_p99"] for a in node_alerts]),
                        "avg_error_rate": np.mean([a["metrics"]["error_rate"] for a in node_alerts])
                    }
                    rows.append(row)
        
        return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description='生成模拟数据和拓扑')
    parser.add_argument('--scenarios', type=int, default=20, help='故障场景数量')
    parser.add_argument('--services', type=int, default=15, help='服务数量')
    parser.add_argument('--output-prefix', type=str, default='', help='输出文件前缀')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    args = parser.parse_args()
    
    random.seed(args.seed)
    np.random.seed(args.seed)
    
    print("="*70)
    print("🏗️  Step 1/5: 生成模拟数据 - GNN根因分析系统")
    print("="*70)
    
    print(f"\n⚙️  配置参数:")
    print(f"   故障场景数: {args.scenarios}")
    print(f"   服务数量: {args.services}")
    print(f"   随机种子: {args.seed}")
    
    # 1. 生成拓扑
    print("\n📐 正在生成服务拓扑...")
    topo_gen = ServiceTopologyGenerator(TOPOLOGY_CONFIG)
    TOPOLOGY_CONFIG["layers"]["gateway"]["count"] = 1
    TOPOLOGY_CONFIG["layers"]["api_services"]["count"] = 3
    TOPOLOGY_CONFIG["layers"]["core_services"]["count"] = max(5, args.services - 10)
    topology = topo_gen.generate()
    
    # 2. 生成故障场景
    print("\n⚡ 正在生成故障场景...")
    scenario_gen = FaultScenarioGenerator(topology, ALERT_CONFIG)
    scenarios = scenario_gen.generate_scenarios(args.scenarios)
    
    # 3. 统计信息
    total_alerts = sum(s["total_alerts"] for s in scenarios)
    root_causes = [s["root_cause"] for s in scenarios]
    
    print(f"\n📊 数据统计:")
    print(f"   总告警数: {total_alerts}")
    print(f"   平均每场景: {total_alerts/len(scenarios):.1f} 条告警")
    print(f"   唯一根因节点: {len(set(root_causes))}")
    print(f"   最常成为根因: {max(set(root_causes), key=root_causes.count)}")
    
    # 4. 导出数据
    print("\n💾 正在导出数据...")
    exporter = DataExporter(DATA_DIRS["raw"])
    exporter.topology = topology
    files = exporter.export_all(topology, scenarios, args.output_prefix)
    
    print(f"\n✅ Step 1 完成! 共生成 {len(scenarios)} 个场景, {total_alerts} 条告警")
    
    return topology, scenarios, files


if __name__ == "__main__":
    main()