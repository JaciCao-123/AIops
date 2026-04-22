# OtelTraceSkill - 分布式链路追踪分析技能

## 概述

基于 **OpenTelemetry + Tempo** 的分布式链路追踪分析系统，用于故障定位、性能瓶颈识别和服务调用关系分析。

## 核心能力

| 能力 | 描述 |
|------|------|
| **Trace 查询** | 通过 Trace ID 查询完整的分布式调用链 |
| **错误链路搜索** | 搜索包含错误的调用链，快速定位故障 |
| **慢请求分析** | 搜索响应时间超过阈值的慢请求 |
| **性能分析** | 分析调用链中的性能瓶颈和热点 Span |
| **服务依赖** | 从 Trace 数据中提取服务调用关系 |

## 技术架构

```
应用服务 (OTel SDK)
    │
    ▼ OTLP (gRPC/HTTP)
OTel Collector
    │
    ▼ OTLP HTTP
Tempo (Trace 存储)
    │
    ▼ Tempo API
AIops Platform (analyze_trace)
```

## 模块路径

```
aiops-platform/backend/app/observability/
├── tempo_query.py         # Tempo 查询客户端
├── config.py              # 可观测性配置
├── root_cause_analyzer.py # 根因分析引擎
└── enhanced_rca.py        # 增强型根因分析

otel-observability/
├── otel-collector-config.yaml  # OTel Collector 配置
├── tempo.yaml                  # Tempo 存储配置
└── docker-compose.yml          # 部署配置
```

## 工具调用

### analyze_trace

查询和分析分布式调用链。

```python
# 通过 Trace ID 查询
result = await analyze_trace(
    trace_id="abc123def456"
)

# 搜索错误链路
result = await analyze_trace(
    service_name="order-service",
    error_only=True,
    lookback="1h"
)

# 搜索慢请求
result = await analyze_trace(
    service_name="payment-service",
    slow_only=True,
    min_duration_ms=1000,
    lookback="30m"
)
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `trace_id` | str | 否 | Trace ID，查询特定调用链 |
| `service_name` | str | 否 | 服务名称，过滤搜索结果 |
| `error_only` | bool | 否 | 只搜索错误链路 |
| `slow_only` | bool | 否 | 只搜索慢请求链路 |
| `min_duration_ms` | int | 否 | 最小持续时间阈值（毫秒） |
| `lookback` | str | 否 | 回溯时间范围，默认 "1h" |
| `limit` | int | 否 | 返回结果数量限制，默认 20 |

**返回结果**:

```python
# Trace ID 查询结果
{
    "success": True,
    "trace_id": "abc123def456",
    "trace": {
        "trace_id": "abc123def456",
        "span_count": 15,
        "services_involved": ["frontend", "backend", "database"],
        "total_duration_ms": 234.5,
        "error_count": 1
    },
    "span_tree": {
        "root_spans_count": 1,
        "tree": [...]
    },
    "performance_analysis": {
        "top_slowest_spans": [...],
        "error_spans": [...]
    }
}

# 搜索结果
{
    "success": True,
    "total_traces": 42,
    "traces": [
        {
            "traceID": "abc123",
            "serviceName": "order-service",
            "duration": 1234,
            "errorCount": 1
        }
    ]
}
```

## 使用场景

### 场景1: 故障定位

```
用户: "order-service 最近有很多错误请求，帮我分析一下"

Agent 执行流程:
1. 调用 analyze_trace(service_name="order-service", error_only=True)
2. 分析错误链路的传播路径
3. 识别根因服务
4. 生成故障分析报告
```

### 场景2: 性能瓶颈分析

```
用户: "payment-service 响应很慢，帮我查一下慢请求"

Agent 执行流程:
1. 调用 analyze_trace(service_name="payment-service", slow_only=True, min_duration_ms=1000)
2. 分析慢请求的调用链
3. 识别耗时最长的 Span
4. 提供优化建议
```

### 场景3: Trace ID 分析

```
用户: "这个请求 trace_id=abc123 很慢，帮我分析一下"

Agent 执行流程:
1. 调用 analyze_trace(trace_id="abc123")
2. 获取完整的调用链树
3. 分析每个 Span 的耗时
4. 识别性能瓶颈点
```

## 配置说明

在 `app/observability/config.py` 中配置 Tempo 连接：

```python
class TempoConfig(BaseModel):
    enabled: bool = True
    url: str = "http://localhost:3200"
    query_url: str = "http://localhost:3200"
    default_lookback: str = "1h"
```

或通过环境变量：

```bash
TEMPO_URL=http://tempo:3200
```

## 与其他工具配合

| 工具 | 配合方式 |
|------|----------|
| `cluster_alerts` | 先聚合告警，再用 analyze_trace 分析关联的 Trace |
| `analyze_service_dependency` | 先获取服务依赖图，再用 analyze_trace 深入分析 |
| `gnn_root_cause_analysis` | 提供 Trace 数据用于 GNN 根因推理 |

## 注意事项

1. **Tempo 连接**: 确保 Tempo 服务可用且网络可达
2. **采样策略**: OTel Collector 的采样策略会影响可查询的 Trace 数量
3. **时间范围**: lookback 参数不要设置过大，避免查询超时
4. **服务命名**: 确保应用使用统一的 service.name 标签

## 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-21
- 维护者: AIOps Team
