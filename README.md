# AIops - 智能运维平台

智能运维（AIOps）平台，集成多智能体架构、知识图谱、时间序列预测和根因分析能力。

## 📁 项目结构

```
AIops/
├── aiops-platform/          # 智能诊断平台（主项目）
│   ├── backend/             # FastAPI 后端
│   ├── frontend/            # React 前端
│   ├── k8s/                 # Kubernetes 部署配置
│   └── docker/              # Docker 配置
├── knowledge_graph/         # 知识图谱构建与查询
└── time_sequence_detection/ # 时间序列检测与分析
    ├── alert_aggregation/        # 🆕 Drain+DBSCAN 运维日志告警聚合（推荐）
    ├── GNN_RCA/                   # GNN 根因分析系统
    ├── Log_Analysis/              # 日志分析与异常检测
    ├── Log_Analysis_IsolationForest_Prophet/  # IsolationForest+Prophet 日志分析
    ├── Log_Analysis_LSTM/         # LSTM 日志分析
    ├── cpu_anomaly_detection/     # CPU 异常检测
    ├── cost_analysis/             # 成本分析与预测
    ├── cost_analysis_Prophet/     # Prophet 成本分析
    ├── cpu_IsolationForest_Prophet/  # IsolationForest+Prophet CPU异常检测
    ├── microservice_rca/          # 微服务根因分析
    └── security_audit/            # 安全审计
```

## 🚀 核心功能

### 0. 🆕 alert_aggregation - Drain + DBSCAN 运维日志告警聚合系统（推荐）

基于 **Drain 日志解析 + DBSCAN 密度聚类** 的智能告警收敛方案，实现海量运维日志的自动聚合与根因分析。

#### 系统架构（5层完整流水线）

```
原始日志流(海量) → Drain解析(模板提取) → 特征构建(向量化) → DBSCAN聚类(相似告警聚合) → 告警收敛(报告生成)
```

| 层级 | 模块 | 核心功能 | 技术实现 |
|------|------|----------|----------|
| **Step 1** | 原始日志流生成器 | 模拟真实运维日志（应用/系统/中间件/数据库） | 多源日志模板库、异常注入 |
| **Step 2** | Drain 解析层 | 提取日志模板，剥离变量，生成模板ID | 固定深度前缀树算法 |
| **Step 3** | 特征构建层 | 将模板+上下文+语义信息转化为向量 | TF-IDF + PCA降维 |
| **Step 4** | DBSCAN 聚类层 | 相似告警自动聚合，发现告警模式 | 基于密度的空间聚类 |
| **Step 5** | 告警收敛层 | 生成聚合报告，优先级排序，处理建议 | 加权评分算法 |

#### 核心特性

✅ **高收敛率**: 64:1 (5000条日志 → 78个聚类)  
✅ **智能路由**: 根据问题类型和严重程度自动选择Agent  
✅ **多维特征**: 模板特征 + 上下文特征 + 语义特征 + 统计特征  
✅ **专业报告**: Markdown格式，含CRITICAL/HIGH/MEDIUM/LOW优先级排序  
✅ **可操作建议**: 自动生成根因分析和处理建议  

#### 快速开始

```bash
# 进入告警聚合目录
cd time_sequence_detection/alert_aggregation

# 快速测试模式（1000条日志）
python3 run_pipeline.py --quick

# 自定义参数运行
python3 run_pipeline.py --logs 10000 --eps 0.3 --min-samples 10
```

#### 命令行参数

```bash
--logs, -l          # 生成日志数量（默认: 5000）
--eps, -e           # DBSCAN的eps参数（邻域半径，默认: 0.5）
--min-samples, -m   # DBSCAN的最小样本数（默认: 5）
--quick, -q         # 快速测试模式（1000条日志）
```

#### 输出文件

```
data/
├── raw/raw_logs.csv                    # 原始日志数据
├── parsed/parsed_logs.csv              # Drain解析结果
├── parsed/log_templates.json           # 日志模板库
├── features/log_features.npz           # 特征矩阵（NumPy格式）
├── features/feature_metadata.json      # 特征元数据
├── clusters/clustered_logs.csv         # 聚类后的日志数据
├── clusters/cluster_labels.json        # 聚类标签
├── clusters/cluster_centers.json       # 聚类中心点
├── clusters/cluster_statistics.json    # 聚类统计信息
└── reports/alert_convergence_report.md # 📋 完整收敛报告（重点！）
```

