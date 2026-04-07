# Prometheus 监控技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. PromQL 查询](#4-promql-查询)
- [5. 告警规则](#5-告警规则)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `Prometheus`, `监控`, `指标`, `metric`
- `PromQL`, `查询`, `告警`, `alert`
- `Grafana`, `Dashboard`, `面板`
- `target`, `scrape`, `采集`

### 1.2 适用条件
- Prometheus 服务状态检查
- 指标查询与分析
- 告警规则配置
- Target 采集问题
- 数据存储问题

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 检查 Prometheus 状态                               │
│  - 服务健康检查                                            │
│  - 版本信息                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 检查 Target 状态                                   │
│  - 采集目标列表                                            │
│  - 目标健康状态                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 指标查询                                           │
│  - 元数据查询                                              │
│  - PromQL 查询                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 告警检查                                           │
│  - 告警规则状态                                            │
│  - 当前告警                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 存储与性能检查                                     │
│  - 存储使用                                                │
│  - 采集性能                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 服务状态检查

```bash
# 检查 Prometheus 服务
systemctl status prometheus

# 检查端口
netstat -tlnp | grep 9090 || ss -tlnp | grep 9090

# 检查 Docker 容器
docker ps | grep prometheus

# 健康检查
curl http://localhost:9090/-/healthy
curl http://localhost:9090/-/ready

# 版本信息
curl http://localhost:9090/api/v1/status/buildinfo

# 运行时信息
curl http://localhost:9090/api/v1/status/runtimeinfo
```

### 3.2 Target 状态检查

```bash
# 查看所有 Target
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'

# 查看失败的 Target
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health == "down")'

# 查看特定 Job 的 Target
curl -s "http://localhost:9090/api/v1/targets?state=active" | jq '.data.activeTargets[] | select(.labels.job == "node")'

# 查看服务发现
curl -s http://localhost:9090/api/v1/service_discovery | jq .
```

### 3.3 指标查询

```bash
# 查看元数据
curl -s http://localhost:9090/api/v1/metadata | jq .

# 查看所有指标名称
curl -s http://localhost:9090/api/v1/label/__name__/values | jq '.data[]' | head -50

# 查看标签值
curl -s "http://localhost:9090/api/v1/label/job/values" | jq .

# 即时查询
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq .

# 范围查询
curl -s 'http://localhost:9090/api/v1/query_range?query=up&start=2025-01-01T00:00:00Z&end=2025-01-01T01:00:00Z&step=60s' | jq .

# 查询系列
curl -s 'http://localhost:9090/api/v1/series?match[]=up' | jq .
```

### 3.4 配置检查

```bash
# 查看当前配置
curl -s http://localhost:9090/api/v1/status/config | jq .

# 查看配置文件
cat /etc/prometheus/prometheus.yml

# 验证配置文件
promtool check config /etc/prometheus/prometheus.yml

# 查看告警规则文件
cat /etc/prometheus/alert.rules.yml

# 验证告警规则
promtool check rules /etc/prometheus/alert.rules.yml
```

### 3.5 告警检查

```bash
# 查看告警规则
curl -s http://localhost:9090/api/v1/rules | jq .

# 查看当前告警
curl -s http://localhost:9090/api/v1/alerts | jq .

# 查看特定告警规则
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | select(.name == "HighCPU")'

# 查看触发的告警
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state == "firing")'
```

### 3.6 存储检查

```bash
# 查看存储统计
curl -s http://localhost:9090/api/v1/status/tsdb | jq .

# 查看数据目录大小
du -sh /var/lib/prometheus/

# 查看数据目录结构
ls -la /var/lib/prometheus/

# 查看内存使用
curl -s http://localhost:9090/api/v1/status/runtimeinfo | jq '.data.memoryUsageBytes'

# 查看采集统计
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data.seriesCountByMetricName'
```

---

## 4. PromQL 查询

### 4.1 常用查询模板

#### 系统监控
```promql
# CPU 使用率
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 内存使用率
(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100

# 磁盘使用率
(1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})) * 100

# 磁盘 I/O
irate(node_disk_io_time_seconds_total[5m])

# 网络流量
irate(node_network_receive_bytes_total[5m])
irate(node_network_transmit_bytes_total[5m])
```

#### 容器监控
```promql
# 容器 CPU 使用率
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (pod, namespace)

# 容器内存使用
sum(container_memory_working_set_bytes{container!=""}) by (pod, namespace)

# 容器网络流量
sum(rate(container_network_receive_bytes_total[5m])) by (pod, namespace)
```

#### 应用监控
```promql
# HTTP 请求速率
rate(http_requests_total[5m])

# HTTP 错误率
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100

# 请求延迟 P99
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# 请求延迟 P95
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

#### 数据库监控
```promql
# MySQL 连接数
mysql_global_status_Threads_connected

# MySQL 查询速率
rate(mysql_global_status_Queries[5m])

# Redis 内存使用
redis_memory_used_bytes / redis_memory_max_bytes * 100

# Redis 连接数
redis_connected_clients
```

### 4.2 常用函数

| 函数 | 说明 | 示例 |
|------|------|------|
| `rate()` | 计算速率 | `rate(metric[5m])` |
| `irate()` | 计算瞬时速率 | `irate(metric[5m])` |
| `increase()` | 计算增量 | `increase(metric[1h])` |
| `sum()` | 求和 | `sum(metric)` |
| `avg()` | 平均值 | `avg(metric)` |
| `max()` | 最大值 | `max(metric)` |
| `min()` | 最小值 | `min(metric)` |
| `count()` | 计数 | `count(metric)` |
| `topk()` | Top K | `topk(10, metric)` |
| `histogram_quantile()` | 分位数 | `histogram_quantile(0.99, metric)` |
| `label_replace()` | 标签替换 | `label_replace(metric, "dst", "$1", "src", "(.*)")` |

---

## 5. 告警规则

### 5.1 常用告警规则

```yaml
groups:
  - name: node_alerts
    rules:
      - alert: HighCPU
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.instance }}"
          description: "CPU usage is {{ $value }}%"

      - alert: HighMemory
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage on {{ $labels.instance }}"
          description: "Memory usage is {{ $value }}%"

      - alert: DiskSpaceLow
        expr: (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space on {{ $labels.instance }}"
          description: "Disk usage is {{ $value }}%"

      - alert: InstanceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Instance {{ $labels.instance }} down"
          description: "{{ $labels.instance }} of job {{ $labels.job }} has been down for more than 1 minute."

  - name: application_alerts
    rules:
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100 > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }}%"

      - alert: HighLatency
        expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "P99 latency is {{ $value }}s"
