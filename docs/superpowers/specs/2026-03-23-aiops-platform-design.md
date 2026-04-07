# AIOps 智能运维平台设计文档

**日期**: 2026-03-23
**版本**: v1.0
**状态**: 待用户审核

---

## 1. 项目概述

### 1.1 项目目标
构建一个综合型AIOps智能运维平台，融合故障排查、日志分析、智能问答三大核心功能。

### 1.2 项目范围
| 功能模块 | 说明 |
|---------|------|
| 故障排查 | Multi-Agent协作，自动分析根因并生成修复方案 |
| 日志分析 | 支持文件上传、API接入、模拟流式日志的异常检测 |
| 智能问答 | 基于拓扑图谱和RAG知识库的运维咨询 |

### 1.3 技术选型
| 层级 | 技术 |
|------|------|
| 前端 | React + TypeScript + Ant Design + ECharts |
| 后端API | Python + FastAPI + SQLAlchemy + SQLite |
| 图谱服务 | 复用 /knowledge_graph 模块 |
| RAG服务 | Python + LangChain (外挂 ops_rag) |
| 日志算法 | Python + 孤立森林 |
| 部署 | Docker Compose |

### 1.4 复用模块
- `/Users/jaci-j/AIops/knowledge_graph/` - 图谱查询 (text2cypher)
- `~/ops_rag/` - RAG知识库 (外挂)

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (React)                            │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│   │ 仪表盘   │  │ 日志列表  │  │ 故障排查  │  │   智能问答   │   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端API (FastAPI)                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│   │ 日志API  │  │MultiAgent│  │ KG查询   │  │   RAG查询    │   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                                    │                    │
         ▼                                    ▼                    ▼
┌─────────────────┐              ┌─────────────────┐    ┌─────────────────┐
│  算法服务       │              │ knowledge_graph │    │   ops_rag       │
│  (孤立森林)     │              │   (text2cypher)│    │  (外挂知识库)   │
└─────────────────┘              └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│     SQLite      │
│  (日志+标注)     │
└─────────────────┘
```

### 2.2 Multi-Agent架构

```
用户输入
    │
    ▼
┌─────────────────┐
│ Intent Parse     │ ← CMDB服务列表
│ Agent (入口)     │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Observability   │ ← Metrics/Logs/Traces
│ Analyst Agent   │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Knowledge       │ ← KG拓扑 + RAG案例 + SOP
│ Expert Agent    │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Master Agent    │
│ (大脑中枢)       │
└─────────────────┘
    │
    ▼
┌─────────────────┐
│ Action Execute  │ ← OOS执行指令
│ Agent (执行层)   │
└─────────────────┘
```

---

## 3. 功能模块详细设计

### 3.1 故障排查模块 (Multi-Agent)

#### Agent 1: Intent Parse Agent
- **职责**: 意图识别 + 实体提取
- **输入**: 用户自然语言
- **输出**: 标准化的JSON {intent, entities, confidence}

#### Agent 2: Observability Analyst Agent
- **职责**: 黄金信号分析 + 根因假设
- **输入**: Metrics/Logs/Traces数据
- **输出**: 分析报告

#### Agent 3: Knowledge Expert Agent
- **职责**: KG拓扑查询 + RAG检索
- **输入**: 拓扑关系 + 历史案例 + SOP
- **输出**: 结构化建议

#### Agent 4: Master Agent
- **职责**: 综合决策 + 方案生成
- **输入**: 以上三者的输出
- **输出**: 根因 + 执行计划

#### Agent 5: Action Execute Agent
- **职责**: OOS指令生成 + 执行
- **输入**: 执行计划
- **输出**: 操作结果

### 3.2 日志分析模块

| 功能 | 说明 |
|------|------|
| 文件上传 | 支持 .log/.txt，最大10MB |
| API接入 | 接收外部系统日志推送 |
| 模拟流式 | 每秒生成模拟日志 |
| 异常检测 | 孤立森林算法 |
| 标注反馈 | 用户纠正误报 |

### 3.3 智能问答模块

| 功能 | 说明 |
|------|------|
| KG查询 | 调用text2cypher查询拓扑 |
| RAG检索 | 从ops_rag检索相关文档 |
| 混合问答 | 综合KG+RAG生成答案 |

---

## 4. 数据库设计

### 4.1 SQLite表结构

```sql
-- 日志表
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10),
    content TEXT,
    source VARCHAR(50),  -- file/api/simulate
    is_anomaly BOOLEAN DEFAULT FALSE,
    anomaly_score FLOAT,
    user_feedback BOOLEAN  -- null: 未标注, true: 误报, false: 确认异常
);