#### 报告示例

生成的收敛报告包含：
- 📊 执行概要（总告警数、收敛率、压缩比）
- 🔴🟠🟡🟢 优先级告警列表（Top 10）
- 每个聚类的详细信息：
  - 严重程度得分 (0.0 - 1.0)
  - 影响范围得分 (0.0 - 1.0)
  - 收敛比率
  - 影响服务列表
  - 关键发现
  - 推荐操作建议
- 📈 技术细节（算法参数、质量指标）

#### 技术栈

| 技术 | 用途 |
|------|------|
| **Drain 算法** | 在线日志解析（固定深度前缀树） |
| **DBSCAN** | 基于密度的空间聚类 |
| **TF-IDF** | 文本特征向量化 |
| **PCA** | 降维（1016维 → 31维） |
| **scikit-learn** | 机器学习工具包 |
| **Pandas** | 数据处理 |
| **NumPy** | 数值计算 |

#### 性能指标

| 指标 | 数值 |
|------|------|
| 处理能力 | 5000条日志 / 6.41秒 |
| 收敛率 | 64:1 |
| 聚类质量 | 轮廓系数 0.5151 (良好) |
| 支持日志源 | 应用/系统/中间件/数据库 |

---

### 1. aiops-platform - 智能诊断平台

基于多智能体架构的智能运维诊断平台：

- **多智能体协作**：Master、Orchestrator、Intent Parser、Skill Manager 等智能体协同工作
- **技能系统**：支持 MySQL 死锁、Redis 异常、Kubernetes Pod、SLB 负载均衡等诊断技能
- **GNN 根因分析**：使用图神经网络进行微服务根因定位
- **Web 界面**：React + Vite 构建的现代化前端界面

**技术栈**：
- 后端：FastAPI + SQLite + Neo4j
- 前端：React + TypeScript + Vite
- AI：OpenAI API / 通义千问
- 部署：Docker + Kubernetes

### 2. knowledge_graph - 知识图谱

运维知识图谱构建与查询系统：

- **基础设施图谱**：服务器、网络、应用拓扑关系
- **Text2Cypher**：自然语言转 Cypher 查询
- **医疗知识图谱**：示例知识图谱构建

**技术栈**：
- Neo4j 图数据库
- Python + OpenAI API

### 3. time_sequence_detection - 时间序列检测与分析

运维场景下的时间序列分析、异常检测与根因定位：

- **🆕 alert_aggregation**（推荐）: Drain + DBSCAN 运维日志告警聚合系统
  - 5层完整流水线架构
  - 高收敛率 (64:1)
  - 智能优先级排序
  - 专业Markdown报告生成
  
- **GNN_RCA**: GNN 根因分析系统
  - 图神经网络微服务故障定位
  - GCN/GAT/GraphSAGE模型
  - LLM智能诊断报告

- **Log_Analysis**: 日志分析与异常检测
- **Log_Analysis_IsolationForest_Prophet**: IsolationForest + Prophet 日志分析
- **Log_Analysis_LSTM**: LSTM 日志时序预测
- **CPU 异常检测**: 多服务器 CPU 使用率异常检测
- **成本分析**: 云资源成本预测与异常检测
- **microservice_rca**: 微服务根因分析
- **security_audit**: SSH、认证、云 API 调用异常检测

**技术栈**：
- Prophet / IsolationForest 时间序列预测与异常检测
- PyTorch + PyTorch Geometric
- 图神经网络（GCN、GAT、GraphSAGE）
- **Drain 算法**: 在线日志解析
- **DBSCAN**: 密度聚类算法
- **TF-IDF + PCA**: 特征提取与降维

## 🛠️ 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+
- Neo4j 4.4+（可选）
- Docker & Kubernetes（可选）

### 安装依赖

```bash
# 后端依赖
cd aiops-platform/backend
pip install -r requirements.txt

# 前端依赖
cd aiops-platform/frontend
npm install
```

### 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入您的配置
# - OpenAI API Key
# - Neo4j 连接信息
# - 阿里云 Access Key（用于 SLB 诊断）
# - SMTP 配置（用于邮件通知）
```

### 启动服务

```bash
# 启动后端
cd aiops-platform/backend
python app/main.py

