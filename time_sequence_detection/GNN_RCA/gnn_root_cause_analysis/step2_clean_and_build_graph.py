#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: 数据清洗、时间对齐与图构建

功能：
1. 告警数据清洗（去重、缺失值、异常值）
2. 时间序列对齐和标准化
3. 构建异构图（Heterogeneous Graph）
4. 节点/边特征工程
5. 导出为 PyG (PyTorch Geometric) 格式

使用方法:
    python step2_clean_and_build_graph.py --input data/raw/alerts.csv
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import numpy as np
import pandas as pd
import networkx as nx

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    CLEANING_CONFIG,
    GRAPH_CONFIG,
    DATA_DIRS,
    ALERT_CONFIG
)


class AlertDataCleaner:
    """告警数据清洗器"""
    
    def __init__(self, config: dict = None):
        self.config = config or CLEANING_CONFIG
        self.cleaning_log = []
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行完整清洗流程"""
        
        print(f"\n🧹 开始数据清洗...")
        print(f"   原始数据: {len(df)} 条记录")
        
        df = self._remove_duplicates(df)
        df = self._handle_missing_values(df)
        df = self._handle_outliers(df)
        df = self._validate_timestamps(df)
        
        print(f"   清洗后: {len(df)} 条记录")
        print(f"   清洗日志:")
        for log in self.cleaning_log[-5:]:
            print(f"      - {log}")
        
        return df
    
    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """去除重复告警"""
        
        original_len = len(df)
        
        # 严格去重：相同节点+类型+时间窗口内
        if 'timestamp' in df.columns and 'node' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df_sorted = df.sort_values('timestamp')
            
            # 定义时间窗口内的重复
            time_window = timedelta(seconds=self.config["duplicate_time_window_seconds"])
            mask = []
            last_seen = {}
            
            for idx, row in df_sorted.iterrows():
                key = (row.get('node', ''), row.get('alert_type', ''))
                current_time = row.get('timestamp', pd.NaT)
                
                if key not in last_seen or \
                   (current_time - last_seen[key]) > time_window:
                    mask.append(True)
                    last_seen[key] = current_time
                else:
                    mask.append(False)
            
            df_cleaned = df_sorted[mask].reset_index(drop=True)
        else:
            df_cleaned = df.drop_duplicates()
        
        removed = original_len - len(df_cleaned)
        self.cleaning_log.append(f"去除 {removed} 条重复记录")
        
        return df_cleaned
    
    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        
        missing_before = df.isnull().sum().sum()
        
        # 关键字段填充策略
        fill_strategies = {
            'severity': 'warning',
            'service': 'unknown',
            'host': 'unknown',
            'message': '(no message)',
            'alert_type': 'unknown_alert'
        }
        
        for col, default in fill_strategies.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)
        
        # 数值型字段用中位数填充
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if df[col].isnull().sum() > 0:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                self.cleaning_log.append(f"{col}: 用中位数 {median_val:.2f} 填充 {df[col].isnull().sum()} 个缺失值")
        
        missing_after = df.isnull().sum().sum()
        self.cleaning_log.append(f"缺失值: {missing_before} → {missing_after}")
        
        return df
    
    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理异常值（IQR方法）"""
        
        iqr_factor = self.config.get("outlier_iqr_factor", 2.0)
        removed_count = 0
        
        # 对数值指标列进行异常值检测
        metric_cols = [col for col in df.columns 
                      if any(x in col.lower() for x in ['cpu', 'mem', 'latency', 'error', 'usage'])]
        
        for col in metric_cols:
            if col in df.columns and df[col].dtype in ['float64', 'int64']:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                lower_bound = Q1 - iqr_factor * IQR
                upper_bound = Q3 + iqr_factor * IQR
                
                outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                n_outliers = outlier_mask.sum()
                
                if n_outliers > 0:
                    # 钳制到边界而非删除
                    df.loc[df[col] < lower_bound, col] = lower_bound
                    df.loc[df[col] > upper_bound, col] = upper_bound
                    removed_count += n_outliers
        
        if removed_count > 0:
            self.cleaning_log.append(f"钳制 {removed_count} 个异常值到IQR范围")
        
        return df
    
    def _validate_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证时间戳"""
        
        if 'timestamp' in df.columns:
            # 确保时间戳格式正确
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                
                # 移除无效时间戳
                invalid_mask = df['timestamp'].isna() | (df['timestamp'] > datetime.now())
                n_invalid = invalid_mask.sum()
                
                if n_invalid > 0:
                    df = df[~invalid_mask]
                    self.cleaning_log.append(f"移除 {n_invalid} 条无效时间戳记录")
                
                # 按时间排序
                df = df.sort_values('timestamp').reset_index(drop=True)
                
            except Exception as e:
                self.cleaning_log.append(f"时间戳转换警告: {e}")
        
        return df


class TimeSeriesAligner:
    """时间序列对齐器"""
    
    def __init__(self, config: dict = None):
        self.config = config or CLEANING_CONFIG
    
    def align(
        self, 
        df: pd.DataFrame, 
        granularity_seconds: int = None
    ) -> pd.DataFrame:
        """将告警时间对齐到统一的时间粒度"""
        
        granularity = granularity_seconds or self.config["time_granularity_seconds"]
        
        print(f"\n⏰ 时间对齐 (粒度: {granularity}s)...")
        
        if 'timestamp' not in df.columns:
            print("   ⚠️ 无timestamp字段，跳过对齐")
            return df
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 向下取整到指定粒度
        df['time_bucket'] = df['timestamp'].dt.floor(f'{granularity}s')
        
        # 统计每个时间桶的告警数
        bucket_stats = df.groupby(['time_bucket', 'node']).size().reset_index(name='count')
        
        print(f"   时间桶数量: {df['time_bucket'].nunique()}")
        print(f"   平均每桶告警: {bucket_stats['count'].mean():.1f}")
        
        return df


class HeterogeneousGraphBuilder:
    """异构图构建器 - 核心组件！"""
    
    def __init__(self, topology_path: str = None, config: dict = None):
        self.topology_path = topology_path
        self.config = config or GRAPH_CONFIG
        self.graph_data = {
            "nodes": {},
            "edges": {},
            "node_features": {},
            "edge_features": {},
            "temporal_features": {}
        }
    
    def build_from_topology_and_alerts(
        self,
        topology_json: dict,
        alerts_df: pd.DataFrame
    ) -> Dict:
        """
        从拓扑结构和告警数据构建异构图
        
        返回 PyG 格式的图数据
        """
        
        print("\n🔗 构建异构图...")
        
        # 1. 解析拓扑结构
        node_list = topology_json.get("nodes", [])
        edge_list = topology_json.get("edges", [])
        
        # 2. 构建节点映射
        node_id_to_idx = {node["id"]: idx for idx, node in enumerate(node_list)}
        num_nodes = len(node_list)
        
        print(f"   节点数: {num_nodes}")
        print(f"   边数: {len(edge_list)}")
        
        # 3. 提取节点特征
        node_features = self._extract_node_features(node_list, alerts_df, node_id_to_idx)
        
        # 4. 提取边特征
        edge_index, edge_attr = self._extract_edge_features(edge_list, node_id_to_idx)
        
        # 5. 提取时序特征（每个节点的告警时间序列）
        temporal_features = self._extract_temporal_features(alerts_df, node_id_to_idx)
        
        # 6. 构建标签（根因标注）
        labels = self._extract_labels(alerts_df, node_id_to_idx)
        
        self.graph_data = {
            "num_nodes": num_nodes,
            "node_id_mapping": node_id_to_idx,
            "node_features": node_features,
            "edge_index": edge_index,
            "edge_attr": edge_attr,
            "temporal_features": temporal_features,
            "labels": labels,
            "node_metadata": node_list
        }
        
        print(f"   节点特征维度: {node_features.shape[1]}")
        print(f"   边索引形状: {edge_index.shape}")
        print(f"   时序特征维度: {list(temporal_features.values())[0].shape if temporal_features else 'N/A'}")
        print(f"   标签分布: 正常={labels.count(0)}, 根因={labels.count(1)}")
        
        return self.graph_data
    
    def _extract_node_features(
        self,
        nodes: List[dict],
        alerts_df: pd.DataFrame,
        node_id_map: Dict[str, int]
    ) -> np.ndarray:
        """提取节点特征向量"""
        
        feature_dim = self.config["node_feature_dim"]
        num_nodes = len(nodes)
        features = np.zeros((num_nodes, feature_dim))
        
        for node_info in nodes:
            node_id = node_info["id"]
            idx = node_id_map[node_id]
            
            # 基础特征（从拓扑属性）
            layer_onehot = self._encode_layer(node_info.get("layer", "unknown"))
            type_onehot = self._encode_service_type(node_info.get("type", "unknown"))
            
            # 从告警数据提取统计特征
            node_alerts = alerts_df[alerts_df['node'] == node_id] if 'node' in alerts_df.columns else pd.DataFrame()
            
            stats_features = self._compute_node_statistics(node_alerts)
            
            # 合并所有特征
            all_features = np.concatenate([
                layer_onehot,           # 层级编码 (5维)
                type_onehot,             # 服务类型编码 (5维)
                stats_features,          # 统计特征 (54维)
            ])
            
            # 截断或填充到目标维度
            actual_dim = min(len(all_features), feature_dim)
            features[idx, :actual_dim] = all_features[:actual_dim]
        
        # 归一化
        features = self._normalize_features(features)
        
        return features.astype(np.float32)
    
    def _encode_layer(self, layer: str) -> np.ndarray:
        """层级one-hot编码"""
        layers = ["gateway", "api_services", "core_services", "data_services", "infra_services"]
        encoding = np.zeros(len(layers))
        if layer in layers:
            encoding[layers.index(layer)] = 1.0
        return encoding
    
    def _encode_service_type(self, service_type: str) -> np.ndarray:
        """服务类型one-hot编码"""
        types = ["ingress", "application", "business", "data", "infrastructure"]
        encoding = np.zeros(len(types))
        if service_type in types:
            encoding[types.index(service_type)] = 1.0
        return encoding
    
    def _compute_node_statistics(self, node_alerts: pd.DataFrame) -> np.ndarray:
        """计算节点的统计特征"""
        
        if len(node_alerts) == 0:
            return np.zeros(54)
        
        features = []
        
        # 告警数量统计
        features.append(len(node_alerts))                           # 总告警数
        features.append(len(node_alerts['alert_type'].unique()))    # 不同告警类型数
        
        # 严重度分布
        severity_order = {'critical': 4, 'major': 3, 'minor': 2, 'warning': 1}
        for sev in ['critical', 'major', 'minor', 'warning']:
            count = (node_alerts['severity'] == sev).sum()
            features.append(count)
            features.append(count / max(len(node_alerts), 1))       # 占比
        
        # 指标统计（如果有metrics列）
        metrics_cols = ['cpu_usage', 'mem_usage', 'latency_p99', 'error_rate']
        for col in metrics_cols:
            if col in node_alerts.columns:
                values = node_alerts[col].dropna()
                if len(values) > 0:
                    features.extend([
                        values.mean(),
                        values.std(),
                        values.min(),
                        values.max(),
                        values.quantile(0.25),
                        values.quantile(0.75)
                    ])
                else:
                    features.extend([0]*6)
            else:
                features.extend([0]*6)
        
        # 时间特征
        if 'timestamp' in node_alerts.columns:
            timestamps = pd.to_datetime(node_alerts['timestamp'])
            duration = (timestamps.max() - timestamps.min()).total_seconds()
            features.append(duration)
            features.append(duration / max(len(timestamps), 1))     # 平均间隔
        else:
            features.extend([0, 0])
        
        result = np.array(features[:54], dtype=np.float32)
        if len(result) < 54:
            result = np.pad(result, (0, 54 - len(result)))
        
        return result
    
    def _extract_edge_features(
        self,
        edges: List[dict],
        node_id_map: Dict[str, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """提取边索引和边特征"""
        
        src_list = []
        dst_list = []
        edge_attrs = []
        
        for edge in edges:
            src = edge["source"]
            dst = edge["target"]
            
            if src in node_id_map and dst in node_id_map:
                src_list.append(node_id_map[src])
                dst_list.append(node_id_map[dst])
                
                # 边特征：调用频率、延迟、依赖类型
                call_freq = edge.get("call_frequency", 100)
                latency = edge.get("latency_avg", 10.0)
                dep_type = self._encode_dependency_type(edge.get("dependency_type", "synchronous"))
                reliability = edge.get("reliability", 0.99)
                
                edge_attr = [
                    np.log1p(call_freq),       # 对数变换
                    latency / 100.0,            # 归一化
                    *dep_type,
                    reliability
                ]
                edge_attrs.append(edge_attr)
                
                # 如果配置了反向边
                if self.config.get("add_reverse_edges", True):
                    src_list.append(node_id_map[dst])
                    dst_list.append(node_id_map[src])
                    
                    reverse_attr = [
                        np.log1p(call_freq),
                        latency / 100.0,
                        *dep_type,
                        reliability * 0.8  # 反向权重略低
                    ]
                    edge_attrs.append(reverse_attr)
        
        edge_index = np.array([src_list, dst_list], dtype=np.int64)
        edge_attr = np.array(edge_attrs, dtype=np.float32)
        
        return edge_index, edge_attr
    
    def _encode_dependency_type(self, dep_type: str) -> list:
        """依赖类型编码"""
        types = ["synchronous", "async", "shared_db", "message_queue"]
        encoding = [0.0] * len(types)
        if dep_type in types:
            encoding[types.index(dep_type)] = 1.0
        return encoding
    
    def _extract_temporal_features(
        self,
        alerts_df: pd.DataFrame,
        node_id_map: Dict[str, int]
    ) -> Dict[int, np.ndarray]:
        """提取时序特征（用于动态GNN）"""
        
        window_size = self.config.get("temporal_window_size", 10)
        time_step_sec = self.config.get("time_step_seconds", 60)
        
        temporal_feats = {}
        
        if 'timestamp' not in alerts_df.columns or 'node' not in alerts_df.columns:
            return temporal_feats
        
        for node_id, idx in node_id_map.items():
            node_alerts = alerts_df[alerts_df['node'] == node_id].copy()
            
            if len(node_alerts) == 0:
                # 无告警的节点用零向量
                temporal_feats[idx] = np.zeros((window_size, 8), dtype=np.float32)
                continue
            
            node_alerts['timestamp'] = pd.to_datetime(node_alerts['timestamp'])
            node_alerts = node_alerts.sort_values('timestamp')
            
            # 创建时间窗口
            start_time = node_alerts['timestamp'].min()
            windows = []
            
            for t in range(window_size):
                window_start = start_time + timedelta(seconds=t * time_step_sec)
                window_end = window_start + timedelta(seconds=time_step_sec)
                
                window_alerts = node_alerts[
                    (node_alerts['timestamp'] >= window_start) &
                    (node_alerts['timestamp'] < window_end)
                ]
                
                if len(window_alerts) > 0:
                    feat = [
                        len(window_alerts),
                        sum(window_alerts['severity'] == 'critical'),
                        sum(window_alerts['severity'] == 'major'),
                        window_alerts['cpu_usage'].mean() if 'cpu_usage' in window_alerts.columns else 0,
                        window_alerts['mem_usage'].mean() if 'mem_usage' in window_alerts.columns else 0,
                        window_alerts['latency_p99'].mean() if 'latency_p99' in window_alerts.columns else 0,
                        window_alerts['error_rate'].mean() if 'error_rate' in window_alerts.columns else 0,
                        len(window_alerts['alert_type'].unique())
                    ]
                else:
                    feat = [0] * 8
                
                windows.append(feat)
            
            temporal_feats[idx] = np.array(windows, dtype=np.float32)
        
        return temporal_feats
    
    def _extract_labels(
        self,
        alerts_df: pd.DataFrame,
        node_id_map: Dict[str, int]
    ) -> List[int]:
        """提取根因标签"""
        
        labels = [0] * len(node_id_map)
        
        if 'is_root_cause' in alerts_df.columns and 'node' in alerts_df.columns:
            root_cause_nodes = alerts_df[alerts_df['is_root_cause'] == True]['node'].unique()
            
            for node_id in root_cause_nodes:
                if node_id in node_id_map:
                    labels[node_id_map[node_id]] = 1
        
        return labels
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Z-score归一化"""
        
        mean = features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        std[std == 0] = 1  # 避免除零
        
        return (features - mean) / std


