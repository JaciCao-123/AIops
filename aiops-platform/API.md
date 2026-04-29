# AIOps API 文档

本文档详细描述了 AIOps 智能运维平台的所有 API 接口。

## 目录

- [认证接口](#认证接口)
- [Agent 接口](#agent接口)
- [LangGraph 多智能体接口](#langgraph-多智能体接口)
- [知识图谱接口](#知识图谱接口)
- [AI 助手接口](#ai-助手接口)
- [审批接口](#审批接口)
- [日志接口](#日志接口)
- [告警接口](#告警接口)
- [链路追踪接口](#链路追踪接口)
- [RCA 接口](#rca-接口)
- [可观测性接口](#可观测性接口)
- [WebSocket](#websocket)

## 认证接口

### 用户注册

```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "string",
  "email": "string",
  "password": "string",
  "is_admin": false
}
```

**响应**:
```json
{
  "code": 200,
  "message": "注册成功",
  "data": {
    "userId": 1,
    "username": "string",
    "email": "string"
  }
}
```

### 用户登录

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=string&password=string
```

**响应**:
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "userId": 1,
      "username": "string",
      "email": "string",
      "roles": ["admin"],
      "permissions": ["*"]
    }
  }
}
```

### 获取当前用户信息

```http
GET /api/auth/me
Authorization: Bearer <token>
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "userId": 1,
    "username": "string",
    "email": "string",
    "roles": ["admin"],
    "permissions": ["*"]
  }
}
```

### 用户登出

```http
POST /api/auth/logout
Authorization: Bearer <token>
```

## Agent 接口

### 处理用户查询

```http
POST /api/multi-agent/process
Content-Type: application/json

{
  "query": "order-service 响应变慢",
  "session_id": "optional-session-id"
}
```

**响应**:
```json
{
  "task_id": "uuid",
  "status": "processing",
  "result": {
    "diagnosis": "...",
    "root_cause": "...",
    "recommendations": []
  }
}
```

### 获取任务状态

```http
GET /api/agent/task/{task_id}
```

**响应**:
```json
{
  "task_id": "uuid",
  "status": "completed",
  "created_at": "2024-04-29T10:00:00",
  "result": {}
}
```

### 获取历史记录

```http
GET /api/agent/history?limit=10
```

## LangGraph 多智能体接口

### 处理诊断请求

```http
POST /api/multi-agent-lg/process
Content-Type: application/json

{
  "query": "order-service 响应变慢，CPU 使用率过高",
  "session_id": "test-session-001"
}
```

**响应**:
```json
{
  "query": "order-service 响应变慢，CPU 使用率过高",
  "intent_data": {
    "intent": "DIAGNOSE",
    "confidence": 0.95,
    "entities": {
      "service": "order-service",
      "symptom": "响应变慢"
    }
  },
  "matched_skills": ["debug_skill", "gnn_rca_skill"],
  "diagnosis_result": {
    "root_cause": "...",
    "recommendations": []
  },
  "iteration_count": 3
}
```

### 流式处理诊断请求

```http
POST /api/multi-agent-lg/process/stream
Content-Type: application/json

{
  "query": "诊断 MySQL 死锁问题",
  "session_id": "test-session-002"
}
```

**响应** (SSE 流):
```
event: node_complete
data: {"node": "intent_parse", "result": {...}}

event: node_complete
data: {"node": "skill_match", "result": {...}}

event: done
data: {"status": "completed"}
```

### 审批操作

```http
POST /api/multi-agent-lg/approve
Content-Type: application/json

{
  "session_id": "test-session-001",
  "approved": true,
  "ssh_user": "root"
}
```

### 获取会话状态

```http
GET /api/multi-agent-lg/state/{session_id}
```

### 健康检查

```http
GET /api/multi-agent-lg/health
```

**响应**:
```json
{
  "status": "healthy",
  "service": "multi-agent-langgraph",
  "framework": "LangGraph",
  "features": ["state_graph", "checkpoint", "human_in_the_loop", "streaming", "conditional_routing"]
}
```

## 知识图谱接口

### 查询知识图谱

```http
GET /api/knowledge/query?service=order-service
GET /api/knowledge/query?query=查询所有服务器
```

**响应**:
```json
{
  "query": "查询 order-service 的详细信息",
  "result": {
    "service": "order-service",
    "properties": {},
    "dependencies": [],
    "runs_on": [],
    "connections": []
  },
  "source": "neo4j_kg"
}
```

### RAG 知识库查询

```http
POST /api/knowledge/rag/query
Content-Type: application/json

{
  "query": "如何处理数据库连接池耗尽",
  "top_k": 5
}
```

**响应**:
```json
{
  "query": "如何处理数据库连接池耗尽",
  "answer": "根据知识库内容生成的回答...",
  "documents": [
    {
      "file": "sop-database.md",
      "snippet": "数据库连接池应急扩容步骤..."
    }
  ],
  "source": "ops_rag_service",
  "best_score": 0.85
}
```

### 获取拓扑图

```http
GET /api/knowledge/topology?service=order-service&depth=2
```

**响应**:
```json
{
  "nodes": [
    {
      "id": "node-1",
      "label": "order-service",
      "type": "Service",
      "properties": {}
    }
  ],
  "edges": [
    {
      "source": "node-1",
      "target": "node-2",
      "type": "DEPENDS_ON"
    }
  ],
  "source": "neo4j_kg"
}
```

## AI 助手接口

### AI 对话

```http
POST /api/ai-chat/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "如何排查 CPU 使用率过高？"}
  ]
}
```

**响应**:
```json
{
  "response": "排查 CPU 使用率过高的步骤：\n1. 使用 top 命令查看..."
}
```

### 清空对话历史

```http
DELETE /api/ai-chat/history
```

### 健康检查

```http
GET /api/ai-chat/health
```

**响应**:
```json
{
  "status": "healthy",
  "service": "ai-chat",
  "model": "qwen-plus",
  "configured": true
}
```

## 审批接口

### 获取审批状态

```http
GET /api/approval/status/{id}
```

### 手动批准

```http
POST /api/approval/approve/{id}
```

### 手动拒绝

```http
POST /api/approval/reject/{id}
```

### 获取待审批列表

```http
GET /api/approval/pending
```

## 日志接口

### 获取日志列表

```http
GET /api/logs?level=ERROR&is_anomaly=true&limit=100
```

### 上传日志文件

```http
POST /api/logs/upload
Content-Type: multipart/form-data

file: <log-file>
```

### 提交反馈

```http
POST /api/logs/{log_id}/feedback
Content-Type: application/json

{
  "feedback_type": true
}
```

### 获取日志统计

```http
GET /api/logs/stats
```

### 写入日志

```http
POST /api/logs/ingest
Content-Type: application/json

{
  "level": "ERROR",
  "content": "Connection timeout",
  "source": "order-service"
}
```

## 告警接口

### 获取告警列表

```http
GET /api/alerts?status=open&severity=critical&limit=100
```

### 获取聚类告警

```http
GET /api/alerts/clustered?lookback=1h
```

### 写入告警

```http
POST /api/alerts/ingest
Content-Type: application/json

{
  "level": "critical",
  "message": "CPU usage over 90%",
  "service": "order-service",
  "labels": {
    "host": "prod-server-01"
  }
}
```

### 获取告警统计

```http
GET /api/alerts/stats?lookback=24h
```

## 链路追踪接口

### 搜索链路

```http
GET /api/traces/search?service_name=order-service&error_only=true&limit=50
```

### 获取链路详情

```http
GET /api/traces/{trace_id}
```

### 获取服务依赖

```http
GET /api/traces/dependency?lookback=24h
```

### 分析链路

```http
POST /api/traces/analyze
Content-Type: application/json

{
  "service_name": "order-service",
  "error_only": true,
  "lookback": "1h"
}
```

## RCA 接口

### 执行根因分析

```http
POST /api/rca/analyze
Content-Type: application/json

{
  "service_name": "order-service",
  "time_window_minutes": 30,
  "include_logs": true,
  "include_traces": true
}
```

### 获取分析报告

```http
GET /api/rca/report/{report_id}
```

### 获取历史报告

```http
GET /api/rca/history?limit=10
```

## 可观测性接口

### 获取指标数据

```http
GET /api/observability/metrics?query=cpu_usage&lookback=1h
```

### 获取系统健康状态

```http
GET /api/observability/health
```

### 获取服务列表

```http
GET /api/observability/services
```

## WebSocket

### Web Terminal

```
ws://localhost:8000/ws/terminal
```

**消息格式**:

输入:
```json
{"type": "input", "data": "ls -la\n"}
```

调整大小:
```json
{"type": "resize", "rows": 24, "cols": 80}
```

输出:
```json
{"type": "output", "data": "total 64\ndrwxr-xr-x  ..."}
```

错误:
```json
{"type": "error", "data": "Connection closed"}
```

## 错误响应

所有接口在发生错误时返回统一格式：

```json
{
  "detail": "错误描述信息"
}
```

常见 HTTP 状态码：

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