```

### 5.2 告警规则最佳实践

1. **设置合理的 `for` 持续时间**
   - 避免瞬时抖动触发告警
   - 常用值: 1m, 5m, 10m

2. **使用合适的严重级别**
   - `critical`: 需要立即处理
   - `warning`: 需要关注
   - `info`: 信息通知

3. **编写清晰的告警描述**
   - 包含关键信息
   - 提供排查方向

---

## 6. 权限边界

### 6.1 安全的只读操作
```bash
/api/v1/query
/api/v1/query_range
/api/v1/labels
/api/v1/series
/api/v1/targets
/api/v1/rules
/api/v1/alerts
/api/v1/status/*
```

### 6.2 需要确认的操作
```bash
/api/v1/admin/tsdb/delete_series  # 删除数据
/api/v1/admin/tsdb/clean_tombstones  # 清理墓碑
/-/reload  # 重载配置
```

### 6.3 危险操作禁止执行
```bash
/-/quit  # 停止服务
/api/v1/admin/tsdb/snapshot  # 创建快照（可能影响性能）
```

---

## 7. 快速诊断脚本

```bash
#!/bin/bash
# Prometheus 快速诊断脚本

PROM_URL="${1:-http://localhost:9090}"

echo "=== Prometheus 健康状态 ==="
curl -s $PROM_URL/-/healthy

echo -e "\n\n=== 版本信息 ==="
curl -s $PROM_URL/api/v1/status/buildinfo | jq -r '.data.version'

echo -e "\n=== Target 状态 ==="
curl -s $PROM_URL/api/v1/targets | jq -r '.data.activeTargets | "总数: \(length), 健康: \([.[] | select(.health == "up")] | length), 异常: \([.[] | select(.health == "down")] | length)"'

echo -e "\n=== 异常 Targets ==="
curl -s $PROM_URL/api/v1/targets | jq -r '.data.activeTargets[] | select(.health == "down") | "Job: \(.labels.job), Instance: \(.labels.instance), Error: \(.lastError)"'

echo -e "\n=== 当前告警 ==="
curl -s $PROM_URL/api/v1/alerts | jq -r '.data.alerts | "总数: \(length), 触发: \([.[] | select(.state == "firing")] | length), 待定: \([.[] | select(.state == "pending")] | length)"'

echo -e "\n=== 触发的告警 ==="
curl -s $PROM_URL/api/v1/alerts | jq -r '.data.alerts[] | select(.state == "firing") | "Alert: \(.labels.alertname), Severity: \(.labels.severity)"'

echo -e "\n=== 存储统计 ==="
curl -s $PROM_URL/api/v1/status/tsdb | jq '{series: .data.numSeries, chunks: .data.numChunks, bytes: .data.numBytes}'

echo -e "\n=== 内存使用 ==="
curl -s $PROM_URL/api/v1/status/runtimeinfo | jq -r '.data.memoryUsageBytes | "内存使用: \(.) bytes"'
```

---

## 8. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
