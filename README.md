# AIops - 智能运维平台

智能运维（AIOps）平台，集成 **Multi-Agent 智能体架构**、**知识图谱**、**时间序列预测** 和 **根因分析** 能力。

## 🎯 项目亮点

- 🤖 **Multi-Agent 协同架构**: 5个专业Agent协同工作，动态规划诊断流程
- 🧠 **LLM 驱动决策**: ReAct 循环 + Function Calling 实现智能推理
- 🔒 **企业级安全防护**: 命令注入防护、审批工作流、RBAC权限控制
- 📊 **全栈算法支持**: GNN、Drain+DBSCAN、Prophet、IsolationForest 等
- 🔬 **🆕 可观测性平台**: Prometheus + Grafana + OTel + Tempo 全链路监控
- 🎯 **🆕 增强型根因分析**: GNN + IF + Prophet 多算法融合推理
- 🌐 **统一数据源管理**: Prometheus、Elasticsearch、Loki、云监控等

---

## 📁 项目架构总览

```
AIops/
├── aiops-platform/              # ⭐ 核心智能诊断平台（Multi-Agent 架构）
│   ├── backend/                 # FastAPI 后端服务
│   │   ├── app/agents/          # Multi-Agent 系统（核心）
│   │   ├── app/api/             # REST API 路由
│   │   ├── app/core/            # 配置 & 数据库
│   │   ├── app/utils/           # 工具类（数据源管理等）
│   │   └── app/observability/   # 🔬 可观测性平台（新增）
│   │       ├── config.py        # 统一配置管理
│   │       ├── prometheus_client.py  # Prometheus 指标采集
│   │       ├── opentelemetry_tracer.py  # OTel 分布式追踪
│   │       ├── tempo_query.py    # Tempo 链路查询
│   │       ├── root_cause_analyzer.py  # 基础RCA引擎
│   │       ├── grafana_dashboard.py  # Grafana仪表盘生成
│   │       └── enhanced_rca.py   # ⭐ 增强型RCA（联合算法）
│   ├── frontend/                # React + TypeScript 前端
│   ├── k8s/                     # Kubernetes 部署配置
│   └── docker/                  # Docker 配置
├── knowledge_graph/             # 🧠 运维知识图谱（Neo4j）
├── time_sequence_detection/     # ⏱️ 时间序列检测算法库
│   ├── alert_aggregation_Drain_DBSCAN/  # 🆕 Drain+DBSCAN 告警聚合（推荐）
│   ├── GNN_RCA/                        # GNN 图神经网络根因分析
│   ├── microservice_rca/               # 微服务根因分析
│   ├── security_audit/                 # 安全审计系统
│   ├── cpu_IsolationForest_Prophet/    # CPU 异常检测
│   ├── cost_analysis_Prophet/          # 成本分析与预测
│   └── ...                             # 其他算法模块
```

---

## 🚀 一、核心平台：aiops-platform（Multi-Agent 智能诊断系统）

> ⭐ **这是整个项目的核心**，采用业界领先的 Multi-Agent + LLM 动态决策架构

### 📖 平台概述

基于 **多智能体协作架构** 的智能运维诊断平台，支持：

- ✅ **自然语言交互**: "order-service 连接池耗尽，帮我排查"
- ✅ **自动意图识别**: NER 实体提取 + 意图分类
- ✅ **动态诊断规划**: LLM 根据 Skill 文件动态生成诊断计划
- ✅ **安全命令执行**: 多层安全检查 + 人工审批机制
- ✅ **知识图谱增强**: Neo4j 拓扑查询 + RAG 检索

### 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Agent 协同架构                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户请求                                                        │
│      │                                                          │
│      ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            MultiAgentOrchestrator (编排器)               │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │         MasterAgent (大脑中枢)                   │    │   │
│  │  │  • ReAct 循环控制                               │    │   │
│  │  │  • Function Calling 动态工具调用                 │    │   │
│  │  │  • 终止条件判断                                 │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │         │           │           │           │            │   │
│  │         ▼           ▼           ▼           ▼            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │
│  │  │ Intent   │ │Knowledge │ │Observabil│ │ Action   │    │   │
│  │  │ Parse    │ │ Expert   │ │ ity      │ │ Execute  │    │   │
│  │  │ Agent    │ │ Agent    │ │ Analyst  │ │ Agent    │    │   │
│  │  │ (入口)   │ │ (知识)   │ │ (感知)   │ │ (执行)   │    │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│      │                                                           │
│      ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         ToolRegistry + SkillManager                      │   │
│  │  • 20+ 工具注册 (SSH、Prometheus、Neo4j...)              │   │
│  │  • 30+ Skill 文件 (MySQL、Redis、K8s...)                 │   │
│  │  • 安全检查 & 审批工作流                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 👥 Agent 角色分工

| Agent | 角色 | 核心职责 | 输入 | 输出 |
|-------|------|----------|------|------|
| **IntentParseAgent** | 入口网关 | NER实体识别、意图分类、关键词提取 | 用户自然语言 | `IntentResult` + `EntitiesResult` |
| **KnowledgeExpertAgent** | 知识专家 | Neo4j拓扑查询、RAG检索、历史案例匹配 | 服务名+症状 | `KnowledgeResult` |
| **ObservabilityAnalystAgent** | 感知分析师 | 收集指标/日志/链路、异常检测 | 服务+实体 | `ObservabilityReport` |
| **MasterAgent** | 大脑中枢 | 动态规划、ReAct循环、最终决策 | 所有上下文 | `DiagnosisDecision` |
| **ActionExecuteAgent** | 执行者 | 生成安全的执行指令、风险评估 | 修复方案 | `ActionResult` |

