"""
MCP 协议数据结构定义

基于 JSON-RPC 2.0 + MCP (Model Context Protocol) 规范。
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── JSON-RPC 2.0 基础消息 ──────────────────────────────


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 请求"""
    jsonrpc: str = "2.0"
    id: str | int
    method: str
    params: Optional[dict] = None


class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 错误"""
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 响应"""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Optional[Any] = None
    error: Optional[JsonRpcError] = None


# ─── MCP 资源定义 ────────────────────────────────────────


class McpResourceDefinition(BaseModel):
    """MCP Resource 定义"""
    uri: str = Field(..., description="资源 URI")
    name: str = Field(..., description="资源名称")
    description: str = Field("", description="资源描述")
    mime_type: str = Field("application/json", description="MIME 类型")


# ─── MCP 工具定义 ────────────────────────────────────────


class McpToolParameter(BaseModel):
    """MCP Tool 参数定义"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False


class McpToolDefinition(BaseModel):
    """MCP Tool 定义"""
    name: str = Field(..., description="工具名称")
    description: str = Field("", description="工具描述")
    input_schema: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "required": [],
        },
        description="JSON Schema 输入参数定义",
    )

    def to_mcp_format(self) -> dict:
        """转换为 MCP SDK 兼容格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# ─── Agent 端工具调用参数 ──────────────────────────────


class McpCallParams(BaseModel):
    """mcp_call 工具的调用参数"""
    tool: str = Field(..., description="MCP Server 上注册的工具名")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数",
    )


# ─── 预定义的工具和资源列表 ─────────────────────────────


# MCP Server 暴露的资源
MCP_RESOURCES: List[McpResourceDefinition] = [
    McpResourceDefinition(
        uri="grafana://metrics",
        name="Prometheus Metrics",
        description="通过 Grafana 代理查询 Prometheus 指标",
    ),
    McpResourceDefinition(
        uri="grafana://logs",
        name="Loki Logs",
        description="通过 Grafana 代理查询 Loki 日志",
    ),
    McpResourceDefinition(
        uri="grafana://dashboards",
        name="Grafana Dashboards",
        description="Grafana 仪表盘列表",
    ),
    McpResourceDefinition(
        uri="grafana://alerts",
        name="Grafana Alerts",
        description="Grafana 告警列表",
    ),
    McpResourceDefinition(
        uri="grafana://datasources",
        name="Grafana Data Sources",
        description="Grafana 数据源列表",
    ),
]

# MCP Server 暴露的工具
MCP_TOOLS: List[McpToolDefinition] = [
    McpToolDefinition(
        name="query_metrics",
        description="通过 Grafana 代理查询 Prometheus 指标，支持 PromQL 即时查询",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PromQL 查询语句，如 node_cpu_seconds_total{mode='idle'}",
                },
                "time": {
                    "type": "string",
                    "description": "查询时间点，如 'now' 或 ISO 格式时间",
                },
            },
            "required": ["query"],
        },
    ),
    McpToolDefinition(
        name="query_metrics_range",
        description="通过 Grafana 代理查询 Prometheus 范围数据",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PromQL 查询语句",
                },
                "start": {
                    "type": "string",
                    "description": "开始时间，如 '1h ago' 或 ISO 格式",
                },
                "end": {
                    "type": "string",
                    "description": "结束时间，如 'now' 或 ISO 格式",
                },
                "step": {
                    "type": "string",
                    "description": "步长，如 '15s'",
                },
            },
            "required": ["query"],
        },
    ),
    McpToolDefinition(
        name="query_logs",
        description="通过 Grafana 代理查询 Loki 日志",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "LogQL 查询语句，如 {app='aiops-backend'} |= 'error'",
                },
                "start": {
                    "type": "string",
                    "description": "开始时间，如 '1h ago' 或 ISO 格式",
                },
                "end": {
                    "type": "string",
                    "description": "结束时间，如 'now' 或 ISO 格式",
                },
                "limit": {
                    "type": "number",
                    "description": "最大返回日志条数，默认 100",
                },
            },
            "required": ["query"],
        },
    ),
    McpToolDefinition(
        name="list_dashboards",
        description="列出 Grafana 仪表盘列表",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词（可选）",
                },
            },
            "required": [],
        },
    ),
    McpToolDefinition(
        name="get_dashboard",
        description="获取 Grafana 仪表盘详情",
        input_schema={
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "仪表盘 UID",
                },
            },
            "required": ["uid"],
        },
    ),
    McpToolDefinition(
        name="list_alerts",
        description="列出 Grafana 告警",
        input_schema={
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "告警状态过滤，如 'alerting'、'firing'",
                },
            },
            "required": [],
        },
    ),
    McpToolDefinition(
        name="get_rag_overview",
        description="获取 RAG Operations Overview 健康快照，返回 RAG 服务请求量、缓存命中率、质量指标、节点耗时、Rerank 指标及最近 ERROR 日志",
        input_schema={
            "type": "object",
            "properties": {
                "lookback": {
                    "type": "string",
                    "description": "错误日志回看窗口，如 '1h'、'30m'，默认 '1h'",
                },
            },
            "required": [],
        },
    ),
    McpToolDefinition(
        name="get_gpu_overview",
        description="获取 System & GPU Overview 健康快照，返回 CPU/内存/磁盘使用率、GPU 利用率/显存/温度/功耗、系统负载及 I/O 指标",
        input_schema={
            "type": "object",
            "properties": {
                "lookback": {
                    "type": "string",
                    "description": "预留参数，默认 '1h'",
                },
            },
            "required": [],
        },
    ),
    McpToolDefinition(
        name="get_vllm_overview",
        description="获取 vLLM 推理引擎健康快照，返回引擎状态、KV Cache 使用率、运行中/等待请求数、QPS、TTFT(p50/p95/p99)、Token 吞吐与累计量",
        input_schema={
            "type": "object",
            "properties": {
                "lookback": {
                    "type": "string",
                    "description": "预留参数，默认 '1h'",
                },
            },
            "required": [],
        },
    ),
]