-- 标注记录表
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER REFERENCES logs(id),
    feedback_type BOOLEAN,  -- true: 误报, false: 确认异常
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 异常统计表 (实时计算)
-- 无需存储，按需计算
```

---

## 5. API设计

### 5.1 日志API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/logs/upload | 文件上传 |
| POST | /api/logs/ingest | API接入日志 |
| GET | /api/logs | 查询日志列表 |
| POST | /api/logs/{id}/feedback | 标注反馈 |
| GET | /api/logs/stats | 异常统计 |

### 5.2 Multi-Agent API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/agent/diagnose | 故障排查入口 |
| GET | /api/agent/status/{task_id} | 查询任务状态 |

### 5.3 知识库API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/kg/query | KG图谱查询 |
| POST | /api/rag/query | RAG知识检索 |
| GET | /api/qa/chat | 智能问答 |

---

## 6. 目录结构

```
/Users/jaci-j/AIops/aiops-platform/
├── frontend/                    # React前端
│   ├── src/
│   │   ├── components/         # 组件
│   │   ├── pages/              # 页面
│   │   ├── hooks/              # 自定义Hooks
│   │   ├── services/           # API调用
│   │   └── types/             # TypeScript类型
│   ├── package.json
│   └── vite.config.ts
├── backend/                    # Python后端
│   ├── app/
│   │   ├── api/                # API路由
│   │   ├── agents/            # Multi-Agent实现
│   │   ├── services/          # 业务逻辑
│   │   ├── models/             # 数据模型
│   │   └── core/               # 核心配置
│   ├── algorithm/             # 算法服务
│   │   └── anomaly_detector.py
│   ├── requirements.txt
│   └── main.py
├── ops_rag/                    # 外挂RAG知识库 (符号链接或引用)
├── docker-compose.yml
└── README.md
```

---

## 7. 部署架构

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - neo4j

  algorithm:
    build: ./backend/algorithm
    ports:
      - "8001:8001"

  neo4j:
    image: neo4j:4.4
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

volumes:
  neo4j_data:
```

---

## 8. 验收标准

| 功能 | 标准 |
|------|------|
| 日志上传 | 支持.log/.txt，最大10MB，上传成功/失败有提示 |
| 模拟日志 | 每秒生成1条，WebSocket实时推送 |
| 异常检测 | 孤立森林算法，召回率>80%，误报率<20% |
| 仪表盘 | 今日异常数、Top5模式、趋势折线图 |
| 日志列表 | 时间戳、级别、内容、异常标签，支持筛选 |
| 用户标注 | 误报/确认异常按钮，记录反馈 |
| 故障排查 | 5个Agent协作，输出分析报告+修复方案 |
| 智能问答 | KG拓扑查询+RAG知识检索 |

---

## 9. 风险与决策

| 风险 | 决策 |
|------|------|
| 现有knowledge_graph是Python，后端也用Python | 复用Python后端，直接调用 |
| SQLite并发性能 | Demo阶段可接受 |
| 前端模拟日志未限流 | 前端每秒最多1条，后端异步处理 |

---

## 10. 下一步

1. 用户审核设计文档
2. 创建项目目录结构
3. 实现后端API框架
4. 实现Multi-Agent
5. 实现前端界面
6. Docker Compose部署