### 🔐 安全体系（7层防护）

#### 多层安全防护架构

```
Layer 1: 命令注入防护 (12种正则模式) → Layer 2: 危险命令黑名单 (18种) → Layer 3: 安全命令白名单 (30+种)
         ↓                              ↓                               ↓
Layer 4: 风险等级分级 (LOW/MEDIUM/HIGH/BLOCKED) → Layer 5: 红线操作拦截 (5类)
         ↓                                                        ↓
Layer 6: 审批工作流 (邮件+API双通道) ← Layer 7: RBAC权限控制 (admin/user)
```

| 层级 | 防护能力 | 核心规则 | 触发动作 |
|------|---------|---------|----------|
| **L1** | 注入攻击检测 | `\$\(`, `/dev/tcp`, `bash -i`, `\|sh` 等12种 | ❌ 直接拒绝 |
| **L2** | 危险命令拦截 | `rm -rf`, `dd if=`, `mkfs`, `shutdown`, `drop database` 等18种 | ❌ 直接拒绝 |
| **L3** | 安全命令放行 | `ls/cat/grep/ps/docker ps/kubectl get` 等30+只读操作 | ✅ 直接执行 |
| **L4** | 风险分级评估 | LOW(只读), MEDIUM(需确认), HIGH(需审批), BLOCKED(禁止) | 分级处理 |
| **L5** | 红线操作拦截 | `delete/release/drop/truncate/restart_core_service` 等9种 | 🛑 强制审批 |
| **L6** | 人工审批流程 | 邮件APPROVE/REJECT + API接口双通道 | 待批准后执行 |
| **L7** | RBAC权限控制 | admin(全部权限) / user(只读+低风险) | 权限不足拒绝 |

**关键文件**: [tool_registry.py](aiops-platform/backend/app/agents/tool_registry.py) · [config.py](aiops-platform/backend/app/core/config.py) · [action_execute.py](aiops-platform/backend/app/agents/action_execute.py) · [approval.py](aiops-platform/backend/app/api/approval.py) · [auth.py](aiops-platform/backend/app/api/auth.py)

### 🛠️ 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **后端框架** | FastAPI 0.104 + Uvicorn | 高性能异步 Web 服务 |
| **前端框架** | React 18 + TypeScript + Vite | 现代化 SPA 应用 |
| **AI 引擎** | OpenAI API / 通义千问 | LLM 推理 & Function Calling |
| **图数据库** | Neo4j 5.x | 知识图谱存储与查询 |
| **关系数据库** | SQLite / PostgreSQL | 业务数据持久化 |
| **认证授权** | JWT + bcrypt + RBAC | 安全认证与权限控制 |
| **部署方案** | Docker + Kubernetes | 容器化编排部署 |

### 📦 核心功能模块

#### 1️⃣ Multi-Agent 诊断系统

