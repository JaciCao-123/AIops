# AIops - 智能运维平台

智能运维（AIOps）平台，集成 **Multi-Agent 智能体架构**、**知识图谱**、**时间序列检测算法库** 和 **根因分析** 能力。

---

## 目录

- [项目亮点](#-项目亮点)
- [项目架构](#-项目架构)
- [一、核心平台：aiops-platform](#一核心平台aiops-platform)
  - [Multi-Agent 架构](#-multi-agent-协同架构)
  - [安全防护体系](#-安全防护体系)
  - [Skill 技能库](#-skill-技能库)
  - [快速开始](#-快速开始)
- [二、算法引擎：time_sequence_detection](#二算法引擎time_sequence_detection)
  - [算法模块概览](#-算法模块概览)
  - [各模块详解](#-各模块详解)
- [三、可观测性平台](#三可观测性平台)
  - [核心模块](#-核心模块)
  - [OpenTelemetry 可观测性组件](#-opentelemetry-可观测性组件-otel-observability)
- [四、部署指南](#四部署指南)
- [技术栈](#-技术栈)

---

## 🎯 项目亮点

| 特性 | 描述 |
|------|------|
| 🤖 **Multi-Agent 协同** | 5个专业Agent协同工作，动态规划诊断流程 |
| 🧠 **LLM 驱动决策** | ReAct 循环 + Function Calling 实现智能推理 |
| 🔒 **企业级安全** | 7层安全防护、审批工作流、RBAC权限控制 |
| 📊 **全栈算法支持** | GNN、Drain+DBSCAN、Prophet、IsolationForest、LSTM 等 |
| 🔬 **可观测性平台** | Prometheus + Grafana + OTel + Tempo 全链路监控 |
| 🌐 **统一数据源** | Prometheus、Elasticsearch、Loki、云监控等 |

---

## 📁 项目架构

```
AIops/
├── aiops-platform/                    # 核心智能诊断平台
│   ├── backend/                       # FastAPI 后端服务
│   │   ├── app/agents/                # Multi-Agent 系统
│   │   ├── app/api/                   # REST API 路由
│   │   ├── app/core/                  # 配置 & 数据库
│   │   ├── app/utils/                 # 工具类
│   │   ├── app/observability/         # 可观测性平台
│   │   ├── algorithm/                 # 算法模块
│   │   └── skills/                    # Skill 技能库 (40+)
│   ├── frontend/                      # React + TypeScript 前端
│   ├── k8s/                           # Kubernetes 部署配置
│   └── docker/                        # Docker 配置
│
├── time_sequence_detection/           # 时间序列检测算法库
│   ├── Log_Analysis_LSTM/             # DeepLog 日志异常检测
│   ├── GNN_RCA/                       # GNN 图神经网络根因分析
│   ├── microservice_rca/              # 微服务根因分析
│   ├── alert_aggregation_Drain_DBSCAN/# 智能告警聚合
│   ├── system_load_prediction/        # 双层漏斗系统负载检测
│   ├── cpu_IsolationForest_Prophet/   # CPU 异常检测
│   ├── cost_analysis_Prophet/         # 成本异常分析
│   └── security_audit/                # 安全审计系统
│
└── knowledge_graph/                   # 运维知识图谱 (Neo4j)
```

---

## 一、核心平台：aiops-platform

### 🏗️ Multi-Agent 协同架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Agent 协同架构                          │
├─────────────────────────────────────────────────────────────────┤
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
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│      │                                                           │
│      ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         ToolRegistry + SkillManager                      │   │
│  │  • 25+ 工具注册 (SSH、Prometheus、Neo4j...)              │   │
│  │  • 40+ Skill 文件 (MySQL、Redis、K8s...)                 │   │
│  │  • 安全检查 & 审批工作流                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 👥 Agent 角色分工

| Agent | 角色 | 核心职责 |
|-------|------|----------|
| **IntentParseAgent** | 入口网关 | NER实体识别、意图分类、关键词提取 |
| **KnowledgeExpertAgent** | 知识专家 | Neo4j拓扑查询、RAG检索、历史案例匹配 |
| **ObservabilityAnalystAgent** | 感知分析师 | 收集指标/日志/链路、异常检测 |
| **MasterAgent** | 大脑中枢 | 动态规划、ReAct循环、最终决策 |
| **ActionExecuteAgent** | 执行者 | 生成安全的执行指令、风险评估 |

### 🔐 安全防护体系

```
Layer 1: 命令注入防护 (12种正则模式)
    ↓
Layer 2: 危险命令黑名单 (18种)
    ↓
Layer 3: 安全命令白名单 (30+种)
    ↓
Layer 4: 风险等级分级 (LOW/MEDIUM/HIGH/BLOCKED)
    ↓
Layer 5: 红线操作拦截 (5类)
    ↓
Layer 6: 审批工作流 (邮件+API双通道)
    ↓
Layer 7: RBAC权限控制 (admin/user)
```

### 📚 Skill 技能库

**文件位置**: [backend/skills/](file:///Users/jaci-j/AIops/aiops-platform/backend/skills/)

#### 诊断类 (Diagnosis)
| Skill | 适用场景 |
|-------|----------|
| `debug_skill` | 服务器/数据库/中间件/K8S 全栈故障排查 |
| `gnn_rca_skill` | 微服务根因分析 (GNN) |
| `microservice_rca_skill` | 微服务根因定位 (GNN) |
| `time_series_rca_skill` | 时间序列根因分析 |
| `mysql_deadlock_skill` | MySQL 死锁排查 |
| `mysql_slow_query_skill` | MySQL 慢查询分析 |
| `redis_skill` | Redis 诊断与优化 |

#### 监控类 (Monitoring)
| Skill | 适用场景 |
|-------|----------|
| `deeplog_anomaly_detection_skill` | DeepLog 日志异常检测 |
| `alert_cluster_skill` | 智能告警聚合 (Drain + Word2Vec + TF-IFD + DBSCAN) |
| `system_load_skill` | 系统负载异常检测 (双层漏斗: IF + LSTM-AE) |
| `cost_analysis_skill` | 云成本异常分析 (Prophet) |
| `cpu_anomaly_skill` | CPU 异常检测 (IF + Prophet) |
| `prometheus_skill` | Prometheus 监控诊断 |

#### 数据库类 (Database)
| Skill | 适用场景 |
|-------|----------|
| `database_ha_skill` | 数据库高可用与复制故障排查 |
| `mysql_failover_skill` | MySQL 主从故障人工切换 |
| `backup_drill_skill` | 数据库备份恢复演练 |
| `postgresql_skill` | PostgreSQL 性能诊断 |
| `mongodb_skill` | MongoDB 副本集与分片诊断 |

#### 中间件类 (Middleware)
| Skill | 适用场景 |
|-------|----------|
| `kafka_skill` | Kafka 集群诊断与消息堆积处理 |
| `nginx_skill` | Nginx Web 服务器诊断 |
| `rabbitmq_skill` | RabbitMQ 队列诊断 |
| `elasticsearch_skill` | Elasticsearch 集群诊断 |

#### 容器类 (Container)
| Skill | 适用场景 |
|-------|----------|
| `k8s_pod_skill` | Kubernetes Pod 诊断 |

#### 网络类 (Network)
| Skill | 适用场景 |
|-------|----------|
| `connectivity_skill` | 网络连通性诊断 |
| `lb_port_connectivity_skill` | 阿里云负载均衡端口连接诊断 |
| `ssl_certificate_skill` | SSL 证书管理 |

#### 安全类 (Security)
| Skill | 适用场景 |
|-------|----------|
| `security_audit_skill` | 安全事件检测与应急响应 |
| `permission_troubleshoot_skill` | 文件/服务权限问题排查 |

#### 云资源类 (Cloud)
| Skill | 适用场景 |
|-------|----------|
| `ecs_skill` | 阿里云 ECS 实例诊断 |
| `vpc_skill` | 阿里云 VPC 网络诊断 |
| `oss_skill` | 阿里云 OSS 存储诊断 |

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

## 二、算法引擎：time_sequence_detection

### 📊 算法模块概览

```
time_sequence_detection/
│
├── Log_Analysis_LSTM/              # 日志异常检测
│   └── DeepLog + LSTM 序列预测
│
├── GNN_RCA/                        # 图神经网络根因分析
│   └── GAT/GCN/GraphSAGE
│
├── microservice_rca/               # 微服务根因分析
│   └── GNN + 服务拓扑
│
├── alert_aggregation_Drain_DBSCAN/ # 智能告警聚合
│   └── Drain + Word2Vec + DBSCAN
│
├── system_load_prediction/         # 系统负载检测
│   └── 双层漏斗: IF + LSTM-AE
│
├── cpu_IsolationForest_Prophet/    # CPU 异常检测
│   └── Isolation Forest + Prophet
│
├── cost_analysis_Prophet/          # 成本异常分析
│   └── Prophet 时序预测
│
└── security_audit/                 # 安全审计系统
    └── 多源日志关联分析
```

### 📦 各模块详解

#### 1. Log_Analysis_LSTM - 日志异常检测

**技术栈**: DeepLog + LSTM

**核心原理**:
- 学习正常日志序列模式
- 预测下一个最可能出现的日志事件
- 实际事件不在 Top-k 预测中则判定为异常

**使用方式**:
```python
from skill import LogAnalysisSkill

skill = LogAnalysisSkill()
result = await skill.detect_logs([
    "[2024-01-01 10:00:00] [ERROR] Connection timeout",
])
```

**文件结构**:
```
Log_Analysis_LSTM/
├── skill.py              # 技能封装（Multi-Agent 接口）
├── 1_generate_data.py    # 日志数据生成
├── 2_parse_logs.py       # 日志解析 (Drain)
├── 3_train_model.py      # 模型训练
└── 4_predict.py          # 异常检测
```

---

#### 2. GNN_RCA - 图神经网络根因分析

**技术栈**: GAT / GCN / GraphSAGE

**核心原理**:
- 构建服务调用拓扑图
- 学习故障传播模式
- 定位最可能的根因服务

**使用方式**:
```python
from gnn_rca import GNNRootCauseAnalyzer

analyzer = GNNRootCauseAnalyzer(data_path="data/")
result = analyzer.analyze(top_k=3)
```

**文件结构**:
```
GNN_RCA/
├── step1_generate_data.py        # 生成拓扑数据
├── step2_clean_and_build_graph.py # 构建图数据
├── step3_gnn_models.py           # GNN 模型定义
├── step4_train_model.py          # 模型训练
└── step5_llm_analysis.py         # LLM 分析报告
```

---

#### 3. microservice_rca - 微服务根因分析

**技术栈**: GNN + 服务拓扑

**核心能力**:
- 构建微服务调用拓扑图
- 分析故障传播路径
- 定位根因服务

**文件结构**:
```
microservice_rca/
├── model.py              # GNN 模型定义
├── step1_generate_data.py # 生成模拟数据
├── step2_clean_data.py   # 数据清洗
├── step3_train_model.py  # 模型训练
└── step4_predict.py      # 根因预测
```

---

#### 4. alert_aggregation_Drain_DBSCAN - 智能告警聚合

**技术栈**: Drain + TF-IDF + Word2Vec + DBSCAN

**核心能力**:
- 离线训练 Word2Vec 学习运维语义
- 在线实时告警聚类压缩
- 多维距离融合（时间 + 语义 + 拓扑）

**使用方式**:
```python
from skill import AlertClusterSkill

skill = AlertClusterSkill()
result = await skill.cluster([
    {"time": "2024-01-01 10:00:00", "node_id": "node-1", "raw_msg": "Connection timeout"},
])
```

**性能指标**:
| 指标 | 数值 |
|------|------|
| 压缩率 | 2:1 ~ 64:1 |
| 处理延迟 | < 100ms / 100条告警 |

---

#### 5. system_load_prediction - 系统负载异常检测

**技术栈**: 双层漏斗架构 (Isolation Forest + LSTM Autoencoder)

**核心原理**:
```
Layer 1: Isolation Forest 快速初筛
  ├─ score ≥ 0.05  → 正常放行
  ├─ score < -0.20 → 严重异常报警
  └─ 中间区间      → 推入 Layer 2

Layer 2: LSTM Autoencoder 深度确诊
  ├─ error > threshold → 确诊异常报警
  └─ error ≤ threshold → 误报释放
```

**核心能力**:
- 实时数据流检测
- 邮件告警（防轰炸冷却机制）
- 动态阈值自适应

---

#### 6. cpu_IsolationForest_Prophet - CPU 异常检测

**技术栈**: Isolation Forest + Prophet

**核心能力**:
- 异常点检测 (Isolation Forest)
- 趋势预测 (Prophet)
- 多服务器并行检测

**文件结构**:
```
cpu_IsolationForest_Prophet/
├── step1_generate_data.py  # 生成 CPU 数据
├── step2_clean_data.py     # 数据清洗
├── step3_train_model.py    # 模型训练
├── step4_visualize.py      # 可视化
├── step5_predict.py        # 预测脚本
└── run_all.py              # 一键运行
```

---

#### 7. cost_analysis_Prophet - 成本异常分析

**技术栈**: Prophet

**核心能力**:
- 成本预测与置信区间
- 异常检测（超出置信区间）
- 根因下钻（定位异常服务和项目）

**使用场景**:
- 云成本激增检测
- 成本趋势分析
- 预算预警

---

#### 8. security_audit - 安全审计系统

**技术栈**: 多源日志关联分析

**核心能力**:
- SSH 暴力破解检测
- 异常登录检测
- 权限提升检测
- 多源日志关联分析

**日志源支持**:
- SSH 日志
- 认证日志
- 应用服务器日志
- 云平台日志

---

## 三、可观测性平台

### 🏗️ 架构设计

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AIOps 可观测性平台                                  │
├──────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐     ┌────────────────────────────────────┐ │
│  │   数据采集层         │     │    算法引擎层                       │ │
│  ├─────────────────────┤     ├────────────────────────────────────┤ │
│  │ • Prometheus 指标   │     │ • GNN_RCA (图神经网络)             │ │
│  │ • Tempo 链路追踪    │     │ • IsolationForest + Prophet       │ │
│  │ • OTel 分布式追踪   │     │ • Drain + DBSCAN 告警聚合          │ │
│  │ • Grafana 可视化    │     │ • LSTM 日志异常检测               │ │
│  └─────────┬───────────┘     └────────────────┬───────────────────┘ │
│            └──────────────────┬────────────────┘                    │
│                               ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │           EnhancedRootCauseAnalyzer (增强型根因分析器)            ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────────────┐  ││
│  │  │ IsolationForest│ │   Prophet    │ │   GNN Root Cause      │  ││
│  │  │ 异常检测       │ │ 时序预测     │ │ 图神经网络推理         │  ││
│  │  └───────────────┘ └──────────────┘ └────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

### 📦 核心模块

| 模块 | 功能描述 |
|------|----------|
| `prometheus_client.py` | PromQL查询、指标采集、异常检测 |
| `opentelemetry_tracer.py` | OTel SDK初始化、自动埋点、Span管理 |
| `tempo_query.py` | Trace查询、性能分析、服务依赖图 |
| `root_cause_analyzer.py` | 基础RCA引擎（规则+统计） |
| `grafana_dashboard.py` | 4种模板仪表盘自动生成+部署 |
| `enhanced_rca.py` | 增强型RCA（联合算法） |

### 使用示例

```python
import asyncio
from app.observability.enhanced_rca import create_enhanced_analyzer

async def enhanced_analysis():
    async with create_enhanced_analyzer() as analyzer:
        report = await analyzer.analyze_enhanced(
            service_name="order-service",
            time_window_minutes=30,
        )
        print(f"使用算法: {report.algorithms_used}")
        for hyp in report.base_report.hypotheses[:3]:
            print(f"根因: {hyp.title} (置信度: {hyp.confidence_score*100:.1f}%)")

asyncio.run(enhanced_analysis())
```

---

### 🔭 OpenTelemetry 可观测性组件 (otel-observability)

**文件位置**: [otel-observability/](file:///Users/jaci-j/AIops/otel-observability/)

独立的 OpenTelemetry 可观测性基础设施，提供完整的 Metrics、Traces、Logs 采集与分析能力。

#### 📁 项目结构

```
otel-observability/
├── docker-compose.yml              # 主编排文件
├── otel-collector-config.yaml      # OTel Collector 配置
├── prometheus.yml                  # Prometheus 配置
├── tempo.yaml                      # Tempo 配置
├── grafana-datasources.yaml        # Grafana 数据源配置
├── alertmanager.yml                # Alertmanager 配置 (AIops 集成)
│
├── bt-server-observability/        # 生产环境部署
│   ├── docker-compose.yml          # 含 Prometheus 完整组件
│   ├── otel-collector-config.yaml
│   ├── prometheus.yml
│   ├── tempo.yaml
│   └── grafana-datasources.yaml
│
├── k8s-agent/                      # Kubernetes 部署
│   ├── namespace.yaml              # 命名空间
│   ├── rbac.yaml                   # 权限配置
│   ├── configmap.yaml              # 配置映射
│   ├── daemonset.yaml              # DaemonSet 部署
│   └── sample-app.yaml             # 示例应用
│
├── microservices/                  # 微服务示例
│   ├── app.py                      # Flask 应用 (OTel 埋点)
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── ecommerce-demo/                 # 电商演示应用
    ├── app.py                      # 订单/商品服务
    ├── Dockerfile.order
    ├── Dockerfile.product
    └── deploy-all.sh
```

#### 🧩 核心组件

| 组件 | 端口 | 功能描述 |
|------|------|----------|
| **Prometheus** | 9090 | 指标采集、存储、告警规则 |
| **Tempo** | 3200 | 分布式链路追踪存储 |
| **OTel Collector** | 4317/4318 | 统一数据采集网关 (gRPC/HTTP) |
| **Grafana** | 3000 | 统一可视化面板 |
| **Alertmanager** | 9093 | 告警路由与通知 |

#### 🔧 OTel Collector 配置亮点

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  tail_sampling:                    # 智能采样策略
    policies:
      - name: error-traces          # 100% 采集错误链路
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow-traces           # 采集慢请求 (>500ms)
        type: latency
        latency: { threshold_ms: 500 }
      - name: sample-10-percent     # 10% 概率采样正常链路
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }

exporters:
  otlphttp: { endpoint: http://tempo:4318 }
  prometheus: { endpoint: 0.0.0.0:8889 }
```

#### 🔗 AIops 平台集成

**Alertmanager Webhook 配置** (`alertmanager.yml`):

```yaml
receivers:
  - name: 'aiops-receiver'
    webhook_configs:
      - url: 'http://host.docker.internal:8000/api/alerts/webhook'
        send_resolved: true
```

**集成架构**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    告警流转架构                                       │
├─────────────────────────────────────────────────────────────────────┤
│  Prometheus                                                         │
│      │ 触发告警规则                                                  │
│      ▼                                                              │
│  Alertmanager ──webhook──▶ AIops Platform                           │
│      │                          │                                   │
│      │                          ▼                                   │
│      │                    /api/alerts/webhook                       │
│      │                          │                                   │
│      │                          ▼                                   │
│      │                    告警聚合 (Drain + DBSCAN)                  │
│      │                          │                                   │
│      │                          ▼                                   │
│      │                    Multi-Agent 诊断                           │
│      │                          │                                   │
│      │                          ▼                                   │
│      └──────────────────── 根因分析报告 ◀───────────────────────────│
└─────────────────────────────────────────────────────────────────────┘
```

#### 🚀 快速部署

**Docker Compose 部署**:

```bash
# 进入目录
cd otel-observability

# 启动所有组件
docker-compose up -d

# 查看服务状态
docker-compose ps

# 访问服务
# Grafana:      http://localhost:3000 (admin/admin123)
# Prometheus:   http://localhost:9090
# Tempo:        http://localhost:3200
# Alertmanager: http://localhost:9093
```

**Kubernetes 部署**:

```bash
cd otel-observability/k8s-agent

# 创建命名空间和权限
kubectl apply -f namespace.yaml
kubectl apply -f rbac.yaml

# 部署 OTel Agent (DaemonSet)
kubectl apply -f configmap.yaml
kubectl apply -f daemonset.yaml

# 部署示例应用
kubectl apply -f sample-app.yaml
```

#### 📊 应用埋点示例

**Python Flask 应用**:

```python
from flask import Flask
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

app = Flask(__name__)

# 初始化 OTel
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
otlp_exporter = OTLPSpanExporter(endpoint="otel-collector:4317")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

@app.route("/api/orders")
def orders():
    with tracer.start_as_current_span("process_order"):
        # 业务逻辑
        return {"status": "ok"}
```

#### 📈 Grafana 仪表盘

启动后，Grafana 自动配置以下数据源：

| 数据源 | 类型 | 用途 |
|--------|------|------|
| Prometheus | Prometheus | 指标查询 |
| Tempo | Tempo | 链路追踪查询 |
| Loki | Loki | 日志查询 (可选) |

**推荐仪表盘**:
- **Node Exporter Full**: 主机监控
- **Tempo Service Graph**: 服务依赖拓扑
- **OTel Collector**: Collector 性能监控

---

## 四、部署指南

### Docker 部署

```bash
# 构建镜像
cd aiops-platform
docker build -t aiops-platform:latest .

# 运行容器
docker run -d \
  --name aiops \
  -p 8000:8000 \
  -p 3000:3000 \
  -v $(pwd)/data:/app/data \
  aiops-platform:latest
```

### Kubernetes 部署

```bash
# 应用配置
kubectl apply -f k8s/local-storage.yaml
kubectl apply -f k8s/kg-api-deployment.yaml
kubectl apply -f k8s/kg-api-service.yaml
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| **后端框架** | FastAPI 0.104 + Uvicorn | 高性能异步 Web 服务 |
| **前端框架** | React 18 + TypeScript + Vite | 现代化 SPA 应用 |
| **AI 引擎** | OpenAI API / 通义千问 | LLM 推理 & Function Calling |
| **图数据库** | Neo4j 5.x | 知识图谱存储与查询 |
| **关系数据库** | SQLite / PostgreSQL | 业务数据持久化 |
| **认证授权** | JWT + bcrypt + RBAC | 安全认证与权限控制 |
| **深度学习** | PyTorch + PyTorch Geometric | GNN、LSTM 等模型 |
| **时序预测** | Prophet | 时间序列预测 |
| **异常检测** | Isolation Forest | 异常点检测 |
| **部署方案** | Docker + Kubernetes | 容器化编排部署 |

---

## 📄 版本信息

- **版本**: v4.1
- **更新时间**: 2025-04-22
- **维护者**: AIOps Team

### 更新日志

#### v4.1 (2025-04-22)
- 新增 otel-observability 可观测性组件文档
- 新增告警中心、链路追踪前端页面
- 完善 Alertmanager 与 AIops 平台集成说明
- 添加 OTel Collector 智能采样配置说明

#### v4.0 (2025-04-21)
- 新增 5 个算法模型 Skill 集成
- 更新 Skill 技能库至 40+ 技能
- 优化 README 结构，增加目录导航
- 完善算法模块文档

#### v3.1 (2025-04-07)
- 优化章节结构
- 新增 7 层安全防护体系
- 完善可观测性平台文档

#### v3.0 (2025-03-28)
- 新增 Multi-Agent 协同架构
- 集成知识图谱与 RAG
- 完善安全审批工作流
