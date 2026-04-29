# RESTful API 设计与实现总结

## 一、项目 RESTful API 概览

本项目基于 **FastAPI** 框架构建了一套完整的 RESTful API 体系，涵盖用户认证、告警管理、知识图谱查询、Multi-Agent 诊断、根因分析、链路追踪等核心功能。

### API 模块结构

```
aiops-platform/backend/app/api/
├── __init__.py          # API Router 聚合
├── auth.py              # 用户认证与授权 API
├── alerts.py            # 告警接入与聚合 API
├── approval.py          # 审批工作流 API
├── agent.py             # 单 Agent 诊断 API
├── multi_agent.py       # Multi-Agent 协同 API
├── knowledge.py         # 知识图谱与 RAG API
├── logs.py              # 日志管理 API
├── rca.py               # 根因分析 API
├── tracing.py           # 链路追踪 API
└── terminal.py          # Web 终端 (WebSocket)
```

---

## 二、RESTful API 设计规范

### 2.1 URL 设计原则

| 设计原则 | 示例 | 说明 |
|---------|------|------|
| **资源名词化** | `/api/auth/users` | 使用名词表示资源，而非动词 |
| **层级清晰** | `/api/knowledge/topology` | 通过路径表达资源层级关系 |
| **版本控制** | `/api/v1/...` (可扩展) | 便于 API 版本迭代 |
| **统一前缀** | `/api/{module}` | 所有业务 API 统一 `/api` 前缀 |

### 2.2 HTTP 方法语义

| HTTP 方法 | 用途 | 示例 |
|-----------|------|------|
| **GET** | 获取资源 | `GET /api/auth/me` 获取当前用户信息 |
| **POST** | 创建资源/执行操作 | `POST /api/auth/login` 用户登录 |
| **DELETE** | 删除资源 | `DELETE /api/auth/users/{user_id}` 删除用户 |
| **PUT/PATCH** | 更新资源 | (项目中主要用 POST 替代) |

### 2.3 响应格式统一

```json
{
    "code": 200,
    "message": "success",
    "data": { ... }
}
```

**错误响应**:
```json
{
    "detail": "错误描述信息"
}
```

---

## 三、核心 API 模块详解

### 3.1 用户认证 API (`auth.py`)

**路由前缀**: `/api/auth`

| 端点 | 方法 | 功能 | 认证要求 |
|------|------|------|----------|
| `/register` | POST | 用户注册 | 无 |
| `/login` | POST | 用户登录 (OAuth2) | 无 |
| `/logout` | POST | 用户登出 | 需要认证 |
| `/me` | GET | 获取当前用户信息 | 需要认证 |
| `/users` | GET | 获取用户列表 | 需要管理员权限 |
| `/users/{user_id}` | DELETE | 删除用户 | 需要管理员权限 |

**核心实现**:

```python
# OAuth2 密码模式认证
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# JWT Token 生成
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

# 权限控制装饰器
def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user
```

**RBAC 权限模型**:
- 管理员权限: `logs:view`, `diagnose:execute`, `terminal:access`, `users:manage`
- 普通用户权限: `logs:view`, `diagnose:view`, `knowledge:view`

---

### 3.2 告警管理 API (`alerts.py`)

**路由前缀**: `/api/alerts`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/webhook` | POST | Alertmanager Webhook | 接收 Prometheus Alertmanager 推送的告警 |
| `/ingest` | POST | 直接接入告警 | 支持其他系统直接推送告警 |
| `/health` | GET | 健康检查 | 服务状态探测 |

**告警聚合流程**:

```
Alertmanager → POST /api/alerts/webhook
                    ↓
            格式转换 (convert_alertmanager_to_cluster_format)
                    ↓
            智能聚合 (Drain + Word2Vec + DBSCAN)
                    ↓
            返回聚合结果
```

**请求体示例**:
```json
{
    "receiver": "aiops-receiver",
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "HighCPU", "instance": "server-01"},
            "annotations": {"summary": "CPU usage > 90%"}
        }
    ]
}
```

---

### 3.3 Multi-Agent 诊断 API (`multi_agent.py`)

**路由前缀**: `/api/multi-agent`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/process` | POST | 完整诊断流程 | 同步返回完整诊断结果 |
| `/process/stream` | POST | 流式诊断 | SSE 实时返回各阶段结果 |
| `/ner` | POST | NER 实体识别 | 仅执行意图解析 |
| `/knowledge` | POST | 知识查询 | 仅查询知识图谱和 RAG |
| `/observability` | POST | 可观测性查询 | 仅查询指标和日志 |
| `/health` | GET | 健康检查 | 服务状态探测 |

