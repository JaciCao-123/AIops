#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: 数据清理和对齐

对生成的微服务调用图数据进行清理、对齐和特征工程
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict


class DataCleaner:
    """数据清理和对齐处理器"""
    
    def __init__(self):
        self.services = []
        self.service_types = {}
        self.topology = {}
        self.service_to_idx = {}
        self.idx_to_service = {}
    
    def load_topology(self, filepath: str) -> Dict:
        """加载拓扑结构"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.services = data['services']
        self.service_types = data['service_types']
        self.topology = data['topology']
        
        self.service_to_idx = {s: i for i, s in enumerate(self.services)}
        self.idx_to_service = {i: s for i, s in enumerate(self.services)}
        
        return data
    
    def load_time_series(self, filepath: str) -> List[Dict]:
        """加载时间序列数据"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    
    def load_training_data(self, data_path: str, labels_path: str) -> Tuple[List[Dict], List[str]]:
        """加载训练数据"""
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        with open(labels_path, 'r', encoding='utf-8') as f:
            labels = json.load(f)
        return data, labels
    
    def clean_metrics(self, metrics: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        清理指标数据
        
        - 处理缺失值
        - 处理异常值
        - 标准化格式
        """
        cleaned = {}
        
        for service, metric in metrics.items():
            cleaned_metric = {}
            
            for key in ['latency_ms', 'error_rate', 'cpu_usage', 'memory_usage', 'throughput_rps']:
                value = metric.get(key)
                
                if value is None or np.isnan(value) or np.isinf(value):
                    cleaned_metric[key] = 0.0
                else:
                    if key == 'latency_ms':
                        cleaned_metric[key] = max(0, min(value, 60000))
                    elif key == 'error_rate':
                        cleaned_metric[key] = max(0, min(value, 1.0))
                    elif key in ['cpu_usage', 'memory_usage']:
                        cleaned_metric[key] = max(0, min(value, 100))
                    elif key == 'throughput_rps':
                        cleaned_metric[key] = max(0, value)
            
            cleaned_metric['is_root_cause'] = metric.get('is_root_cause', False)
            cleaned_metric['anomaly_type'] = metric.get('anomaly_type', 'normal')
            
            cleaned[service] = cleaned_metric
        
        return cleaned
    
    def align_timestamps(self, data: List[Dict], interval_seconds: int = 60) -> List[Dict]:
        """
        对齐时间戳
        
        - 确保时间间隔一致
        - 填充缺失时间点
        """
        if not data:
            return data
        
        aligned = []
        base_time = datetime.fromisoformat(data[0]['timestamp'])
        
        for i, record in enumerate(data):
            expected_time = base_time + pd.Timedelta(seconds=i * interval_seconds)
            actual_time = datetime.fromisoformat(record['timestamp'])
            
            time_diff = abs((actual_time - expected_time).total_seconds())
            
            if time_diff <= interval_seconds * 0.5:
                record['timestamp'] = expected_time.isoformat()
                aligned.append(record)
            else:
                aligned.append({
                    'timestamp': expected_time.isoformat(),
                    'metrics': {},
                    'root_cause': None,
                    'is_anomaly': False
                })
        
        return aligned
    
    def extract_features(self, metrics: Dict[str, Dict]) -> np.ndarray:
        """
        提取特征向量
        
        Returns:
            shape: (num_services, num_features)
        """
        feature_keys = ['latency_ms', 'error_rate', 'cpu_usage', 'memory_usage', 'throughput_rps']
        features = np.zeros((len(self.services), len(feature_keys)))
        
        for i, service in enumerate(self.services):
            if service in metrics:
                for j, key in enumerate(feature_keys):
                    features[i, j] = metrics[service].get(key, 0.0)
        
        return features
    
    def normalize_features(self, features: np.ndarray, 
                           method: str = 'minmax') -> Tuple[np.ndarray, Dict]:
        """
        标准化特征
        
        Args:
            features: 特征矩阵
            method: 标准化方法 ('minmax' 或 'zscore')
            
        Returns:
            (标准化后的特征, 标准化参数)
        """
        if method == 'minmax':
            min_vals = features.min(axis=0)
            max_vals = features.max(axis=0)
            range_vals = max_vals - min_vals
            range_vals[range_vals == 0] = 1
            
            normalized = (features - min_vals) / range_vals
            params = {'min': min_vals, 'max': max_vals}
        else:
            mean_vals = features.mean(axis=0)
            std_vals = features.std(axis=0)
            std_vals[std_vals == 0] = 1
            
            normalized = (features - mean_vals) / std_vals
            params = {'mean': mean_vals, 'std': std_vals}
        
        return normalized, params
    
    def build_adjacency_matrix(self) -> np.ndarray:
        """
        构建邻接矩阵
        
        Returns:
            shape: (num_services, num_services)
        """
        n = len(self.services)
        adj = np.zeros((n, n))
        
        for service, deps in self.topology.items():
            i = self.service_to_idx[service]
            for dep in deps:
                j = self.service_to_idx[dep]
                adj[i, j] = 1
                adj[j, i] = 1
        
        adj = adj + np.eye(n)
        
        return adj
    
    def build_edge_index(self) -> np.ndarray:
        """
        构建边索引（用于 PyTorch Geometric）
        
        Returns:
            shape: (2, num_edges)
        """
        edges = []
        
        for service, deps in self.topology.items():
            i = self.service_to_idx[service]
            for dep in deps:
                j = self.service_to_idx[dep]
                edges.append([i, j])
                edges.append([j, i])
        
        for i in range(len(self.services)):
            edges.append([i, i])
        
        return np.array(edges).T
    
    def create_graph_data(self, record: Dict, normalize_params: Optional[Dict] = None) -> Dict:
        """
        创建图数据
        
        Args:
            record: 单条数据记录
            normalize_params: 标准化参数
            
        Returns:
            图数据字典
        """
        metrics = self.clean_metrics(record['metrics'])
        features = self.extract_features(metrics)
        
        if normalize_params:
            features = (features - normalize_params['min']) / (normalize_params['max'] - normalize_params['min'] + 1e-8)
        
        edge_index = self.build_edge_index()
        
        labels = np.zeros(len(self.services))
        if record.get('root_cause') and record['root_cause'] in self.service_to_idx:
            labels[self.service_to_idx[record['root_cause']]] = 1
        
        return {
            'x': features,
            'edge_index': edge_index,
            'y': labels,
            'root_cause': record.get('root_cause'),
            'is_anomaly': record.get('is_anomaly', False),
            'timestamp': record.get('timestamp')
        }
    
    def process_time_series(self, data: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        处理时间序列数据
        
        Returns:
            (处理后的数据列表, 标准化参数)
        """
        print("  - 清理指标数据...")
        cleaned_data = []
        all_features = []
        
        for record in data:
            cleaned_metrics = self.clean_metrics(record['metrics'])
            features = self.extract_features(cleaned_metrics)
            all_features.append(features)
            
            cleaned_data.append({
                **record,
                'metrics': cleaned_metrics
            })
        
        print("  - 对齐时间戳...")
        aligned_data = self.align_timestamps(cleaned_data)
        
        print("  - 计算标准化参数...")
        all_features = np.array(all_features)
        _, normalize_params = self.normalize_features(all_features.reshape(-1, 5))
        
        print("  - 创建图数据...")
        graph_data = []
        for record in aligned_data:
            graph = self.create_graph_data(record, normalize_params)
            graph_data.append(graph)
        
        return graph_data, normalize_params
    
    def process_training_data(self, data: List[Dict], labels: List[str]) -> Tuple[List[Dict], Dict]:
        """
        处理训练数据
        
        Returns:
            (处理后的数据列表, 标准化参数)
        """
        print("  - 清理指标数据...")
        all_features = []
        
        for record in data:
            cleaned_metrics = self.clean_metrics(record['metrics'])
            features = self.extract_features(cleaned_metrics)
            all_features.append(features)
            record['metrics'] = cleaned_metrics
        
        print("  - 计算标准化参数...")
        all_features = np.array(all_features)
        _, normalize_params = self.normalize_features(all_features.reshape(-1, 5))
        
        print("  - 创建图数据...")
        graph_data = []
        for i, record in enumerate(data):
            graph = self.create_graph_data(record, normalize_params)
            graph['label'] = labels[i]
            graph_data.append(graph)
        
        return graph_data, normalize_params
    
    def save_processed_data(self, data: List[Dict], filepath: str):
        """保存处理后的数据"""
        save_data = []
        for item in data:
            save_item = {
                'x': item['x'].tolist(),
                'edge_index': item['edge_index'].tolist(),
                'y': item['y'].tolist(),
                'root_cause': item.get('root_cause'),
                'is_anomaly': item.get('is_anomaly', False),
                'timestamp': item.get('timestamp'),
                'label': item.get('label')
            }
            save_data.append(save_item)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2)
        print(f"数据已保存到: {filepath}")
    
    def save_normalize_params(self, params: Dict, filepath: str):
        """保存标准化参数"""
        save_params = {
            'min': params['min'].tolist(),
            'max': params['max'].tolist()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_params, f, indent=2)
        print(f"标准化参数已保存到: {filepath}")


