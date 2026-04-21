# Log_Analysis_LSTM Multi-Agent 集成说明

## 概述

本文档说明如何将 Log_Analysis_LSTM 模块集成到 Multi-Agent AIOps 系统中。

## 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Multi-Agent System                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Master Agent│───▶│Skill Manager│───▶│Tool Registry│     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                              │                   │          │
│                              ▼                   ▼          │
│                    ┌─────────────────────────────────┐     │
│                    │ deeplog_anomaly_detection_skill │     │
│                    └─────────────────────────────────┘     │
│                                          │                  │
└──────────────────────────────────────────│──────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Log_Analysis_LSTM 模块                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  skill.py   │───▶│ DeepLog模型 │───▶│ 异常检测结果│     │
│  │ (仅推理)    │    │  (已训练)   │    │             │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 集成文件说明

### 1. tool_registry.py

**文件路径**: `aiops-platform/backend/app/agents/tool_registry.py`

**新增工具**: `detect_log_anomalies`

```python
# 注册工具
self.register("detect_log_anomalies", self._detect_log_anomalies)

# 工具实现
async def _detect_log_anomalies(
    self,
    logs: List[str] = None,
    data_path: str = None,
    model_path: str = None,
    top_k: int = 3
) -> Dict[str, Any]:
    """
    使用 DeepLog 模型检测日志异常（仅推理，不训练）
    """
    # 加载 LogAnalysisSkill
    from Log_Analysis_LSTM.skill import LogAnalysisSkill
    
    skill = LogAnalysisSkill(model_path=model_path, top_k=top_k)
    
    if logs:
        result = await skill.detect_logs(logs)
    else:
        result = await skill.detect_from_file(data_path=data_path)
    
    return result
```

### 2. skill_manager.py

**文件路径**: `aiops-platform/backend/app/agents/skill_manager.py`

**更新关键词**:

```python
"deeplog_anomaly_detection_skill": {
    "path": "monitoring/deeplog_anomaly_detection_skill.md",
    "category": "monitoring",
    "description": "DeepLog 日志异常检测",
    "keywords": [
        "日志异常检测", "日志异常", "异常日志", "anomaly detection",
        "deeplog", "lstm", "日志序列", "日志模式",
        "日志预测", "日志分析", "log analysis",
        "detect_log_anomalies", "日志异常推理"
    ]
}
```

### 3. deeplog_anomaly_detection_skill.md

**文件路径**: `aiops-platform/backend/skills/monitoring/deeplog_anomaly_detection_skill.md`

**新增章节**: Multi-Agent 集成说明

## 使用方式

### 方式1: 通过 Multi-Agent 对话

```
用户: "帮我检测这些日志是否有异常"
      [日志内容...]

Agent:
1. 识别意图 -> 匹配 deeplog_anomaly_detection_skill
2. 调用工具 -> detect_log_anomalies(logs=[...])
3. 返回结果 -> 异常检测结果和建议
```

### 方式2: 直接调用工具

```python
from app.agents.tool_registry import ToolRegistry

registry = ToolRegistry()

result = await registry.execute(
    "detect_log_anomalies",
    logs=[
        "[2024-01-01 10:00:00.000] [INFO] [order-service] Receive Request",
        "[2024-01-01 10:00:00.100] [ERROR] [database-service] Connection Timeout",
    ],
    top_k=3
)

print(f"检测到 {result['anomalies_detected']} 个异常")
print(f"异常率: {result['anomaly_rate']:.2f}%")
```

### 方式3: 使用 Skill 类

```python
import asyncio
from skill import LogAnalysisSkill

async def main():
    skill = LogAnalysisSkill()
    result = await skill.detect_from_file()
    print(f"异常数: {result.anomalies_detected}")

asyncio.run(main())
```

## 工作流程

### 离线阶段（训练）

```bash
# 在 Log_Analysis_LSTM 目录下执行
cd /path/to/Log_Analysis_LSTM

# 1. 生成训练数据
python 1_generate_data.py

# 2. 解析日志
python 2_parse_logs.py

# 3. 训练模型
python 3_train_model.py
```

### 在线阶段（推理）

```
Multi-Agent 接收用户请求
        ↓
Skill Manager 匹配关键词
        ↓
加载 deeplog_anomaly_detection_skill.md
        ↓
调用 detect_log_anomalies 工具
        ↓
加载 LogAnalysisSkill (仅推理)
        ↓
返回异常检测结果
```

## API 参数说明

### detect_log_anomalies

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `logs` | List[str] | 否 | 原始日志列表（优先使用） |
| `data_path` | str | 否 | 结构化日志文件路径 |
| `model_path` | str | 否 | 模型文件路径（默认使用预训练模型） |
| `top_k` | int | 否 | 预测的 Top-k 事件数，默认 3 |

### 返回结果

```python
{
    "success": True,                    # 是否成功
    "total_logs": 600,                  # 总日志数
    "total_predictions": 590,           # 总预测次数
    "anomalies_detected": 45,           # 检测到的异常数
    "anomaly_rate": 7.63,               # 异常率 (%)
    "anomaly_event_stats": {            # 异常事件统计
        "E99": 25,
        "E88": 20
    },
    "anomalies_sample": [               # 异常样本（最多10条）
        {
            "timestamp": "2024-01-01 10:05:23.456",
            "expected_events": ["E1", "E5", "E2"],
            "actual_event": "E99",
            "actual_template": "Connection Timeout"
        }
    ]
}
```

## 注意事项

1. **仅推理模式**: Multi-Agent 集成只做推理，不进行模型训练
2. **模型依赖**: 需要预先训练好模型文件 `models/deeplog_model.pth`
3. **日志格式**: 支持标准格式 `[timestamp] [level] [service] message`
4. **检测灵敏度**: `top_k` 参数越小，检测越敏感

## 故障排查

### 问题1: 模型文件不存在

```
错误: Model file not found: models/deeplog_model.pth

解决方案:
cd /path/to/Log_Analysis_LSTM
python 1_generate_data.py
python 2_parse_logs.py
python 3_train_model.py
```

### 问题2: 模块导入失败

```
错误: No module named 'Log_Analysis_LSTM.skill'

解决方案:
确保 Log_Analysis_LSTM 目录存在于正确路径:
- /Users/jaci-j/AIops/time_sequence_detection/Log_Analysis_LSTM/
```

### 问题3: 异常检测率为 0

```
解决方案:
1. 增加 top_k 值（如从 1 改为 3）
2. 检查日志数据是否包含异常模式
3. 重新训练模型，增加训练数据量
```

## 版本信息

- 版本: 1.1.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