**Multi-Agent 协作流程**:

```
POST /api/multi-agent/process
        ↓
1. IntentParseAgent    → NER 实体识别、意图分类
        ↓
2. KnowledgeExpertAgent → 知识图谱查询、RAG 检索
        ↓
3. ObservabilityAnalystAgent → 指标/日志/链路查询
        ↓
4. MasterAgent         → 整合信息、决策推理
        ↓
5. ActionExecuteAgent  → 执行修复操作 (如需)
        ↓
返回诊断报告
```

**流式响应 (SSE)**:
```python
@router.post("/process/stream")
async def process_multi_agent_stream(request: MultiAgentRequest):
    async def event_generator():
        async for event in orchestrator.process_query_stream(request.query):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

---

### 3.4 知识图谱 API (`knowledge.py`)

**路由前缀**: `/api/knowledge`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/query` | GET | 查询知识图谱 | 支持服务名和自然语言查询 |
| `/rag/query` | POST | RAG 检索增强 | 调用 RAG 服务获取知识 |
| `/topology` | GET | 获取服务拓扑 | 返回服务依赖关系图 |
| `/qa/chat` | GET | 知识问答 | 结合 KG 和 RAG 的问答接口 |

**Neo4j Cypher 查询示例**:
```python
# 查询服务依赖关系
result = session.run("""
    MATCH (s {name: $name})-[r:DEPENDS_ON]->(dep)
    RETURN s.name as service, collect({name: dep.name, type: labels(dep)[0]}) as deps
""", name=service_name)
```

---

### 3.5 根因分析 API (`rca.py`)

**路由前缀**: `/api/rca`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/analyze` | POST | 执行根因分析 | 整合 Metrics/Traces/Logs 多维分析 |
| `/report/{report_id}` | GET | 获取分析报告 | 按 ID 查询历史报告 |
| `/history` | GET | 获取历史报告 | 列出最近的分析报告 |

**根因分析响应结构**:
```json
{
    "report_id": "abc12345",
    "service_name": "order-service",
    "status": "completed",
    "hypotheses": [
        {
            "title": "数据库连接池耗尽",
            "confidence_score": 0.92,
            "severity": "critical",
            "evidences": [...],
            "remediation_steps": [...]
        }
    ],
    "algorithms_used": ["time_series_correlation", "trace_analysis"]
}
```

---

### 3.6 链路追踪 API (`tracing.py`)

**路由前缀**: `/api/traces`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/search` | GET | 搜索 Trace 列表 | 支持服务名、错误、慢请求过滤 |
| `/{trace_id}` | GET | 获取 Trace 详情 | 返回完整 Span 信息 |
| `/dependency` | GET | 服务依赖关系 | 返回服务调用拓扑 |
| `/analyze` | POST | Trace 分析 | 性能瓶颈和错误分析 |

**查询参数示例**:
```
GET /api/traces/search?service_name=order-service&error_only=true&lookback=1h&limit=50
```

---

### 3.7 审批工作流 API (`approval.py`)

**路由前缀**: `/api/approval`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/reply` | POST | 处理邮件回复 | 解析邮件内容判断批准/拒绝 |
| `/status/{approval_id}` | GET | 获取审批状态 | 查询审批进度 |
| `/approve/{approval_id}` | POST | 手动批准 | API 方式批准操作 |
| `/reject/{approval_id}` | POST | 手动拒绝 | API 方式拒绝操作 |
| `/pending` | GET | 待审批列表 | 列出所有待审批操作 |

---

### 3.8 日志管理 API (`logs.py`)

**路由前缀**: `/api/logs`

| 端点 | 方法 | 功能 | 说明 |
|------|------|------|------|
| `/upload` | POST | 上传日志文件 | 支持 .log/.txt 文件 |
| `/ingest` | POST | 接入单条日志 | 实时日志接入 |
| `` | GET | 查询日志列表 | 支持分页和过滤 |
| `/{log_id}/feedback` | POST | 提交反馈 | 用户反馈异常检测结果 |
| `/stats` | GET | 日志统计 | 异常率、级别分布等 |
| `/ws/simulate` | WebSocket | 日志模拟推送 | 实时推送模拟日志 |

---

## 四、RESTful API 设计亮点

### 4.1 依赖注入模式

使用 FastAPI 的 `Depends` 实现依赖注入，解耦认证、数据库等依赖：

```python
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"code": 200, "data": user_to_response(current_user).model_dump()}

