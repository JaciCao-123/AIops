#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 预测和根因分析

使用训练好的模型对新数据进行根因定位
"""

import os
import json
import torch
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model import load_model, RootCausePredictor


class RootCauseAnalyzer:
    """根因分析器"""
    
    def __init__(self, model_path: str, topology_path: str, 
                 normalize_params_path: str, device: str = 'cpu'):
        """
        初始化分析器
        
        Args:
            model_path: 模型文件路径
            topology_path: 拓扑文件路径
            normalize_params_path: 标准化参数文件路径
            device: 计算设备
        """
        with open(topology_path, 'r', encoding='utf-8') as f:
            topology_data = json.load(f)
        
        self.services = topology_data['services']
        self.service_types = topology_data['service_types']
        self.topology = topology_data['topology']
        self.service_to_idx = {s: i for i, s in enumerate(self.services)}
        self.idx_to_service = {i: s for i, s in enumerate(self.services)}
        
        with open(normalize_params_path, 'r', encoding='utf-8') as f:
            params = json.load(f)
        self.normalize_min = np.array(params['min'])
        self.normalize_max = np.array(params['max'])
        
        checkpoint = torch.load(model_path, map_location=device)
        metadata = checkpoint.get('metadata', {})
        model_type = metadata.get('model_type', 'gat')
        hidden_dim = metadata.get('hidden_dim', 64)
        num_layers = metadata.get('num_layers', 3)
        
        self.model = load_model(
            filepath=model_path,
            model_type=model_type,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            device=device
        )
        
        self.predictor = RootCausePredictor(self.model, device)
        
        self.edge_index = self._build_edge_index()
    
    def _build_edge_index(self) -> np.ndarray:
        """构建边索引"""
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
    
    def normalize_features(self, features: np.ndarray) -> np.ndarray:
        """标准化特征"""
        return (features - self.normalize_min) / (self.normalize_max - self.normalize_min + 1e-8)
    
    def extract_features(self, metrics: Dict[str, Dict]) -> np.ndarray:
        """提取特征"""
        feature_keys = ['latency_ms', 'error_rate', 'cpu_usage', 'memory_usage', 'throughput_rps']
        features = np.zeros((len(self.services), len(feature_keys)))
        
        for i, service in enumerate(self.services):
            if service in metrics:
                for j, key in enumerate(feature_keys):
                    features[i, j] = metrics[service].get(key, 0.0)
        
        return features
    
    def analyze(self, metrics: Dict[str, Dict], top_k: int = 3) -> Dict:
        """
        分析根因
        
        Args:
            metrics: 服务指标字典
            top_k: 返回 Top-K 候选
            
        Returns:
            分析结果
        """
        features = self.extract_features(metrics)
        features = self.normalize_features(features)
        
        predicted_idx, probs = self.predictor.predict(features, self.edge_index)
        top_k_results = self.predictor.predict_top_k(features, self.edge_index, k=top_k)
        
        predicted_service = self.idx_to_service[predicted_idx]
        
        top_k_services = [
            {
                'service': self.idx_to_service[idx],
                'probability': float(prob),
                'service_type': self.service_types[self.idx_to_service[idx]]
            }
            for idx, prob in top_k_results
        ]
        
        anomaly_services = []
        for i, service in enumerate(self.services):
            if probs[i] > 0.3:
                anomaly_services.append({
                    'service': service,
                    'probability': float(probs[i]),
                    'metrics': metrics.get(service, {})
                })
        
        propagation_path = self._get_propagation_path(predicted_service)
        
        return {
            'predicted_root_cause': predicted_service,
            'confidence': float(probs[predicted_idx]),
            'top_k_candidates': top_k_services,
            'anomaly_services': anomaly_services,
            'propagation_path': propagation_path,
            'all_probabilities': {
                service: float(probs[i]) 
                for i, service in enumerate(self.services)
            }
        }
    
    def _get_propagation_path(self, root_service: str) -> List[str]:
        """获取异常传播路径"""
        visited = [root_service]
        queue = [root_service]
        
        while queue:
            current = queue.pop(0)
            for service, deps in self.topology.items():
                if current in deps and service not in visited:
                    visited.append(service)
                    queue.append(service)
        
        return visited
    
    def generate_report(self, analysis_result: Dict, 
                        metrics: Dict[str, Dict]) -> str:
        """生成分析报告"""
        report = []
        report.append("=" * 60)
        report.append("微服务根因分析报告")
        report.append("=" * 60)
        report.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        report.append("## 1. 根因定位结果")
        report.append("-" * 40)
        root = analysis_result['predicted_root_cause']
        confidence = analysis_result['confidence']
        report.append(f"根因服务: {root}")
        report.append(f"置信度: {confidence:.2%}")
        report.append(f"服务类型: {self.service_types[root]}")
        report.append("")
        
        if root in metrics:
            report.append("根因服务指标:")
            m = metrics[root]
            for key, value in m.items():
                if isinstance(value, (int, float)):
                    report.append(f"  - {key}: {value:.2f}")
        report.append("")
        
        report.append("## 2. Top-K 候选服务")
        report.append("-" * 40)
        for i, candidate in enumerate(analysis_result['top_k_candidates'], 1):
            report.append(f"{i}. {candidate['service']} "
                         f"(置信度: {candidate['probability']:.2%}, "
                         f"类型: {candidate['service_type']})")
        report.append("")
        
        report.append("## 3. 异常传播路径")
        report.append("-" * 40)
        path = analysis_result['propagation_path']
        report.append(" → ".join(path))
        report.append("")
        
        report.append("## 4. 受影响服务")
        report.append("-" * 40)
        for svc in analysis_result['anomaly_services']:
            report.append(f"- {svc['service']} (概率: {svc['probability']:.2%})")
        report.append("")
        
        report.append("## 5. 建议措施")
        report.append("-" * 40)
        suggestions = self._generate_suggestions(root, analysis_result)
        for i, sug in enumerate(suggestions, 1):
            report.append(f"{i}. {sug}")
        
        return "\n".join(report)
    
    def _generate_suggestions(self, root_service: str, 
                              analysis_result: Dict) -> List[str]:
        """生成建议措施"""
        suggestions = []
        service_type = self.service_types[root_service]
        confidence = analysis_result['confidence']
        
        if service_type == 'database':
            suggestions.append("检查数据库连接池状态和慢查询")
            suggestions.append("检查数据库锁等待和死锁情况")
            suggestions.append("考虑增加数据库读副本或缓存层")
        elif service_type == 'cache':
            suggestions.append("检查缓存命中率和内存使用情况")
            suggestions.append("检查缓存连接和集群状态")
            suggestions.append("考虑增加缓存容量或优化缓存策略")
        elif service_type == 'backend':
            suggestions.append("检查服务实例健康状态和资源使用")
            suggestions.append("检查依赖服务的响应时间")
            suggestions.append("考虑扩容或重启异常实例")
        elif service_type == 'frontend':
            suggestions.append("检查前端服务响应时间和错误率")
            suggestions.append("检查后端 API 调用链路")
            suggestions.append("考虑启用降级或熔断机制")
        
        if confidence > 0.8:
            suggestions.append(f"高置信度 ({confidence:.0%})，建议优先处理 {root_service}")
        else:
            suggestions.append(f"置信度较低 ({confidence:.0%})，建议结合人工分析")
        
        return suggestions


def main():
    print("=" * 60)
    print("Step 4: 预测和根因分析")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    models_dir = os.path.join(base_dir, 'models')
    data_dir = os.path.join(base_dir, 'data')
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"\n使用设备: {device}")
    
    model_files = {
        'gcn': os.path.join(models_dir, 'gcn_model.pt'),
        'gat': os.path.join(models_dir, 'gat_model.pt'),
        'sage': os.path.join(models_dir, 'sage_model.pt')
    }
    
    available_models = {k: v for k, v in model_files.items() if os.path.exists(v)}
    
    if not available_models:
        print("未找到训练好的模型，请先运行 step3_train_model.py")
        return
    
    model_type = list(available_models.keys())[0]
    model_path = available_models[model_type]
    print(f"\n使用模型: {model_path}")
    
    analyzer = RootCauseAnalyzer(
        model_path=model_path,
        topology_path=os.path.join(data_dir, 'raw', 'topology.json'),
        normalize_params_path=os.path.join(data_dir, 'cleaned', 'normalize_params.json'),
        device=device
    )
    
    print("\n📂 加载测试数据...")
    with open(os.path.join(data_dir, 'cleaned', 'time_series_graph.json'), 'r') as f:
        test_data = json.load(f)
    
    anomaly_data = [d for d in test_data if d.get('is_anomaly')]
    print(f"   - 总数据点: {len(test_data)}")
    print(f"   - 异常数据点: {len(anomaly_data)}")
    
    if anomaly_data:
        print("\n" + "=" * 60)
        print("分析异常案例")
        print("=" * 60)
        
        for i, case in enumerate(anomaly_data[:3]):
            print(f"\n案例 {i+1}:")
            print("-" * 40)
            
            metrics = {}
            for j, service in enumerate(analyzer.services):
                x = np.array(case['x'][j])
                metrics[service] = {
                    'latency_ms': x[0],
                    'error_rate': x[1],
                    'cpu_usage': x[2],
                    'memory_usage': x[3],
                    'throughput_rps': x[4]
                }
            
            result = analyzer.analyze(metrics, top_k=3)
            
            print(f"实际根因: {case.get('root_cause', 'N/A')}")
            print(f"预测根因: {result['predicted_root_cause']}")
            print(f"置信度: {result['confidence']:.2%}")
            
            print("\nTop-3 候选:")
            for j, cand in enumerate(result['top_k_candidates'], 1):
                print(f"  {j}. {cand['service']} ({cand['probability']:.2%})")
            
            is_correct = result['predicted_root_cause'] == case.get('root_cause')
            print(f"\n预测结果: {'✅ 正确' if is_correct else '❌ 错误'}")
    
    print("\n" + "=" * 60)
    print("评估模型性能")
    print("=" * 60)
    
    correct = 0
    top3_correct = 0
    total = len(anomaly_data)
    
    for case in anomaly_data:
        metrics = {}
        for j, service in enumerate(analyzer.services):
            x = np.array(case['x'][j])
            metrics[service] = {
                'latency_ms': x[0],
                'error_rate': x[1],
                'cpu_usage': x[2],
                'memory_usage': x[3],
                'throughput_rps': x[4]
            }
        
        result = analyzer.analyze(metrics, top_k=3)
        
        if result['predicted_root_cause'] == case.get('root_cause'):
            correct += 1
        
        top3_services = [c['service'] for c in result['top_k_candidates']]
        if case.get('root_cause') in top3_services:
            top3_correct += 1
    
    print(f"Top-1 准确率: {correct}/{total} ({correct/total*100:.1f}%)")
    print(f"Top-3 准确率: {top3_correct}/{total} ({top3_correct/total*100:.1f}%)")
    
    print("\n" + "=" * 60)
    print("示例：生成完整分析报告")
    print("=" * 60)
    
    if anomaly_data:
        case = anomaly_data[0]
        metrics = {}
        for j, service in enumerate(analyzer.services):
            x = np.array(case['x'][j])
            metrics[service] = {
                'latency_ms': x[0],
                'error_rate': x[1],
                'cpu_usage': x[2],
                'memory_usage': x[3],
                'throughput_rps': x[4]
            }
        
        result = analyzer.analyze(metrics, top_k=3)
        report = analyzer.generate_report(result, metrics)
        print(report)


if __name__ == "__main__":
    main()