# 启动前端（新终端）
cd aiops-platform/frontend
npm run dev
```

访问 http://localhost:3000 使用 Web 界面。

## 📚 详细文档

- [aiops-platform/README.md](./aiops-platform/README.md) - 智能诊断平台详细文档
- [time_sequence_prediction/README.md](./time_sequence_prediction/README.md) - 时间序列预测详细文档

## 🔧 核心技术

### Multi-Agent 协同工作机制

#### 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Multi-Agent 协同架构                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │   用户请求   │                                                            │
│  └──────┬──────┘                                                            │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MultiAgentOrchestrator (编排器)                   │   │
│  │  ┌─────────────────────────────────────────────────────────────┐   │   │
│  │  │                    MasterAgent (大脑中枢)                    │   │   │
│  │  │  • 动态规划诊断流程                                          │   │   │
│  │  │  • ReAct 循环控制                                           │   │   │
│  │  │  • Function Calling 调用工具                                │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │         │              │              │              │              │   │
│  │         ▼              ▼              ▼              ▼              │   │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │   │
│  │  │ Intent   │   │ Knowledge│   │Observability│ │ Action   │        │   │
│  │  │ Parse    │   │ Expert   │   │ Analyst    │ │ Execute  │        │   │
│  │  │ Agent    │   │ Agent    │   │ Agent      │ │ Agent    │        │   │
│  │  │ (入口)   │   │ (知识)   │   │ (感知)     │ │ (执行)   │        │   │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ToolRegistry + SkillManager                       │   │
│  │  • 工具注册与执行                                                    │   │
│  │  • Skill 动态加载                                                    │   │
│  │  • 安全检查与审批                                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Agent 角色分工

| Agent | 角色 | 核心职责 | 输入 | 输出 |
|-------|------|----------|------|------|
| **IntentParseAgent** | 入口网关 | NER 实体识别、意图分类 | 用户自然语言 | `IntentResult` + `EntitiesResult` |
| **KnowledgeExpertAgent** | 知识专家 | 查询知识图谱、RAG 检索 | 服务名 + 症状 | `KnowledgeResult` (拓扑 + RAG 上下文) |
| **ObservabilityAnalystAgent** | 感知分析师 | 收集指标/日志/链路、分析异常 | 服务 + 实体 | `ObservabilityResult` (分析报告) |
| **MasterAgent** | 大脑中枢 | 动态规划、ReAct 循环、决策 | 所有上下文 | `DiagnosisDecision` |
| **ActionExecuteAgent** | 执行者 | 生成安全执行指令 | 修复方案 | `ActionResult` (含风险评估) |

#### ReAct 循环 (Reasoning + Acting)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ReAct 循环 (Reasoning + Acting)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │ Thought  │ ──▶│  Action  │ ──▶│Observation│ ──▶│ Decision │ │
│  │  (思考)  │    │  (行动)  │    │  (观察)   │    │  (决策)  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│       ▲                                                │       │
│       └────────────────────────────────────────────────┘       │
│                         (循环直到终止)                          │
│                                                                 │
│  终止条件:                                                      │
│  1. 调用 submit_diagnosis_result 提交结果                       │
│  2. 调用 ask_user_confirmation 需要用户确认                     │
│  3. 达到最大迭代次数 (40)                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 数据流向

```
用户输入
    │
    ▼
┌──────────────────┐
│ IntentParseAgent │
│ parse()          │───────▶ IntentResult
└──────────────────┘              │
                                  ▼
┌──────────────────┐       ┌──────────────────┐
│ KnowledgeExpert  │◀──────│ MasterAgent      │
│ query()          │───────▶ KnowledgeResult  │
└──────────────────┘       └──────────────────┘
                                  │
                                  ▼
┌──────────────────┐       ┌──────────────────┐
│ Observability    │◀──────│ ToolRegistry     │
│ analyze()        │───────▶ ObservabilityRes │
└──────────────────┘       └──────────────────┘
                                  │
                                  ▼
                           ┌──────────────────┐
                           │ ActionExecute    │
                           │ execute()        │───────▶ ActionResult
                           └──────────────────┘