@router.get("/users")
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return {"code": 200, "data": [user_to_response(u).model_dump() for u in users]}
```

### 4.2 Pydantic 数据验证

使用 Pydantic 模型进行请求/响应数据验证：

```python
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_admin: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
```

### 4.3 后台任务处理

对于耗时操作，使用 `BackgroundTasks` 异步处理：

```python
@router.post("/diagnose")
async def diagnose(
    request: DiagnoseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_diagnosis_pipeline, task_id, request.user_input, db)
    return {"task_id": task_id, "status": "pending"}
```

### 4.4 流式响应 (SSE)

支持 Server-Sent Events 实现实时数据推送：

```python
@router.post("/process/stream")
async def process_multi_agent_stream(request: MultiAgentRequest):
    async def event_generator():
        async for event in orchestrator.process_query_stream(request.query):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 4.5 WebSocket 支持

对于需要双向通信的场景（如 Web Terminal），使用 WebSocket：

```python
@app.add_api_websocket_route("/ws/terminal", websocket_terminal)

async def websocket_terminal(websocket: WebSocket):
    await websocket.accept()
    session = TerminalSession()
    await session.start()
    
    while True:
        message = await websocket.receive_text()
        data = json.loads(message)
        if data.get("type") == "input":
            await session.write(data.get("data", ""))
```

---

## 五、面试问答指南

### Q1: 请介绍一下你项目中 RESTful API 的设计？

**回答要点**:

> 在 AIops 智能运维平台项目中，我基于 FastAPI 框架设计了一套完整的 RESTful API 体系，主要包含以下几个模块：
>
> **1. API 设计原则**:
> - 遵循 RESTful 规范，使用名词化 URL 表示资源，如 `/api/auth/users`、`/api/alerts/webhook`
> - HTTP 方法语义化：GET 获取资源、POST 创建/执行、DELETE 删除
> - 统一的响应格式：`{code, message, data}` 三段式结构
>
> **2. 核心模块**:
> - **认证模块** (`/api/auth`): 实现 OAuth2 密码模式 + JWT Token 认证，支持 RBAC 权限控制
> - **告警模块** (`/api/alerts`): 提供 Alertmanager Webhook 接入，实现告警智能聚合
> - **Multi-Agent 模块** (`/api/multi-agent`): 支持同步和流式两种诊断模式
> - **知识图谱模块** (`/api/knowledge`): 整合 Neo4j 和 RAG 服务
>
> **3. 技术亮点**:
> - 使用 FastAPI 的依赖注入实现认证和权限解耦
> - Pydantic 模型进行严格的数据验证
> - BackgroundTasks 处理耗时诊断任务
> - SSE 流式响应实现实时诊断反馈

---

### Q2: 你是如何实现 API 认证和权限控制的？

**回答要点**:

> 我实现了基于 **OAuth2 + JWT + RBAC** 的认证授权体系：
>
> **1. 认证流程**:
> - 用户通过 `POST /api/auth/login` 提交用户名密码
> - 服务端验证后生成 JWT Token (有效期 24 小时)
> - 客户端后续请求在 Header 中携带 `Authorization: Bearer <token>`
>
> **2. 权限控制**:
> - 使用 FastAPI 的 `Depends` 依赖注入实现权限拦截
> - `get_current_user`: 验证 Token 并获取当前用户
> - `require_admin`: 检查是否为管理员权限
>
> **3. RBAC 模型**:
> - 用户表存储 `roles`、`permissions`、`scope` 字段 (JSON 格式)
> - 管理员权限: `logs:edit`, `diagnose:execute`, `terminal:access`
> - 普通用户权限: `logs:view`, `diagnose:view`
>
> **代码示例**:
> ```python
> @router.get("/users")
> def list_users(current_user: User = Depends(require_admin)):
>     # 只有管理员可以访问
>     ...
> ```