**文件位置**: [backend/app/agents/](file:///Users/jaci-j/AIops/aiops-platform/backend/app/agents/)

```bash
# 核心文件
├── orchestrator.py       # 编排器（协调所有Agent）
├── master.py             # 大脑中枢（ReAct循环控制）
├── intent_parse.py       # 意图识别（NER实体提取）
├── knowledge.py          # 知识查询（Neo4j + RAG）
├── observability.py      # 可观测性分析
├── action_execute.py     # 动作执行（安全沙箱）
├── tool_registry.py      # 工具注册中心（20+工具）
├── skill_manager.py      # Skill管理器（30+技能文件）
└── schemas.py            # 数据模型定义
```

**支持的诊断场景**:
- ✅ MySQL 死锁/慢查询/主从切换
- ✅ Redis 连接池/内存/持久化问题
- ✅ Kubernetes Pod 故障/OOM/重启
- ✅ SLB 负载均衡异常
- ✅ Nginx 配置错误/高延迟
- ✅ Elasticsearch 集群状态
- ✅ Kafka 消息积压
- ✅ SSH 连接故障排查
- ✅ 通用服务器故障诊断

#### 2️⃣ 统一数据源管理

**文件位置**: [backend/app/utils/data_source_manager.py](file:///Users/jaci-j/AIops/aiops-platform/backend/app/utils/data_source_manager.py)

```python
class DataSourceManager:
    """支持6种数据源的统一接口"""
    
    DATA_SOURCES = {
        "local": {"type": "filesystem"},           # 本地文件
        "prometheus": {"type": "monitoring"},       # Prometheus 监控
        "elasticsearch": {"type": "logging"},       # ES 日志
        "loki": {"type": "logging"},                # Grafana Loki
        "aliyun_monitor": {"type": "cloud_monitoring"},  # 云监控
        "jaeger": {"type": "tracing"}               # 链路追踪
    }
```

#### 3️⃣ 认证与权限系统

**文件位置**: [backend/app/api/auth.py](file:///Users/jaci-j/AIops/aiops-platform/backend/app/api/auth.py)

特性：
- JWT Token 认证（24小时有效期）
- bcrypt 密码哈希
- RBAC 权限模型（角色+权限+范围）
- 管理员/普通用户角色分离

#### 4️⃣ Web 前端界面

**文件位置**: [frontend/src/](file:///Users/jaci-j/AIops/aiops-platform/frontend/src/)

页面列表：
- 📊 **仪表盘**: 系统概览、关键指标
- 🐛 **故障诊断**: 自然语言输入、实时诊断进度
- 📋 **日志列表**: 日志查看、异常标注
- 🧠 **知识库**: 知识图谱可视化、RAG问答
- 💬 **智能问答**: 运维知识咨询
- 💻 **Web终端**: 在线SSH终端（管理员专属）

### 🚀 快速开始

```bash
# 1. 克隆项目
git clone <repository-url>
cd AIops

# 2. 安装后端依赖
cd aiops-platform/backend
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入：
#   - OPENAI_API_KEY=your-key
#   - NEO4J_PASSWORD=your-password
#   - SECRET_KEY=your-secret-key

# 4. 启动后端服务
python app/main.py
# 访问 http://localhost:8000/docs 查看 API 文档

# 5. 启动前端（新终端）
cd ../frontend
npm install
npm run dev
# 访问 http://localhost:3000 使用 Web 界面
```

---

## ⏱️ 二、算法引擎：time_sequence_detection（时间序列检测与分析）

> 包含多种运维场景下的时序数据分析、异常检测和根因定位算法

### 📂 模块清单（按推荐程度排序）

| 序号 | 模块名称 | 算法技术 | 适用场景 | 推荐度 |
|------|---------|---------|---------|--------|
| **1** | **alert_aggregation_Drain_DBSCAN** | Drain + DBSCAN | 运维日志告警聚合 | ⭐⭐⭐⭐⭐ 强烈推荐 |
| **2** | **GNN_RCA** | 图神经网络 (GCN/GAT/GraphSAGE) | 微服务根因分析 | ⭐⭐⭐⭐⭐ 推荐 |
| **3** | **microservice_rca** | GCN + GAT | 微服务故障定位 | ⭐⭐⭐⭐ 推荐 |
| **4** | **security_audit** | 规则引擎 + 统计模型 | 安全事件检测 | ⭐⭐⭐⭐ 推荐 |
| **5** | **cpu_IsolationForest_Prophet** | IsolationForest + Prophet | CPU使用率异常检测 | ⭐⭐⭐ 良好 |
| **6** | **cost_analysis_Prophet** | Prophet 时序预测 | 云成本异常检测 | ⭐⭐⭐ 良好 |

---

### 🆕 1. alert_aggregation_Drain_DBSCAN - Drain+DBSCAN 告警聚合系统（强烈推荐）

> 基于 **Drain 日志解析 + DBSCAN 密度聚类** 的智能告警收敛方案

#### 系统架构（5层完整流水线）

```
原始日志流(海量) → Drain解析(模板提取) → 特征构建(向量化) → DBSCAN聚类(相似告警聚合) → 告警收敛(报告生成)
```

| 层级 | 模块 | 核心功能 | 技术实现 |
|------|------|----------|----------|
| **Step 1** | 原始日志流生成器 | 模拟真实运维日志 | 多源日志模板库、异常注入 |
| **Step 2** | Drain 解析层 | 提取日志模板，剥离变量 | 固定深度前缀树算法 |
| **Step 3** | 特征构建层 | 模板+上下文+语义→向量 | TF-IDF + PCA降维 |
| **Step 4** | DBSCAN 聚类层 | 相似告警自动聚合 | 基于密度的空间聚类 |
| **Step 5** | 告警收敛层 | 优先级排序+报告生成 | 加权评分算法 |

#### 核心特性

✅ **超高收敛率**: 64:1 (5000条日志 → 78个聚类)  
✅ **多维特征融合**: 模板特征 + 上下文特征 + 语义特征 + 统计特征  
✅ **智能优先级排序**: CRITICAL/HIGH/MEDIUM/LOW 四级分类  
✅ **专业报告生成**: Markdown格式，含处理建议  

#### 性能指标

| 指标 | 数值 |
|------|------|
| 处理能力 | 5000条日志 / 6.41秒 |
| 收敛率 | **64:1** |
| 聚类质量 | 轮廓系数 0.5151 (良好) |
| 降维效果 | 1016维 → 31维 (PCA) |

#### 快速开始

```bash
cd time_sequence_detection/alert_aggregation_Drain_DBSCAN

# 快速测试（1000条日志）
python3 run_pipeline.py --quick

# 自定义参数
python3 run_pipeline.py --logs 10000 --eps 0.3 --min-samples 10
```

#### 命令行参数

```bash
--logs, -l          # 日志数量（默认: 5000）
--eps, -e           # DBSCAN eps参数（默认: 0.5）
--min-samples, -m   # DBSCAN 最小样本数（默认: 5）
--quick, -q         # 快速测试模式
```

#### 输出文件

```
data/
├── raw/raw_logs.csv                    # 原始日志
├── parsed/parsed_logs.csv              # Drain解析结果
├── parsed/log_templates.json           # 日志模板库
├── features/log_features.npz           # 特征矩阵
├── clusters/clustered_logs.csv         # 聚类结果
├── clusters/cluster_statistics.json    # 聚类统计
└── reports/alert_convergence_report.md # 📋 完整收敛报告
```

#### 技术栈

| 技术 | 用途 |
|------|------|
| **Drain** | 在线日志解析（固定深度前缀树） |
| **DBSCAN** | 基于密度的空间聚类 |
| **TF-IDF** | 文本特征向量化 |
| **PCA** | 降维（1016维 → 31维） |
| **scikit-learn** | 机器学习工具包 |

---

### 🧠 2. GNN_RCA - GNN 图神经网络根因分析系统

> 使用 **图神经网络** 进行微服务故障的根因定位

#### 系统架构

```
原始数据 → 数据清洗 → 图构建(GCN/GAT/GraphSAGE) → GNN训练 → LLM分析 → RCA报告
```

#### 支持的模型架构

| 模型 | 特点 | 适用场景 |
|------|------|---------|
| **GCN** | 图卷积网络 | 规则拓扑结构 |
| **GAT** | 图注意力机制 | 不规则拓扑、重要节点识别 |
| **GraphSAGE** | 采样聚合 | 大规模图、归纳学习 |
| **TemporalGNN** | 时序图网络 | 时序依赖的故障传播 |

#### 核心特性

✅ **多种GNN架构**: GCN/GAT/GraphSAGE/TemporalGNN  
✅ **注意力机制**: 自动学习节点重要性  
✅ **残差连接**: 深层网络梯度优化  
✅ **LLM增强分析**: 生成可解释的诊断报告  

#### 快速开始

```bash
cd time_sequence_detection/GNN_RCA/gnn_root_cause_analysis

# 运行完整流水线
python3 run_pipeline.py --epochs 50 --model gat
```

#### 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| PyTorch | 2.0+ | 深度学习框架 |
| PyTorch Geometric | 2.3+ | 图神经网络 |
| NetworkX | 3.x | 图数据处理 |
| OpenAI API | 1.6+ | LLM 分析 |

---

### 🔍 3. microservice_rca - 微服务根因分析

> 针对 **微服务架构** 的专用根因分析工具

#### 核心功能

- 服务调用链分析
- 异常传播路径追踪
- 根因概率计算
- 影响范围评估

#### 技术特点

- 使用 **GCN + GAT** 混合架构
- 支持 **动态拓扑** 构建
- 提供 **置信度评分**

---

### 🛡️ 4. security_audit - 安全审计系统

> 运维安全事件的 **自动化检测与关联分析**

#### 检测类型

| 检测器 | 检测目标 | 方法 |
|--------|---------|------|
| **SSH暴力破解** | 登录失败频率 | 统计规则 |
| **认证异常** | 异常登录行为 | 孤立森林 |
| **云API滥用** | 异常API调用 | 规则+ML |
| **权限提升** | 异常提权操作 | 规则引擎 |

#### 关联分析引擎

- 时间窗口聚类
- 攻击链重构
- 威胁等级评估

---

### 📈 5. cpu_IsolationForest_Prophet - CPU 异常检测

> 使用 **IsolationForest + Prophet** 双模型进行 CPU 使用率异常检测

#### 算法组合

| 模型 | 作用 |
|------|------|
| **Prophet** | 时序建模、趋势预测、周期性分解 |
| **IsolationForest** | 无监督异常检测、离群点识别 |

#### 适用场景

- 单机/多机 CPU 监控
- 周期性负载模式识别
- 突发异常检测

---

### 💰 6. cost_analysis_Prophet - 成本分析与预测

> 基于 **Prophet 时序模型** 的云资源成本预测与异常检测

#### 功能特性

- 成本趋势预测
- 异常支出检测
- 优化建议生成

---

## 🧠 三、知识图谱：knowledge_graph（基础设施拓扑与查询）

> 基于 **Neo4j** 的运维知识图谱，支持自然语言查询

### 核心功能

#### 1️⃣ Text2Cypher - 自然语言转 Cypher 查询

将用户的自然语言问题转换为 Neo4j 的 Cypher 查询语句：

```python
示例转换：
"prod-server-01 连接了哪些网络设备？"
    ↓
"MATCH (s:Server {name: 'prod-server-01'})-[:CONNECTED_TO]->(n:NetworkDevice)
 RETURN n.name AS 设备名称, n.type AS 类型"
```

#### 2️⃣ 知识图谱 schema

**节点类型**:
- `Server`: 服务器（name, ip, location, cpu_usage, owner）
- `Middleware`: 中间件（Kafka, Redis, type, status）
- `NetworkDevice`: 网络设备（Switch, Firewall, bandwidth）
- `Storage`: 存储（OSS, bucket_name, region）
- `Database`: 数据库（MySQL, Redis, port, memory）

**关系类型**:
- `CONNECTED_TO`: 网络连接
- `PUBLISH_EVENT` / `CONSUME_EVENT`: 消息队列
- `READS_FROM` / `WRITES_TO`: 数据读写
- `DEPENDS_ON`: 服务依赖

### 技术栈

| 技术 | 用途 |
|------|------|
| **Neo4j 5.x** | 图数据库存储 |
| **OpenAI API** | 自然语言理解 |
| **Python neo4j driver** | 数据库驱动 |

### 快速开始

```bash
cd knowledge_graph

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 NEO4J_URI, NEO4J_PASSWORD, QWEN_API_KEY

# 运行 CLI 查询工具
python infra_text2cypher.py
```

---

## 🛠️ 四、快速开始指南

### 环境要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.9+ | 3.10+ |
| Node.js | 18+ | 20+ |
| Neo4j | 4.4+ | 5.x (可选) |
| Docker | 20+ | 最新版 (可选) |
| Kubernetes | 1.25+ | 最新版 (可选) |

### 一键安装（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd AIops

# 安装核心平台依赖
cd aiops-platform/backend
pip install -r requirements.txt

cd ../frontend
npm install

# 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 文件（必填项见下方）
```

### 必填环境变量

```bash
# .env 文件配置

# ===== AI 引擎 =====
OPENAI_API_KEY=sk-xxx                    # OpenAI/通义千问 API Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus

# ===== 安全配置 =====
SECRET_KEY=your-super-secret-key-min-32-chars  # ⚠️ 必须 >= 32 字符

# ===== 数据库 =====
DATABASE_URL=sqlite:///./data/aiops.db       # 或 PostgreSQL

# ===== Neo4j（知识图谱）=====
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password

# ===== SSH 远程命令执行 =====
SSH_USER=root
SSH_KEY_PATH=~/.ssh/id_rsa

# ===== 邮件通知（可选）=====
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=your-email@163.com
SMTP_PASSWORD=your-smtp-password
```

### 启动服务

```bash
# 终端 1: 启动后端
cd aiops-platform/backend
python app/main.py
# → http://localhost:8000 (API)
# → http://localhost:8000/docs (Swagger文档)

# 终端 2: 启动前端
cd aiops-platform/frontend
npm run dev
# → http://localhost:3000 (Web界面)
```

### 验证安装

```bash
# 1. 健康检查
curl http://localhost:8000/health
# 预期输出: {"status":"healthy"}

# 2. 查看 API 文档
浏览器打开: http://localhost:8000/docs

# 3. 测试登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

---

## 📚 五、详细文档

| 文档 | 路径 | 内容 |
|------|------|------|
| **核心平台文档** | [aiops-platform/README.md](./aiops-platform/README.md) | Multi-Agent 架构详解 |
| **告警聚合文档** | [time_sequence_detection/alert_aggregation_Drain_DBSCAN/](./time_sequence_detection/alert_aggregation_Drain_DBSCAN/) | Drain+DBSCAN 使用指南 |
| **GNN-RCA 文档** | [time_sequence_detection/GNN_RCA/](./time_sequence_detection/GNN_RCA/) | GNN 根因分析教程 |
| **知识图谱文档** | [knowledge_graph/](./knowledge_graph/) | Neo4j 图谱构建指南 |

---

## 🔧 六、核心技术详解

### Multi-Agent ReAct 工作流程

#### 完整执行示例

**用户输入**: `"order-service 连接池耗尽，帮我排查"`

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: IntentParseAgent (意图识别)                         │
├─────────────────────────────────────────────────────────────┤
│ Input:  "order-service 连接池耗尽，帮我排查"                 │
│ Output:                                                     │
│   intent = "DIAGNOSE"                                       │
│   entities = {                                              │
│     services: ["order-service"],                            │
│     symptoms: ["连接池耗尽"]                                 │
│   }                                                         │
│   confidence = "HIGH"                                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Skill 匹配                                          │
├─────────────────────────────────────────────────────────────┤
│ Matched: ["debug_skill", "mysql_deadlock_skill"]            │
│ Content Length: ~15,000 chars                               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: MasterAgent ReAct Loop                              │
├─────────────────────────────────────────────────────────────┤
│ Iteration 1:                                                │
│   Thought: 需要检查 order-service 的数据库连接状态           │
│   Action: execute_command("SHOW STATUS LIKE 'Threads_connected'") │
│   Observation: Threads_connected = 150/200 (75%)            │
│                                                             │
│ Iteration 2:                                                │
│   Thought: 连接数偏高，需要检查慢查询                         │
│   Action: execute_command("SHOW PROCESSLIST")               │
│   Observation: 发现 12 个慢查询正在执行                     │
│                                                             │
│ Iteration 3:                                                │
│   Thought: 定位到根本原因，需要提交诊断结果                  │
│   Action: submit_diagnosis_result(                           │
│     problem_type="database_connection_pool_exhaustion",     │
│     root_cause="慢查询导致连接池耗尽",                       │
│     recommendation="优化SQL或增加连接池大小",                 │
│     risk_level="MEDIUM"                                     │
│   )                                                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ Final Result                                                 │
├─────────────────────────────────────────────────────────────┤
│ Status: COMPLETED                                           │
│ Root Cause: 慢查询导致 MySQL 连接池耗尽                      │
│ Impact: order-service 响应时间增加 300%                      │
│ Recommendation:                                            │
│   1. 优化 TOP 10 慢查询 SQL                                 │
│   2. 增加 connection_pool_size 至 300                       │
│   3. 启用 query_cache                                      │
│ Confidence: HIGH                                           │
└─────────────────────────────────────────────────────────────┘
```

### 数据源统一访问示例

```python
from app.utils.data_source_manager import DataSourceManager

dsm = DataSourceManager()

# 列出可用数据源
sources = dsm.list_available_sources()
# → [{"name": "local", "available": True}, ...]

# 从 Prometheus 加载指标
metrics = await dsm.load_data(
    source_name="prometheus",
    data_type="metrics",
    query="up"
)

# 从 Elasticsearch 加载日志
logs = await dsm.load_data(
    source_name="elasticsearch",
    data_type="logs",
    index="logstash-*"
)

# 从本地文件加载数据（用于 GNN 训练）
data = await dsm.load_data(
    source_name="local",
    data_type="logs",
    data_path="/path/to/training_data"
)
```

---

## 🎯 七、项目评级与改进路线图

### 📊 Code Review 总评: A- (82/100)

| 维度 | 评分 | 说明 |
|------|------|------|
| 🏗️ **架构设计** | 8.5/10 | Multi-Agent 设计先进，模块化清晰 |
| 💻 **代码质量** | 8.0/10 | 注释详尽，可读性好 |
| 🔒 **安全性** | 7.5/10 | 有安全机制但需加固 |
| ⚡ **性能** | 7.0/10 | 可优化空间大 |
| 🧪 **测试覆盖** | 4.5/10 | 严重不足 (~10%) |
| 📚 **文档完整度** | 9.0/10 | 非常完善 |
| 🔧 **可维护性** | 8.0/10 | 配置驱动，易于扩展 |
| 🚀 **创新性** | 9.0/10 | Multi-Agent + GNN + 知识图谱 |

### 🚀 近期待办（P0/P1）

#### 🔴 本周必须完成

- [ ] **修复默认密码硬编码** - [auth.py](file:///Users/jaci-j/AIops/aiops-platform/backend/app/api/auth.py#L234)
- [ ] **收紧 CORS 配置** - [main.py](file:///Users/jaci-j/AIops/aiops-platform/backend/app/main.py#L32)
- [ ] **实现 JWT Token 黑名单** - 登出后失效
- [ ] **强制 SECRET_KEY 验证** - >= 32字符

#### 🟡 本月完成

- [ ] **搭建 pytest 测试框架**
- [ ] **核心模块测试覆盖率达到 60%**
  - [ ] tool_registry.py (85%)
  - [ ] auth.py (90%)
  - [ ] config.py (80%)
  - [ ] orchestrator.py (70%)
- [ ] **添加 LLM 调用重试机制** (tenacity)
- [ ] **统一错误处理** (logging 替代 print)

#### 🟢 下季度规划

- [ ] **PostgreSQL 迁移** (替代 SQLite)
- [ ] **Redis 缓存层** (热点数据缓存)
- [ ] **异步数据库改造** (asyncpg)
- [ ] **CI/CD 流水线** (GitHub Actions)
- [ ] **可观测性平台** (Prometheus + Grafana + Jaeger)

---

## 📈 八、性能基准与最佳实践

### 当前性能指标

| 指标 | 当前值 | 目标值 | 优化方向 |
|------|--------|--------|---------|
| API 平均响应时间 | < 500ms | < 200ms | Redis 缓存 |
| P99 延迟 | < 2s | < 1s | 异步改造 |
| 并发用户数 | 50 | 500 | 连接池优化 |
| LLM 调用成功率 | 95% | 99.9% | 重试机制 |
| 内存占用 | < 512MB | < 1GB | 对象复用 |

### 最佳实践建议

#### 1️⃣ 生产环境部署

```yaml
# k8s/deployment.yaml 示例
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "1000m"

replicas: 3  # 高可用

livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

#### 2️⃣ 安全加固清单

- [x] ✅ bcrypt 密码哈希
- [x] ✅ JWT Token 认证
- [x] ✅ RBAC 权限控制
- [x] ✅ 命令注入防护
- [ ] ⚠️ Rate Limiting (API 限流)
- [ ] ⚠️ HTTPS 强制跳转
- [ ] ⚠️ Security Headers (HSTS, X-Frame-Options)
- [ ] ⚠️ 审计日志 (用户操作记录)

#### 3️⃣ 监控告警

```python
# 推荐监控指标
METRICS = {
    "api_request_duration_seconds": "API 响应时间",
    "llm_call_success_total": "LLM 调用成功率",
    "agent_execution_time_seconds": "Agent 执行耗时",
    "active_connections gauge": "活跃连接数",
    "diagnosis_tasks_total": "诊断任务总数",
}
```

---

## 🤝 九、贡献指南

### 开发规范

1. **代码风格**: Black + isort + flake8
2. **类型注解**: 所有函数必须有类型提示
3. **文档字符串**: Google Style Docstrings
4. **提交信息**: Conventional Commits

### 提交 PR 流程

```bash
# 1. 创建分支
git checkout -b feature/your-feature-name

# 2. 编写代码 & 测试
# 确保测试通过
pytest tests/ -v --cov=app

# 3. 提交代码
git commit -m "feat: add new feature"

# 4. 推送并创建 PR
git push origin feature/your-feature-name
# GitHub 上创建 Pull Request
```

---

## 📄 十、许可证

MIT License

Copyright (c) 2024-2026 AIOps Team

---

## 🙏 致谢

- **OpenAI / 通义千问**: LLM 推理能力
- **FastAPI**: 高性能 Web 框架
- **PyTorch Geometric**: 图神经网络库
- **Neo4j**: 图数据库
- **React**: 前端框架

---

## 📞 联系方式

如有问题或建议，请提交 Issue 或联系维护团队。

**最后更新**: 2026-04-18  
**文档版本**: v3.0 (新增 Observability 可观测平台 + 增强型根因分析)

---

## 🔬 五、Observability 可观测性平台（新增）

> ⭐ **集成 Prometheus、Grafana、OpenTelemetry、Tempo 的企业级可观测平台，联合 time_sequence_detection 算法库实现智能根因分析**

### 📖 平台概述

基于 **多数据源融合 + 多算法推理** 的新一代智能运维可观测平台：

- 📊 **统一数据采集**: Prometheus 指标、Tempo 链路、OTel 追踪、Grafana 可视化
- 🧠 **增强型根因分析**: GNN 图神经网络 + IsolationForest + Prophet 多算法融合
- 🔄 **自动仪表盘生成**: Grafana Dashboard JSON 自动创建与部署
- ⚡ **分布式追踪**: OpenTelemetry 全链路埋点与上下文传播
- 🎯 **多维证据融合**: 加权置信度评估 + 自动修复建议

### 🏗️ 架构设计

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AIOps 增强型根因分析平台                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐     ┌────────────────────────────────────┐ │
│  │   Observability      │     │    time_sequence_detection         │ │
│  │   (数据采集层)        │ ──▶ │    (算法引擎层)                    │ │
│  ├─────────────────────┤     ├────────────────────────────────────┤ │
│  │ • Prometheus 指标   │     │ • GNN_RCA (图神经网络)             │ │
│  │ • Tempo 链路追踪    │     │ • IsolationForest + Prophet       │ │
│  │ • OTEL 分布式追踪   │     │ • Drain + DBSCAN 告警聚合          │ │
│  │ • Grafana 可视化    │     │ • LSTM 日志异常检测               │ │
│  └─────────┬───────────┘     └────────────────┬───────────────────┘ │
│            │                                  │                      │
│            ▼                                  ▼                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │              Data Bridge Layer (数据桥接层)                       ││
│  │  Prometheus → Pandas DataFrame | Tempo → Graph Structure        ││
│  └─────────────────────────┬───────────────────────────────────────┘│
│                            │                                        │
│  ┌─────────────────────────▼───────────────────────────────────────┐│
│  │           EnhancedRootCauseAnalyzer (增强型根因分析器)            ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  ││
│  │  │ IsolationForest│ │   Prophet    │ │   GNN Root Cause      │  ││
│  │  │ 异常检测       │ │ 时序预测     │ │ 图神经网络推理         │  ││
│  │  └──────┬─────────┘ └──────┬───────┘ └────────┬───────────────┘  ││
│  │         │                  │                   │                 ││
│  │         └──────────────────┼───────────────────┘                 ││
│  │                            ▼                                    ││
│  │              Multi-Algorithm Fusion Engine                      ││
│  └─────────────────────────────────────────────────────────────────┘│
│                            │                                        │
│                            ▼                                        │
│              📊 Enhanced RCA Report (增强型报告)                     │
│              • 多源证据融合  • 加权置信度  • 根因排序               │
└──────────────────────────────────────────────────────────────────────┘
```

### 📦 核心模块

| 模块 | 文件位置 | 功能描述 |
|------|----------|----------|
| **config.py** | `backend/app/observability/config.py` | 统一配置管理（Pydantic模型） |
| **prometheus_client.py** | `backend/app/observability/prometheus_client.py` | PromQL查询、指标采集、异常检测 |
| **opentelemetry_tracer.py** | `backend/app/observability/opentelemetry_tracer.py` | OTel SDK初始化、自动埋点、Span管理 |
| **tempo_query.py** | `backend/app/observability/tempo_query.py` | Trace查询、性能分析、服务依赖图 |
| **root_cause_analyzer.py** | `backend/app/observability/root_cause_analyzer.py` | 基础RCA引擎（规则+统计） |
| **grafana_dashboard.py** | `backend/app/observability/grafana_dashboard.py` | 4种模板仪表盘自动生成+部署 |
| **enhanced_rca.py** | `backend/app/observability/enhanced_rca.py` | ⭐ 增强型RCA（联合算法） |

### 🚀 快速开始

#### 安装依赖

```bash
cd aiops-platform/backend

# 核心依赖
pip install httpx opentelemetry-api opentelemetry-sdk \
            opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi \
            numpy pydantic pandas scikit-learn prophet torch torch_geometric
```

#### 基础使用（Prometheus + Tempo + RCA）

```python
import asyncio
from app.observability import (
    create_prometheus_client,
    create_tempo_client,
    create_root_cause_analyzer,
)

async def quick_start():
    async with create_root_cause_analyzer() as rca:
        report = await rca.analyze_incident(
            service_name="order-service",
            time_window_minutes=15,
        )
        
        print(f"最可能原因: {report.top_hypothesis.title}")
        print(f"置信度: {report.root_confidence*100:.1f}%")

asyncio.run(quick_start())
```

#### 增强型使用（联合 GNN + IF + Prophet）

```python
import asyncio
from app.observability.enhanced_rca import create_enhanced_analyzer

async def enhanced_analysis():
    async with create_enhanced_analyzer() as analyzer:
        # 自动运行: 基础RCA + IsolationForest + Prophet + GNN
        report = await analyzer.analyze_enhanced(
            service_name="order-service",
            time_window_minutes=30,
        )
        
        print(f"使用算法: {report.algorithms_used}")
        for hyp in report.base_report.hypotheses[:3]:
            print(f"根因: {hyp.title} (置信度: {hyp.confidence_score*100:.1f}%)")
            for ev in hyp.evidences:
                print(f"  ✓ [{ev.source}] {ev.description}")

asyncio.run(enhanced_analysis())
```

#### OpenTelemetry 追踪集成

```python
from app.observability.opentelemetry_tracer import (
    initialize_observability,
    trace_operation,
    SpanKind,
)

# 初始化
tracer = initialize_observability()

# 装饰器方式自动埋点
@trace_operation(name="database_query", kind=SpanKind.CLIENT)
async def query_database(user_id):
    result = await db.query(user_id)
    return result

# 上下文管理器方式
async with tracer.async_span_context("api_request") as span:
    tracer.set_attribute(span, "http.method", "GET")
    # 业务逻辑...
```

#### Grafana 仪表盘自动部署

```python
import asyncio
from app.observability.grafana_dashboard import (
    create_dashboard_generator,
    DashboardTemplate,
)

async def deploy_dashboards():
    async with create_dashboard_generator() as gen:
        # 生成系统监控仪表盘
        dashboard = gen.generate_dashboard(
            template=DashboardTemplate.SYSTEM_OVERVIEW,
            title="AIOps - 系统资源监控",
        )
        
        # 部署到 Grafana
        result = await gen.deploy_to_grafana(dashboard)
        print(f"仪表盘 URL: {result['url']}")

asyncio.run(deploy_dashboards())
```

### 📊 支持的算法集成

| 算法 | 来源模块 | 功能 | 适用场景 |
|------|---------|------|---------|
| **GNN (GCN/GAT)** | `microservice_rca`, `GNN_RCA` | 图神经网络微服务根因定位 | 微服务级联故障 |
| **IsolationForest** | `cpu_IsolationForest_Prophet` | 无监督统计异常检测 | CPU/内存突增 |
| **Prophet** | `cpu_IsolationForest_Prophet`, `cost_analysis_Prophet` | 时序趋势预测与偏差检测 | 周期性模式破坏 |
| **Drain + DBSCAN** | `alert_aggregation_Drain_DBSCAN` | 日志告警聚合收敛 | 告警风暴处理 |
| **Z-Score 统计** | 内置实现 | 实时异常评分 | 快速阈值告警 |

### 🎯 使用场景示例

#### 场景1: 服务故障自动诊断

```bash
# order-service 出现大量5xx错误，触发自动根因分析
python -c "
import asyncio
from app.observability.enhanced_rca import create_enhanced_analyzer

async def diagnose():
    async with create_enhanced_analyzer() as rca:
        report = await rca.analyze_enhanced(service='order-service')
        print(report.to_dict())

asyncio.run(diagnose())
"
```

#### 场景2: 性能瓶颈定位

```python
# 分析慢请求的调用链瓶颈
async with create_tempo_client() as tempo:
    slow_traces = await tempo.search_slow_traces(min_duration="3s")
    
    for trace_info in slow_traces.traces[:5]:
        analysis = await tempo.analyze_trace_performance(trace_info["traceID"])
        for bn in analysis["bottleneck_analysis"]:
            print(f"瓶颈: {bn['operation_name']} ({bn['duration_ms']:.0f}ms)")
```

#### 场景3: 全栈监控仪表盘

```python
# 一键生成并部署4种专业仪表盘
templates = [
    DashboardTemplate.SYSTEM_OVERVIEW,       # 系统资源监控
    DashboardTemplate.APPLICATION_PERFORMANCE, # APM应用性能
    DashboardTemplate.ROOT_CAUSE_ANALYSIS,     # 根因分析工作台
    DashboardTemplate.SERVICE_MESH,           # 服务网格监控
]

for template in templates:
    dashboard = gen.generate_dashboard(template=template)
    await gen.deploy_to_grafana(dashboard)
```

### 📁 目录结构

```
aiops-platform/backend/app/observability/
├── __init__.py              # 包导出（含增强模块）
├── config.py                # Pydantic 配置模型
├── prometheus_client.py     # Prometheus 查询客户端
├── opentelemetry_tracer.py  # OTel 分布式追踪
├── tempo_query.py           # Tempo 链路查询与分析
├── root_cause_analyzer.py   # 基础根因分析引擎
├── grafana_dashboard.py     # Grafana 仪表盘生成器
├── enhanced_rca.py          # ⭐ 增强型RCA（联合算法）
├── examples.py              # 基础使用示例
└── enhanced_examples.py     # ⭐ 增强使用示例
```

### 🔧 配置说明

通过环境变量或 Pydantic 模型配置各组件：

```bash
# Prometheus
export PROMETHEUS_URL=http://localhost:9090

# Grafana
export GRAFANA_URL=http://localhost:3000
export GRAFANA_API_KEY=your-api-key

# Tempo
export TEMPO_URL=http://localhost:3200

# OpenTelemetry
export OTEL_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=aiops-platform
```

---

## 📝 六、项目路线图

### ✅ 已完成

- [x] Multi-Agent 智能诊断系统
- [x] 时间序列检测算法库（6个模块）
- [x] Neo4j 知识图谱
- [x] 安全审计系统
- [x] **🆕 Observability 可观测性平台**
- [x] **🆕 增强 RCA（GNN + IF + Prophet 联合）**

### 🔄 进行中

- [ ] LLM 增强的自然语言诊断报告生成
- [ ] Kubernetes Operator 自动化运维
- [ ] 更多数据源适配器开发

### 📌 计划中

- [ ] AIOps Agent Marketplace（技能市场）
- [ ] 多租户隔离与企业版功能
- [ ] 边缘计算节点支持