def main():
    print("=" * 60)
    print("Step 2: 数据清理和对齐")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    raw_dir = os.path.join(base_dir, 'data', 'raw')
    cleaned_dir = os.path.join(base_dir, 'data', 'cleaned')
    os.makedirs(cleaned_dir, exist_ok=True)
    
    cleaner = DataCleaner()
    
    print("\n📂 加载拓扑结构...")
    cleaner.load_topology(os.path.join(raw_dir, 'topology.json'))
    print(f"   - 服务数量: {len(cleaner.services)}")
    
    print("\n📂 处理时间序列数据...")
    time_series = cleaner.load_time_series(os.path.join(raw_dir, 'time_series.json'))
    processed_ts, norm_params = cleaner.process_time_series(time_series)
    cleaner.save_processed_data(processed_ts, os.path.join(cleaned_dir, 'time_series_graph.json'))
    cleaner.save_normalize_params(norm_params, os.path.join(cleaned_dir, 'normalize_params.json'))
    
    print("\n📂 处理训练数据...")
    train_data, train_labels = cleaner.load_training_data(
        os.path.join(raw_dir, 'train_data.json'),
        os.path.join(raw_dir, 'train_labels.json')
    )
    processed_train, _ = cleaner.process_training_data(train_data, train_labels)
    cleaner.save_processed_data(processed_train, os.path.join(cleaned_dir, 'train_graph.json'))
    
    print("\n📊 处理完成:")
    print(f"   - 时间序列图数据: {len(processed_ts)} 条")
    print(f"   - 训练图数据: {len(processed_train)} 条")
    print(f"   - 服务数量: {len(cleaner.services)}")
    print(f"   - 边数量: {cleaner.build_edge_index().shape[1]}")


if __name__ == "__main__":
    main()
