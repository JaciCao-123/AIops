"""
MCP (Model Context Protocol) Observability Bridge

通过 MCP 协议标准化 Observation Agent 获取 Grafana/Prometheus 数据的方式。
Agent 通过 mcp_call 工具与 MCP Server 交互，统一数据获取入口。

架构:
    Agent (MCP Client) → mcp_call()
        → HTTP POST /api/mcp/messages (JSON-RPC)
            → MCP Server (mcp Python SDK)
                → GrafanaUnifiedClient
                    → Grafana API (47.76.53.232:3000)
                        → Prometheus 代理查询
                        → Loki 代理查询
                        → 仪表盘/告警列表

使用方式:
    # Agent 端 (LLM 自动选择工具)
    result = await mcp_call("query_metrics", {"query": "node_cpu_seconds_total"})
    
    # 或直接使用 MCP Client
    client = McpClient()
    result = await client.call_tool("query_metrics", {"query": "..."})
"""

from .grafana_client import GrafanaUnifiedClient
from .client import McpClient
from .server import McpServer
from .router import router as mcp_router
from .schemas import (
    JsonRpcRequest,
    JsonRpcResponse,
    McpToolDefinition,
    McpResourceDefinition,
    McpCallParams,
    MCP_TOOLS,
    MCP_RESOURCES,
)

__all__ = [
    "GrafanaUnifiedClient",
    "McpClient",
    "McpServer",
    "mcp_router",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "McpToolDefinition",
    "McpResourceDefinition",
    "McpCallParams",
    "MCP_TOOLS",
    "MCP_RESOURCES",
]
