
# 成本异常分析模块 (`cost_analysis`)

## 模块功能

本模块提供了一个完整的、端到端的云成本异常检测与根因分析解决方案。它基于“离线训练 + 在线预测”的思路，模拟了从数据生成、清洗、模型训练到最终告警和分析的全过程。

## 核心特性

- **模拟真实数据**: 生成包含周期性、趋势和噪声的、多维度的模拟云成本数据。
- **异常注入**: 在指定日期为特定项目和服务注入成本激增的异常，用于验证检测效果。
- **模型训练**: 使用 Facebook Prophet 模型对总成本进行训练，学习正常的成本波动模式。
- **异常检测**: 实时预测成本，并通过与置信区间的比较来识别异常点。
- **根因分析**: 当检测到总成本异常时，能自动下钻到明细数据，定位到导致异常的具体服务和项目。

## 文件结构

```
.cost_analysis/
├── data/
│   ├── raw/              # 存放原始生成的数据 (cost_raw.csv)
│   └── cleaned/          # 存放清洗、聚合后的数据 (cost_total_hourly.csv)
├── models/
│   └── prophet_cost_model.pkl # 存放训练好的模型文件
├── step1_generate_cost_data.py     # 步骤1：生成模拟原始数据
├── step2_clean_cost_data.py        # 步骤2：清洗并聚合数据
├── step3_train_cost_model.py       # 步骤3：训练成本预测模型
└── step4_predict_cost_anomaly.py   # 步骤4：预测、告警与根因分析
```

## 如何运行

在 `time_sequence_prediction` 目录下，直接运行主脚本即可：

```bash
python run_cost_analysis.py
```

脚本将会按顺序自动执行所有步骤，并打印出每一步的结果，包括最终的异常检测和根因分析报告。

## 先决条件

请确保已安装必要的Python库，特别是 `prophet`。

```bash
pip install pandas numpy prophet
```
