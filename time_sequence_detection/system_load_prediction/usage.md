# AIOps 实时监控系统 — 使用文档

## 概述

本系统是一个基于**双层漏斗架构**的实时异常检测与邮件报警平台：

- **Layer 1**: Isolation Forest 快速初筛（三分类：正常 / 严重异常 / 疑似）
- **Layer 2**: LSTM Autoencoder 深度确诊（重构误差 + 动态阈值）
- **报警**: SMTP 邮件通知 + 防轰炸冷却机制

---

## 目录结构

```
system_load_prediction/
├── realtime_monitor.py          # 主脚本（完整可运行）
├── dual_funnel_detector.py      # 离线批量检测版本
├── data/                        # 数据目录
│   └── (运行时自动生成)
├── models/                      # 模型目录
│   ├── rt_if_model.pkl          # Isolation Forest 模型
│   ├── rt_lstm_ae.pth           # LSTM Autoencoder 权重
│   └── rt_ae_scaler.pkl         # 归一化 Scaler
└── output/                      # 输出目录
    └── dual_funnel_detection_results.png
```

---

## 环境要求

### Python 版本

- Python >= 3.8

### 依赖库

```
numpy>=1.21.0
pandas>=1.3.0
torch>=1.9.0          # PyTorch (CPU 或 GPU)
scikit-learn>=1.0.0
matplotlib>=3.4.0     # 仅离线版需要
```

### 安装

```bash
pip install numpy pandas torch scikit-learn matplotlib
```

---

## 配置

### 邮箱配置

邮箱参数从 `.env` 文件读取，路径为：
```
{项目根}/aiops-platform/backend/.env
```

所需配置项：

| 变量 | 说明 | 示例 |
|------|------|------|
| `SMTP_HOST` | SMTP 服务器地址 | `smtp.163.com` |
| `SMTP_PORT` | SMTP 端口 | `465` (SSL) |
| `SMTP_USER` | 发件人邮箱 | `xxx@163.com` |
| `SMTP_PASSWORD` | 授权码（非登录密码） | `XXXXXXXXXXXX` |
| `SMTP_FROM_EMAIL` | 发件人显示邮箱 | 同 SMTP_USER |
| `ALERT_TO_EMAIL` | 收件人邮箱 | 可与发件人相同 |

> **注意**：163/QQ 等邮箱需在设置中开启 POP3/SMTP 并获取授权码

### 脚本内全局变量（可按需修改）

位于 `realtime_monitor.py` 顶部：

```python
# 报警冷却时间（秒）— 冷却期内不重复发邮件
ALERT_COOLDOWN = 60

# 数据流间隔（秒）— 每隔多久生成一个数据点
STREAM_INTERVAL = 0.5

# LSTM-AE 滑动窗口大小 — 提取多少历史点供模型分析
WINDOW_SIZE = 30

# IF 阈值 — 调整 IF 的敏感度
IF_SEVERE_THRESHOLD = -0.20       # 低于此值 → 严重异常
IF_SUSPICIOUS_THRESHOLD = 0.05     # 低于此值 → 疑似
IF_CONTAMINATION = 0.08            # IF 的污染率参数

# AE 动态阈值参数
AE_THRESHOLD_K = 2.5              # 越小越敏感
AE_WARMUP = 20                     # 前N个点不判定（收集基线）
```

---

## 使用方法

### 基本启动

```bash
cd /Users/jaci-j/AIops/time_sequence_detection/system_load_prediction
python3 realtime_monitor.py
```

### 启动流程

脚本启动后会自动执行以下步骤：

```
Step 1: 🏋️ 训练模型
  ├── 生成 1440 分钟正常训练数据
  ├── 训练 Isolation Forest (14维特征)
  └── 训练 LSTM Autoencoder (~60 epochs, Early Stop)

Step 2: 🚀 进入主循环
  ├── 初始化滑动窗口、检测引擎、邮件报警器
  └── 开始实时数据流检测

Step 3: 🔄 持续运行
  ├── 每 0.5 秒生成一个数据点
  ├── 更新滑动窗口 → IF 打分 → (疑似则) AE 诊断
  ├── 异常时发送邮件（受冷却机制约束）
  └── 每 50 个点打印统计摘要
```

