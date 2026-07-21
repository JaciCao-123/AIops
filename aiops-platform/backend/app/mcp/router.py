"""
FastAPI 路由 — 挂载 MCP Server

提供两种访问方式：
1. SSE + POST (MCP 标准协议): 用于标准 MCP Client
2. HTTP POST 直接调用: 用于 Agent 端快速调用
"""

import json
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..utils.logger import get_logger
from .schemas import JsonRpcRequest, JsonRpcResponse, MCP_TOOLS, MCP_RESOURCES
from .server import McpServer

logger = get_logger("mcp.router")
router = APIRouter(prefix="/api/mcp", tags=["mcp"])

# 全局 MCP Server 实例
_mcp_server: Optional[McpServer] = None


def get_server() -> McpServer:
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = McpServer()
    return _mcp_server


# ─── 请求/响应模型 ──────────────────────────────────────


class ToolCallRequest(BaseModel):
    """HTTP 工具调用请求"""
    tool: str
    params: dict = {}


# ─── MCP 协议端点 ────────────────────────────────────────


@router.get("/sse")
async def sse_endpoint(request: Request):
    """
    MCP SSE 端点 — 建立 Server-Sent Events 长连接

    MCP Client 通过此端点建立连接，接收 Server 推送的消息。
    """
    async def event_generator():
        server = get_server()
        # 发送 endpoint 事件告知 Client 消息发送地址
        yield f"event: endpoint\ndata: /api/mcp/messages\n\n"

        # 发送 server 信息
        server_info = json.dumps({
            "name": server.server_name,
            "version": server.server_version,
        })
        yield f"event: server\ndata: {server_info}\n\n"

        # 保持连接
        try:
            while True:
                await asyncio.sleep(30)
                yield f"event: heartbeat\ndata: \n\n"
        except asyncio.CancelledError:
            logger.info("SSE connection closed")
        finally:
            await server.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages")
async def messages_endpoint(request: Request):
    """
    MCP 消息端点 — 接收 Client 发送的 JSON-RPC 消息

    Client 通过此端点发送工具调用、资源列表等请求。
    """
    body = await request.json()
    jsonrpc_req = JsonRpcRequest(**body)
    server = get_server()

    try:
        if jsonrpc_req.method == "tools/list":
            # 返回工具列表
            tools = [t.to_mcp_format() for t in MCP_TOOLS]
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": jsonrpc_req.id,
                "result": {"tools": tools},
            })

        elif jsonrpc_req.method == "resources/list":
            # 返回资源列表
            resources = [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mime_type,
                }
                for r in MCP_RESOURCES
            ]
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": jsonrpc_req.id,
                "result": {"resources": resources},
            })

        elif jsonrpc_req.method == "tools/call":
            # 执行工具调用
            params = jsonrpc_req.params or {}
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = await server.handle_tool_call(tool_name, arguments)
            result_text = json.dumps(result, ensure_ascii=False, default=str)

            return JSONResponse({
                "jsonrpc": "2.0",
                "id": jsonrpc_req.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text,
                        }
                    ],
                },
            })

        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": jsonrpc_req.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {jsonrpc_req.method}",
                },
            })

    except Exception as e:
        logger.error(f"MCP message error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": jsonrpc_req.id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}",
            },
        })


# ─── HTTP 直接调用端点 (Agent 端使用) ──────────────────


@router.post("/call/{tool_name}")
async def direct_tool_call(tool_name: str, request: ToolCallRequest):
    """
    直接调用 MCP 工具 (HTTP POST 方式)

    Agent 端通过此端点快速调用工具，无需走完整 MCP 协议握手。

    请求体:
        {"tool": "query_metrics", "params": {"query": "..."}}

    响应:
        工具执行结果的 JSON
    """
    if tool_name != request.tool:
        raise HTTPException(
            status_code=400,
            detail=f"Tool name mismatch: path={tool_name}, body={request.tool}",
        )

    server = get_server()
    result = await server.handle_tool_call(request.tool, request.params)
    return JSONResponse(content=result)


@router.get("/tools")
async def list_tools():
    """列出所有可用的 MCP 工具 (用于 Agent 发现能力)"""
    return JSONResponse(content={
        "tools": [t.to_mcp_format() for t in MCP_TOOLS],
        "tool_count": len(MCP_TOOLS),
    })


@router.get("/status")
async def mcp_status():
    """MCP Server 健康状态检查"""
    server = get_server()
    grafana_ok = False
    try:
        client = await server.get_grafana_client()
        grafana_client = await client._get_client()
        health_resp = await grafana_client.get("/api/health")
        grafana_ok = health_resp.status_code == 200
    except Exception:
        grafana_ok = False

    return {
        "server": server.server_name,
        "version": server.server_version,
        "status": "running",
        "grafana_connected": grafana_ok,
        "grafana_url": server.grafana_url,
        "tool_count": len(MCP_TOOLS),
        "resource_count": len(MCP_RESOURCES),
    }


@router.get("/resources")
async def list_resources():
    """列出所有可用的 MCP 资源"""
    return JSONResponse(content={
        "resources": [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
            }
            for r in MCP_RESOURCES
        ],
        "resource_count": len(MCP_RESOURCES),
    })
