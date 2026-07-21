# Grafana 日志读取工具

> **日期**: 2026-07-08
> **状态**: Implemented
> **作者**: AIOps Team
> **标签**: `grafana` `loki` `logs` `observability` `tool`

---

## 1. 背景与动机

- **问题描述**：当前 observability agent 使用 mock 数据进行分析，无法读取 Grafana/Loki 中的真实日志数据，导致诊断结果缺乏实时性。
- **用户场景**：用户希望 Agent 能通过自然语言查询 Grafana 上托管的 Loki 日志，例如 "查询最近 1 小时 aiops-backend 的错误日志"。
- **现有方案不足**：
  - `DataSourceManager._load_from_loki()` 直接调用 Loki API（端口 3100），但生产环境通常不暴露 Loki 端口，需通过 Grafana 反向代理（端口 3000）。
  - `GrafanaDashboardGenerator` 只管理仪表盘，不支持日志查询。
  - 无对应工具注册在 `ToolRegistry` 中，ReAct Agent 无法调用。

## 2. 功能概述

- **功能名称**：`query_grafana_logs`
- **所属类别**：`tools/`
- **功能类型**：新增

## 3. 详细设计

### 3.1 功能描述

新增一个 `query_grafana_logs` 工具，通过 Grafana API 代理查询 Loki 数据源的日志。支持：
- 按 LogQL 查询语句过滤日志
- 按时间范围查询（开始/结束时间，支持相对时间如 "最近 1 小时"）
- 限制返回条数
- 支持流式/分页查询大结果集

### 3.2 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `app/agents/grafana_log_client.py` | Grafana Loki 日志查询客户端 |
| 修改 | `app/agents/tool_registry.py` | 注册 `query_grafana_logs` 工具 |
| 修改 | `app/agents/__init__.py` | 导出新模块 |

### 3.3 接口定义

**Tool 签名**（ReAct Agent 可调用）：

```python
query_grafana_logs(
    query: str,           # LogQL 查询语句，如 '{app="aiops-backend"} |= "error"'
    start: str = "",      # 开始时间，如 "1h ago" 或 "2026-07-08T00:00:00Z"
    end: str = "",        # 结束时间，如 "now" 或 "2026-07-08T12:00:00Z"
    limit: int = 100,     # 最大返回条数
    datasource: str = ""  # Grafana 数据源名称，默认使用 "Loki"
) -> dict
```

**返回格式**：

```json
{
  "success": true,
  "datasource": "Loki",
  "query": "{app=\"aiops-backend\"} |= \"error\"",
  "time_range": "1h ago → now",
  "result_count": 42,
  "results": [
    {
      "timestamp": "2026-07-08T10:00:00Z",
      "line": "ERROR: connection refused",
      "labels": {"app": "aiops-backend", "level": "error"}
    }
  ],
  "stats": {
    "query_time_ms": 235,
    "ingester_reached": true
  }
}
```

### 3.4 数据流

```
用户请求 → intent_parse (意图识别)
    → skill_match (匹配 log_analysis_skill / prometheus_skill)
    → react_agent (LLM 决定调用 query_grafana_logs 工具)
        → GrafanaLogClient.query_logs()
            → GET /api/datasources/proxy/{uid}/loki/api/v1/query_range
        → 返回结构化日志数据
    → LLM 分析日志结果
    → finalize (汇总输出)
```

Grafana 代理请求流程：

```
Tool → http://grafana:3000/api/datasources/proxy/{loki_uid}/loki/api/v1/query_range
         ↓
    Grafana Server (认证 + 代理)
         ↓
    Loki (实际日志存储)
```

### 3.5 Grafana API 调用方式

通过 Grafana 的 **DataSource Proxy API** 访问 Loki，无需直接暴露 Loki 端口：

```
GET /api/datasources/proxy/{datasource_id}/loki/api/v1/query_range
```

认证方式（复用现有 `GrafanaConfig`）：
- Bearer Token: `Authorization: Bearer {api_key}`
- 或 Basic Auth: `Authorization: Basic base64({username}:{password})`

## 4. 变更步骤

### 4.1 Step 1: 创建 Grafana 日志查询客户端

- **文件**：`app/agents/grafana_log_client.py`
- **操作**：新建文件
- **内容**：
  - 类 `GrafanaLogClient`
  - 构造函数读取 `GrafanaConfig`（url, api_key, username, password）
  - 方法 `get_loki_datasource_uid()` → 查询 Grafana API 获取 Loki 数据源的 UID
  - 方法 `query_logs(query, start, end, limit)` → 通过代理 API 查询 Loki
  - 方法 `_parse_time_range(start, end)` → 解析相对时间

### 4.2 Step 2: 注册工具到 ToolRegistry

- **文件**：`app/agents/tool_registry.py`
- **操作**：在 `_register_default_tools()` 中新增 `query_grafana_logs` 工具
- **代码示例**：

```python
def _tool_query_grafana_logs(self, query: str, start: str = "", end: str = "", limit: int = 100, datasource: str = "") -> dict:
    """通过 Grafana 查询 Loki 日志"""
    client = GrafanaLogClient()
    return client.query_logs(query, start, end, limit, datasource)
```

### 4.3 Step 3: 更新 __init__.py

- **文件**：`app/agents/__init__.py`
- **操作**：添加 `from .grafana_log_client import GrafanaLogClient`

## 5. 影响范围

- **影响的功能**：observability agent 的日志分析能力
- **向后兼容**：是（新增工具，不影响现有工具）
- **需要同步更新**：`tool_registry.py`、`__init__.py`

## 6. 验证标准

- [ ] 单元测试：`GrafanaLogClient.query_logs()` 能正确解析时间和返回格式
- [ ] 集成测试：连接真实 Grafana 实例能返回日志结果
- [ ] ReAct Agent 能成功调用 `query_grafana_logs` 工具
- [ ] 错误处理：Grafana 不可达时返回友好错误信息

---

## 审批记录

| 日期 | 审批人 | 结论 | 备注 |
|------|-------|------|------|
| YYYY-MM-DD | | 通过/驳回 | |
