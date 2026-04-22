# ServiceDependencySkill - 服务依赖关系分析技能

## 概述

从分布式追踪数据中提取服务调用关系，构建服务依赖拓扑图，用于理解微服务架构和识别故障传播路径。

## 核心能力

| 能力 | 描述 |
|------|------|
| **服务拓扑构建** | 从 Trace 数据自动发现服务调用关系 |
| **调用统计** | 统计服务间的调用次数、错误率、延迟 |
| **依赖可视化** | 生成可用于可视化的依赖图数据 |
| **故障传播分析** | 识别潜在的故障传播路径 |

## 技术架构

```
Tempo (Trace 存储)
    │
    ▼ Trace 数据
analyze_service_dependency
    │
    ├── 解析 Span 关系
    ├── 提取服务调用边
    └── 统计调用指标
    │
    ▼
服务依赖图 (Nodes + Edges)
```

## 工具调用

### analyze_service_dependency

从 Trace 数据构建服务依赖图。

```python
# 分析所有服务的依赖关系
result = await analyze_service_dependency(
    lookback="24h"
)

# 只分析特定服务
result = await analyze_service_dependency(
    lookback="1h",
    service_filter=["order-service", "payment-service", "inventory-service"]
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `lookback` | str | 否 | 回溯时间范围，默认 "24h" |
| `service_filter` | List[str] | 否 | 服务过滤列表，只分析指定服务 |

**返回结果**:

```python
{
    "success": True,
    "nodes": [
        {"id": "frontend", "name": "frontend"},
        {"id": "backend", "name": "backend"},
        {"id": "database", "name": "database"},
        {"id": "cache", "name": "cache"}
    ],
    "edges": [
        {
            "source": "frontend",
            "target": "backend",
            "call_count": 15000,
            "error_count": 150,
            "error_rate": 1.0,
            "avg_latency_ms": 45.2,
            "p99_latency_ms": 234.5
        },
        {
            "source": "backend",
            "target": "database",
            "call_count": 12000,
            "error_count": 12,
            "error_rate": 0.1,
            "avg_latency_ms": 12.3,
            "p99_latency_ms": 89.2
        }
    ],
    "total_services": 4,
    "total_edges": 3,
    "lookback": "24h"
}
```

## 使用场景

### 场景1: 微服务架构理解

```
用户: "帮我分析一下当前系统的服务依赖关系"

Agent 执行流程:
1. 调用 analyze_service_dependency(lookback="24h")
2. 构建服务依赖图
3. 分析关键服务和瓶颈点
4. 生成架构概览报告
```

### 场景2: 故障传播分析

```
用户: "payment-service 出现故障，可能影响哪些服务？"

Agent 执行流程:
1. 调用 analyze_service_dependency(lookback="1h")
2. 找到所有依赖 payment-service 的下游服务
3. 分析错误率高的调用边
4. 生成故障影响范围报告
```

### 场景3: 性能瓶颈定位

```
用户: "order-service 响应慢，可能是哪个依赖服务的问题？"

Agent 执行流程:
1. 调用 analyze_service_dependency(service_filter=["order-service"])
2. 分析 order-service 的所有下游依赖
3. 找到延迟最高的调用边
4. 结合 analyze_trace 深入分析
```

## 数据可视化

返回的数据可以直接用于前端可视化：

```javascript
// 使用 D3.js 或 G6 渲染
const data = {
    nodes: result.nodes,
    edges: result.edges.map(e => ({
        source: e.source,
        target: e.target,
        value: e.call_count,
        errorRate: e.error_rate
    }))
};
```

## 与其他工具配合

| 工具 | 配合方式 |
|------|----------|
| `analyze_trace` | 先获取依赖图，再用 analyze_trace 深入分析特定调用链 |
| `gnn_root_cause_analysis` | 提供服务拓扑数据用于 GNN 根因推理 |
| `cluster_alerts` | 结合告警聚合结果，分析告警的服务依赖关系 |

## 性能考虑

1. **查询范围**: lookback 参数越大，查询的 Trace 越多，耗时越长
2. **服务过滤**: 使用 service_filter 可以减少查询量
3. **缓存策略**: 考虑缓存依赖图结果，避免频繁查询

## 注意事项

1. **采样影响**: OTel Collector 的采样策略会影响依赖关系的准确性
2. **服务命名**: 确保应用使用统一的 service.name 标签
3. **异步调用**: 消息队列等异步调用可能无法正确识别依赖关系

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
