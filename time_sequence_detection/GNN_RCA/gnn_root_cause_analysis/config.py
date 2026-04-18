#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNN 根因分析系统 - 全局配置

基于图神经网络的微服务故障根因定位系统
"""

import os
from datetime import datetime, timedelta
import torch

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 数据目录配置
DATA_DIRS = {
    "raw": os.path.join(BASE_DIR, "data", "raw"),
    "cleaned": os.path.join(BASE_DIR, "data", "cleaned"),
    "graphs": os.path.join(BASE_DIR, "data", "graphs"),
    "models": os.path.join(BASE_DIR, "data", "models"),
    "results": os.path.join(BASE_DIR, "data", "results")
}

# 确保数据目录存在
for dir_path in DATA_DIRS.values():
    os.makedirs(dir_path, exist_ok=True)

# 模拟数据生成配置
TOPOLOGY_CONFIG = {
    # 服务拓扑结构
    "num_services": 15,              # 微服务数量
    "num_hosts": 8,                  # 主机/节点数量
    
    # 拓扑类型: "microservices" / "layered" / "mesh" / "random"
    "topology_type": "microservices",
    
    # 层级结构（用于 microservices 类型）
    "layers": {
        "gateway": {"count": 1, "upstream": []},
        "api_services": {"count": 3, "upstream": ["gateway"]},
        "core_services": {"count": 5, "upstream": ["api_services"]},
        "data_services": {"count": 4, "upstream": ["core_services"]},
        "infra_services": {"count": 2, "upstream": ["core_services"]}
    },
    
    # 边的权重（调用频率）
    "edge_weights": {
        "high_freq": (100, 500),     # 高频调用（同层服务间）
        "medium_freq": (50, 200),    # 中频调用（跨层）
        "low_freq": (10, 50)         # 低频调用（基础设施）
    }
}

ALERT_CONFIG = {
    # 告警生成参数
    "num_scenarios": 20,             # 故障场景数
    "time_range_hours": 2,          # 时间范围
    "alerts_per_scenario": (5, 15), # 每个场景的告警数
    
    # 根因概率分布
    "root_cause_distribution": {
        "infra_services": 0.35,      # 35% 的根因在基础设施层
        "data_services": 0.30,       # 30% 在数据层
        "core_services": 0.20,       # 20% 在核心业务层
        "api_services": 0.10,        # 10% 在API层
        "gateway": 0.05             # 5% 在网关层
    },
    
    # 故障传播延迟（秒）
    "propagation_delay": {
        "same_layer": (5, 30),      # 同层传播
        "adjacent_layer": (10, 60), # 相邻层
        "cross_layer": (30, 120)    # 跨多层
    },
    
    # 告警类型
    "alert_types": [
        "CPU使用率过高",
        "内存不足",
        "磁盘空间不足",
        "网络延迟过高",
        "连接超时",
        "连接池耗尽",
        "响应时间过长",
        "错误率上升",
        "Pod重启",
        "节点NotReady"
    ],
    
    # 严重程度
    "severity_levels": ["critical", "major", "minor", "warning"]
}

# 数据清洗配置
CLEANING_CONFIG = {
    "time_granularity_seconds": 30,   # 时间对齐粒度
    "max_missing_ratio": 0.3,
    "outlier_iqr_factor": 2.0,
    "duplicate_time_window_seconds": 5,
    "min_alerts_per_service": 2       # 最少告警数（过滤噪声）
}

# 图构建配置
GRAPH_CONFIG = {
    # 图类型: "heterogeneous" / "homogeneous" / "temporal"
    "graph_type": "heterogeneous",
    
    # 节点特征维度
    "node_feature_dim": 64,
    
    # 边特征
    "edge_features": ["call_frequency", "latency_avg", "dependency_type"],
    
    # 时间窗口设置
    "temporal_window_size": 10,      # 时间步数
    "time_step_seconds": 60,         # 每步60秒
    
    # 图增强
    "use_self_loops": True,
    "add_reverse_edges": True,
    "normalize_edges": True
}

# GNN 模型配置
MODEL_CONFIG = {
    # 模型架构选择
    "model_type": "gat",            # "gcn" / "gat" / "sage" / "transformer"
    
    # GCN/GAT 参数
    "hidden_dim": 128,
    "num_layers": 3,
    "num_heads": 4,                  # GAT 注意力头数
    "dropout": 0.3,
    "activation": "relu",
    
    # 归一化
    "use_batch_norm": True,
    "use_layer_norm": False,
    "use_residual": True,
    
    # 输出层
    "output_dim": 1,                 # 二分类：是否为根因
    
    # 训练超参数
    "learning_rate": 0.001,
    "weight_decay": 5e-4,
    "batch_size": 32,
    "epochs": 100,
    "early_stopping_patience": 15,
    "gradient_clip_value": 5.0,
    
    # 类别权重（处理不平衡）
    "class_weights": {0: 1.0, 1: 3.0},  # 根因样本权重更高
    
    # 设备
    "device": "auto"                # "auto" / "cuda" / "cpu"
}

# 训练策略配置
TRAINING_CONFIG = {
    # 数据划分
    "train_ratio": 0.7,
    "val_ratio": 0.15,
    "test_ratio": 0.15,
    
    # 数据增强
    "use_augmentation": True,
    "augmentation_methods": ["node_dropout", "edge_dropout", "feature_noise"],
    "augmentation_prob": 0.3,
    
    # 交叉验证
    "use_cross_validation": False,
    "n_folds": 5,
    
    # 保存策略
    "save_best_only": True,
    "save_checkpoint_every": 10,
    "checkpoint_dir": os.path.join(BASE_DIR, "checkpoints"),
    
    # 日志
    "log_dir": os.path.join(BASE_DIR, "logs"),
    "log_level": "INFO",
    "tensorboard": True
}

# LLM 分析配置
LLM_CONFIG = {
    "provider": "openai",
    "model": "gpt-4-turbo-preview",
    "temperature": 0.7,
    "max_tokens": 2000,
    
    "prompt_template": """
你是一位资深的 AIOps 故障诊断专家，擅长分析微服务架构中的根因问题。

## 系统拓扑信息
{topology_info}

## GNN 分析结果
{gnn_analysis}

## 关键指标
- 可疑根因节点: {suspected_root_causes}
- 故障传播路径: {propagation_paths}
- 影响范围: {affected_scope}
- 时间线: {timeline}

请基于以上信息：
1. **确认根因**: GNN识别的根因是否合理？是否有遗漏？
2. **影响评估**: 这个根因导致了哪些连锁反应？
3. **处理建议**: 给出具体的排查步骤和修复方案
4. **预防措施**: 如何避免类似问题再次发生？

请以专业、简洁的方式输出。
""",
    
    "api_key_env": "OPENAI_API_KEY",
    "base_url": None
}

# 可视化配置
VISUALIZATION_CONFIG = {
    "figure_size": (16, 12),
    "dpi": 150,
    "node_size_range": (200, 800),
    "edge_width_range": (1, 5),
    "color_map": "RdYlGn_r",
    "layout": "spring",           # spring / circular / kamada_kawai
    "show_labels": True,
    "highlight_root_cause": True,
    "save_format": "png"
}


def get_device():
    """获取计算设备"""
    if MODEL_CONFIG["device"] == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        return torch.device(MODEL_CONFIG["device"])