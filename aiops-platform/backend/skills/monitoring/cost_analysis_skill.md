# CostAnalysisSkill - 云成本异常分析技能

## 概述

基于 **Prophet** 的云成本异常检测与根因分析系统，用于识别成本激增并定位异常服务和项目。

## 核心能力

| 能力 | 描述 |
|------|------|
| **成本预测** | 使用 Prophet 模型预测正常成本波动范围 |
| **异常检测** | 识别超出置信区间的成本异常点 |
| **根因分析** | 自动下钻定位导致异常的具体服务和项目 |

## 技术架构

```
离线阶段:
  历史成本数据 → 数据清洗 → Prophet训练 → prophet_cost_model.pkl

在线阶段:
  实时成本数据 → Prophet预测 → 置信区间比较 → 异常检测 → 根因下钻
```

## 模块路径

```
time_sequence_detection/cost_analysis_Prophet/
├── step1_generate_cost_data.py     # 生成模拟成本数据
├── step2_clean_cost_data.py        # 清洗并聚合数据
├── step3_train_cost_model.py       # 训练成本预测模型
└── step4_predict_cost_anomaly.py   # 预测、告警与根因分析
```

## 工具调用

### detect_cost_anomaly

检测成本异常并返回根因分析结果。

```python
result = await detect_cost_anomaly(
    data_path="/path/to/cost_data.csv",
    confidence_interval=0.95
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `data_path` | str | 否 | 成本数据路径，默认使用模拟数据 |
| `confidence_interval` | float | 否 | 置信区间，默认 0.95 |

**返回结果**:

```python
{
    "success": True,
    "anomalies_detected": 3,
    "anomaly_dates": ["2024-01-15", "2024-01-20", "2024-01-25"],
    "root_causes": [
        {
            "date": "2024-01-15",
            "project": "project-A",
            "service": "EC2",
            "cost_increase": 150.5,
            "percentage": 45.2
        }
    ],
    "total_cost_anomaly": 450.75
}
```

## 使用场景

### 场景1: 成本异常检测

```
用户: "帮我检查最近一周的云成本是否有异常"

Agent 执行流程:
1. 调用 load_data_from_source 获取成本数据
2. 调用 detect_cost_anomaly 检测异常
3. 返回异常日期和根因分析
```

### 场景2: 成本趋势分析

```
用户: "分析本月成本趋势"

Agent 执行流程:
1. 加载成本数据
2. 使用 Prophet 预测趋势
3. 返回趋势分析和预警
```

## 离线训练

```bash
cd time_sequence_detection/cost_analysis_Prophet
python step1_generate_cost_data.py
python step2_clean_cost_data.py
python step3_train_cost_model.py
```

## 数据格式

### 输入数据格式 (CSV)

```csv
timestamp,project,service,cost
2024-01-01 00:00:00,project-A,EC2,100.5
2024-01-01 00:00:00,project-A,RDS,50.2
2024-01-01 00:00:00,project-B,S3,30.1
```

## 注意事项

1. **数据周期**: 建议使用至少 30 天的历史数据进行训练
2. **季节性**: Prophet 会自动学习周/月季节性模式
3. **异常注入**: 训练数据应排除已知的异常点

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