---

### Q3: 你是如何处理耗时 API 请求的？

**回答要点**:

> 对于诊断类耗时操作，我采用了三种策略：
>
> **1. 后台任务 (BackgroundTasks)**:
> - 创建任务后立即返回 task_id
> - 客户端通过轮询 `GET /api/agent/status/{task_id}` 获取进度
>
> **2. 流式响应 (SSE)**:
> - 使用 Server-Sent Events 实时推送各阶段结果
> - 客户端可以实时看到诊断进度
> ```python
> return StreamingResponse(event_generator(), media_type="text/event-stream")
> ```
>
> **3. WebSocket**:
> - 对于 Web Terminal 等需要双向通信的场景
> - 实现了完整的终端会话管理

---

### Q4: 告警聚合 API 是如何设计的？

**回答要点**:

> 告警聚合 API 设计了两种接入方式：
>
> **1. Alertmanager Webhook 接入**:
> - 端点: `POST /api/alerts/webhook`
> - 接收 Prometheus Alertmanager 推送的告警
> - 自动解析告警格式并转换为内部格式
>
> **2. 直接接入**:
> - 端点: `POST /api/alerts/ingest`
> - 支持其他系统直接推送告警
>
> **聚合流程**:
> 1. 格式转换: 将 Alertmanager 格式转换为统一格式 `{time, node_id, raw_msg}`
> 2. 智能聚合: 使用 Drain + Word2Vec + DBSCAN 算法进行聚类
> 3. 返回结果: 聚类数量、各类代表告警、根因识别
>
> **性能指标**:
> - 告警压缩率: 2:1 ~ 64:1
> - 处理延迟: < 100ms / 100 条告警

---

### Q5: 你是如何保证 API 的可维护性的？

**回答要点**:

> 我从以下几个方面保证 API 的可维护性：
>
> **1. 模块化设计**:
> - 每个 API 模块独立文件，职责单一
> - 通过 `APIRouter` 组织路由，支持前缀和标签
>
> **2. 数据验证**:
> - 使用 Pydantic 模型定义请求/响应结构
> - 自动生成 OpenAPI 文档 (Swagger UI)
>
> **3. 统一响应格式**:
> - 成功: `{code: 200, message: "success", data: {...}}`
> - 错误: 使用 HTTPException 抛出，FastAPI 自动处理
>
> **4. 文档自动生成**:
> - FastAPI 自动生成 Swagger 文档 (`/docs`)
> - 类型注解 + Pydantic 模型自动生成 Schema
>
> **5. 健康检查**:
> - 每个模块提供 `/health` 端点
> - 支持服务监控和负载均衡探测

---

## 六、API 端点汇总表

| 模块 | 前缀 | 端点数 | 核心功能 |
|------|------|--------|----------|
| 认证 | `/api/auth` | 6 | 注册、登录、用户管理 |
| 告警 | `/api/alerts` | 3 | Webhook 接入、告警聚合 |
| Multi-Agent | `/api/multi-agent` | 5 | 诊断流程、NER、知识查询 |
| 知识图谱 | `/api/knowledge` | 4 | KG 查询、RAG、拓扑 |
| 根因分析 | `/api/rca` | 3 | RCA 分析、报告查询 |
| 链路追踪 | `/api/traces` | 4 | Trace 搜索、依赖分析 |
| 审批 | `/api/approval` | 5 | 审批流程、邮件回复 |
| 日志 | `/api/logs` | 5 | 日志上传、查询、统计 |
| 终端 | `/ws/terminal` | 1 | WebSocket 终端 |

**总计**: 约 **36 个 API 端点** + 1 个 WebSocket 端点

---

## 七、技术栈总结

| 技术 | 用途 |
|------|------|
| **FastAPI** | Web 框架，自动生成 OpenAPI 文档 |
| **Pydantic** | 数据验证和序列化 |
| **SQLAlchemy** | ORM 数据库操作 |
| **JWT (jose)** | Token 生成和验证 |
| **bcrypt** | 密码加密 |
| **OAuth2PasswordBearer** | OAuth2 认证方案 |
| **httpx** | 异步 HTTP 客户端 (调用 RAG 服务) |
| **WebSocket** | 双向通信 (Web Terminal) |
| **SSE (StreamingResponse)** | 流式响应 |
