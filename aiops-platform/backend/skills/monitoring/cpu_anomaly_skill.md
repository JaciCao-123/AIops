# CPUAnomalySkill - CPU 异常检测技能

## 概述

基于 **Isolation Forest + Prophet** 的 CPU 异常检测系统，用于多服务器 CPU 使用率异常检测与预测。

## 核心能力

| 能力 | 描述 |
|------|------|
| **异常检测** | 使用 Isolation Forest 检测 CPU 异常点 |
| **趋势预测** | 使用 Prophet 预测 CPU 使用趋势 |
| **多机监控** | 支持多服务器并行检测与对比分析 |

## 技术架构

```
离线阶段:
  历史CPU数据 → 数据清洗 → IF/Prophet训练 → 模型保存

在线阶段:
  实时CPU数据 → Isolation Forest检测 → Prophet预测 → 异常告警
```

## 模块路径

```
time_sequence_detection/cpu_IsolationForest_Prophet/
├── step1_generate_data.py     # 生成模拟CPU数据
├── step2_clean_data.py        # 数据清洗
├── step3_train_model.py       # 训练模型
├── step4_visualize.py         # 可视化
├── step5_predict.py           # 预测脚本
├── run_all.py                 # 一键运行
└── reports/                   # 输出报告
```

## 工具调用

### detect_cpu_anomaly

检测 CPU 异常并返回预测结果。

```python
result = await detect_cpu_anomaly(
    server_id="server-1",
    data_path="/path/to/cpu_data.csv",
    forecast_periods=60
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `server_id` | str | 否 | 服务器ID，默认检测所有服务器 |
| `data_path` | str | 否 | CPU数据路径 |
| `forecast_periods` | int | 否 | 预测未来多少个时间点，默认 60 |

**返回结果**:

```python
{
    "success": True,
    "server_id": "server-1",
    "anomalies_detected": 5,
    "anomaly_timestamps": ["2024-01-01 10:05:00", "2024-01-01 10:10:00"],
    "forecast": {
        "trend": "increasing",
        "next_hour_avg": 65.5,
        "peak_predicted": 85.2
    },
    "current_status": {
        "cpu_usage": 45.2,
        "status": "normal"
    }
}
```

## 使用场景

### 场景1: 单服务器 CPU 异常检测

```
用户: "检查 server-1 的 CPU 是否有异常"

Agent 执行流程:
1. 加载 server-1 的 CPU 数据
2. 调用 detect_cpu_anomaly 检测异常
3. 返回异常点和趋势预测
```

### 场景2: 多服务器对比分析

```
用户: "对比所有服务器的 CPU 使用情况"

Agent 执行流程:
1. 加载所有服务器数据
2. 调用 detect_cpu_anomaly 检测每台服务器
3. 返回对比分析报告
```

## 离线训练

```bash
cd time_sequence_detection/cpu_IsolationForest_Prophet
python run_all.py
```

## 数据格式

### 输入数据格式 (CSV)

```csv
timestamp,server_id,cpu_usage,memory_usage
2024-01-01 00:00:00,server-1,45.2,60.5
2024-01-01 00:00:00,server-2,30.1,55.2
```

## 注意事项

1. **数据频率**: 建议使用 1 分钟或 5 分钟粒度的数据
2. **训练周期**: 至少需要 7 天的历史数据
3. **阈值调整**: 可根据业务特点调整异常阈值

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
