# MCP Observability Bridge — 通过 MCP 协议接入 Grafana/Prometheus

> **日期**: 2026-07-08
> **状态**: Implemented
> **作者**: AIOps Team
> **标签**: `mcp` `grafana` `prometheus` `observability` `agent`

---

## 1. 背景与动机

- **问题描述**：当前 Observation Agent 获取可观测数据的方式分散且不统一：
  - Prometheus 指标直接调用 `prometheus_client.py`
  - Grafana 日志通过 `GrafanaLogClient` 获取
  - 这些数据源没有被抽象成统一的协议接口，Agent 需要了解每个数据源的细节
  - 新增数据源时需要修改 Agent 代码
- **用户场景**：Agent 通过统一的 MCP 协议接口获取指标、日志、仪表盘信息、告警等非结构化数据，与具体数据源解耦。
- **现有方案不足**：
  - 已有的 `GrafanaLogClient` 和 `PrometheusClient` 是独立实现，Agent 需要分别调用不同工具
  - 没有统一的资源发现机制，Agent 无法动态知道有哪些数据可用
  - 不符合 MCP（Model Context Protocol）标准，未来难以接入 MCP 生态

## 2. 功能概述

- **功能名称**：MCP Observability Bridge
- **所属类别**：`architecture/`
- **功能类型**：新增

### 连接信息

| 服务 | 地址 | 类型 |
|------|------|------|
| **Grafana** | `http://47.76.53.232:3000` | 跳板机 nginx 代理，需补充 API Key |
| **Prometheus** | 通过 Grafana Datasource Proxy 访问 | 无需直接连接 |
| **Loki** | 通过 Grafana Datasource Proxy 访问 | 无需直接连接 |

> 注：Prometheus 和 Loki 均通过 Grafana 的数据源代理 API 访问，MCP Server 只需连接 Grafana 一个入口。

### 总体架构

```
┌──────────────────────────────────────────────────────┐
│                    AIOps Backend                       │
│                                                        │
│  ┌──────────────────┐      ┌──────────────────────┐  │
│  │  Observation     │      │  MCP Server            │  │
│  │  Agent           │─────▶│  (SSE/HTTP)            │  │
│  │  (MCP Client)    │      │  /mcp/sse + /mcp/msg   │  │
│  │                  │◀─────│  Resources + Tools      │  │
│  └──────────────────┘      └───────────┬──────────┘  │
│                                        │              │
│                         ┌──────────────┼──────────┐   │
│                         ▼              ▼          ▼   │
│              ┌──────────────┐  ┌────────────┐  ┌────┐│
│              │GrafanaLog-   │  │Grafana     │  │Pro-││
│              │Client(日志)  │  │Dashboard   │  │... ││
│              └──────┬───────┘  └─────┬──────┘  └─┬──┘│
└─────────────────────┼────────────────┼───────────┼───┘
                      ▼                ▼           ▼
               http://47.76.53.232:3000 (Grafana nginx 代理)
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         Prometheus    Loki       Alertmanager
         (数据源)      (数据源)     (数据源)
```

### 通信模型

```
Agent (MCP Client)                  MCP Server                  Grafana (47.76.53.232:3000)
        │                               │                                      │
        │  1. 发现资源列表                │                                      │
        │  GET /mcp/resources            │                                      │
        │◀────── 资源列表 ──────────────│                                      │
        │                               │                                      │
        │  2. 查询 Prometheus 指标       │                                      │
        │  POST /mcp/tools/call         │                                      │
        │  {name:"query_metrics",       │                                      │
        │   args:{query:"node_cpu_..."}}│                                      │
        │                               │──▶ GET /api/datasources/proxy/... ──▶│
        │                               │◀─── JSON 结果 ◀── (Grafana 代理 Prometheus)
        │◀───── 结构化结果 ────────────│                                      │
        │                               │                                      │
        │  3. 查询 Loki 日志             │                                      │
        │  POST /mcp/tools/call         │                                      │
        │  {name:"query_logs",          │                                      │
        │   args:{query:"{app=...}"}}   │                                      │
        │                               │──▶ GET /api/datasources/proxy/... ──▶│
        │                               │◀─── 日志数据 ◀── (Grafana 代理 Loki)
        │◀───── 结构化结果 ────────────│                                      │
```

## 3. 详细设计

### 3.1 MCP Server 模块（`app/mcp/`）

MCP Server 是一个内嵌在 FastAPI 中的服务，提供统一的 MCP 协议接口。

#### 3.1.1 目录结构

