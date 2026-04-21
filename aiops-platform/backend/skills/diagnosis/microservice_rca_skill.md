# MicroserviceRCASkill - 微服务根因分析技能

## 概述

基于 **GNN (图神经网络)** 的微服务根因定位系统，用于在微服务架构中快速定位故障根因。

## 核心能力

| 能力 | 描述 |
|------|------|
| **拓扑建模** | 构建微服务调用拓扑图 |
| **异常传播分析** | 分析故障在服务间的传播路径 |
| **根因定位** | 使用 GNN 定位最可能的根因服务 |

## 技术架构

```
离线阶段:
  拓扑数据 + 指标数据 → 图构建 → GNN训练 → 模型保存

在线阶段:
  异常服务列表 → 加载模型 → GNN推理 → 根因排序
```

## 模块路径

```
time_sequence_detection/microservice_rca/
├── step1_generate_data.py     # 生成模拟数据
├── step2_clean_data.py        # 数据清洗
├── step3_train_model.py       # 训练GNN模型
├── step4_predict.py           # 预测脚本
├── model.py                   # GNN模型定义
├── run_all.py                 # 一键运行
├── data/
│   ├── raw/                   # 原始数据
│   └── cleaned/               # 清洗后数据
└── models/                    # 模型文件
```

## 工具调用

### analyze_microservice_rca

分析微服务故障根因。

```python
result = await analyze_microservice_rca(
    anomaly_services=["order-service", "payment-service"],
    data_path="/path/to/microservice_data",
    top_k=3
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `anomaly_services` | List[str] | 是 | 异常服务列表 |
| `data_path` | str | 否 | 数据路径 |
| `top_k` | int | 否 | 返回的根因数量，默认 3 |

**返回结果**:

```python
{
    "success": True,
    "root_causes": [
        {
            "service": "database-service",
            "probability": 0.85,
            "propagation_path": ["database-service", "order-service", "payment-service"],
            "evidence": "High latency detected in database queries"
        }
    ],
    "affected_services": ["order-service", "payment-service", "user-service"],
    "confidence": "HIGH"
}
```

## 使用场景

### 场景1: 微服务故障定位

```
用户: "order-service 和 payment-service 都出现异常，帮我定位根因"

Agent 执行流程:
1. 调用 analyze_microservice_rca 分析根因
2. 返回最可能的根因服务和传播路径
3. 提供修复建议
```

### 场景2: 全链路故障分析

```
用户: "分析整个调用链的故障传播"

Agent 执行流程:
1. 加载服务拓扑数据
2. 使用 GNN 分析传播路径
3. 返回完整的故障传播图
```

## 离线训练

```bash
cd time_sequence_detection/microservice_rca
python run_all.py
```

## 数据格式

### 拓扑数据 (topology.json)

```json
{
    "services": ["order-service", "payment-service", "database-service"],
    "edges": [
        {"source": "order-service", "target": "database-service"},
        {"source": "order-service", "target": "payment-service"}
    ]
}
```

### 时间序列数据 (time_series.json)

```json
{
    "order-service": {
        "cpu": [45.2, 46.1, ...],
        "latency": [120, 125, ...]
    }
}
```

## 注意事项

1. **拓扑完整性**: 确保拓扑数据包含所有相关服务
2. **训练数据**: 需要包含正常和异常场景的数据
3. **模型更新**: 定期重新训练模型以适应架构变化

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
