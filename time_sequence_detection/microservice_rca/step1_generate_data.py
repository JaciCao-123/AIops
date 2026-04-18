#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 生成微服务调用图模拟数据

生成微服务架构的调用关系图数据，用于根因定位训练
"""

import os
import json
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any


class MicroserviceGraphGenerator:
    """微服务调用图数据生成器"""
    
    def __init__(self, num_services: int = 20, seed: int = 42):
        """
        初始化生成器
        
        Args:
            num_services: 微服务数量
            seed: 随机种子
        """
        self.num_services = num_services
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        
        self.services = self._generate_service_names()
        self.service_types = self._assign_service_types()
        self.topology = self._generate_topology()
        self.service_metrics = {}
    
    def _generate_service_names(self) -> List[str]:
        """生成服务名称"""
        prefixes = ['user', 'order', 'payment', 'inventory', 'notification', 
                    'auth', 'gateway', 'config', 'cache', 'db',
                    'api', 'worker', 'scheduler', 'logger', 'monitor',
                    'search', 'recommend', 'analytics', 'storage', 'queue']
        
        services = []
        for i in range(self.num_services):
            if i < len(prefixes):
                services.append(f"{prefixes[i]}-service")
            else:
                services.append(f"service-{i+1}")
        
        return services
    
    def _assign_service_types(self) -> Dict[str, str]:
        """分配服务类型"""
        types = ['frontend', 'backend', 'database', 'cache', 'queue', 'external']
        weights = [0.1, 0.5, 0.15, 0.1, 0.1, 0.05]
        
        service_types = {}
        for service in self.services:
            service_types[service] = random.choices(types, weights=weights)[0]
        
        return service_types
    
    def _generate_topology(self) -> Dict[str, List[str]]:
        """生成服务调用拓扑"""
        topology = {service: [] for service in self.services}
        
        for i, service in enumerate(self.services):
            if self.service_types[service] == 'frontend':
                continue
            
            num_deps = random.randint(1, min(5, self.num_services - i - 1))
            possible_deps = self.services[i+1:]
            
            if possible_deps:
                deps = random.sample(possible_deps, min(num_deps, len(possible_deps)))
                topology[service] = deps
        
        return topology
    
    def _generate_normal_metrics(self, service: str, timestamp: datetime) -> Dict[str, float]:
        """生成正常状态的服务指标"""
        service_type = self.service_types[service]
        
        if service_type == 'frontend':
            latency = random.uniform(50, 150)
            error_rate = random.uniform(0, 0.01)
            cpu = random.uniform(20, 40)
            memory = random.uniform(30, 50)
            throughput = random.uniform(100, 500)
        elif service_type == 'backend':
            latency = random.uniform(10, 100)
            error_rate = random.uniform(0, 0.02)
            cpu = random.uniform(30, 60)
            memory = random.uniform(40, 70)
            throughput = random.uniform(200, 1000)
        elif service_type == 'database':
            latency = random.uniform(5, 50)
            error_rate = random.uniform(0, 0.005)
            cpu = random.uniform(40, 70)
            memory = random.uniform(60, 80)
            throughput = random.uniform(500, 2000)
        elif service_type == 'cache':
            latency = random.uniform(1, 10)
            error_rate = random.uniform(0, 0.001)
            cpu = random.uniform(10, 30)
            memory = random.uniform(50, 80)
            throughput = random.uniform(1000, 5000)
        else:
            latency = random.uniform(10, 80)
            error_rate = random.uniform(0, 0.01)
            cpu = random.uniform(20, 50)
            memory = random.uniform(30, 60)
            throughput = random.uniform(100, 800)
        
        return {
            'latency_ms': round(latency, 2),
            'error_rate': round(error_rate, 4),
            'cpu_usage': round(cpu, 2),
            'memory_usage': round(memory, 2),
            'throughput_rps': round(throughput, 2)
        }
    
    def _generate_anomaly_metrics(self, service: str, timestamp: datetime, 
                                   anomaly_type: str) -> Dict[str, float]:
        """生成异常状态的服务指标"""
        normal = self._generate_normal_metrics(service, timestamp)
        
        if anomaly_type == 'latency_spike':
            normal['latency_ms'] = normal['latency_ms'] * random.uniform(5, 20)
            normal['cpu_usage'] = min(100, normal['cpu_usage'] * random.uniform(1.5, 2.5))
        elif anomaly_type == 'error_spike':
            normal['error_rate'] = random.uniform(0.1, 0.5)
            normal['latency_ms'] = normal['latency_ms'] * random.uniform(2, 5)
        elif anomaly_type == 'resource_exhaustion':
            normal['cpu_usage'] = random.uniform(90, 99)
            normal['memory_usage'] = random.uniform(90, 99)
            normal['latency_ms'] = normal['latency_ms'] * random.uniform(3, 10)
        elif anomaly_type == 'throughput_drop':
            normal['throughput_rps'] = normal['throughput_rps'] * random.uniform(0.1, 0.3)
            normal['latency_ms'] = normal['latency_ms'] * random.uniform(2, 5)
        
        return normal
    
    def _propagate_anomaly(self, root_service: str, anomaly_type: str,
                           timestamp: datetime, affected_services: set) -> Dict[str, Dict]:
        """传播异常到下游服务"""
        metrics = {}
        
        for service in self.services:
            if service == root_service:
                metrics[service] = self._generate_anomaly_metrics(
                    service, timestamp, anomaly_type
                )
                metrics[service]['is_root_cause'] = True
                metrics[service]['anomaly_type'] = anomaly_type
            elif service in affected_services:
                m = self._generate_normal_metrics(service, timestamp)
                m['latency_ms'] *= random.uniform(1.5, 3)
                m['error_rate'] = min(1.0, m['error_rate'] * random.uniform(2, 5))
                m['is_root_cause'] = False
                m['anomaly_type'] = 'propagated'
                metrics[service] = m
            else:
                metrics[service] = self._generate_normal_metrics(service, timestamp)
                metrics[service]['is_root_cause'] = False
                metrics[service]['anomaly_type'] = 'normal'
        
        return metrics
    
    def _get_downstream_services(self, root_service: str) -> set:
        """获取下游受影响的服务"""
        visited = set()
        queue = [root_service]
        
        while queue:
            current = queue.pop(0)
            for service, deps in self.topology.items():
                if current in deps and service not in visited:
                    visited.add(service)
                    queue.append(service)
        
        return visited
    
    def generate_time_series(self, duration_hours: int = 24, 
                              interval_minutes: int = 1,
                              anomaly_rate: float = 0.05) -> List[Dict]:
        """
        生成时间序列数据
        
        Args:
            duration_hours: 持续时间（小时）
            interval_minutes: 采样间隔（分钟）
            anomaly_rate: 异常发生率
            
        Returns:
            时间序列数据列表
        """
        start_time = datetime(2024, 1, 1, 0, 0, 0)
        total_points = duration_hours * 60 // interval_minutes
        
        data = []
        anomaly_types = ['latency_spike', 'error_spike', 'resource_exhaustion', 'throughput_drop']
        
        for i in range(total_points):
            timestamp = start_time + timedelta(minutes=i * interval_minutes)
            
            is_anomaly = random.random() < anomaly_rate
            
            if is_anomaly:
                root_service = random.choice(self.services)
                anomaly_type = random.choice(anomaly_types)
                affected = self._get_downstream_services(root_service)
                metrics = self._propagate_anomaly(root_service, anomaly_type, 
                                                   timestamp, affected)
                root_cause = root_service
            else:
                metrics = {}
                for service in self.services:
                    metrics[service] = self._generate_normal_metrics(service, timestamp)
                    metrics[service]['is_root_cause'] = False
                    metrics[service]['anomaly_type'] = 'normal'
                root_cause = None
            
            record = {
                'timestamp': timestamp.isoformat(),
                'metrics': metrics,
                'root_cause': root_cause,
                'is_anomaly': is_anomaly
            }
            data.append(record)
        
        return data
    
    def generate_training_data(self, num_samples: int = 1000) -> Tuple[List[Dict], List[str]]:
        """
        生成训练数据
        
        Args:
            num_samples: 样本数量
            
        Returns:
            (数据列表, 标签列表)
        """
        data = []
        labels = []
        anomaly_types = ['latency_spike', 'error_spike', 'resource_exhaustion', 'throughput_drop']
        
        for _ in range(num_samples):
            timestamp = datetime.now()
            
            if random.random() < 0.5:
                root_service = random.choice(self.services)
                anomaly_type = random.choice(anomaly_types)
                affected = self._get_downstream_services(root_service)
                metrics = self._propagate_anomaly(root_service, anomaly_type, 
                                                   timestamp, affected)
                label = root_service
            else:
                metrics = {}
                for service in self.services:
                    metrics[service] = self._generate_normal_metrics(service, timestamp)
                    metrics[service]['is_root_cause'] = False
                    metrics[service]['anomaly_type'] = 'normal'
                label = 'normal'
            
            data.append({
                'timestamp': timestamp.isoformat(),
                'metrics': metrics,
                'topology': self.topology
            })
            labels.append(label)
        
        return data, labels
    
    def save_data(self, data: List[Dict], filepath: str):
        """保存数据到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"数据已保存到: {filepath}")
    
    def save_topology(self, filepath: str):
        """保存拓扑结构"""
        topology_data = {
            'services': self.services,
            'service_types': self.service_types,
            'topology': self.topology
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(topology_data, f, indent=2, ensure_ascii=False)
        print(f"拓扑结构已保存到: {filepath}")


def main():
    print("=" * 60)
    print("Step 1: 生成微服务调用图模拟数据")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, 'data', 'raw')
    os.makedirs(data_dir, exist_ok=True)
    
    generator = MicroserviceGraphGenerator(num_services=20, seed=42)
    
    print("\n📊 生成服务拓扑...")
    generator.save_topology(os.path.join(data_dir, 'topology.json'))
    
    print("\n📊 生成时间序列数据...")
    time_series_data = generator.generate_time_series(
        duration_hours=24,
        interval_minutes=1,
        anomaly_rate=0.05
    )
    generator.save_data(time_series_data, os.path.join(data_dir, 'time_series.json'))
    
    print("\n📊 生成训练数据...")
    train_data, train_labels = generator.generate_training_data(num_samples=5000)
    generator.save_data(train_data, os.path.join(data_dir, 'train_data.json'))
    
    with open(os.path.join(data_dir, 'train_labels.json'), 'w', encoding='utf-8') as f:
        json.dump(train_labels, f, indent=2)
    
    print("\n📊 统计信息:")
    print(f"   - 服务数量: {len(generator.services)}")
    print(f"   - 时间序列数据点: {len(time_series_data)}")
    print(f"   - 训练样本数: {len(train_data)}")
    
    anomaly_count = sum(1 for d in time_series_data if d['is_anomaly'])
    print(f"   - 时间序列异常点: {anomaly_count} ({anomaly_count/len(time_series_data)*100:.1f}%)")
    
    normal_count = sum(1 for l in train_labels if l == 'normal')
    print(f"   - 训练正常样本: {normal_count}")
    print(f"   - 训练异常样本: {len(train_labels) - normal_count}")


if __name__ == "__main__":
    main()
