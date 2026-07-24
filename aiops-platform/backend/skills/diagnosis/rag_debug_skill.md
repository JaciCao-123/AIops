# RAG 系统故障排查 Skill

## 适用场景

- RAG（检索增强生成）系统故障排查
- RAG 服务异常（响应慢、报错、不可用）
- RAG 组件间通信异常（Qdrant、vLLM、Redis、PostgreSQL）
- RAG 知识库检索异常（命中率低、无结果、结果错误）
- RAG 观测数据链路异常（Grafana/Prometheus/Loki 数据缺失）

## RAG 系统架构 (47.76.53.232, Docker Compose)

```
rag_frontend (Nginx/React)      端口 3001
    │
rag_backend (FastAPI)           端口 8001
    │
    ├── rag_qdrant (向量数据库)     端口 6333
    ├── rag_vllm (大模型推理)       端口 8000
    ├── rag_redis (缓存)            端口 6379
    ├── rag_postgres (元数据)       端口 5432
    └── rag_asr (语音识别, 可选)
```

## 可观测性栈 (共享同一套 Grafana)

Grafana URL: http://172.21.36.91:3000 (已通过 MCP 集成)

Grafana 中预置的仪表盘:
- `rag-overview`: RAG 系统概览（请求量、延迟、错误率）
- `service-topology`: 基于 OpenTelemetry trace 的服务调用拓扑图
- `system-overview`: 主机级资源监控
- `vllm-overview`: vLLM 推理性能监控

相关 Prometheus 指标 (通过 `traces_service_graph_request_total` 获取):
```
traces_service_graph_request_total{client="rag_backend", server="rag_qdrant"}
traces_service_graph_request_total{client="rag_backend", server="rag_vllm"}
```

## 关键 PromQL 查询

```promql
# 服务拓扑
sum by (client, server) (traces_service_graph_request_total)

# 服务请求错误率
sum(rate(traces_service_graph_request_total{code=~"5.."}[5m])) by (client, server)

# 服务请求延迟
histogram_quantile(0.99, sum(rate(traces_service_graph_request_duration_seconds_bucket[5m])) by (le, client, server))
```

## 诊断流程

### 步骤 1: 获取 RAG 服务调用拓扑

使用 `mcp_call` 工具查询 Grafana 中的服务拓扑：

```
工具: mcp_call
参数: tool="query_metrics", params={"query": "sum by (client, server) (traces_service_graph_request_total)", "time": "now-15m"}
```

分析拓扑: 查看 RAG 各服务间调用关系是否正常，是否有异常的客户端/服务端节点。

### 步骤 2: 查询 Grafana 告警

使用 `mcp_call` 工具获取告警列表：

```
工具: mcp_call
参数: tool="list_alerts", params={"state": ""}
```

### 步骤 3: 查询 RAG 服务错误日志

使用 `mcp_call` 工具查询 RAG 各个容器的 Loki 日志：

```
工具: mcp_call
参数: tool="query_logs", params={"query": '{container=~"rag_.*",namespace="docker"} |= "error"', "start": "now-1h", "limit": 100}
```

```
工具: mcp_call
参数: tool="query_logs", params={"query": '{container="rag_backend"} |= "exception"', "start": "now-1h", "limit": 100}
```

```
工具: mcp_call
参数: tool="query_logs", params={"query": '{container="rag_vllm"} |= "error"', "start": "now-1h", "limit": 100}
```

### 步骤 4: 查询 RAG 服务关键指标

使用 `mcp_call` 查询各服务的性能和健康指标：

```
# RAG 请求量
工具: mcp_call
参数: tool="query_metrics", params={"query": "sum by (container) (rate(container_cpu_usage_seconds_total{container=~\"rag_.*\"}[5m]))"}
```

```
# RAG 服务内存使用
工具: mcp_call
参数: tool="query_metrics", params={"query": "sum by (container) (container_memory_usage_bytes{container=~\"rag_.*\"})"}
```

### 步骤 5: SSH 连接到跳板机查询容器状态 (只读)

使用 `execute_command` 工具通过跳板机查询 RAG 容器状态：

```
# 查看所有 RAG 容器状态
工具: execute_command
参数: target_host="47.76.53.232", command="docker ps --filter name=rag_ --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", risk_level="low"

# 查看容器资源占用
工具: execute_command
参数: target_host="47.76.53.232", command="docker stats --no-stream --filter name=rag_", risk_level="low"

# 查看 RAG 后端日志（最后 50 行）
工具: execute_command
参数: target_host="47.76.53.232", command="docker logs rag_backend --tail 50 2>&1", risk_level="low"

# 查看 vLLM 后端日志（最后 50 行）
工具: execute_command
参数: target_host="47.76.53.232", command="docker logs rag_vllm --tail 50 2>&1", risk_level="low"

# 查看 Qdrant 日志（最后 30 行）
工具: execute_command
参数: target_host="47.76.53.232", command="docker logs rag_qdrant --tail 30 2>&1", risk_level="low"
```

### 步骤 6: 分析代码给出建议 (可选)

使用 `execute_command` 工具读取 RAG 项目关键代码文件，分析可能的根因：

```
# 查看项目结构
工具: execute_command
参数: target_host="47.76.53.232", command="ls /opt/rag_project/backend/", risk_level="low"

# 查看 RAG 配置
工具: execute_command
参数: target_host="47.76.53.232", command="cat /opt/rag_project/backend/.env 2>/dev/null || cat /opt/rag_project/backend/core/config.py", risk_level="low"

# 查看 docker-compose 配置
工具: execute_command
参数: target_host="47.76.53.232", command="cat /opt/rag_project/docker-compose.yml", risk_level="low"
```

## 常见故障模式

| 症状 | 可能原因 | 检查点 |
|------|---------|--------|
| RAG 回答慢/超时 | vLLM 负载高或 OOM | `docker stats rag_vllm`, 检查 vLLM 日志 |
| Qdrant 查询失败 | Qdrant 连接数满或磁盘满 | `docker logs rag_qdrant`, 检查 Qdrant 健康 |
| Redis 缓存异常 | Redis 内存不足 | `docker exec rag_redis redis-cli INFO memory` |
| 无检索结果 | Qdrant collection 为空或 embedding 异常 | 检查 qdrant 日志 |
| RAG backend 报 500 | 依赖服务不可用 | 检查拓扑图中各服务状态 |

## 诊断报告

诊断完成后，输出应包括：

1. **服务拓扑状态**: RAG 各服务的调用关系和健康状态
2. **异常指标**: 发现的异常指标和趋势
3. **错误日志摘要**: 关键错误信息和时间点
4. **根因分析**: 问题根因判断
5. **修复建议**: 操作建议（仅给出建议，不自动执行修复操作）
6. **代码分析**: （如需要）相关代码的分析和修改建议

## 安全边界

- 本 Skill 仅执行只读操作（查询、分析）
- 不允许修改 Docker 容器配置或代码文件
- 不允许重启容器或服务
- 不允许修改 Grafana 配置或 RAG 项目代码
