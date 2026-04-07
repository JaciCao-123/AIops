# GNN 根因分析技能

本文档定义了基于图神经网络(GNN)的海量日志根因分析流程。适用对象：MasterAgent, Orchestrator。调用原则：先构建服务依赖图，再进行日志关联分析，最后使用 GNN 模型定位根因。

---

## 1. 适用场景与触发条件

### 1.1 触发关键词
- `根因分析`, `RCA`, `root cause`, `故障定位`, `日志关联`
- `服务调用链`, `异常传播`, `GNN`, `图神经网络`, `微服务故障`
- `trace`, `链路`, `拓扑`, `依赖`, `传播路径`, `海量日志`

### 1.2 适用条件
- 多服务/微服务架构的故障场景
- 存在海量日志数据（日志文件、trace 数据）
- 需要定位故障源头和传播路径
- 传统规则方法无法快速定位
- 需要分析服务间依赖关系

### 1.3 不适用场景
- 单机故障（使用 debug_skill）
- 网络连接问题（使用 login_skill）
- 简单的资源告警（使用 debug_skill）

---

## 2. 数据源配置

### 2.1 可用数据源
| 数据源 | 类型 | 说明 | 适用场景 |
|--------|------|------|----------|
| local | filesystem | 本地文件系统，支持 Parquet 格式 | 离线分析、历史数据 |
| prometheus | monitoring | Prometheus 监控系统 | 实时指标查询 |
| elasticsearch | logging | Elasticsearch 日志平台 | 日志检索、分析 |
| loki | logging | Grafana Loki 日志系统 | 云原生日志 |
| jaeger | tracing | Jaeger 链路追踪 | 调用链分析 |
| aliyun_monitor | cloud_monitoring | 阿里云云监控 | 云资源监控 |

### 2.2 数据类型
- `logs`: 日志数据
- `metrics`: 指标数据
- `traces`: 链路追踪数据

### 2.3 数据加载示例
```json
// 查看可用数据源
{"tool": "list_data_sources"}

// 从本地文件加载日志
{
  "tool": "load_data_from_source",
  "args": {
    "source_name": "local",
    "data_type": "logs",
    "data_path": "/Users/jaci-j/AIops/GNN/2025-06-06"
  }
}

// 从 Prometheus 查询指标
{
  "tool": "load_data_from_source",
  "args": {
    "source_name": "prometheus",
    "data_type": "metrics",
    "query": "rate(http_requests_total[5m])"
  }
}

// 从 Elasticsearch 检索日志
{
  "tool": "load_data_from_source",
  "args": {
    "source_name": "elasticsearch",
    "data_type": "logs",
    "query": {"query": {"match": {"level": "ERROR"}}}
  }
}
```

---

## 3. ReAct 分析流程

### 步骤一：数据收集 (Data Collection)

**思考逻辑**：
- 首先需要查看可用的数据源
- 根据数据源类型选择合适的加载方式
- 需要确定时间范围，避免分析过多无关数据

**工具调用**：
```json
// 1. 先查看可用数据源
{
  "tool": "list_data_sources",
  "args": {}
}

// 2. 从指定数据源加载数据
{
  "tool": "load_data_from_source",
  "args": {
    "source_name": "local",
    "data_type": "logs",
    "time_range": ["2025-06-06 00:00:00", "2025-06-06 23:59:59"],
    "data_path": "/Users/jaci-j/AIops/GNN/2025-06-06"
  }
}
```

**观察与判断**：
- 若数据源不可用：尝试其他数据源或询问用户
- 若 `total_logs == 0`：数据路径错误或无数据，询问用户确认路径
- 若 `total_logs > 1000000`：数据量大，建议采样或限制时间范围
- 若 `error_logs == 0`：无错误日志，可能不是故障时段，询问用户

**进入下一步条件**：成功加载数据且存在错误日志

---

### 步骤二：异常检测 (Anomaly Detection)

**思考逻辑**：
- 数据已加载，需要识别哪些服务出现异常
- 使用 Isolation Forest 算法检测异常服务
- 异常阈值默认 0.95，可根据场景调整

**工具调用**：
```json
{
  "tool": "load_metrics_and_detect_anomalies",
  "args": {
    "metric_path": "/Users/jaci-j/AIops/GNN/2025-06-06",
    "services": ["frontend", "cartservice", "checkoutservice"],
    "anomaly_threshold": 0.95
  }
}
```

**观察与判断**：
- 若 `anomaly_services == []`：未检测到异常，可能阈值过高，建议降低阈值
- 若 `len(anomaly_services) == 1`：单一服务异常，可能是根因
- 若 `len(anomaly_services) > 3`：多个服务异常，需要 GNN 分析传播路径

**进入下一步条件**：检测到至少一个异常服务

---

### 步骤三：构建服务图 (Graph Construction)

**思考逻辑**：
- 异常服务已识别，需要构建服务依赖图
- 图结构用于 GNN 模型理解服务间关系
- 边表示调用关系，节点表示服务

**工具调用**：
```json
{
  "tool": "build_service_graph",
  "args": {
    "services": ["frontend", "cartservice", "redis-cart", ...],
    "dependencies": [
      {"source": "frontend", "target": "cartservice"},
      {"source": "cartservice", "target": "redis-cart"}
    ]
  }
}
```

**观察与判断**：
- 若 `num_nodes < 2`：服务数量不足，无法构建有效图
- 若 `num_edges == 0`：无依赖关系，GNN 无法分析传播
- 正常情况：记录图结构，用于后续 GNN 分析

**进入下一步条件**：成功构建图且节点数 >= 2

---

