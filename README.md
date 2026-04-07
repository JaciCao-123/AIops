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
└── time_sequence_prediction/ # 时间序列预测与异常检测
    ├── cpu_anomaly_detection/    # CPU 异常检测
    ├── cost_analysis/            # 成本分析与预测
    ├── microservice_rca/         # 微服务根因分析
    └── security_audit/           # 安全审计
```

## 🚀 核心功能

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

### 3. time_sequence_prediction - 时间序列预测

运维场景下的时间序列分析与预测：

- **CPU 异常检测**：多服务器 CPU 使用率异常检测
- **成本分析**：云资源成本预测与异常检测
- **微服务根因分析**：基于 GNN 的微服务故障根因定位
- **安全审计**：SSH、认证、云 API 调用异常检测

**技术栈**：
- Prophet 时间序列预测
- PyTorch + PyTorch Geometric
- 图神经网络（GCN、GAT、GraphSAGE）

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

### 多智能体架构

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

如有问题或建议，请提交 Issue。
