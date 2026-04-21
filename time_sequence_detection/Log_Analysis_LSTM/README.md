# Log_Analysis_LSTM - 基于 DeepLog 的日志异常检测技能

## 概述

本模块实现了基于 **DeepLog** 的日志序列异常检测功能，可集成到 Multi-Agent AIOps 系统中作为核心技能使用。

DeepLog 是一种基于 LSTM 的日志异常检测方法，通过学习正常日志序列的模式，预测下一个可能出现的日志事件，从而检测偏离正常模式的异常行为。

**📖 [Multi-Agent 集成说明](./INTEGRATION.md)**

## 核心原理

### DeepLog 模型架构

```
输入序列 (EventId) 
    ↓
Embedding Layer (将 EventId 转换为稠密向量)
    ↓
LSTM Layer (学习日志序列的时序模式)
    ↓
Linear Layer (映射到事件空间)
    ↓
Softmax (输出每个事件的概率分布)
```

### 异常检测机制

1. **滑动窗口**: 使用固定大小的窗口遍历日志序列
2. **预测**: 基于前 N 个事件预测下一个最可能出现的 Top-k 个事件
3. **判定**: 如果实际事件不在预测的 Top-k 列表中，则判定为异常

## 目录结构

```
Log_Analysis_LSTM/
├── skill.py              # 技能封装（Multi-Agent 接口，仅推理）
├── 1_generate_data.py    # 日志数据生成脚本（离线）
├── 2_parse_logs.py       # 日志解析脚本（离线）
├── 3_train_model.py      # 模型训练脚本（离线）
├── 4_predict.py          # 异常检测脚本（独立运行）
├── data/
│   ├── raw/              # 原始日志
│   │   └── logs_raw.log
│   └── cleaned/          # 结构化日志
│       └── logs_structured.csv
├── models/
│   ├── deeplog_model.pth       # 最终模型
│   └── deeplog_model_best.pth  # 最佳模型
├── reports/
│   └── anomaly_detection_results.csv
└── README.md
```

## 工作流程

### 离线阶段（训练）

```bash
# Step 1: 生成模拟日志数据
python 1_generate_data.py

# Step 2: 解析日志，提取事件模板
python 2_parse_logs.py

# Step 3: 训练 DeepLog 模型
python 3_train_model.py
```

### 在线阶段（推理）

```bash
# 方式1: 使用独立脚本
python 4_predict.py

# 方式2: 使用 skill.py 集成到 Multi-Agent
from skill import LogAnalysisSkill
skill = LogAnalysisSkill()
result = await skill.detect_from_file()
```

## 快速开始

### 1. 安装依赖

```bash
pip install torch pandas numpy
```

### 2. 离线训练

```bash
cd /path/to/Log_Analysis_LSTM

# 生成数据、解析、训练
python 1_generate_data.py
python 2_parse_logs.py
python 3_train_model.py
```

### 3. 在线检测

```python
import asyncio
from skill import LogAnalysisSkill

async def main():
    # 加载已训练的模型进行检测
    skill = LogAnalysisSkill()
    result = await skill.detect_from_file()
    
    print(f"检测到 {result.anomalies_detected} 个异常")
    print(f"异常率: {result.anomaly_rate:.2f}%")

asyncio.run(main())
```

## API 参考

### LogAnalysisSkill

日志分析技能类，仅提供推理功能（不包含训练）。

```python
from skill import LogAnalysisSkill, create_skill

# 创建实例（自动加载已有模型）
skill = LogAnalysisSkill()

# 或使用工厂函数
skill = await create_skill()
```

#### 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_path` | str | `models/deeplog_model.pth` | 模型文件路径 |
| `top_k` | int | 3 | 预测的 Top-k 事件数 |
| `auto_load` | bool | True | 是否自动加载模型 |

#### 方法

| 方法 | 说明 | 返回类型 |
|------|------|----------|
| `load_model()` | 手动加载模型 | `bool` |
| `detect_from_file(data_path, test_ratio)` | 从结构化日志文件检测 | `DetectionResult` |
| `detect_logs(logs)` | 实时检测原始日志 | `DetectionResult` |
| `execute(logs, data_path)` | 执行入口（兼容 Multi-Agent） | `DetectionResult` |

