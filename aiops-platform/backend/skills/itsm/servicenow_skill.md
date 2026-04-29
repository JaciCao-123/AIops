# ServiceNow ITSM Skill - 工单与变更查询技能

## 概述

连接 ServiceNow ITSM 平台，查询 CMDB 配置项、事件工单、变更记录、问题记录，并分析变更是否可能是问题的根因。

## 核心能力

| 能力 | 描述 |
|------|------|
| **CMDB 查询** | 查询服务器、网络设备、应用等配置项信息 |
| **变更记录查询** | 查询节点的变更历史，分析变更与问题的关联 |
| **事件工单查询** | 查询关联的事件工单 |
| **问题记录查询** | 查询关联的问题记录 |
| **变更根因分析** | 分析最近变更是否可能是问题的根因 |
| **综合健康检查** | 整合 CMDB、工单、变更，生成健康报告 |

## 技术架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ServiceNow ITSM 集成架构                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    AIops Multi-Agent                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │
│  │  │ MasterAgent  │  │Observability │  │ KnowledgeExpert  │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │   │
│  │         └─────────────────┼───────────────────┘            │   │
│  │                           ▼                                 │   │
│  │              ┌────────────────────────┐                     │   │
│  │              │     ToolRegistry       │                     │   │
│  │              │  - query_servicenow_ci │                     │   │
│  │              │  - query_servicenow_   │                     │   │
│  │              │    changes             │                     │   │
│  │              │  - query_servicenow_   │                     │   │
│  │              │    incidents           │                     │   │
│  │              │  - analyze_change_     │                     │   │
│  │              │    as_root_cause       │                     │   │
│  │              └───────────┬────────────┘                     │   │
│  └──────────────────────────┼──────────────────────────────────┘   │
│                             │                                      │
│  ┌──────────────────────────┼──────────────────────────────────┐   │
│  │                ServiceNow Client (统一连接器)                │   │
│  │  ┌──────────────────────┴──────────────────────┐            │   │
│  │  │  • 连接管理 (connect/close)                  │            │   │
│  │  │  • 认证 (Basic Auth)                        │            │   │
│  │  │  • 请求封装 (GET/POST)                      │            │   │
│  │  │  • 错误处理                                  │            │   │
│  │  └──────────────────────┬──────────────────────┘            │   │
│  └──────────────────────────┼──────────────────────────────────┘   │
│                             │ REST API                             │
│                             ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     ServiceNow Instance                      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │   │
│  │  │ CMDB (CI)    │ │ Change       │ │ Incident / Problem   │ │   │
│  │  │ 配置管理数据库│ │ 变更管理     │ │ 事件/问题管理        │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 模块路径

```
aiops-platform/backend/
├── app/
│   └── utils/
│       └── servicenow_client.py    # ServiceNow 统一连接器
│
└── skills/
    └── itsm/
        └── servicenow_skill.md     # 本文件
```

## 前置条件

### 环境变量配置

在 `.env` 文件中配置 ServiceNow 连接信息：

```bash
# ServiceNow 配置
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
SERVICENOW_API_VERSION=v2
SERVICENOW_TIMEOUT=30
```

### 权限要求

ServiceNow 用户需要以下角色：
- `itil` - 基础 ITIL 角色
- `cmdb_read` - CMDB 读取权限
- `incident_read` - 事件工单读取权限
- `problem_read` - 问题记录读取权限
- `change_read` - 变更记录读取权限

## 工具调用

### 1. query_servicenow_ci

查询 ServiceNow CMDB 中的配置项信息。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ci_name | string | 否 | 配置项名称（支持模糊匹配） |
| ci_type | string | 否 | 配置项类型：server, network_device, application, database, cluster |
| ip_address | string | 否 | IP 地址 |
| status | string | 否 | 运行状态：operational, non_operational |
| limit | integer | 否 | 返回结果数量限制，默认 10 |

**示例**：
```json
{
  "ci_name": "prod-web-01",
  "ci_type": "server",
  "status": "operational"
}
```