### 步骤四：GNN 根因分析 (Root Cause Analysis)

**思考逻辑**：
- 图已构建，运行 GNN 模型进行根因预测
- GNN 会考虑服务间依赖和异常传播
- 返回 Top-K 根因候选

**工具调用**：
```json
{
  "tool": "gnn_root_cause_analysis",
  "args": {
    "data_path": "/Users/jaci-j/AIops/GNN/2025-06-06",
    "anomaly_services": ["frontend", "cartservice"],
    "top_k": 3,
    "model_type": "GAT"
  }
}
```

**观察与判断**：
- 若 `confidence == "LOW"`：结果不可靠，建议结合其他方法验证
- 若 `root_causes[0].probability > 0.8`：高置信度，可直接给出结论
- 若多个根因概率接近：需要进一步分析，查看传播路径

**进入下一步条件**：GNN 分析成功返回结果

---

### 步骤五：生成报告 (Report Generation)

**思考逻辑**：
- GNN 分析完成，需要生成人类可读的报告
- 报告包含根因服务、传播路径、证据链
- 保存报告到中间文件供后续查看

**工具调用**：
```json
{
  "tool": "generate_rca_report",
  "args": {
    "rca_result": {
      "root_causes": [...],
      "propagation_path": [...],
      "confidence": "HIGH"
    },
    "logs": [...],
    "metrics": {...}
  }
}
```

**观察与判断**：
- 报告生成成功，准备提交最终诊断结果

---

### 步骤六：提交结果 (Submit Result)

**思考逻辑**：
- 所有分析步骤完成
- 需要调用 submit_diagnosis_result 结束诊断流程
- 这是 ReAct 流程的终止标志

**工具调用**：
```json
{
  "tool": "submit_diagnosis_result",
  "args": {
    "problem_type": "service",
    "root_cause": "redis-cart 内存使用率过高导致连接超时",
    "impact": "影响 cartservice 和 frontend 服务",
    "recommendation": "扩容 redis-cart 内存或优化数据结构",
    "risk_level": "MEDIUM",
    "confidence": "HIGH",
    "analysis_summary": "通过 GNN 分析发现 redis-cart 是根因，概率 92%..."
  }
}
```

---

## 4. 权限边界与安全规则

### 4.1 危险命令禁止执行
以下命令类型**绝对不可执行**：
- 删除操作: `rm -rf`, `drop database`, `truncate table`
- 系统操作: `shutdown`, `reboot`, `init 0/6`
- 磁盘操作: `dd if=`, `mkfs`, `fdisk`
- 权限修改: `chmod -R 777`, `chown -R`
- 远程脚本: `wget ... | sh`, `curl ... | sh`

### 4.2 需要确认的操作
以下操作需要先调用 `ask_user_confirmation`：
- 重启服务
- 停止容器/Pod
- 修改配置文件
- 清理日志文件

### 4.3 安全的只读操作
以下操作可以安全执行：
- 查看日志: `cat`, `tail`, `head`, `grep`, `journalctl`
- 查看状态: `systemctl status`, `docker ps`, `kubectl get`
- 查看资源: `df`, `du`, `free`, `top`, `ps`, `uptime`
- 网络诊断: `ping`, `traceroute`, `netstat`, `ss`

---

## 5. 决策逻辑与回退机制

### 5.1 正常流程
```
list_data_sources → load_data → detect_anomalies → build_graph → gnn_analysis → report → submit
```

### 5.2 异常处理

| 异常情况 | 处理方式 |
|---------|----------|
| 数据源不可用 | 尝试其他数据源或询问用户 |
| 无日志数据 | 提示用户检查数据源，或切换到 debug_skill |
| 无异常服务 | 降低阈值重试，或提示可能无故障 |
| 图构建失败 | 使用默认拓扑，或提示服务信息不完整 |
| GNN 模型错误 | 使用 fallback 规则方法，或提示人工分析 |

### 5.3 回退策略
```
GNN 失败 → 回退到规则方法 → 回退到人工分析
```

---

## 6. 使用示例

### 示例 1：从本地文件分析
```
用户: 使用 GNN 分析 2025-06-06 的日志数据，找出 frontend 响应慢的根因

Agent 执行:
1. list_data_sources → 查看可用数据源
2. load_data_from_source(local, logs) → 加载 7,211,748 条日志
3. load_metrics_and_detect_anomalies → 发现 frontend, cartservice 异常
4. build_service_graph → 构建 11 节点 13 边的图
5. gnn_root_cause_analysis → 根因 redis-cart (概率 92%)
6. generate_rca_report → 生成报告
7. submit_diagnosis_result → 提交结果
```

### 示例 2：从 Prometheus 实时分析
```
用户: 分析当前服务的异常情况

Agent 执行:
1. list_data_sources → 查看可用数据源
2. load_data_from_source(prometheus, metrics) → 查询实时指标
3. load_data_from_source(elasticsearch, logs) → 检索错误日志
4. build_service_graph → 构建服务图
5. gnn_root_cause_analysis → 分析根因
6. submit_diagnosis_result → 提交结果
```

---

## 7. 注意事项

1. **数据源选择**: 优先使用实时数据源进行在线分析，使用本地文件进行离线分析
2. **内存要求**: 加载大量数据时需要足够的内存
3. **模型依赖**: 需要安装 torch, torch_geometric, pandas, pyarrow
4. **实时性**: GNN 推理通常 < 1 秒，数据加载可能需要几秒
5. **可解释性**: GNN 输出包含注意力权重，可解释传播路径
6. **安全第一**: 任何操作前先考虑安全性，危险命令会被系统拦截