```

#### 完整执行示例

**用户输入**: "order-service 连接池耗尽，帮我排查"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 1: IntentParseAgent                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  "order-service 连接池耗尽，帮我排查"                                 │
│ Output: IntentResult(                                                       │
│   intent = "DIAGNOSE",                                                      │
│   entities = {                                                              │
│     "services": [{"type": "SERVICE", "value": "order-service"}],            │
│     "symptoms": [{"type": "SYMPTOM", "value": "连接池耗尽"}]                 │
│   },                                                                        │
│   confidence = "HIGH"                                                       │
│ )                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 2: Skill 匹配                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ Matched Skills: ["debug_skill", "mysql_deadlock_skill"]                     │
│ Content Length: ~15,000 chars                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 3: ReAct 循环 (MasterAgent)                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ Iteration 1:                                                                │
│   Thought: 需要先了解 order-service 的拓扑依赖                              │
│   Action:   query_knowledge_graph(service="order-service")                  │
│   Result:   {upstream: ["payment-service"], downstream: ["user-service"]}   │
│                                                                             │
│ Iteration 2:                                                                │
│   Thought: 需要检查数据库连接状态                                            │
│   Action:   execute_command("SHOW STATUS LIKE 'Threads_connected'")         │
│   Result:   {Threads_connected: 148, max_connections: 150}                  │
│                                                                             │
│ Iteration 3:                                                                │
│   Thought: 连接数接近上限，需要检查慢查询                                    │
│   Action:   execute_command("SELECT * FROM mysql.slow_log ...")             │
│   Result:   {slow_queries: [...], longest_query: "SELECT * FROM orders..."} │
│                                                                             │
│ Iteration 4:                                                                │
│   Thought: 已定位根因，提交诊断结果                                          │
│   Action:   submit_diagnosis_result(                                        │
│               problem_type="connection_pool_exhaustion",                    │
│               root_cause="慢查询导致连接池阻塞",                              │
│               recommendation="优化慢查询 + 增加连接池大小"                   │
│             )                                                               │
│   Result:   {status: "completed"}                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Step 4: 返回结果                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ {                                                                           │
│   "final_decision": {                                                       │
│     "problem_type": "connection_pool_exhaustion",                           │
│     "root_cause": "慢查询导致连接池阻塞",                                    │
│     "recommendation": "优化慢查询 + 增加连接池大小",                         │
│     "risk_level": "MEDIUM",                                                 │
│     "confidence": "HIGH"                                                    │
│   },                                                                        │
│   "execution_history": [...],                                               │
│   "duration_seconds": 12.5                                                  │
│ }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 关键设计亮点

| 设计点 | 实现方式 | 优势 |
|--------|----------|------|
| **动态规划** | LLM 根据 Skill 内容实时决策 | 灵活应对各种场景，无需硬编码流程 |
| **ReAct 循环** | Thought → Action → Observation → Decision | 可解释性强，每步都有推理过程 |
| **Schema 契约** | Pydantic 强类型模型 | 类型安全，接口清晰 |
| **Skill 驱动** | 关键词匹配 + 渐进式披露 | 可扩展，易维护 |
| **安全防护栏** | 命令注入检测 + 审批流控 | 防止误操作，保障生产安全 |
| **工具注册制** | ToolRegistry 统一管理 | 解耦工具实现与调用 |

### 多智能体架构（简化版）

```
用户请求 → Master Agent
              ↓
         Intent Parser（意图识别）
              ↓
         Skill Manager（技能匹配）
              ↓
         Orchestrator（任务编排）
              ↓
         Action Executor（执行诊断）
              ↓
         知识库 / 工具 / LLM
```

### GNN 根因分析

使用图神经网络分析微服务调用图，定位故障根因：

- **GCN**：图卷积网络
- **GAT**：图注意力网络
- **GraphSAGE**：大规模图采样

### 时间序列预测

使用 Prophet 进行时间序列预测和异常检测：

- 自动检测趋势和季节性
- 异常点识别
- 置信区间预测

## 🎯 应用场景

1. **故障诊断**：自动诊断 MySQL 死锁、Redis 异常、Kubernetes Pod 故障
2. **根因分析**：微服务故障根因定位
3. **容量规划**：CPU、内存、存储容量预测
4. **成本优化**：云资源成本分析与预测
5. **安全审计**：异常登录、API 调用检测

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📧 联系方式

### Skill 关键词匹配优化

#### 关键词权重系统

为提高 Skill 匹配准确率，实现了带权重的关键词匹配系统：

```python
WEIGHTED_KEYWORDS = {
    "kafka_skill": {
        "core": {"kafka": 10, "kafka故障": 10, "消息队列故障": 9},      # 核心关键词
        "symptom": {"消息堆积": 10, "consumer lag": 10, "消费延迟": 8}, # 症状关键词
        "component": {"broker": 5, "partition": 5, "topic": 5},          # 组件关键词
        "alias": {"mq": 7}                                                # 别名/缩写
    },
    # ... 34 个 skills
}
```

**权重设计原则**：
| 类别 | 权重范围 | 说明 |
|------|----------|------|
| core | 8-10 | 核心标识词，如组件名、故障类型 |
| symptom | 5-10 | 症状描述词，如"堆积"、"死锁" |
| component | 3-5 | 相关组件词，如"broker"、"partition" |
| alias | 6-8 | 常用别名/缩写，如"mq"、"es" |

#### 同义词扩展系统

支持同义词自动扩展，提高匹配召回率：

```python
SYNONYM_MAP = {
    "故障": ["问题", "异常", "错误", "报错", "失败"],
    "慢": ["缓慢", "卡顿", "延迟", "耗时", "响应慢"],
    "不通": ["无法连接", "连不上", "连接失败", "网络不通"],
    # ... 更多同义词
}