**返回示例**：
```json
{
  "success": true,
  "count": 1,
  "cis": [
    {
      "sys_id": "abc123",
      "name": "prod-web-01",
      "short_description": "Production Web Server 01",
      "ip_address": "10.0.1.100",
      "operational_status": "Operational",
      "location": "DC-Beijing",
      "managed_by": "John Doe",
      "sys_class_name": "cmdb_ci_server"
    }
  ]
}
```

### 2. query_servicenow_changes

查询 ServiceNow 变更记录。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ci_name | string | 否 | 关联的配置项名称 |
| change_number | string | 否 | 变更编号 |
| change_type | string | 否 | 变更类型：normal, emergency, standard |
| state | string | 否 | 变更状态：new, assess, authorize, scheduled, implement, review, closed |
| lookback_hours | integer | 否 | 回溯时间（小时），默认 72 |
| limit | integer | 否 | 返回结果数量限制，默认 20 |

**示例**：
```json
{
  "ci_name": "prod-web-01",
  "lookback_hours": 72
}
```

**返回示例**：
```json
{
  "success": true,
  "count": 2,
  "ci_name": "prod-web-01",
  "lookback_hours": 72,
  "changes": [
    {
      "sys_id": "chg001",
      "number": "CHG0056789",
      "short_description": "Security patch update",
      "type": "normal",
      "state": "Implemented",
      "start_date": "2026-04-20 10:00:00",
      "end_date": "2026-04-20 12:00:00",
      "ci_name": "prod-web-01",
      "assigned_to": "Jane Smith"
    }
  ]
}
```

### 3. query_servicenow_incidents

查询 ServiceNow 事件工单。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ci_name | string | 否 | 关联的配置项名称 |
| incident_number | string | 否 | 工单编号 |
| priority | string | 否 | 优先级：1-critical, 2-high, 3-moderate, 4-low |
| state | string | 否 | 工单状态：new, in_progress, on_hold, resolved, closed |
| lookback_hours | integer | 否 | 回溯时间（小时），默认 72 |
| limit | integer | 否 | 返回结果数量限制，默认 20 |

### 4. analyze_change_as_root_cause

**核心工具**：分析变更是否可能是问题的根因。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| node_name | string | 是 | 节点名称 |
| problem_time | string | 否 | 问题发生时间 |
| lookback_hours | integer | 否 | 回溯时间（小时），默认 72 |

**返回示例**：
```json
{
  "success": true,
  "node_name": "prod-web-01",
  "has_recent_changes": true,
  "changes": [...],
  "analysis": {
    "most_recent_change": {
      "number": "CHG0056789",
      "description": "Security patch update",
      "type": "normal",
      "state": "Implemented",
      "start_date": "2026-04-20 10:00:00",
      "assigned_to": "Jane Smith"
    },
    "is_likely_root_cause": true,
    "reason": "Found recent change 'CHG0056789' on this node. Change type: normal, Description: Security patch update",
    "confidence": "MEDIUM",
    "recommendation": "建议检查变更 CHG0056789 的详细内容，确认是否与当前问题相关。变更负责人: Jane Smith"
  }
}
```

### 5. get_servicenow_node_health

获取节点综合健康状态。

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| node_name | string | 否 | 节点名称或主机名 |
| ip_address | string | 否 | IP 地址 |
| lookback_hours | integer | 否 | 回溯时间（小时），默认 72 |

**返回示例**：
```json
{
  "success": true,
  "node": {
    "name": "prod-web-01",
    "sys_id": "abc123",
    "type": "cmdb_ci_server",
    "ip_address": "10.0.1.100",
    "operational_status": "Operational",
    "location": "DC-Beijing",
    "managed_by": "John Doe"
  },
  "health_score": 85,
  "health_status": "healthy",
  "active_incidents": [...],
  "open_problems": [...],
  "recent_changes": [...],
  "summary": {
    "total_incidents": 1,
    "total_problems": 0,
    "total_changes": 2,
    "lookback_hours": 72
  }
}
```

## 使用场景

### 场景1：节点异常时自动检查变更记录