```
backend/app/mcp/
├── __init__.py             # 包初始化，FastAPI 子路由注册
├── server.py               # MCP Server 核心：FastAPI Router + SSE 端点
├── resources.py            # MCP 资源定义（Resource 发现）
├── tools.py                # MCP 工具定义（Tool 执行逻辑）
├── client.py               # Agent 端 MCP Client 封装
└── schemas.py              # MCP 协议数据结构（JSON-RPC）
```

#### 3.1.2 MCP 资源

通过 `GET /mcp/resources` 返回可用的数据资源列表，使 Agent 能动态发现可获取的数据。

| 资源 URI | 类型 | 说明 |
|---------|------|------|
| `grafana://metrics` | 资源 | 通过 Grafana 代理查询 Prometheus 指标 |
| `grafana://logs` | 资源 | 通过 Grafana 代理查询 Loki 日志 |
| `grafana://dashboards` | 资源 | Grafana 仪表盘列表 |
| `grafana://alerts` | 资源 | Grafana 告警列表 |
| `grafana://datasources` | 资源 | Grafana 数据源列表 |

#### 3.1.3 MCP 工具

通过 `POST /mcp/tools/call` 调用的可执行操作：

| 工具名称 | 参数 | 说明 |
|---------|------|------|
| `query_metrics` | query, time, duration | 通过 Grafana 代理执行 PromQL 查询 |
| `query_metrics_range` | query, start, end, step | 通过 Grafana 代理执行 PromQL 范围查询 |
| `query_logs` | query, start, end, limit | 通过 Grafana 代理查询 Loki 日志 |
| `list_dashboards` | - | 列出 Grafana 仪表盘 |
| `get_dashboard` | uid | 获取指定仪表盘详情 |
| `list_alerts` | - | 列出 Grafana 告警 |

#### 3.1.4 传输协议

使用 **SSE (Server-Sent Events) + HTTP POST** 作为 MCP 传输层：

- **SSE 端点**: `GET /mcp/sse` — 长连接，MCP Server 通过此端面向 Client 推送消息
- **消息端点**: `POST /mcp/messages` — Client 通过此端点向 Server 发送 JSON-RPC 消息
- 兼容 MCP 标准传输协议

#### 3.1.5 JSON-RPC 消息格式

```json
// Client → Server (请求)
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "query_metrics",
    "arguments": {
      "query": "node_cpu_seconds_total{mode='idle'}",
      "time": "now"
    }
  }
}

// Server → Client (响应)
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"success\": true, \"resultType\": \"vector\", \"results\": [...]}"
      }
    ]
  }
}
```

### 3.2 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `app/mcp/__init__.py` | MCP 模块初始化，注册 FastAPI 子路由 |
| 新增 | `app/mcp/server.py` | MCP Server 核心：SSE 端点 + 消息路由 |
| 新增 | `app/mcp/resources.py` | 资源定义和发现 |
| 新增 | `app/mcp/tools.py` | 工具实现（调用现有 PrometheusClient / GrafanaLogClient） |
| 新增 | `app/mcp/schemas.py` | JSON-RPC 消息结构 |
| 新增 | `app/mcp/client.py` | Agent 端 MCP Client 封装 |
| 修改 | `app/main.py` | 挂载 MCP 子路由到 FastAPI |
| 修改 | `app/agents/tool_registry.py` | 替换独立的 query_grafana_logs，改为统一 mcp_query 工具 |
| 修改 | `requirements.txt` | 添加 `mcp>=1.0.0` 依赖 |

### 3.3 MCP Client 在 Agent 侧的使用方式

Agent 通过统一的 `mcp_query` 工具与 MCP Server 交互：

```python
# ToolRegistry 中注册
self.register("mcp_call", self._mcp_call)

# 调用方式（LLM 自动选择）
mcp_call(
    tool="query_metrics",                    # MCP Server 上注册的工具名
    params={                                  # 工具参数
        "query": 'node_cpu_seconds_total{mode="idle"}'
    }
)
```

### 3.4 数据流

```
用户 → "检查集群CPU使用率"
  → intent_parse
    → skill_match (匹配 prometheus_skill)
      → react_agent (LLM)
        → 调用 mcp_call("query_metrics", ...)
          → MCP Client (agent端)
            → HTTP POST /mcp/messages (JSON-RPC)
              → MCP Server
                → Grafana 代理 API
                  → POST /api/ds/query (Grafana 统一查询接口)
                    → Grafana 查询 Prometheus 数据源
                    ← Prometheus 返回数据
                ← MCP Server 封装为标准化结果
              ← MCP Client 返回
            ← 结构化数据
          ← LLM 分析数据
        ← 生成诊断报告
      ← finalize
```

