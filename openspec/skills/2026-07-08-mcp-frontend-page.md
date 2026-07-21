# MCP 数据源管理页面

> **日期**: 2026-07-08
> **状态**: Implemented
> **作者**: AIOps Team
> **标签**: `frontend` `mcp` `datasource` `observability`

---

## 1. 背景与动机

- **问题描述**：MCP Server 已在后端实现，但用户无法在前端看到数据源的状态、可用工具和查询结果。
- **用户场景**：运维人员希望在前端查看 Grafana 连接状态、浏览可用的数据查询工具、快速测试 PromQL/LogQL 查询，而不需要切换到 Grafana UI。
- **现有方案不足**：现有页面分散（日志、告警、链路追踪），没有统一的"数据源"入口来查看和管理可观测数据连接。

## 2. 功能概述

- **功能名称**：MCP 数据源管理页面
- **所属类别**：`skills/`
- **功能类型**：新增

### 页面结构

```
数据源页面 (/datasources)
├── 状态概览卡片
│   ├── MCP Server 状态 (运行中/已停止)
│   ├── Grafana 连接状态 (已连接/断开)
│   └── 可用工具数量
├── 工具列表 (Table)
│   ├── 工具名、描述、参数表
│   └── "试运行" 按钮 → 弹出输入参数对话框 → 执行并展示结果
└── Grafana 快捷链接
    ├── 跳转到 Grafana Explorer
    ├── 跳转到 Grafana 仪表盘
    └── 跳转到 Grafana 告警
```

## 3. 详细设计

### 3.1 文件变更清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `frontend/src/pages/Datasources.tsx` | MCP 数据源页面组件 |
| 修改 | `frontend/src/App.tsx` | 添加路由 `/datasources` 和侧边栏菜单项 |
| 修改 | `frontend/src/types/index.ts` | 添加 MCP 相关类型定义 |
| 修改 | `frontend/src/services/api.ts` | 添加 MCP API 方法 |
| 修改 | `backend/app/mcp/router.py` | 新增 `/mcp/status` 健康检查端点 |

### 3.2 类型定义

```typescript
// MCP 工具信息
interface McpToolInfo {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, { type: string; description: string }>;
    required: string[];
  };
}

// MCP 状态
interface McpStatus {
  server: string;
  version: string;
  status: "running" | "stopped";
  grafana_connected: boolean;
  tool_count: number;
  resource_count: number;
}

// MCP 工具调用结果
interface McpCallResult {
  success: boolean;
  error?: string;
  result_count?: number;
  results?: any[];
  [key: string]: any;
}
```

### 3.3 API 端点

| 前端 API 方法 | 后端地址 | 说明 |
|-------------|---------|------|
| `mcpApi.getStatus()` | `GET /mcp/status` | MCP Server 健康状态 |
| `mcpApi.getTools()` | `GET /mcp/tools` | 可用工具列表 |
| `mcpApi.callTool(name, params)` | `POST /mcp/call/{name}` | 调用工具并返回结果 |

### 3.4 页面 UI 设计

```
┌─────────────────────────────────────────────────────────┐
│  MCP 数据源                                              │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ MCP Server   │  │ Grafana      │  │ 可用工具      │  │
│  │ ● 运行中     │  │ ● 已连接     │  │ 6 个          │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 工具列表                           [+ 刷新]     │    │
│  ├────────┬──────────────┬──────────┬────────────┤    │
│  │ 工具名  │ 描述         │ 参数     │ 操作        │    │
│  ├────────┼──────────────┼──────────┼────────────┤    │
│  │ query_ │ 通过Grafana  │ query    │ [▶ 试运行] │    │
│  │ metrics│ 查询指标     │ (必填)   │            │    │
│  ├────────┼──────────────┼──────────┼────────────┤    │
│  │ query_ │ 查询Loki     │ query    │ [▶ 试运行] │    │
│  │ logs   │ 日志         │ (必填)   │            │    │
│  └────────┴──────────────┴──────────┴────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Grafana 快捷链接                                 │    │
│  │ [📊 打开 Grafana] [📋 仪表盘列表] [🔔 告警中心] │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 3.5 后端状态端点

在 `router.py` 中新增：

```python
@router.get("/status")
async def mcp_status():
    """MCP Server 健康状态检查"""
    server = get_server()
    try:
        # 检查 Grafana 连接
        client = await server.get_grafana_client()
        grafana_client = await client._get_client()
        health_resp = await grafana_client.get("/api/health")
        grafana_ok = health_resp.status_code == 200
    except:
        grafana_ok = False
    
    return {
        "server": server.server_name,
        "version": server.server_version,
        "status": "running",
        "grafana_connected": grafana_ok,
        "tool_count": len(MCP_TOOLS),
        "resource_count": len(MCP_RESOURCES),
    }
```

## 4. 变更步骤

### 4.1 Step 1: 后端添加 `/mcp/status` 端点

- **文件**：`backend/app/mcp/router.py`

### 4.2 Step 2: 前端添加 MCP 类型和 API

- **文件**：`frontend/src/types/index.ts`, `frontend/src/services/api.ts`

### 4.3 Step 3: 创建 Datasources 页面组件

- **文件**：`frontend/src/pages/Datasources.tsx`

### 4.4 Step 4: 注册路由和侧边栏

- **文件**：`frontend/src/App.tsx`
- **操作**：添加路由 `/datasources` 和侧边栏菜单项

## 5. 影响范围

- **影响的功能**：前端新增一个页面，侧边栏新增一个菜单项
- **向后兼容**：是（仅新增，不影响现有功能）
- **需要同步更新**：`index.ts`, `api.ts`, `App.tsx`, `router.py`

## 6. 验证标准

- [ ] 访问 `/datasources` 能看到 MCP 状态卡片（含 Grafana 连接状态）
- [ ] 工具列表能正确展示 6 个 MCP 工具信息
- [ ] 点击"试运行"输入参数后能返回查询结果
- [ ] Grafana 快捷链接能正确跳转
- [ ] 侧边栏菜单正确显示且可点击

---

## 审批记录

| 日期 | 审批人 | 结论 | 备注 |
|------|-------|------|------|
| YYYY-MM-DD | | 通过/驳回 | |
