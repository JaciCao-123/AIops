#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图神经网络模型定义

基于 PyTorch Geometric 实现微服务根因定位模型
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, GCNConv, global_mean_pool, SAGEConv
from torch_geometric.data import Data, Batch
import numpy as np
from typing import Optional, Tuple, List, Dict


class GCNRootCauseModel(nn.Module):
    """
    基于 GCN 的根因定位模型
    """
    
    def __init__(self, num_features: int = 5, hidden_dim: int = 64, 
                 num_layers: int = 3, dropout: float = 0.3):
        super(GCNRootCauseModel, self).__init__()
        
        self.num_layers = num_layers
        self.dropout = dropout
        
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        
        self.convs.append(GCNConv(num_features, hidden_dim))
        self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        for _ in range(num_layers - 2):
            self.convs.append(GCNConv(hidden_dim, hidden_dim))
            self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        self.convs.append(GCNConv(hidden_dim, hidden_dim))
        self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        self.fc1 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc2 = nn.Linear(hidden_dim // 2, 1)
        
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                batch: Optional[torch.Tensor] = None) -> torch.Tensor:
        
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        
        x = F.relu(self.fc1(x))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.fc2(x)
        
        return x.squeeze(-1)


class GATRootCauseModel(nn.Module):
    """
    基于 GAT (Graph Attention Network) 的根因定位模型
    """
    
    def __init__(self, num_features: int = 5, hidden_dim: int = 64,
                 num_layers: int = 3, heads: int = 4, dropout: float = 0.3):
        super(GATRootCauseModel, self).__init__()
        
        self.num_layers = num_layers
        self.dropout = dropout
        self.heads = heads
        
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        
        self.convs.append(GATConv(num_features, hidden_dim // heads, 
                                   heads=heads, dropout=dropout))
        self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        for _ in range(num_layers - 2):
            self.convs.append(GATConv(hidden_dim, hidden_dim // heads,
                                       heads=heads, dropout=dropout))
            self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        self.convs.append(GATConv(hidden_dim, hidden_dim // heads,
                                   heads=heads, dropout=dropout))
        self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        self.fc1 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc2 = nn.Linear(hidden_dim // 2, 1)
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                batch: Optional[torch.Tensor] = None) -> torch.Tensor:
        
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            x = self.bns[i](x)
            x = F.elu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        
        x = F.elu(self.fc1(x))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.fc2(x)
        
        return x.squeeze(-1)


class SAGERootCauseModel(nn.Module):
    """
    基于 GraphSAGE 的根因定位模型
    """
    
    def __init__(self, num_features: int = 5, hidden_dim: int = 64,
                 num_layers: int = 3, dropout: float = 0.3):
        super(SAGERootCauseModel, self).__init__()
        
        self.num_layers = num_layers
        self.dropout = dropout
        
        self.convs = nn.ModuleList()
        self.bns = nn.ModuleList()
        
        self.convs.append(SAGEConv(num_features, hidden_dim))
        self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        for _ in range(num_layers - 2):
            self.convs.append(SAGEConv(hidden_dim, hidden_dim))
            self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        self.convs.append(SAGEConv(hidden_dim, hidden_dim))
        self.bns.append(nn.BatchNorm1d(hidden_dim))
        
        self.fc1 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc2 = nn.Linear(hidden_dim // 2, 1)
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                batch: Optional[torch.Tensor] = None) -> torch.Tensor:
        
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            x = self.bns[i](x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        
        x = F.relu(self.fc1(x))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = self.fc2(x)
        
        return x.squeeze(-1)


class AnomalyDetectionModel(nn.Module):
    """
    异常检测模型（判断整个系统是否存在异常）
    """
    
    def __init__(self, num_features: int = 5, hidden_dim: int = 64,
                 num_layers: int = 2, dropout: float = 0.3):
        super(AnomalyDetectionModel, self).__init__()
        
        self.convs = nn.ModuleList()
        
        self.convs.append(GCNConv(num_features, hidden_dim))
        for _ in range(num_layers - 1):
            self.convs.append(GCNConv(hidden_dim, hidden_dim))
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor,
                batch: torch.Tensor) -> torch.Tensor:
        
        for conv in self.convs:
            x = conv(x, edge_index)
            x = F.relu(x)
        
        x = global_mean_pool(x, batch)
        x = self.fc(x)
        
        return x.squeeze(-1)


