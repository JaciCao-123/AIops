"""
MCP Server — 通过 MCP (Model Context Protocol) 暴露 Grafana 可观测数据

使用 mcp Python SDK 实现，支持 SSE 传输协议和 JSON-RPC 消息格式。

MCP Server 注册的工具:
    - query_metrics:    通过 Grafana 代理查询 Prometheus 指标
    - query_metrics_range: 查询 Prometheus 范围数据
    - query_logs:       通过 Grafana 代理查询 Loki 日志
    - list_dashboards:  列出 Grafana 仪表盘
    - get_dashboard:    获取仪表盘详情
    - list_alerts:      列出 Grafana 告警
"""

import json
import logging
from typing import Any, Dict

from ..utils.logger import get_logger

logger = get_logger("mcp.server")


class McpServer:
    """
    MCP Server 封装

    与 FastAPI 集成，通过 SSE 端点暴露 MCP 协议接口。
    内部调用 GrafanaUnifiedClient 执行实际查询。
    """

    def __init__(self):
        self._grafana_client = None
        self._initialized = False

    @property
    def grafana_url(self) -> str:
        from ..observability.config import get_observability_config
        return get_observability_config().grafana.url

    @property
    def server_name(self) -> str:
        return "aiops-observability"

    @property
    def server_version(self) -> str:
        return "1.0.0"

    async def get_grafana_client(self):
        """延迟加载 Grafana 客户端"""
        if self._grafana_client is None:
            from .grafana_client import GrafanaUnifiedClient
            self._grafana_client = GrafanaUnifiedClient()
        return self._grafana_client

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """
        处理 MCP 工具调用

        由 MCP Server 的消息处理器调用，执行对应工具并返回结果。
        """
        logger.info(f"MCP tool call: {tool_name}({arguments})")

        if tool_name == "query_metrics":
            return await self._call_query_metrics(arguments)
        elif tool_name == "query_metrics_range":
            return await self._call_query_metrics_range(arguments)
        elif tool_name == "query_logs":
            return await self._call_query_logs(arguments)
        elif tool_name == "list_dashboards":
            return await self._call_list_dashboards(arguments)
        elif tool_name == "get_dashboard":
            return await self._call_get_dashboard(arguments)
        elif tool_name == "list_alerts":
            return await self._call_list_alerts(arguments)
        elif tool_name == "get_rag_overview":
            client = await self.get_grafana_client()
            return await client.get_rag_overview(
                lookback=arguments.get("lookback", "1h"),
            )
        elif tool_name == "get_gpu_overview":
            client = await self.get_grafana_client()
            return await client.get_gpu_overview(
                lookback=arguments.get("lookback", "1h"),
            )
        elif tool_name == "get_vllm_overview":
            client = await self.get_grafana_client()
            return await client.get_vllm_overview(
                lookback=arguments.get("lookback", "1h"),
            )
        else:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

    async def _call_query_metrics(self, args: dict) -> dict:
        client = await self.get_grafana_client()
        return await client.query_metrics(
            query=args.get("query", ""),
            time=args.get("time", ""),
        )

    async def _call_query_metrics_range(self, args: dict) -> dict:
        client = await self.get_grafana_client()
        return await client.query_metrics_range(
            query=args.get("query", ""),
            start=args.get("start", ""),
            end=args.get("end", ""),
            step=args.get("step", ""),
        )

    async def _call_query_logs(self, args: dict) -> dict:
        client = await self.get_grafana_client()
        return await client.query_logs(
            query=args.get("query", ""),
            start=args.get("start", ""),
            end=args.get("end", ""),
            limit=args.get("limit", 100),
        )

    async def _call_list_dashboards(self, args: dict) -> dict:
        client = await self.get_grafana_client()
        return await client.list_dashboards(
            query=args.get("query", ""),
        )

    async def _call_get_dashboard(self, args: dict) -> dict:
        client = await self.get_grafana_client()
        return await client.get_dashboard(
            uid=args.get("uid", ""),
        )

    async def _call_list_alerts(self, args: dict) -> dict:
        client = await self.get_grafana_client()
        return await client.list_alerts(
            state=args.get("state", ""),
        )

    async def close(self):
        """关闭资源"""
        if self._grafana_client:
            await self._grafana_client.close()
            self._grafana_client = None


# ─── FastAPI 集成 ──────────────────────────────────────

"""
FastAPI 路由集成方式（在 main.py 中挂载）:

```python
from app.mcp.router import mcp_router
app.include_router(mcp_router, prefix="/mcp")
```

MCP Server 的 SSE 端点：
    GET  /api/mcp/sse       -- SSE 连接端点
    POST /api/mcp/messages  -- 消息接收端点

替代方案：也支持通过 HTTP POST 直接调用工具：
    POST /api/mcp/call/{tool_name}
    Body: {"query": "..."}
```
"""