SYNONYM_GROUPS = {
    "消息堆积": ["消息积压", "消费延迟", "consumer lag", "队列堆积"],
    "慢查询": ["sql慢", "查询慢", "慢sql", "sql执行慢"],
    "内存溢出": ["oom", "out of memory", "内存不足", "内存泄漏"],
    # ... 更多同义词组
}
```

#### 匹配流程

```
用户查询
    ↓
┌─────────────────────────────────────┐
│  1. 文本预处理                       │
│     - 转小写                         │
│     - 合并 symptoms/entities         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  2. 同义词扩展                       │
│     - SYNONYM_MAP 基础同义词         │
│     - SYNONYM_GROUPS 场景同义词      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  3. 加权关键词匹配                   │
│     - WEIGHTED_KEYWORDS 权重匹配     │
│     - SKILL_REGISTRY 关键词补充      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  4. 组件优先级加分                   │
│     - java/jvm → jvm_skill +15       │
│     - kafka → kafka_skill +10        │
│     - nginx → nginx_skill +10        │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  5. 排序返回 Top-5                   │
│     - 得分 >= 5 或 Top-3 返回        │
└─────────────────────────────────────┘
```

#### 匹配效果对比

| 查询 | 优化前 | 优化后 |
|------|--------|--------|
| kafka消息积压严重 | kafka_skill (43) | kafka_skill (53) ✓ |
| 数据库查询很慢 | mysql_slow_query_skill (8) | mysql_slow_query_skill (24) ✓ |
| mysql锁死了 | debug_skill (9) | mysql_deadlock_skill (9) ✓ |
| java内存溢出 | debug_skill (18) | jvm_skill (27) ✓ |
| java oom | debug_skill (43) | jvm_skill (43) ✓ |
| pod起不来 | k8s_pod_skill (18) | k8s_pod_skill (18) ✓ |

---

## 📅 更新日志

### 2026-04-18 - v2.0.0 重大更新

#### 🎉 新功能：Drain + DBSCAN 运维日志告警聚合系统

**位置**: `time_sequence_detection/alert_aggregation/`

**核心亮点**:
- ✨ **5层完整架构**: 日志生成 → Drain解析 → 特征构建 → DBSCAN聚类 → 告警收敛
- 🚀 **高收敛率**: 64:1 (5000条日志 → 78个聚类)
- 🎯 **智能优先级**: CRITICAL/HIGH/MEDIUM/LOW 自动分级
- 📊 **专业报告**: Markdown格式，含处理建议和根因分析
- ⚡ **高性能**: 5000条日志仅需6.41秒

**技术栈升级**:
- 新增 Drain 算法（固定深度前缀树）
- 新增 DBSCAN 密度聚类算法
- 新增 TF-IDF + PCA 特征工程流水线
- 加权评分算法（严重程度 + 影响范围）

**新增文件**:
```
alert_aggregation/
├── config.py                      # 全局配置
├── run_pipeline.py                # 主流水线脚本
├── step1_log_generator.py         # 原始日志流生成器
├── step2_drain_parser.py          # Drain解析层
├── step3_feature_builder.py       # 特征构建层
├── step4_dbscan_clustering.py     # DBSCAN聚类层
└── step5_alert_convergence.py     # 告警收敛层
```

**其他更新**:
- 📚 新增数据库备份演练技能文档 (`backup_drill_skill.md`)
- 🌐 新增 DR Drill 前端页面 (`dr-drill.html`)
- 🔧 优化 Skill 匹配优先级和前端确认流程
- 📦 重构项目结构为 `time_sequence_detection/`

---

如有问题或建议，请提交 Issue。