### 停止

按 **`Ctrl+C`** 优雅退出，会打印最终统计信息。

---

## 输出解读

### 控制台实时输出

每行代表一个数据点的检测结果：

```
🟢 [14:58:43] CPU= 27.3% MEM= 53.5% DISK=  6.1% │ NORMAL │ IF=+0.053
🟡 [14:58:44] CPU= 23.5% MEM= 53.7% DISK=  6.2% │ FALSE_POSITIVE │ IF=+0.039 │ AE_err=0.03221
🟣 [14:58:50] CPU= 24.5% MEM= 57.9% DISK= 81.1% │ CONFIRMED_ANOMALY │ IF=-0.150 │ AE_err=0.46478
🔴 [14:59:02] CPU= 98.2% MEM= 55.1% DISK=  8.3% │ SEVERE │ IF=-0.452
```

| 图标 | 标签 | 含义 | 处理方式 |
|------|------|------|----------|
| 🟢 | `NORMAL` | 正常 | 放行，无操作 |
| 🔴 | `SEVERE` | IF 判定严重异常 | **立即报警**（邮件） |
| 🟣 | `CONFIRMED_ANOMALY` | LSTM-AE 确诊异常 | **确诊报警**（邮件） |
| 🟡 | `FALSE_POSITIVE` | IF 疑似但 AE 判定正常 | 误报释放，仅日志 |

字段含义：
- `IF=±X.XXX`: Isolation Forest 异常分数（越小越异常）
- `AE_err=X.XXXXXX`: LSTM Autoencoder 重构误差

### 统计摘要（每 50 点打印）

```
────────────────────────────────────────────────────────────
  📊 检测统计: 总计=100
     🟢 正常:         27 ( 27.0%)
     🔴 IF严重:        0 (  0.0%)
     🟡 IF疑似:       73 ( 73.0%)
     🟣 AE确诊:        2 (  2.0%)
     🟡 AE误报释放:   59 ( 59.0%)
────────────────────────────────────────────────────────────
```

### 邮件内容示例

收到报警邮件后，内容包含：

- **异常发生时间**
- **判定来源**：IF 直接拦截 / LSTM-AE 确诊
- **指标数值表格**（CPU/MEM/DiskIO 当前值 + 正常范围 + 状态标记）
- **检测详情**：IF 分数、AE 重构误差和阈值

### Ground Truth 标注

控制台会额外显示模拟数据的真实标签（用于验证）：

```
🏷️  [Ground Truth] type=disk_storm source=explicit
🏷️  [Ground Truth] type=sawtooth source=implicit
```

---

## 架构详解

### 双层漏斗流程图

```
数据点 (CPU, MEM, DISK)
        │
        ▼
┌─────────────────────────┐
│   Layer 1: IF 初筛      │
│                         │
│  构建 14 维增强特征:     │
│  ├─ 原始 3 维           │
│  ├─ rolling_mean (×3)   │
│  ├─ rolling_std  (×3)   │
│  ├─ diff_from_mean(×3)  │
│  ├─ cpu_mem_product     │
│  └─ cpu_disk_ratio      │
│                         │
│  score ≥ 0.05  → 🟢放行  │
│  score < -0.20 → 🔴报警  │
│  中间区间      → 🟡推L2  │
└────────┬────────────────┘
         │ (仅疑似点)
         ▼
┌─────────────────────────┐
│ Layer 2: LSTM-AE 确诊   │
│                         │
│  从滑动窗口提取序列:      │
│  shape=(30, 3)           │
│                         │
│  Encoder:               │
│  BiLSTM(→96d) → FC(→24d)│
│  → latent vector        │
│                         │
│  Decoder:               │
│  repeat(30次) → LSTM →FC│
│  → reconstructed        │
│                         │
│  error > threshold → 🟣  │
│  error ≤ threshold → 🟡  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│    EmailAlerter         │
│                         │
│  冷却期内?              │
│  ├─ 是 → [Suppressed]   │
│  └─ 否 → 📧 发送邮件    │
└─────────────────────────┘
```