```
用户: "prod-web-01 服务器 CPU 使用率异常升高，请排查"

Agent 执行流程:
1. 调用 execute_command 收集服务器指标
2. 发现 CPU 使用率异常
3. 调用 analyze_change_as_root_cause 检查最近变更
4. 发现 2 小时前有安全补丁变更
5. 分析变更与问题的关联性
6. 返回诊断结果和建议
```

### 场景2：服务故障时关联变更分析

```
用户: "order-service 服务响应时间突然变长"

Agent 执行流程:
1. 调用 load_metrics_and_detect_anomalies 检测异常
2. 发现 order-service 在 10:30 开始异常
3. 调用 query_servicenow_changes 查询变更
4. 发现 10:15 有数据库配置变更
5. 调用 analyze_change_as_root_cause 分析关联
6. 返回根因分析报告
```

### 场景3：综合健康检查

```
用户: "检查 prod-web-01 的健康状态"

Agent 执行流程:
1. 调用 get_servicenow_node_health
2. 获取 CMDB 信息
3. 查询关联工单
4. 查询变更历史
5. 计算健康评分
6. 返回综合健康报告
```

## 典型诊断流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                    变更根因分析诊断流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  用户输入: "prod-web-01 CPU 异常"                                   │
│      │                                                              │
│      ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Step 1: 监控数据采集                                         │   │
│  │ • execute_command: 收集 CPU/内存/磁盘指标                    │   │
│  │ • load_metrics_and_detect_anomalies: 检测异常                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│      │                                                              │
│      ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Step 2: 异常确认                                             │   │
│  │ • 发现 CPU 使用率从 30% 飙升至 90%                           │   │
│  │ • 异常开始时间: 2026-04-22 10:30                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│      │                                                              │
│      ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Step 3: 变更记录查询 (ServiceNow)                            │   │
│  │ • query_servicenow_ci: 确认节点存在于 CMDB                   │   │
│  │ • query_servicenow_changes: 查询最近 72 小时变更             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│      │                                                              │
│      ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Step 4: 变更根因分析                                         │   │
│  │ • analyze_change_as_root_cause: 分析变更与问题关联           │   │
│  │ • 发现 10:15 有安全补丁变更                                  │   │
│  │ • 变更时间与异常时间高度相关                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│      │                                                              │
│      ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Step 5: 生成诊断报告                                         │   │
│  │ • 根因: 安全补丁变更导致 CPU 异常                            │   │
│  │ • 置信度: HIGH                                               │   │
│  │ • 建议: 回滚补丁或联系变更负责人 Jane Smith                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│      │                                                              │
│      ▼                                                              │
│  submit_diagnosis_result: 提交诊断结果                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 与其他 Skill 的协作

### 与 debug_skill 协作

```
1. debug_skill 收集服务器指标
2. 发现异常后，调用 ServiceNow 工具
3. 检查最近变更记录
4. 分析变更是否为根因
```

### 与 gnn_rca_skill 协作

```
1. gnn_rca_skill 分析微服务拓扑
2. 定位异常服务
3. 调用 ServiceNow 查询该服务的变更记录
4. 结合拓扑和变更信息，确定根因
```

### 与 incident_response_skill 协作

```
1. incident_response_skill 处理 P0 故障
2. 调用 ServiceNow 查询相关变更
3. 快速判断是否需要回滚
4. 执行应急响应
```

## 注意事项

1. **网络连通性**: 确保 AIops 平台可以访问 ServiceNow 实例
2. **API 限流**: ServiceNow REST API 有请求频率限制，注意控制查询频率
3. **数据同步**: CMDB 数据可能与实际环境存在延迟，建议结合实时监控数据
4. **权限管理**: 确保配置的 ServiceNow 用户具有足够的查询权限
5. **敏感信息**: 不要在日志中记录 ServiceNow 密码等敏感信息
6. **变更窗口**: 注意区分计划内变更和紧急变更

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 连接失败 | 返回错误信息，建议检查网络和配置 |
| 认证失败 | 返回认证错误，建议检查用户名密码 |
| 节点不存在 | 返回节点未找到，建议检查节点名称 |
| 无变更记录 | 返回无变更，继续其他诊断路径 |

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-22
- 维护者: AIOps Team