### 3.5 MCP Python SDK 使用方式

```python
# MCP Server (使用 mcp 包)
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent

server = Server("aiops-observability")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_metrics",
            description="通过 Grafana 代理查询 Prometheus 指标",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "PromQL 查询语句"},
                    "time": {"type": "string", "description": "查询时间点"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="query_logs",
            description="通过 Grafana 代理查询 Loki 日志",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "LogQL 查询语句"},
                    "start": {"type": "string", "description": "开始时间"},
                    "limit": {"type": "number", "description": "返回条数"}
                },
                "required": ["query"]
            }
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "query_metrics":
        # 通过 Grafana 代理查询 Prometheus
        result = await grafana_client.query_prometheus(arguments["query"])
        return [TextContent(type="text", text=json.dumps(result))]
    elif name == "query_logs":
        # 通过 Grafana 代理查询 Loki
        result = await grafana_client.query_logs(**arguments)
        return [TextContent(type="text", text=json.dumps(result))]
```

## 4. 变更步骤

### 4.1 Step 1: 创建 MCP 模块基础结构

- **文件**：`app/mcp/__init__.py`, `app/mcp/schemas.py`
- **操作**：定义 JSON-RPC 消息结构和包初始化

### 4.2 Step 2: 实现 MCP Server

- **文件**：`app/mcp/server.py`
- **操作**：实现 MCP 协议核心，包含：
  - SSE 端点 (`GET /mcp/sse`)
  - 消息端点 (`POST /mcp/messages`)
  - 资源列表 (grafana://metrics, grafana://logs, etc.)
  - 工具定义 (query_metrics, query_logs, list_dashboards, etc.)
  - 工具执行逻辑 (调用 GrafanaClient 代理查询)

### 4.3 Step 3: 实现 Grafana 统一客户端

- **文件**：`app/mcp/grafana_client.py`
- **操作**：封装 Grafana Data Source Proxy API 的统一客户端：
  - `query_prometheus()` — 通过 Grafana 代理查询 Prometheus
  - `query_logs()` — 通过 Grafana 代理查询 Loki（复用 GrafanaLogClient）
  - `list_dashboards()` — 列出仪表盘（复用 GrafanaDashboardGenerator）
  - `list_alerts()` — 列出告警

### 4.4 Step 4: 实现 MCP Client

- **文件**：`app/mcp/client.py`
- **操作**：Agent 端的 MCP 客户端，通过 HTTP 调用 MCP Server

### 4.5 Step 5: 注册到 FastAPI

- **文件**：`app/main.py`
- **操作**：挂载 MCP 子路由 (`/mcp`)

### 4.6 Step 6: 更新 ToolRegistry

- **文件**：`app/agents/tool_registry.py`
- **操作**：
  - 新增 `mcp_call` 统一工具
  - 保留现有 `query_grafana_logs` 工具（向后兼容）

### 4.7 Step 7: 安装依赖 & 配置

- **命令**：`pip install mcp`
- **配置**：在 `.env` 或环境变量中添加：
  ```bash
  GRAFANA_URL=http://47.76.53.232:3000
  GRAFANA_API_KEY=<your-api-key>
  ```

## 5. 影响范围

- **影响的功能**：
  - 现有的 `query_grafana_logs` 工具将保留（向后兼容），新增 `mcp_query` 统一入口
  - ToolRegistry 新增 1 个工具（`mcp_query`）
  - 新增 `app/mcp/` 模块（5 个文件）
  - FastAPI 新增 `/mcp/` 路由
- **向后兼容**：是（保留原有工具，新增 MCP 协议层）
- **需要同步更新**：
  - `requirements.txt`（添加 `mcp` 依赖）
  - `app/main.py`（挂载路由）

## 6. 验证标准

- [ ] MCP Server 启动后，`curl http://localhost:8000/mcp/resources` 返回资源列表
- [ ] MCP Server 能通过 Grafana 代理查询 Prometheus 指标 (`query_metrics`)
- [ ] MCP Server 能通过 Grafana 代理查询 Loki 日志 (`query_logs`)
- [ ] Agent 端 `mcp_call` 工具能正确调用 MCP Server 并返回数据
- [ ] SSE 长连接正常建立和通信
- [ ] 原有 `query_grafana_logs` 工具仍可用（向后兼容）
- [ ] 配置 `GRAFANA_API_KEY` 后能正常认证访问

---

## 审批记录

| 日期 | 审批人 | 结论 | 备注 |
|------|-------|------|------|
| YYYY-MM-DD | | 通过/驳回 | |
