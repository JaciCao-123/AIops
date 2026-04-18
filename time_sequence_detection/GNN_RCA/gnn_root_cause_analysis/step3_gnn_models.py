#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: GNN 模型定义

支持的模型架构:
1. GCN (Graph Convolutional Network) - 基础图卷积
2. GAT (Graph Attention Network) - 图注意力机制 ⭐推荐
3. GraphSAGE - 采样聚合
4. TemporalGNN - 时序图神经网络

使用方法:
    from step3_gnn_models import RootCauseGNN
    
    model = RootCauseGNN(model_type="gat", input_dim=64, hidden_dim=128)
"""

import os
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
import math

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import MODEL_CONFIG, get_device


class GCNLayer(nn.Module):
    """GCN层实现"""
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool = True,
        activation: str = "relu"
    ):
        super().__init__()
        
        self.linear = nn.Linear(in_features, out_features, bias=bias)
        self.activation = activation
        
        # 初始化权重
        nn.init.xavier_uniform_(self.linear.weight)
        if bias:
            nn.init.zeros_(self.linear.bias)
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        
        # 线性变换
        x = self.linear(x)
        
        # 消息传递 (GCN的归一化邻接矩阵)
        row, col = edge_index
        deg = degree(col, x.size(0), dtype=x.dtype)
        deg_inv_sqrt = deg.pow(-0.5)
        deg_inv_sqrt[deg_inv_sqrt == float('inf')] = 0
        
        norm = deg_inv_sqrt[row] * deg_inv_sqrt[col]
        
        # 聚合邻居信息
        out = torch.zeros_like(x)
        out.index_add_(0, col, x[row] * norm.view(-1, 1))
        
        # 激活函数
        if self.activation == "relu":
            out = F.relu(out)
        elif self.activation == "leaky_relu":
            out = F.leaky_relu(out, 0.2)
        elif self.activation == "gelu":
            out = F.gelu(out)
        
        return out


class GATLayer(nn.Module):
    """Graph Attention层实现"""
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        heads: int = 4,
        concat: bool = True,
        dropout: float = 0.3,
        negative_slope: float = 0.2,
        bias: bool = True
    ):
        super().__init__()
        
        self.in_features = in_features
        self.out_features = out_features
        self.heads = heads
        self.concat = concat
        
        # 为每个注意力头定义线性变换
        self.W = nn.Parameter(torch.empty(heads, in_features, out_features))
        self.att_src = nn.Parameter(torch.empty(heads, out_features, 1))
        self.att_dst = nn.Parameter(torch.empty(heads, out_features, 1))
        
        if bias and concat:
            self.bias = nn.Parameter(torch.empty(heads * out_features))
        elif bias:
            self.bias = nn.Parameter(torch.empty(out_features))
        else:
            self.register_parameter('bias', None)
        
        self.leaky_relu = nn.LeakyReLU(negative_slope)
        self.dropout = nn.Dropout(dropout)
        
        self._reset_parameters()
    
    def _reset_parameters(self):
        nn.init.xavier_uniform_(self.W)
        nn.init.xavier_uniform_(self.att_src)
        nn.init.xavier_uniform_(self.att_dst)
        if self.bias is not None:
            nn.init.zeros_(self.bias)
    
    def forward(
        self, 
        x: torch.Tensor, 
        edge_index: torch.Tensor,
        return_attention: bool = False
    ) -> torch.Tensor:
        
        N = x.size(0)
        
        # 线性变换 [heads, N, out_features]
        h = torch.einsum('ni,hio->hno', x, self.W)
        
        # 计算注意力分数 [heads, N]
        att_src_2d = self.att_src.squeeze(-1)  # [heads, out_features]
        att_dst_2d = self.att_dst.squeeze(-1)  # [heads, out_features]
        
        attn_src = torch.einsum('hno,ho->hn', h, att_src_2d)
        attn_dst = torch.einsum('hno,ho->hn', h, att_dst_2d)
        
        # 边的注意力系数
        row, col = edge_index
        
        # 正确的索引方式: [heads, E]
        attn_src_edges = attn_src[:, col]  # [heads, num_edges]
        attn_dst_edges = attn_dst[:, row]   # [heads, num_edges]
        
        edge_attn = attn_src_edges + attn_dst_edges  # [heads, num_edges]
        edge_attn = self.leaky_relu(edge_attn)
        
        # Softmax归一化 (按目标节点归一化)
        edge_attn = torch.softmax(edge_attn, dim=1)  # 沿边维度归一化
        edge_attn = self.dropout(edge_attn)
        
        # 消息聚合
        out = torch.zeros_like(h)
        
        for head in range(self.heads):
            h_head = h[head]  # [N, out_features]
            attn_head = edge_attn[head]  # [E]
            
            # 聚合邻居信息
            messages = h_head[row] * attn_head.unsqueeze(-1)  # [E, out_features]
            out_head = torch.zeros(N, self.out_features, device=x.device)
            out_head.index_add_(0, col, messages)
            out[head] = out_head
        
        if self.concat:
            out = out.reshape(N, self.heads * self.out_features)
        else:
            out = out.mean(dim=0)
        
        if self.bias is not None:
            out = out + self.bias
        
        if return_attention:
            return out, edge_attn
        return out


class SAGELayer(nn.Module):
    """GraphSAGE层实现"""
    
    def __init__(
        self,
        in_features: int,
        out_features: int,
        aggregator: str = "mean",
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.aggregator = aggregator
        
        self.self_linear = nn.Linear(in_features, out_features)
        self.neighbor_linear = nn.Linear(in_features, out_features)
        self.dropout = nn.Dropout(dropout)
        
        nn.init.xavier_uniform_(self.self_linear.weight)
        nn.init.xavier_uniform_(self.neighbor_linear.weight)
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        
        row, col = edge_index
        
        # 自身特征
        self_out = self.self_linear(x)
        
        # 邻居聚合
        neighbor_out = torch.zeros_like(self.neighbor_linear(x))
        neighbor_out.index_add_(0, col, self.neighbor_linear(x[row]))
        
        # 归一化
        deg = degree(col, x.size(0))
        deg.clamp_(min=1)
        neighbor_out = neighbor_out / deg.unsqueeze(-1)
        
        # 合并
        out = self.dropout(F.relu(self_out + neighbor_out))
        
        return out


def degree(index, num_nodes, dtype=None):
    """计算节点的度"""
    out = torch.zeros(num_nodes, dtype=dtype or index.dtype)
    ones = torch.ones(index.size(0), dtype=dtype or index.dtype)
    out.scatter_add_(0, index, ones)
    return out


def softmax(src, index, num_nodes):
    """沿目标节点维度做softmax"""
    out = torch.zeros(num_nodes, src.size(1) if src.dim() > 1 else src.size(0), 
                     dtype=src.dtype)
    out_max = torch.zeros(num_nodes, dtype=src.dtype)
    out_max.scatter_reduce_(0, index, src, reduce='amax', include_self=True)
    src = src - out_max[index]
    out.exp().scatter_add_(0, index, src.exp())
    out[out == 0] = 1
    out = src / out[index]
    return out


class TemporalAttentionLayer(nn.Module):
    """时序注意力层（处理动态图）"""
    
    def __init__(self, feature_dim: int, num_heads: int = 4, dropout: float = 0.3):
        super().__init__()
        
        self.num_heads = num_heads
        self.head_dim = feature_dim // num_heads
        
        self.query = nn.Linear(feature_dim, feature_dim)
        self.key = nn.Linear(feature_dim, feature_dim)
        self.value = nn.Linear(feature_dim, feature_dim)
        
        self.out_proj = nn.Linear(feature_dim, feature_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.head_dim)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [batch_size, seq_len, feature_dim]
        """
        B, T, D = x.shape
        
        q = self.query(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.key(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.value(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        
        # 注意力计算
        attn = torch.matmul(q, k.transpose(-2, -1)) / self.scale
        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)
        
        # 加权求和
        out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(B, T, D)
        out = self.out_proj(out)
        
        return out


class RootCauseGNN(nn.Module):
    """
    根因检测GNN模型 - 主模型类
    
    支持多种架构组合，自动选择最适合根因分析的配置
    """
    
    def __init__(
        self,
        model_type: str = "gat",
        input_dim: int = 64,
        hidden_dim: int = 128,
        num_layers: int = 3,
        num_heads: int = 4,
        dropout: float = 0.3,
        use_temporal: bool = False,
        temporal_window: int = 10,
        use_edge_attr: bool = True,
        output_dim: int = 1,
        **kwargs
    ):
        super().__init__()
        
        self.model_type = model_type.lower()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.use_temporal = use_temporal
        self.use_edge_attr = use_edge_attr
        
        # 输入投影层
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # 边特征编码器（如果使用）
        if use_edge_attr:
            self.edge_encoder = nn.Sequential(
                nn.Linear(7, hidden_dim),  # 7维边特征
                nn.ReLU()
            )
        else:
            self.edge_encoder = None
        
        # GNN层堆叠
        self.gnn_layers = nn.ModuleList()
        self.norms = nn.ModuleList()
        
        for i in range(num_layers):
            in_dim = hidden_dim if i == 0 else hidden_dim
            
            if self.model_type == "gcn":
                layer = GCNLayer(in_dim, hidden_dim, dropout=dropout)
            elif self.model_type == "gat":
                layer = GATLayer(
                    in_dim, 
                    hidden_dim // num_heads if i < num_layers - 1 else hidden_dim,
                    heads=num_heads,
                    dropout=dropout,
                    concat=(i < num_layers - 1)
                )
            elif self.model_type == "sage":
                layer = SAGELayer(in_dim, hidden_dim, dropout=dropout)
            else:
                raise ValueError(f"不支持的模型类型: {model_type}")
            
            self.gnn_layers.append(layer)
            self.norms.append(nn.LayerNorm(hidden_dim))
        
        # 时序模块（可选）
        if use_temporal:
            self.temporal_encoder = nn.GRU(
                input_size=8,  # 8维时序特征
                hidden_size=hidden_dim,
                num_layers=2,
                batch_first=True,
                bidirectional=True,
                dropout=dropout
            )
            
            self.temporal_attention = TemporalAttentionLayer(
                feature_dim=hidden_dim * 2,
                num_heads=num_heads,
                dropout=dropout
            )
            
            self.temporal_fusion = nn.Linear(hidden_dim * 2 + hidden_dim, hidden_dim)
        
        # 读出函数（图级别池化）
        self.readout = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # 分类头
        classifier_input_dim = hidden_dim
        if use_temporal:
            classifier_input_dim = hidden_dim
        
        self.classifier = nn.Sequential(
            nn.Linear(classifier_input_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, output_dim)
        )
        
        # 初始化权重
        self._init_weights()
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(
        self,
        node_features: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
        temporal_features: Optional[Dict[int, torch.Tensor]] = None,
        return_intermediate: bool = False
    ) -> torch.Tensor:
        """
        前向传播
        
        Args:
            node_features: [num_nodes, input_dim] 节点特征
            edge_index: [2, num_edges] 边索引
            edge_attr: [num_edges, edge_dim] 边特征（可选）
            temporal_features: {node_idx: [window, feat_dim]} 时序特征（可选）
            return_intermediate: 是否返回中间表示
            
        Returns:
            logits: [num_nodes, output_dim] 每个节点的根因概率
        """
        
        # 输入投影
        x = self.input_proj(node_features)
        
        # 边特征编码
        if self.edge_encoder is not None and edge_attr is not None:
            edge_emb = self.edge_encoder(edge_attr)
        else:
            edge_emb = None
        
        # GNN层前向传播
        intermediate_representations = []
        
        for i, (layer, norm) in enumerate(zip(self.gnn_layers, self.norms)):
            
            # 残差连接
            residual = x
            
            if isinstance(layer, GATLayer):
                x = layer(x, edge_index)
            else:
                x = layer(x, edge_index)
            
            x = norm(x)
            x = F.relu(x)
            x = x + residual  # 残差连接
            
            intermediate_representations.append(x)
        
        # 时序融合（如果启用）
        if self.use_temporal and temporal_features is not None:
            x = self._fuse_temporal(x, temporal_features)
        
        # 读出
        x_readout = self.readout(x)
        
        # 分类
        logits = self.classifier(x_readout)
        
        if return_intermediate:
            return logits, intermediate_representations
        
        return logits
    
    def _fuse_temporal(
        self, 
        spatial_features: torch.Tensor,
        temporal_features: Dict[int, torch.Tensor]
    ) -> torch.Tensor:
        """融合空间和时间特征"""
        
        num_nodes = spatial_features.size(0)
        
        # 编码所有节点的时序特征
        temporal_encoded_list = []
        
        for node_idx in range(num_nodes):
            if node_idx in temporal_features:
                t_feat = temporal_features[node_idx].unsqueeze(0)  # [1, window, 8]
                
                # GRU编码
                gru_out, _ = self.temporal_encoder(t_feat)  # [1, window, hidden*2]
                
                # 注意力加权
                attn_out = self.temporal_attention(gru_out)  # [1, window, hidden*2]
                
                # 取最后一个时间步
                final_feat = attn_out[:, -1, :]  # [1, hidden*2]
                temporal_encoded_list.append(final_feat)
            else:
                # 无时序特征的节点用零向量
                zero_feat = torch.zeros(1, self.hidden_dim * 2, device=spatial_features.device)
                temporal_encoded_list.append(zero_feat)
        
        temporal_encoded = torch.cat(temporal_encoded_list, dim=0)  # [num_nodes, hidden*2]
        
        # 融合空间和时序特征
        fused = torch.cat([spatial_features, temporal_encoded], dim=-1)
        fused = self.temporal_fusion(fused)
        fused = F.relu(fused)
        
        return fused


class ModelFactory:
    """模型工厂类"""
    
    @staticmethod
    def create_model(config: dict = None, **kwargs) -> RootCauseGNN:
        """根据配置创建模型"""
        
        config = config or MODEL_CONFIG
        
        # 合并配置和kwargs（kwargs优先）
        model_params = {
            "model_type": kwargs.get("model_type", config.get("model_type", "gat")),
            "input_dim": kwargs.get("input_dim", config.get("node_feature_dim", 64)),
            "hidden_dim": kwargs.get("hidden_dim", config.get("hidden_dim", 128)),
            "num_layers": kwargs.get("num_layers", config.get("num_layers", 3)),
            "num_heads": kwargs.get("num_heads", config.get("num_heads", 4)),
            "dropout": kwargs.get("dropout", config.get("dropout", 0.3)),
            "use_edge_attr": True,
        }
        
        # 添加其他可能的参数
        for key, value in kwargs.items():
            if key not in model_params:
                model_params[key] = value
        
        return RootCauseGNN(**model_params)
    
    @staticmethod
    def get_model_summary(model: RootCauseGNN) -> dict:
        """获取模型摘要"""
        
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        
        return {
            "model_type": model.model_type,
            "total_parameters": total_params,
            "trainable_parameters": trainable_params,
            "layers": len(model.gnn_layers),
            "hidden_dim": model.hidden_dim,
            "use_temporal": model.use_temporal,
            "size_mb": total_params * 4 / 1024 / 1024  # float32
        }


if __name__ == "__main__":
    print("="*70)
    print("🧠 Step 3/5: GNN模型定义测试")
    print("="*70)
    
    device = get_device()
    print(f"\n💻 使用设备: {device}")
    
    # 创建模型
    model = ModelFactory.create_model()
    model = model.to(device)
    
    # 打印模型信息
    summary = ModelFactory.get_model_summary(model)
    print(f"\n📊 模型信息:")
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    # 测试前向传播
    print("\n🧪 测试前向传播...")
    
    num_nodes = 15
    input_dim = 64
    
    # 创建模拟输入（使用更规范的边）
    node_features = torch.randn(num_nodes, input_dim).to(device)
    
    # 创建链式拓扑的边 (更符合真实场景)
    src_nodes = []
    dst_nodes = []
    for i in range(num_nodes - 1):
        src_nodes.append(i)
        dst_nodes.append(i + 1)
        if i > 0:  # 添加反向边
            src_nodes.append(i + 1)
            dst_nodes.append(i)
    
    edge_index = torch.tensor([src_nodes, dst_nodes], dtype=torch.long).to(device)
    edge_attr = torch.randn(len(src_nodes), 7).to(device)
    
    print(f"   边数: {edge_index.shape[1]}")
    
    # 前向传播
    with torch.no_grad():
        logits = model(node_features, edge_index, edge_attr)
    
    print(f"   输入形状: nodes={node_features.shape}, edges={edge_index.shape}")
    print(f"   输出形状: {logits.shape}")
    print(f"   输出范围: [{logits.min():.4f}, {logits.max():.4f}]")
    
    # 测试带时序特征的前向传播
    print("\n⏰ 测试时序模式...")
    model_temporal = ModelFactory.create_model(use_temporal=True).to(device)
    
    temporal_feats = {
        i: torch.randn(10, 8).to(device)  # 10个时间步，8维特征
        for i in range(num_nodes)
    }
    
    with torch.no_grad():
        logits_t = model_temporal(node_features, edge_index, edge_attr, temporal_feats)
    
    print(f"   时序输出形状: {logits_t.shape}")
    
    print(f"\n✅ 模型定义完成，可以开始训练!")