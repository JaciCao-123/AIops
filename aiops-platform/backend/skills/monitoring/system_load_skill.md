# SystemLoadSkill - 系统负载异常检测技能

## 概述

基于 **双层漏斗架构** 的系统负载异常检测系统，结合 Isolation Forest 快速初筛和 LSTM Autoencoder 深度确诊。

## 核心能力

| 能力 | 描述 |
|------|------|
| **快速初筛** | Isolation Forest 三分类：正常 / 严重异常 / 疑似 |
| **深度确诊** | LSTM Autoencoder 重构误差 + 动态阈值 |
| **实时监控** | 支持实时数据流检测与邮件告警 |

## 技术架构

```
双层漏斗架构:

Layer 1: Isolation Forest 初筛
  数据点 → 14维增强特征 → IF打分
  ├─ score ≥ 0.05  → 正常放行
  ├─ score < -0.20 → 严重异常报警
  └─ 中间区间      → 推入 Layer 2

Layer 2: LSTM Autoencoder 确诊
  滑动窗口序列 → BiLSTM编码 → 解码重构
  ├─ error > threshold → 确诊异常报警
  └─ error ≤ threshold → 误报释放
```

## 模块路径

```
time_sequence_detection/system_load_prediction/
├── realtime_monitor.py          # 实时监控主脚本
├── dual_funnel_detector.py      # 离线批量检测版本
├── data/                        # 数据目录
├── models/                      # 模型目录
│   ├── rt_if_model.pkl          # Isolation Forest 模型
│   ├── rt_lstm_ae.pth           # LSTM Autoencoder 权重
│   └── rt_ae_scaler.pkl         # 归一化 Scaler
└── output/                      # 输出目录
```

## 工具调用

### detect_system_load_anomaly

检测系统负载异常。

```python
result = await detect_system_load_anomaly(
    metrics={"cpu": 85.5, "memory": 70.2, "disk_io": 45.3},
    window_size=30
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `metrics` | Dict | 是 | 指标数据，包含 cpu, memory, disk_io |
| `window_size` | int | 否 | 滑动窗口大小，默认 30 |

**返回结果**:

```python
{
    "success": True,
    "status": "CONFIRMED_ANOMALY",
    "if_score": -0.15,
    "ae_error": 0.45,
    "ae_threshold": 0.12,
    "metrics": {
        "cpu": {"value": 85.5, "status": "HIGH"},
        "memory": {"value": 70.2, "status": "NORMAL"},
        "disk_io": {"value": 45.3, "status": "NORMAL"}
    },
    "recommendation": "CPU usage is abnormally high, check running processes"
}
```

### 状态说明

| 状态 | 含义 | 处理方式 |
|------|------|----------|
| `NORMAL` | 正常 | 无操作 |
| `SEVERE` | IF 判定严重异常 | 立即报警 |
| `CONFIRMED_ANOMALY` | LSTM-AE 确诊异常 | 确诊报警 |
| `FALSE_POSITIVE` | IF 疑似但 AE 判定正常 | 误报释放 |

## 使用场景

### 场景1: 实时负载监控

```
用户: "监控服务器的实时负载情况"

Agent 执行流程:
1. 持续采集 CPU/Memory/DiskIO 指标
2. 调用 detect_system_load_anomaly 检测
3. 异常时触发告警
```

### 场景2: 历史数据分析

```
用户: "分析过去一小时的负载异常"

Agent 执行流程:
1. 加载历史指标数据
2. 使用双层漏斗批量检测
3. 返回异常时间点和类型
```

## 离线训练

```bash
cd time_sequence_detection/system_load_prediction
python realtime_monitor.py
```

启动后会自动：
1. 生成训练数据
2. 训练 Isolation Forest 模型
3. 训练 LSTM Autoencoder 模型
4. 进入实时监控模式

## 参数调优

### 让检测更敏感

```python
IF_SUSPICIOUS_THRESHOLD = 0.15   # 放宽疑似阈值
AE_THRESHOLD_K = 1.8             # 降低动态阈值
```

### 让检测更保守

```python
IF_SEVERE_THRESHOLD = -0.35      # 收紧严重阈值
AE_THRESHOLD_K = 3.5             # 提高动态阈值
```

## 邮件告警配置

在 `.env` 文件中配置：

```
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=xxx@163.com
SMTP_PASSWORD=授权码
ALERT_TO_EMAIL=xxx@163.com
```

## 注意事项

1. **窗口预热**: 前 20 个点用于收集基线，不进行判定
2. **冷却机制**: 默认 60 秒内不重复发送告警
3. **模型更新**: 定期重新训练以适应负载模式变化

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
