"""
MCP Client — Agent 侧调用 MCP Server 的客户端

提供给 Observation Agent / ReAct Agent 使用，封装了
与 MCP Server 的 HTTP 通信，支持：
- 工具调用 (call_tool)
- 资源列表 (list_resources)
- 工具列表 (list_tools)
"""

import json
from typing import Any, Dict, List, Optional
import httpx

from ..utils.logger import get_logger
from ..core.config import settings

logger = get_logger("mcp.client")


class McpClient:
    """
    MCP Client

    通过 HTTP 调用内嵌的 MCP Server，获取 Grafana 可观测数据。

    通常由 ToolRegistry 中的 mcp_call 工具间接使用，
    也可以在代码中直接使用:
        client = McpClient()
        result = await client.call_tool("query_metrics", {"query": "..."})
    """

    def __init__(self, base_url: str = ""):
        self.base_url = (base_url or f"http://localhost:{settings.APP_PORT or 8000}").rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60,
            )
        return self._client

    async def call_tool(self, tool_name: str, params: dict = None) -> Dict[str, Any]:
        """
        调用 MCP 工具

        Args:
            tool_name: 工具名，如 query_metrics, query_logs
            params: 工具参数，如 {"query": "node_cpu_..."}

        Returns:
            工具的响应结果
        """
        client = await self._get_client()
        payload = {"tool": tool_name, "params": params or {}}

        try:
            response = await client.post(
                f"/mcp/call/{tool_name}",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"MCP call failed: {e.response.status_code} - {e.response.text[:200]}")
            return {
                "success": False,
                "error": f"MCP Server returned HTTP {e.response.status_code}",
                "tool": tool_name,
            }
        except httpx.RequestError as e:
            logger.error(f"MCP connection failed: {e}")
            return {
                "success": False,
                "error": f"Cannot connect to MCP Server: {e}",
                "tool": tool_name,
            }

    async def list_tools(self) -> List[Dict[str, Any]]:
        """获取 MCP Server 上所有可用的工具列表"""
        client = await self._get_client()
        try:
            response = await client.get("/mcp/tools")
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])
        except Exception as e:
            logger.error(f"List MCP tools failed: {e}")
            return []

    async def list_resources(self) -> List[Dict[str, Any]]:
        """获取 MCP Server 上所有可用的资源列表"""
        client = await self._get_client()
        try:
            response = await client.get("/mcp/resources")
            response.raise_for_status()
            data = response.json()
            return data.get("resources", [])
        except Exception as e:
            logger.error(f"List MCP resources failed: {e}")
            return []

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