def main():
    parser = argparse.ArgumentParser(description='清洗数据并构建图')
    parser.add_argument('--topology', type=str, required=True, help='拓扑JSON文件路径')
    parser.add_argument('--alerts', type=str, required=True, help='告警CSV文件路径')
    parser.add_argument('--output-prefix', type=str, default='', help='输出前缀')
    args = parser.parse_args()
    
    print("="*70)
    print("🧹 Step 2/5: 数据清洗与图构建 - GNN根因分析系统")
    print("="*70)
    
    # 1. 加载数据
    print("\n📥 加载数据...")
    with open(args.topology, 'r') as f:
        topology = json.load(f)
    
    alerts_df = pd.read_csv(args.alerts)
    print(f"   拓扑文件: {args.topology}")
    print(f"   告警文件: {args.alerts} ({len(alerts_df)} 条)")
    
    # 2. 清洗数据
    cleaner = AlertDataCleaner(CLEANING_CONFIG)
    cleaned_df = cleaner.clean(alerts_df.copy())
    
    # 3. 时间对齐
    aligner = TimeSeriesAligner(CLEANING_CONFIG)
    aligned_df = aligner.align(cleaned_df)
    
    # 4. 构建异构图
    builder = HeterogeneousGraphBuilder(args.topology, GRAPH_CONFIG)
    graph_data = builder.build_from_topology_and_alerts(topology, aligned_df)
    
    # 5. 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_prefix or f"cleaned_{timestamp}"
    
    output_dir = DATA_DIRS["cleaned"]
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存清洗后的告警
    cleaned_file = os.path.join(output_dir, f"{prefix}_cleaned_alerts.csv")
    aligned_df.to_csv(cleaned_file, index=False)
    
    # 保存图数据为NPZ
    graph_file = os.path.join(DATA_DIRS["graphs"], f"{prefix}_graph_data.npz")
    np.savez(
        graph_file,
        node_features=graph_data["node_features"],
        edge_index=graph_data["edge_index"],
        edge_attr=graph_data["edge_attr"],
        labels=np.array(graph_data["labels"]),
        **{f"temporal_{k}": v for k, v in graph_data["temporal_features"].items()}
    )
    
    # 保存元数据
    meta_file = os.path.join(output_dir, f"{prefix}_metadata.json")
    metadata = {
        "num_nodes": graph_data["num_nodes"],
        "num_edges": len(graph_data["edge_index"][0]),
        "feature_dim": graph_data["node_features"].shape[1],
        "num_root_causes": sum(graph_data["labels"]),
        "num_normal": len(graph_data["labels"]) - sum(graph_data["labels"]),
        "created_at": datetime.now().isoformat(),
        "node_id_mapping": graph_data["node_id_mapping"]
    }
    
    with open(meta_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n💾 输出文件:")
    print(f"   ✓ 清洗后的告警: {cleaned_file}")
    print(f"   ✓ 图数据(NPZ): {graph_file}")
    print(f"   ✓ 元数据: {meta_file}")
    
    print(f"\n✅ Step 2 完成! 图已准备就绪供GNN训练使用")
    
    return graph_data


if __name__ == "__main__":
    main()