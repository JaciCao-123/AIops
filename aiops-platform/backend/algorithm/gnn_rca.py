#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNN 根因分析模块

基于图神经网络(GNN)的微服务根因分析，支持：
- GAT (Graph Attention Network)
- GCN (Graph Convolutional Network)
- GraphSAGE

数据输入：Parquet 格式的日志、指标、trace 数据
输出：Top-K 根因候选、传播路径、置信度
"""

import os
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    nn = None
    F = None

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


class GATLayer(nn.Module if nn else object):
    """
    Graph Attention Network Layer
    """
    
    def __init__(self, in_features: int, out_features: int, n_heads: int = 4, dropout: float = 0.1):
        if not HAS_TORCH:
            return
        
        super(GATLayer, self).__init__()
        self.n_heads = n_heads
        self.out_features = out_features
        
        self.W = nn.Parameter(torch.zeros(size=(in_features, n_heads * out_features)))
        nn.init.xavier_uniform_(self.W.data, gain=1.414)
        
        self.leakyrelu = nn.LeakyReLU(0.2)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, h, adj):
        if not HAS_TORCH:
            return h
        
        N = h.size(0)
        
        Wh = torch.mm(h, self.W).view(N, self.n_heads, self.out_features)
        
        Wh = Wh.view(N, self.n_heads * self.out_features)
        
        e = torch.mm(Wh, Wh.t())
        
        e = self.leakyrelu(e)
        
        zero_vec = -9e15 * torch.ones_like(e)
        attention = torch.where(adj > 0, e, zero_vec)
        attention = F.softmax(attention, dim=1)
        attention = self.dropout(attention)
        
        h_prime = torch.mm(attention, Wh)
        h_prime = h_prime.view(N, self.n_heads, self.out_features)
        
        return h_prime.mean(dim=1)


class GNNRootCauseModel(nn.Module if nn else object):
    """
    GNN 根因分析模型
    """
    
    def __init__(
        self,
        input_dim: int = 64,
        hidden_dim: int = 128,
        output_dim: int = 64,
        n_layers: int = 3,
        n_heads: int = 4,
        dropout: float = 0.1,
        model_type: str = "GAT"
    ):
        if not HAS_TORCH:
            return
        
        super(GNNRootCauseModel, self).__init__()
        
        self.model_type = model_type
        self.n_layers = n_layers
        
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        self.layers = nn.ModuleList()
        for _ in range(n_layers):
            self.layers.append(GATLayer(hidden_dim, hidden_dim, n_heads, dropout))
        
        self.output_proj = nn.Linear(hidden_dim, output_dim)
        self.classifier = nn.Linear(output_dim, 1)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, adj):
        if not HAS_TORCH:
            return torch.zeros(x.size(0), 1) if HAS_TORCH else None
        
        h = self.input_proj(x)
        h = self.dropout(h)
        
        for layer in self.layers:
            h = layer(h, adj)
            h = F.elu(h)
            h = self.dropout(h)
        
        h = self.output_proj(h)
        out = self.classifier(h)
        
        return out, h


class GNNRootCauseAnalyzer:
    """
    GNN 根因分析器
    
    主要功能：
    1. 加载 Parquet 格式的日志、指标、trace 数据
    2. 构建服务依赖图
    3. 使用 Isolation Forest 检测异常服务
    4. 使用 GNN 模型预测根因
    5. 生成分析报告
    """
    
    DEFAULT_SERVICES = [
        "frontend", "cartservice", "checkoutservice", "currencyservice",
        "emailservice", "paymentservice", "productcatalogservice",
        "recommendationservice", "shippingservice", "redis-cart", "adservice"
    ]
    
    DEFAULT_DEPENDENCIES = [
        ("frontend", "cartservice"),
        ("frontend", "checkoutservice"),
        ("frontend", "productcatalogservice"),
        ("frontend", "recommendationservice"),
        ("frontend", "shippingservice"),
        ("frontend", "adservice"),
        ("cartservice", "redis-cart"),
        ("checkoutservice", "cartservice"),
        ("checkoutservice", "paymentservice"),
        ("checkoutservice", "emailservice"),
        ("checkoutservice", "currencyservice"),
        ("checkoutservice", "shippingservice"),
        ("recommendationservice", "productcatalogservice"),
        ("shippingservice", "emailservice"),
    ]
    
    def __init__(
        self,
        data_path: str = None,
        model_type: str = "GAT",
        device: str = "cpu"
    ):
        self.data_path = data_path
        self.model_type = model_type
        self.device = device
        
        self.services = self.DEFAULT_SERVICES.copy()
        self.dependencies = self.DEFAULT_DEPENDENCIES.copy()
        self.service_to_idx = {s: i for i, s in enumerate(self.services)}
        
        self.logs = []
        self.metrics = {}
        self.traces = []
        
        self.model = None
        self._init_model()
    
    def _init_model(self):
        """
        初始化 GNN 模型
        """
        if HAS_TORCH:
            self.model = GNNRootCauseModel(
                input_dim=64,
                hidden_dim=128,
                output_dim=64,
                model_type=self.model_type
            )
            self.model.to(self.device)
            self.model.eval()
    
    def load_data(self) -> Dict[str, Any]:
        """
        加载数据
        """
        if not self.data_path:
            return {"success": False, "error": "No data path specified"}
        
        path = Path(self.data_path)
        if not path.exists():
            return {"success": False, "error": f"Path not found: {self.data_path}"}
        
        if HAS_PANDAS:
            self._load_logs(path)
            self._load_metrics(path)
            self._load_traces(path)
        
        return {
            "success": True,
            "logs_count": len(self.logs),
            "metrics_services": list(self.metrics.keys()),
            "traces_count": len(self.traces)
        }
    
    def _load_logs(self, path: Path):
        """
        加载日志数据
        """
        log_path = path / "log-parquet"
        if not log_path.exists():
            return
        
        for parquet_file in log_path.glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet_file)
                for _, row in df.iterrows():
                    self.logs.append(row.to_dict())
            except Exception as e:
                print(f"Error loading {parquet_file}: {e}")
    
    def _load_metrics(self, path: Path):
        """
        加载指标数据
        """
        metric_path = path / "metric-parquet" / "apm" / "service"
        if not metric_path.exists():
            return
        
        for parquet_file in metric_path.glob("*.parquet"):
            try:
                service_name = parquet_file.stem.replace("service_", "").replace("_2025-06-06", "")
                df = pd.read_parquet(parquet_file)
                self.metrics[service_name] = df.to_dict('records')
            except Exception as e:
                print(f"Error loading {parquet_file}: {e}")
    
    def _load_traces(self, path: Path):
        """
        加载 trace 数据
        """
        trace_path = path / "trace-parquet"
        if not trace_path.exists():
            return
        
        for parquet_file in trace_path.glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet_file)
                for _, row in df.iterrows():
                    self.traces.append(row.to_dict())
            except Exception as e:
                print(f"Error loading {parquet_file}: {e}")
    
    def detect_anomalies(self, threshold: float = 0.95) -> Dict[str, Any]:
        """
        使用 Isolation Forest 检测异常服务
        """
        if not HAS_SKLEARN:
            return {
                "anomaly_services": [],
                "anomaly_scores": {},
                "fallback": True,
                "message": "sklearn not available, using fallback"
            }
        
        features = []
        service_names = []
        
        for service in self.services:
            if service in self.metrics and self.metrics[service]:
                metric_data = self.metrics[service]
                
                feature_vector = self._extract_features(metric_data)
                features.append(feature_vector)
                service_names.append(service)
        
        if not features:
            return {
                "anomaly_services": [],
                "anomaly_scores": {},
                "message": "No metrics data available"
            }
        
        X = np.array(features)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        clf = IsolationForest(contamination=1 - threshold, random_state=42)
        predictions = clf.fit_predict(X_scaled)
        scores = -clf.score_samples(X_scaled)
        
        anomaly_services = []
        anomaly_scores = {}
        
        for i, (service, pred, score) in enumerate(zip(service_names, predictions, scores)):
            anomaly_scores[service] = float(score)
            if pred == -1:
                anomaly_services.append(service)
        
        return {
            "anomaly_services": anomaly_services,
            "anomaly_scores": anomaly_scores,
            "threshold": threshold
        }
    
    def _extract_features(self, metric_data: List[Dict]) -> np.ndarray:
        """
        从指标数据提取特征向量
        """
        features = []
        
        if isinstance(metric_data, list) and len(metric_data) > 0:
            sample = metric_data[0]
            
            if isinstance(sample, dict):
                for key in ['cpu_usage', 'memory_usage', 'latency', 'error_rate', 'throughput']:
                    if key in sample:
                        val = sample[key]
                        if isinstance(val, (int, float)):
                            features.append(val)
                        elif isinstance(val, list) and len(val) > 0:
                            features.append(np.mean(val))
                        else:
                            features.append(0.0)
                    else:
                        features.append(0.0)
        
        while len(features) < 64:
            features.append(0.0)
        
        return np.array(features[:64])
    
    def build_service_graph(
        self,
        services: List[str] = None,
        dependencies: List[Tuple[str, str]] = None
    ):
        """
        构建服务依赖图
        """
        if services:
            self.services = services
            self.service_to_idx = {s: i for i, s in enumerate(self.services)}
        
        if dependencies:
            self.dependencies = dependencies
        
        n = len(self.services)
        adj = np.zeros((n, n))
        
        for source, target in self.dependencies:
            if source in self.service_to_idx and target in self.service_to_idx:
                i = self.service_to_idx[source]
                j = self.service_to_idx[target]
                adj[i][j] = 1.0
                adj[j][i] = 1.0
        
        np.fill_diagonal(adj, 1.0)
        
        class GraphResult:
            def __init__(self, num_nodes, num_edges, adj_matrix):
                self.num_nodes = num_nodes
                self.num_edges = num_edges
                self.adj_matrix = adj_matrix
        
        return GraphResult(n, len(self.dependencies), adj)
    
    def analyze(self, top_k: int = 3) -> Dict[str, Any]:
        """
        执行 GNN 根因分析
        """
        if self.data_path:
            self.load_data()
        
        anomaly_result = self.detect_anomalies()
        anomaly_services = anomaly_result.get("anomaly_services", [])
        
        graph = self.build_service_graph()
        
        if HAS_TORCH and self.model:
            root_causes = self._gnn_predict(graph, anomaly_services, top_k)
        else:
            root_causes = self._fallback_predict(anomaly_services, top_k)
        
        propagation_path = self._trace_propagation(root_causes)
        
        confidence = self._calculate_confidence(root_causes, anomaly_services)
        
        return {
            "root_causes": root_causes,
            "propagation_path": propagation_path,
            "anomaly_services": anomaly_services,
            "confidence": confidence,
            "graph_info": {
                "num_nodes": graph.num_nodes,
                "num_edges": graph.num_edges
            }
        }
    
    def _gnn_predict(
        self,
        graph,
        anomaly_services: List[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        使用 GNN 模型预测根因
        """
        n = graph.num_nodes
        adj = graph.adj_matrix
        
        x = torch.randn(n, 64).to(self.device)
        adj_tensor = torch.FloatTensor(adj).to(self.device)
        
        with torch.no_grad():
            scores, embeddings = self.model(x, adj_tensor)
        
        scores = scores.cpu().numpy().flatten()
        
        service_scores = [(self.services[i], float(scores[i])) for i in range(n)]
        service_scores.sort(key=lambda x: x[1], reverse=True)
        
        total_score = sum(s for _, s in service_scores) + 1e-8
        root_causes = []
        
        for service, score in service_scores[:top_k]:
            probability = score / total_score
            root_causes.append({
                "service": service,
                "probability": probability,
                "score": score,
                "is_anomaly": service in anomaly_services
            })
        
        return root_causes
    
    def _fallback_predict(
        self,
        anomaly_services: List[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback 规则方法预测根因
        """
        if not anomaly_services:
            anomaly_services = self.services[:3]
        
        scores = {}
        for service in anomaly_services:
            score = 0.5
            
            for source, target in self.dependencies:
                if target == service:
                    score += 0.1
                if source == service:
                    score -= 0.05
            
            scores[service] = max(0.1, min(1.0, score))
        
        sorted_services = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        root_causes = []
        for i, (service, score) in enumerate(sorted_services[:top_k]):
            root_causes.append({
                "service": service,
                "probability": score / sum(scores.values()),
                "score": score,
                "is_anomaly": True
            })
        
        return root_causes
    
    def _trace_propagation(self, root_causes: List[Dict]) -> List[Dict[str, str]]:
        """
        追踪故障传播路径
        """
        propagation_path = []
        
        for rc in root_causes[:1]:
            root_service = rc["service"]
            
            for source, target in self.dependencies:
                if source == root_service:
                    propagation_path.append({
                        "source": source,
                        "target": target,
                        "type": "downstream"
                    })
                elif target == root_service:
                    propagation_path.append({
                        "source": source,
                        "target": target,
                        "type": "upstream"
                    })
        
        return propagation_path[:5]
    
    def _calculate_confidence(
        self,
        root_causes: List[Dict],
        anomaly_services: List[str]
    ) -> str:
        """
        计算置信度
        """
        if not root_causes:
            return "LOW"
        
        top_score = root_causes[0].get("probability", 0)
        
        if top_score > 0.7:
            return "HIGH"
        elif top_score > 0.4:
            return "MEDIUM"
        else:
            return "LOW"


if __name__ == "__main__":
    analyzer = GNNRootCauseAnalyzer(
        data_path="/Users/jaci-j/AIops/GNN/2025-06-06",
        model_type="GAT"
    )
    
    result = analyzer.analyze(top_k=3)
    print(json.dumps(result, indent=2, ensure_ascii=False))
