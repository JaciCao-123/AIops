# AlertClusterSkill - 智能告警聚合技能

## 概述

基于 **Drain + TF-IDF + Word2Vec + DBSCAN** 的智能告警聚合系统，用于告警风暴的智能压缩与聚合。

## 核心能力

| 能力 | 描述 |
|------|------|
| **离线训练** | 从历史日志训练专用 Word2Vec 模型，学习运维领域语义 |
| **在线聚合** | 实时接收告警，智能聚类压缩 |
| **语义理解** | 基于词向量的语义相似度计算，识别语义相近的告警 |
| **多维融合** | 时间 + 语义 + 拓扑三维距离融合，精准聚类 |

## 技术架构

```
离线阶段:
  历史日志 → IT正则分词 → Word2Vec训练 → it_word2vec.model

在线阶段:
  实时告警 → Drain模板提取 → Word2Vec向量化 → 多维距离矩阵 → DBSCAN聚类 → 聚合结果
```

## 模块路径

```
time_sequence_detection/alert_aggregation_Drain_DBSCAN/
├── skill.py               # AlertClusterSkill 封装（异步接口）
├── core_engine.py         # 在线聚合引擎
├── w2v_trainer.py         # Word2Vec 训练模块
├── text_preprocessor.py   # IT日志正则分词函数
├── models.py              # Pydantic 数据类定义
└── config.py              # 超参配置
```

## 工具调用

### cluster_alerts

聚合告警列表，返回聚类结果。

```python
result = await cluster_alerts(
    alerts=[
        {"time": "2023-10-01 10:00:01", "node_id": "node-1", "raw_msg": "Connection timeout"},
        {"time": "2023-10-01 10:00:02", "node_id": "node-1", "raw_msg": "Connection failed"},
    ],
    eps=0.5,
    min_samples=2
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `alerts` | List[Dict] | 是 | 告警列表，每条包含 time, node_id, raw_msg |
| `eps` | float | 否 | DBSCAN 邻域半径，默认 0.5 |
| `min_samples` | int | 否 | DBSCAN 最小样本数，默认 2 |

**返回结果**:

```python
{
    "success": True,
    "total_input": 10,
    "noise_count": 0,
    "clusters": [
        {
            "cluster_id": 0,
            "alert_count": 5,
            "representative_alert": "Memory allocation failed",
            "affected_nodes": ["node-1", "node-2", "node-3"]
        }
    ],
    "compression_ratio": "2.0:1"
}
```

## 使用场景

### 场景1: 告警风暴压缩

```
用户: "最近5分钟有100条告警，帮我分析一下"

Agent 执行流程:
1. 调用 load_data_from_source 获取告警数据
2. 调用 cluster_alerts 进行聚合
3. 返回聚类结果和压缩率
```

### 场景2: 实时告警聚合

```
用户: "对这些告警进行聚合分析"

Agent 执行流程:
1. 接收用户提供的告警列表
2. 调用 cluster_alerts(alerts=...)
3. 分析聚类模式并生成报告
```

## 离线训练

在调用聚合功能前，需要先训练 Word2Vec 模型：

```bash
cd time_sequence_detection/alert_aggregation_Drain_DBSCAN
python main.py
```

## 参数调优

| 场景 | eps | min_samples | 说明 |
|------|-----|-------------|------|
| 高精度（少聚类） | 0.3 | 3 | 只有非常相似的告警才会聚合 |
| 平衡（推荐） | 0.5 | 2 | 适中的聚合粒度 |
| 高召回（多聚类） | 0.8 | 1 | 更宽松的聚合条件 |

## 注意事项

1. **训练数据质量**: Word2Vec 模型效果取决于训练语料的质量和数量
2. **模型一致性**: 离线训练和在线推理必须使用相同的分词函数
3. **参数调优**: 根据实际告警特点调整 DBSCAN 参数

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
