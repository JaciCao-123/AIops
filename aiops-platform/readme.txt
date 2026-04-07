# AIOps 智能运维平台

基于多智能体架构的自动化运维诊断平台，集成了知识图谱、RAG知识库、动态决策引擎、邮件审批系统和 Web Terminal，实现智能故障诊断、根因分析和自动化运维。

## 📋 目录

- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [多智能体系统](#多智能体系统)
- [工作流程](#工作流程)
- [技术栈](#技术栈)
- [安装部署](#安装部署)
- [使用指南](#使用指南)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [API 接口](#api-接口)

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           前端界面层 (React + TypeScript)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  用户认证    │  │  故障诊断    │  │  Web Terminal │  │  知识图谱    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           后端服务层 (FastAPI)                               │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Multi-Agent 协调器 (Orchestrator)                   │  │
│  │                                                                        │  │
│  │   ┌─────────────┐    ┌─────────────────────────────────────────────┐  │  │
│  │   │ SkillManager│───▶│              MasterAgent                    │  │  │
│  │   │ (技能文件)   │    │         (动态决策 + Function Calling)        │  │  │
│  │   └─────────────┘    └─────────────────────────────────────────────┘  │  │
│  │                                    │                                   │  │
│  │                                    ▼                                   │  │
│  │   ┌───────────────────────────────────────────────────────────────┐   │  │
│  │   │                      ToolRegistry                             │   │  │
│  │   │  • execute_command      • send_approval_email                 │   │  │
│  │   │  • save_diagnosis_plan  • check_approval_status               │   │  │
│  │   │  • save_execution_output• execute_approved_command            │   │  │
│  │   │  • query_knowledge_graph• ask_user_confirmation               │   │  │
│  │   └───────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  用户认证系统    │  │  WebSocket终端  │  │  邮件审批系统    │             │
│  │  (JWT + RBAC)   │  │  (xterm.js)     │  │  (SMTP)         │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│        ┌─────────────────────┼─────────────────────┐                       │
│        ▼                     ▼                     ▼                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  Neo4j       │  │  RAG 知识库   │  │  阿里云监控  │                     │
│  │  (知识图谱)   │  │  (SOP文档)   │  │  (实例状态)  │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## ✨ 核心功能

### 1. 用户认证系统
- **用户注册**: 支持新用户注册，密码 bcrypt 加密
- **用户登录**: JWT Token 认证，支持自动刷新
- **角色权限**: 管理员 (admin) 和普通用户 (user) 两种角色
- **权限控制**: Web Terminal 仅管理员可访问

### 2. 智能故障诊断
- **意图识别**: 自动识别用户查询意图和关键实体
- **动态决策**: LLM 根据 skill 文件动态规划诊断步骤
- **Function Calling**: LLM 自主调用工具执行操作
- **根因分析**: 综合分析收集的信息，定位问题根源
- **解决方案**: 提供具体可执行的修复建议

### 3. 邮件审批系统
- **审批请求**: 高风险操作自动发送审批邮件
- **邮件回复**: 支持 APPROVE/REJECT 关键词审批
- **审批记录**: 所有审批记录持久化存储
- **自动执行**: 审批通过后自动执行操作

### 4. Web Terminal
- **实时终端**: 基于 xterm.js 的 Web 终端
- **WebSocket**: 实时双向通信
- **PTY 支持**: 真实终端体验
- **权限控制**: 仅管理员可访问

### 5. 知识图谱集成
- **拓扑可视化**: 展示服务间的依赖关系
- **影响分析**: 分析故障影响范围
- **历史查询**: 查询节点的变更历史和关联信息

### 6. RAG 知识库
- **SOP 文档检索**: 检索相关故障排查文档
- **相似案例匹配**: 匹配历史故障处理案例
- **知识增强**: 结合知识库提供更准确的诊断建议

## 🤖 多智能体系统

### 核心架构：动态决策模式

系统采用 **LLM + Function Calling** 的动态决策模式，不再使用硬编码流程：

```
┌─────────────────────────────────────────────────────────────────┐
│                      MasterAgent (大脑中枢)                      │
│                                                                  │
│   1. 加载相关 Skill 文件 (debug_skill.md, login_skill.md)       │
│   2. 构建 LLM Prompt (包含 skill 内容和可用工具)                 │
│   3. LLM 动态规划并调用工具                                      │
│   4. 根据工具返回结果继续决策                                    │
│   5. 循环直到得出最终结论                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1. IntentParseAgent (意图解析代理)
**职责**: 入口网关，准确识别意图和实体

**核心能力**:
- NER 命名实体识别
- 意图分类 (DIAGNOSE / QUERY_STATUS / EXECUTE_FIX / GENERAL_QA)
- 关键词提取
- 模糊输入处理

**提取实体类型**:
- SERVICE: 服务名称
- SERVER: 服务器/主机名
- IP: IP 地址
- SYMPTOM: 故障现象
- METRIC: 指标名称 (CPU/内存/磁盘等)
- ACTION: 操作动作

### 2. MasterAgent (主控代理)
**职责**: 大脑中枢，动态决策

**核心能力**:
- 根据 skill 文件动态生成诊断计划
- 使用 Function Calling 调用工具
- 根据执行结果动态决策下一步
- 生成最终诊断报告

**关键特性**:
- 不使用硬编码流程
- LLM 自主决策执行步骤
- 支持邮件审批高风险操作
- 最大迭代次数保护

### 3. SkillManager (技能管理器)
**职责**: 加载和管理技能文件

**核心能力**:
- 加载 debug_skill.md (故障排查技能)
- 加载 login_skill.md (连接方法技能)
- 根据关键词匹配相关技能
- 提供技能内容给 LLM

### 4. ToolRegistry (工具注册中心)
**职责**: 注册和执行工具

**可用工具**:

| 工具名称 | 功能 | 风险等级 |
|---------|------|---------|
| `execute_command` | 在目标服务器执行命令 | low-medium |
| `save_diagnosis_plan` | 保存诊断计划 | low |
| `save_execution_output` | 保存执行输出 | low |
| `send_approval_email` | 发送审批邮件 | low |
| `check_approval_status` | 检查审批状态 | low |
| `execute_approved_command` | 审批后执行命令 | high |
| `query_knowledge_graph` | 查询知识图谱 | low |
| `query_rag` | 查询 RAG 知识库 | low |
| `ask_user_confirmation` | 请求用户确认 | low |

### 5. EmailSender (邮件发送器)
**职责**: 发送审批邮件和处理回复

**核心能力**:
- 发送 HTML 格式审批邮件
- 管理待审批操作
- 处理邮件回复审批
- 审批记录持久化

## 🔄 工作流程

### 动态诊断流程

```
用户查询: "8.136.226.231 内存使用率过高"
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: 意图识别 (IntentParseAgent)                        │
│ • 识别服务器: 8.136.226.231                                 │
│ • 识别症状: 内存使用率过高                                   │
│ • 意图分类: DIAGNOSE                                        │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 2: 动态决策 (MasterAgent + LLM)                       │
│                                                              │
│ Iteration 1:                                                │
│   LLM 决策 → save_diagnosis_plan                            │
│   → 保存诊断计划: free -m, ps aux --sort=-%mem              │
│                                                              │
│ Iteration 2:                                                │
│   LLM 决策 → execute_command                                │
│   → 执行: ssh 8.136.226.231 "free -m"                       │
│                                                              │
│ Iteration 3:                                                │
│   LLM 决策 → save_execution_output                          │
│   → 保存执行结果                                             │
│                                                              │
│ Iteration 4:                                                │
│   LLM 决策 → execute_command                                │
│   → 执行: ssh 8.136.226.231 "ps aux --sort=-%mem | head"    │
│                                                              │
│ Iteration 5:                                                │
│   LLM 决策 → send_approval_email                            │
│   → 发送审批邮件: kill -9 1539                              │
│                                                              │
│ Iteration 6:                                                │
│   LLM 决策 → 最终结论                                        │
│   → 问题类型: memory                                        │
│   → 根本原因: stress 进程占用 3GB 内存                      │
│   → 建议操作: kill -9 1539 (需审批)                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 3: 邮件审批 (EmailSender)                             │
│ • 发送审批邮件到管理员邮箱                                   │
│ • 管理员回复 APPROVE 或 REJECT                              │
│ • 审批通过后自动执行操作                                     │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
返回诊断结果
```

## 🛠️ 技术栈

### 后端
- **框架**: FastAPI
- **数据库**: SQLite (aiops.db)
- **图数据库**: Neo4j
- **AI 能力**: OpenAI API (通义千问 Qwen)
- **认证**: JWT + bcrypt
- **终端**: WebSocket + PTY
- **邮件**: SMTP (SSL)
- **自动化**: Ansible
- **监控集成**: 阿里云 SDK

### 前端
- **框架**: React + TypeScript
- **UI 组件**: Ant Design
- **终端**: xterm.js
- **构建工具**: Vite
- **状态管理**: React Context + Hooks

### 关键依赖
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.2
pydantic-settings==2.1.0
openai==1.6.1
neo4j==5.14.1
python-jose[cryptography]==3.3.0
bcrypt==4.1.2
websockets==12.0
python-dotenv==1.0.0
```

## 🚀 安装部署

### 1. 环境要求
- Python 3.8+
- Node.js 16+
- Neo4j 5.x (可选，用于知识图谱)
- RAG 服务 (可选，用于知识库检索)

### 2. 后端部署

```bash
cd aiops-platform/backend

# 安装依赖
pip install -r requirements.txt

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置必要的参数
# 详细配置见下方"配置说明"部分

# 创建数据目录
mkdir -p data/approvals

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### 3. 前端部署

```bash
cd aiops-platform/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 4. Neo4j 部署 (可选)

```bash
# 使用 Docker 启动 Neo4j
docker run \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.14.1
```

访问 `http://localhost:7474`，使用 `neo4j/password` 登录。

## 📝 使用指南

### 1. 用户注册与登录

访问 `http://localhost:5173/login`：

- **注册**: 点击"注册"按钮，填写用户名和密码
- **登录**: 使用注册的账号登录
- **权限**: 
  - 普通用户: 可使用诊断、知识图谱等功能
  - 管理员: 额外可使用 Web Terminal

### 2. 故障诊断

访问 `http://localhost:5173/diagnose`，输入故障描述：

**示例 1: 磁盘空间问题**
```
8.136.226.231 /dev/shm 出现了磁盘爆满
```

**示例 2: 内存使用率过高**
```
8.136.226.231 出现了 memory 使用率过高的情况
```

**示例 3: 需要审批的操作**
```
8.136.226.231 内存过高，帮我排查并处理
```

### 3. Web Terminal (管理员)

以管理员身份登录后，访问 `http://localhost:5173/terminal`：

- 实时终端操作
- 支持所有 shell 命令
- WebSocket 实时通信

### 4. 邮件审批

当系统检测到高风险操作时：

1. 自动发送审批邮件到管理员邮箱
2. 邮件包含操作详情和审批 ID
3. 管理员回复邮件：
   - `APPROVE <审批ID>` - 批准执行
   - `REJECT <审批ID>` - 拒绝执行
4. 系统自动处理审批结果

### 5. 知识图谱查询

访问 `http://localhost:5173/knowledge-graph`，输入节点名称查询：

**示例**:
```
order-service
```

## ⚙️ 配置说明

### 环境变量 (.env)

```bash
# 通用配置
APP_NAME="AIOps Platform"
DEBUG=True
SECRET_KEY="your-secret-key-change-in-production"

# 数据库配置
DATABASE_URL="sqlite:///./data/aiops.db"

# Neo4j 配置 (知识图谱)
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"

# RAG 服务配置
RAG_SERVICE_URL="http://localhost:8001"

# OpenAI API 配置
OPENAI_API_KEY="your_api_key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
OPENAI_MODEL="qwen-plus"

# 阿里云 API 配置 (用于云主机监控)
ALIYUN_ACCESS_KEY_ID="your_access_key_id"
ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"
ALIYUN_REGION_ID="cn-hangzhou"

# SMTP 邮件配置 (用于审批邮件)
SMTP_HOST="smtp.163.com"
SMTP_PORT=465
SMTP_USER="your_email@163.com"
SMTP_PASSWORD="your_smtp_password"  # 163邮箱使用授权码
SMTP_FROM_EMAIL="your_email@163.com"
```

### debug_skill.md

系统核心知识库，定义了各类故障的排查方法：

**主要章节**:
1. **磁盘问题排查** - 磁盘使用率检查、大文件定位、/dev/shm 处理
2. **网络问题排查** - 连通性检测、DNS 解析、链路追踪
3. **内存问题排查** - 内存使用概览、进程监控、OOM Killer
4. **云服务器特殊检查** - 阿里云实例状态检查

### login_skill.md

定义了各类资源的连接方法和诊断工作流：

**连接方法**:
- 阿里云 ECS (SSH/Ansible)
- Kubernetes Pod (kubectl)
- MySQL 数据库

## 📂 项目结构

```
aiops-platform/
├── backend/                        # 后端服务
│   ├── app/
│   │   ├── agents/                # 多智能体系统
│   │   │   ├── intent_parse.py   # 意图解析
│   │   │   ├── master.py         # 主控代理 (动态决策)
│   │   │   ├── knowledge.py      # 知识专家
│   │   │   ├── observability.py  # 可观测性分析
│   │   │   ├── action_execute.py # 执行代理
│   │   │   ├── orchestrator.py   # 协调器
│   │   │   ├── skill_manager.py  # 技能管理器
│   │   │   └── tool_registry.py  # 工具注册中心
│   │   ├── api/                   # API 接口
│   │   │   ├── agent.py          # Agent API
│   │   │   ├── auth.py           # 认证 API
│   │   │   ├── approval.py       # 审批 API
│   │   │   ├── terminal.py       # WebSocket 终端
│   │   │   ├── knowledge.py      # 知识图谱 API
│   │   │   └── multi_agent.py    # Multi-Agent API
│   │   ├── core/                  # 核心配置
│   │   │   ├── config.py         # 配置管理
│   │   │   ├── database.py       # 数据库
│   │   │   └── security.py       # 安全相关
│   │   ├── utils/                 # 工具类
│   │   │   ├── email_sender.py   # 邮件发送
│   │   │   ├── file_manager.py   # 文件管理
│   │   │   └── aliyun_monitor.py # 阿里云监控
│   │   └── main.py               # 应用入口
│   ├── data/                      # 数据目录
│   │   ├── approvals/            # 审批记录
│   │   ├── diagnosis/            # 诊断计划
│   │   └── outputs/              # 执行输出
│   ├── .env                       # 环境变量
│   ├── debug_skill.md            # 故障排查技能
│   └── login_skill.md            # 连接方法技能
├── frontend/                      # 前端服务
│   ├── src/
│   │   ├── pages/                # 页面组件
│   │   │   ├── Login.tsx        # 登录页
│   │   │   ├── Register.tsx     # 注册页
│   │   │   ├── Dashboard.tsx    # 仪表盘
│   │   │   ├── Diagnose.tsx     # 诊断页
│   │   │   ├── Terminal.tsx     # Web终端
│   │   │   ├── KnowledgeGraph.tsx
│   │   │   └── QA.tsx
│   │   ├── contexts/             # React Context
│   │   │   ├── AuthContext.tsx  # 认证状态
│   │   │   └── TerminalContext.tsx # 终端状态
│   │   ├── services/             # API 服务
│   │   └── types/                # TypeScript 类型
│   └── package.json
└── README.md
```

## 🔌 API 接口

### 认证接口

| 方法 | 路径 | 描述 |
|-----|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/auth/me` | 获取当前用户信息 |

### 诊断接口

| 方法 | 路径 | 描述 |
|-----|------|------|
| POST | `/api/multi-agent/process` | 执行诊断 |
| GET | `/api/multi-agent/history` | 获取历史记录 |

### 审批接口

| 方法 | 路径 | 描述 |
|-----|------|------|
| POST | `/api/approval/reply` | 处理邮件回复 |
| GET | `/api/approval/status/{id}` | 获取审批状态 |
| POST | `/api/approval/approve/{id}` | 手动批准 |
| POST | `/api/approval/reject/{id}` | 手动拒绝 |
| GET | `/api/approval/pending` | 获取待审批列表 |

### WebSocket

| 路径 | 描述 |
|------|------|
| `/ws/terminal` | Web Terminal 连接 |

## � 中间文件管理

所有中间文件自动保存在 `backend/data/` 目录：

```
data/
├── approvals/                    # 审批记录
│   └── f95fd092.json            # 审批详情
├── diagnosis_plan/              # 诊断计划
│   └── 20260328_225210.json
├── execution_output/            # 执行输出
│   └── 8.136.226.231_20260328.txt
└── full_results/                # 完整结果
    └── 20260328_225210.json
```

## � 邮件审批示例

### 审批邮件内容

```
主题: [AIOps] 操作审批请求 - Kill high memory process

尊敬的管理员：

系统检测到需要人工审批的操作，请确认是否执行。

📋 操作详情
操作类型: Kill high memory process stress (PID 1539)
目标服务器: 8.136.226.231
风险等级: MEDIUM
影响范围: 终止 stress 进程将释放约 3GB 内存

🔧 执行命令
kill -9 1539

✅ 审批方式
审批ID: f95fd092
请回复: APPROVE f95fd092 或 REJECT f95fd092
```

### 审批记录

```json
{
  "approval_id": "f95fd092",
  "operation": "Kill high memory process stress (PID 1539)",
  "risk": "medium",
  "commands": ["kill -9 1539"],
  "target_host": "8.136.226.231",
  "status": "approved",
  "approved_at": "2026-03-28T22:52:11",
  "approved_by": "18565693545@163.com"
}
```

## 🎯 核心特性

### 1. 智能诊断
- ✅ 自动意图识别和实体提取
- ✅ 动态诊断计划生成 (基于 skill 文件)
- ✅ LLM Function Calling 自主决策
- ✅ 基于知识库的根因分析
- ✅ 可解释的决策过程

### 2. 自动化执行
- ✅ SSH 自动执行诊断命令
- ✅ 中间文件自动保存
- ✅ 执行结果自动解析
- ✅ Web Terminal 实时操作

### 3. 安全审批
- ✅ 高风险操作邮件审批
- ✅ 审批记录持久化
- ✅ 支持邮件回复审批
- ✅ 审批后自动执行

### 4. 用户管理
- ✅ 用户注册与登录
- ✅ JWT Token 认证
- ✅ 角色权限控制 (RBAC)
- ✅ 密码 bcrypt 加密

### 5. 知识增强
- ✅ Neo4j 知识图谱集成
- ✅ RAG 知识库检索
- ✅ Skill 文件动态加载
- ✅ 历史案例匹配

## 📄 License

MIT License