### LSTM Autoencoder 结构

```
Input: (batch, seq_len=30, features=3)

Encoder:
  BiLSTM(input=3, hidden=48, layers=2, bidirectional=True)
  → output shape: (batch, 30, 96)
  取最后时间步 → (batch, 96)
  Linear(96 → 24) + ReLU + Dropout
  → Latent vector: (batch, 24)

Decoder:
  repeat latent to (batch, 30, 24)
  LSTM(input=24, hidden=48, layers=2)
  → output shape: (batch, 30, 48)
  Linear(48 → 3)
  → Reconstructed: (batch, 30, 3)

Loss: MSE(input, reconstructed) per sample
判定: reconstruction_error vs EWMA dynamic threshold
```

### 邮件防轰炸机制

```
时间轴:
  T=0s   检测到异常 → 发送邮件 ✅  last_alert_time = 0
  T=10s  又检测到 → 冷却中 ❌  [Suppressed] (剩余50s)
  T=30s  又检测到 → 冷却中 ❌  [Suppressed] (剩余30s)
  T=61s  又检测到 → 冷却结束 → 发送邮件 ✅  last_alert_time = 61
  ...
```

---

## 参数调优指南

### 让检测更敏感（捕获更多异常）

```python
# 放宽 IF 疑似阈值 → 更多点进入 L2
IF_SUSPICIOUS_THRESHOLD = 0.15   # 默认 0.05

# 降低 AE 动态阈值 k 值 → 更容易触发确诊
AE_THRESHOLD_K = 1.8             # 默认 2.5
```

### 让检测更保守（减少误报）

```python
# 收紧 IF 严重阈值 → 只有极端值才直接报警
IF_SEVERE_THRESHOLD = -0.35      # 默认 -0.20

# 提高 AE 动态阈值 k 值 → 只有明显异常才触发
AE_THRESHOLD_K = 3.5             # 默认 2.5
```

### 调整数据流速度

```python
STREAM_INTERVAL = 1.0            # 每 1 秒一个点（默认 0.5s）
```

### 调整报警频率

```python
ALERT_COOLDOWN = 120             # 冷却期改为 120 秒（默认 60s）
```

---

## 故障排查

### 问题：邮件发送失败

**检查项**：
1. `.env` 文件是否存在且路径正确
2. `SMTP_PASSWORD` 是否为授权码（非登录密码）
3. 邮箱是否已开启 SMTP 服务
4. 端口是否正确（SSL 用 465，TLS 用 587）

**日志提示**：
```
❌ 邮件配置缺失 (SMTP_USER / SMTP_PASSWORD), 跳过发送
❌ 邮件发送失败: ...
```

### 问题：检测效果不理想

**现象**：大量误报或漏检

**建议**：
1. 先用离线版 `dual_funnel_detector.py` 批量测试，观察混淆矩阵
2. 根据结果调整阈值参数
3. 检查训练数据分布是否匹配实际场景

### 问题：LSTM-AE 不触发

**原因**：窗口未填满或动态阈值未就绪

**确认**：前 20 个疑似点会显示 `AE_warmup` 阶段，这是正常行为

---

## 相关文件

| 文件 | 用途 |
|------|------|
| `realtime_monitor.py` | 实时监控主脚本（本文档主题） |
| `dual_funnel_detector.py` | 离线批量检测 + 可视化评估版 |

---

## License

内部工具，仅供 AIOps 平台使用。