### 数据模型

#### DetectionResult

```python
@dataclass
class DetectionResult:
    total_logs: int              # 总日志数
    total_predictions: int       # 总预测次数
    anomalies_detected: int      # 检测到的异常数
    anomaly_rate: float          # 异常率 (%)
    anomalies: List[AnomalyResult]  # 异常列表
    anomaly_event_stats: Dict[str, int]  # 异常事件统计
```

#### AnomalyResult

```python
@dataclass
class AnomalyResult:
    timestamp: str              # 异常发生时间
    expected_events: List[str]  # 预测的 Top-k 事件
    expected_probs: List[float] # 预测概率
    actual_event: str           # 实际事件
    actual_template: str        # 实际事件模板
    window: List[str]           # 滑动窗口内容
```

## Multi-Agent 集成示例

### 作为技能使用

```python
import asyncio
from skill import LogAnalysisSkill

class MyAgent:
    def __init__(self):
        self.log_skill = LogAnalysisSkill()
    
    async def analyze_logs(self, logs: list):
        # 实时检测原始日志
        result = await self.log_skill.execute(logs=logs)
        
        if result.anomalies_detected > 0:
            print(f"发现 {result.anomalies_detected} 个异常!")
            for anomaly in result.anomalies[:5]:
                print(f"  - {anomaly.timestamp}: {anomaly.actual_template}")
        
        return result

async def main():
    agent = MyAgent()
    
    # 模拟实时日志流
    logs = [
        "[2024-01-01 10:00:00.000] [INFO] [order-service] Receive Request",
        "[2024-01-01 10:00:00.100] [INFO] [database-service] Query Database",
        "[2024-01-01 10:00:00.200] [ERROR] [auth-service] Validate User Failed",
    ]
    
    result = await agent.analyze_logs(logs)

asyncio.run(main())
```

### 与其他技能协作

```python
import asyncio
from skill import LogAnalysisSkill

async def multi_skill_pipeline():
    log_skill = LogAnalysisSkill()
    
    # 检测日志异常
    result = await log_skill.detect_from_file()
    
    if result.anomaly_rate > 5.0:
        print("异常率过高，触发告警聚合...")
        # 调用其他技能，如 AlertClusterSkill
    
    return result

asyncio.run(multi_skill_pipeline())
```

## 异常类型说明

### 正常流程 (Normal Flow)

```
[INFO] [order-service] Receive Request
[INFO] [database-service] Query Database
[INFO] [auth-service] Validate User
[INFO] [order-service] Create Order
[INFO] [order-service] Return Response
```

### 异常A - 连接超时 (Connection Timeout)

```
[INFO] [order-service] Receive Request
[INFO] [database-service] Query Database
[INFO] [auth-service] Validate User
[INFO] [order-service] Create Order
[INFO] [order-service] Return Response
[ERROR] [database-service] Connection Timeout  ← 异常事件
```

### 异常B - 认证失败 (Authentication Failure)

```
[INFO] [order-service] Receive Request
[INFO] [database-service] Query Database
[ERROR] [auth-service] Validate User Failed  ← 异常事件
[WARN] [order-service] System Rollback
```

## 输出示例

### 控制台输出

```
检测完成: 45 个异常, 异常率 3.02%

异常事件统计:
  E99: 25 次
  E88: 20 次
```

### 异常详情

```python
for anomaly in result.anomalies:
    print(f"时间: {anomaly.timestamp}")
    print(f"预测: {anomaly.expected_events}")
    print(f"实际: {anomaly.actual_event} - {anomaly.actual_template}")
```

## 注意事项

1. **训练与推理分离**: 训练是离线阶段，推理是在线阶段
2. **模型文件**: 首次使用前必须运行训练脚本生成模型
3. **日志格式**: 支持标准格式 `[timestamp] [level] [service] message`
4. **检测灵敏度**: `top_k` 参数越小，检测越敏感

## 依赖版本

```
torch>=1.9.0
pandas>=1.3.0
numpy>=1.20.0
```

## 参考资料

- [DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning](https://dl.acm.org/doi/10.1145/3133956.3134015)
- [LogHub: A Large Collection of System Log Datasets](https://github.com/logpai/loghub)