class RootCausePredictor:
    """
    根因定位预测器
    """
    
    def __init__(self, model: nn.Module, device: str = 'cpu'):
        self.model = model.to(device)
        self.device = device
        self.model.eval()
    
    def predict(self, x: np.ndarray, edge_index: np.ndarray) -> Tuple[int, np.ndarray]:
        """
        预测根因服务
        
        Args:
            x: 节点特征 (num_nodes, num_features)
            edge_index: 边索引 (2, num_edges)
            
        Returns:
            (预测的根因节点索引, 所有节点的概率分布)
        """
        x_tensor = torch.FloatTensor(x).to(self.device)
        edge_index_tensor = torch.LongTensor(edge_index).to(self.device)
        
        with torch.no_grad():
            scores = self.model(x_tensor, edge_index_tensor)
            probs = torch.sigmoid(scores)
            probs_np = probs.cpu().numpy()
            
            predicted_idx = np.argmax(probs_np)
        
        return predicted_idx, probs_np
    
    def predict_top_k(self, x: np.ndarray, edge_index: np.ndarray, 
                      k: int = 3) -> List[Tuple[int, float]]:
        """
        预测 Top-K 根因服务
        
        Returns:
            [(节点索引, 概率), ...]
        """
        _, probs = self.predict(x, edge_index)
        
        top_k_indices = np.argsort(probs)[-k:][::-1]
        results = [(idx, probs[idx]) for idx in top_k_indices]
        
        return results


def create_model(model_type: str = 'gat', num_features: int = 5,
                 hidden_dim: int = 64, num_layers: int = 3,
                 dropout: float = 0.3, device: str = 'cpu') -> nn.Module:
    """
    创建模型
    
    Args:
        model_type: 模型类型 ('gcn', 'gat', 'sage')
        num_features: 输入特征维度
        hidden_dim: 隐藏层维度
        num_layers: 图卷积层数
        dropout: Dropout 比率
        device: 设备
        
    Returns:
        模型实例
    """
    if model_type == 'gcn':
        model = GCNRootCauseModel(
            num_features=num_features,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout
        )
    elif model_type == 'gat':
        model = GATRootCauseModel(
            num_features=num_features,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout
        )
    elif model_type == 'sage':
        model = SAGERootCauseModel(
            num_features=num_features,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return model.to(device)


def save_model(model: nn.Module, filepath: str, metadata: Optional[Dict] = None):
    """保存模型"""
    checkpoint = {
        'model_state_dict': model.state_dict(),
        'model_type': model.__class__.__name__,
        'metadata': metadata or {}
    }
    torch.save(checkpoint, filepath)
    print(f"模型已保存到: {filepath}")


def load_model(filepath: str, model_type: str = 'gat', num_features: int = 5,
               hidden_dim: int = 64, num_layers: int = 3, 
               dropout: float = 0.3, device: str = 'cpu') -> nn.Module:
    """加载模型"""
    model = create_model(
        model_type=model_type,
        num_features=num_features,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        dropout=dropout,
        device=device
    )
    
    checkpoint = torch.load(filepath, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    print(f"模型已加载: {filepath}")
    return model


if __name__ == "__main__":
    print("测试模型定义...")
    
    num_nodes = 20
    num_features = 5
    num_edges = 100
    
    x = torch.randn(num_nodes, num_features)
    edge_index = torch.randint(0, num_nodes, (2, num_edges))
    
    print("\n测试 GCN 模型:")
    gcn_model = GCNRootCauseModel(num_features=num_features)
    out = gcn_model(x, edge_index)
    print(f"  输出形状: {out.shape}")
    print(f"  参数量: {sum(p.numel() for p in gcn_model.parameters())}")
    
    print("\n测试 GAT 模型:")
    gat_model = GATRootCauseModel(num_features=num_features)
    out = gat_model(x, edge_index)
    print(f"  输出形状: {out.shape}")
    print(f"  参数量: {sum(p.numel() for p in gat_model.parameters())}")
    
    print("\n测试 GraphSAGE 模型:")
    sage_model = SAGERootCauseModel(num_features=num_features)
    out = sage_model(x, edge_index)
    print(f"  输出形状: {out.shape}")
    print(f"  参数量: {sum(p.numel() for p in sage_model.parameters())}")
