# 日志分析技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 日志分析技巧](#4-日志分析技巧)
- [5. 常见日志模式](#5-常见日志模式)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `日志`, `log`, `日志分析`, `日志搜索`
- `ELK`, `Elasticsearch`, `Kibana`, `Loki`
- `错误日志`, `异常`, `exception`, `error`
- `grep`, `awk`, `sed`, `日志过滤`

### 1.2 适用条件
- 应用日志分析
- 错误日志排查
- 日志模式识别
- 日志统计与聚合
- 日志时间序列分析

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 确定日志源                                         │
│  - 日志文件位置                                            │
│  - 日志平台 (ELK/Loki)                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 日志过滤                                           │
│  - 时间范围过滤                                            │
│  - 关键词过滤                                              │
│  - 日志级别过滤                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 日志分析                                           │
│  - 错误模式识别                                            │
│  - 统计分析                                                │
│  - 关联分析                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 根因定位                                           │
│  - 错误堆栈分析                                            │
│  - 时间线重建                                              │
│  - 相关日志关联                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 生成分析报告                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 文件日志分析

#### 基础查看
```bash
# 查看日志文件
cat /var/log/app.log

# 查看最后 N 行
tail -n 100 /var/log/app.log

# 实时查看
tail -f /var/log/app.log

# 查看前 N 行
head -n 100 /var/log/app.log

# 分页查看
less /var/log/app.log
```

#### 时间过滤
```bash
# 查看今天的日志
grep "$(date '+%Y-%m-%d')" /var/log/app.log

# 查看指定时间范围
awk '/2025-04-05 10:00/,/2025-04-05 11:00/' /var/log/app.log

# 查看最近 N 分钟的日志
find /var/log -name "*.log" -mmin -30 -exec tail {} \;

# 使用 sed 按时间过滤
sed -n '/2025-04-05 10:00/,/2025-04-05 11:00/p' /var/log/app.log
```

#### 关键词过滤
```bash
# 搜索关键词
grep "ERROR" /var/log/app.log
grep -i "error" /var/log/app.log  # 忽略大小写

# 多关键词搜索
grep -E "ERROR|WARN|FATAL" /var/log/app.log

# 排除关键词
grep -v "DEBUG" /var/log/app.log

# 显示行号
grep -n "ERROR" /var/log/app.log

# 显示上下文
grep -A 5 "ERROR" /var/log/app.log  # 后 5 行
grep -B 5 "ERROR" /var/log/app.log  # 前 5 行
grep -C 5 "ERROR" /var/log/app.log  # 前后各 5 行

# 统计匹配数量
grep -c "ERROR" /var/log/app.log
```

#### 统计分析
```bash
# 统计日志级别分布
grep -oE "(ERROR|WARN|INFO|DEBUG)" /var/log/app.log | sort | uniq -c | sort -rn

# 统计 IP 访问量
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -10

# 统计 HTTP 状态码
awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn

# 统计每分钟请求数
awk '{print substr($4, 2, 16)}' /var/log/nginx/access.log | sort | uniq -c

# 统计错误类型分布
grep "ERROR" /var/log/app.log | awk -F': ' '{print $2}' | sort | uniq -c | sort -rn | head -10
```

#### 高级分析
```bash
# 提取 JSON 日志字段
cat app.log | jq -r 'select(.level == "ERROR") | .message'

# 分析异常堆栈
grep -A 20 "Exception" /var/log/app.log

# 查找唯一错误
grep "ERROR" /var/log/app.log | sort -u

# 合并多个日志文件
cat /var/log/app/*.log > combined.log

# 压缩日志搜索
zgrep "ERROR" /var/log/app.log.gz
zcat /var/log/app.log.gz | grep "ERROR"
```

### 3.2 Docker 容器日志

```bash
# 查看容器日志
docker logs <container>

# 实时查看
docker logs -f <container>

# 查看最后 N 行
docker logs --tail 100 <container>

# 查看时间范围
docker logs --since "2025-04-05T10:00:00" <container>
docker logs --since 1h <container>

# 查看带时间戳
docker logs -t <container>

# 过滤日志
docker logs <container> 2>&1 | grep "ERROR"
```

### 3.3 Kubernetes 日志

```bash
# 查看 Pod 日志
kubectl logs <pod> -n <namespace>

# 查看指定容器日志
kubectl logs <pod> -n <namespace> -c <container>

# 实时查看
kubectl logs -f <pod> -n <namespace>

# 查看上一个容器日志
kubectl logs <pod> -n <namespace> --previous

# 查看最近 N 行
kubectl logs <pod> -n <namespace> --tail=100

# 查看时间范围
kubectl logs <pod> -n <namespace> --since=1h

# 查看所有容器日志
kubectl logs <pod> -n <namespace> --all-containers

# 查看 Deployment 所有 Pod 日志
kubectl logs deployment/<deployment> -n <namespace>
```

### 3.4 Elasticsearch/ELK 查询

```bash
# 基础查询
curl -X GET "localhost:9200/logs-*/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "level": "ERROR"
    }
  },
  "size": 10
}'

# 时间范围查询
curl -X GET "localhost:9200/logs-*/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": [
        {"match": {"level": "ERROR"}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  }
}'

# 聚合统计
curl -X GET "localhost:9200/logs-*/_search" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "error_types": {
      "terms": {
        "field": "error_type.keyword",
        "size": 10
      }
    }
  }
}'
```

### 3.5 Loki 查询

```bash
# LogQL 基础查询
# 查看特定应用的日志
{app="myapp"}

# 过滤关键词
{app="myapp"} |= "error"

# 多条件过滤
{app="myapp"} |= "error" != "timeout"

# 正则匹配
{app="myapp"} |~ "error.*timeout"

# JSON 解析
{app="myapp"} | json | level = "error"

# 统计查询
sum(rate({app="myapp"} |= "error" [5m]))

# 按 label 聚合
sum by (status) (rate({app="myapp"} | json [5m]))
```

---

## 4. 日志分析技巧

### 4.1 日志级别识别

| 级别 | 关键词 | 说明 |
|------|--------|------|
| DEBUG | DEBUG, debug, 调试 | 调试信息 |
| INFO | INFO, info, 信息 | 一般信息 |
| WARN | WARN, WARNING, warn, 警告 | 警告信息 |
| ERROR | ERROR, error, 错误 | 错误信息 |
| FATAL | FATAL, fatal, CRITICAL | 致命错误 |

### 4.2 常用分析模式

#### 错误频率分析
```bash
# 每小时错误数量
awk '{print substr($1, 1, 13)}' /var/log/app.log | grep "ERROR" | uniq -c

# 错误趋势
grep "ERROR" /var/log/app.log | awk '{print $1, $2}' | cut -d: -f1 | uniq -c
```

#### 关联分析
```bash
# 查找同一请求的完整日志
grep "request_id=abc123" /var/log/app.log

# 查找错误前后的上下文
grep -B 10 -A 10 "NullPointerException" /var/log/app.log
```

#### 性能分析
```bash
# 查找慢请求
grep -E "duration=[0-9]{4,}" /var/log/app.log

# 统计响应时间分布
awk -F'duration=' '{print $2}' /var/log/app.log | cut -d' ' -f1 | sort -n | uniq -c
```

---

## 5. 常见日志模式

### 5.1 应用错误日志

```
2025-04-05 10:30:15.123 ERROR [main] com.example.Service - Failed to process request
java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.Service.process(Service.java:100)
    at com.example.Controller.handle(Controller.java:50)
    at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
```

**分析要点**:
- 时间戳: 2025-04-05 10:30:15.123
- 日志级别: ERROR
- 线程: main
- 类名: com.example.Service
- 异常类型: NullPointerException
- 堆栈跟踪: 定位到具体代码行

### 5.2 Nginx 访问日志

```
192.168.1.100 - - [05/Apr/2025:10:30:15 +0800] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0" 0.050
```

**分析要点**:
- 客户端 IP: 192.168.1.100
- 时间: 05/Apr/2025:10:30:15 +0800
- 请求方法: GET
- 请求路径: /api/users
- 状态码: 200
- 响应大小: 1234 bytes
- User-Agent: Mozilla/5.0
- 响应时间: 0.050s

### 5.3 MySQL 慢查询日志

```
# Time: 2025-04-05T10:30:15.123456Z
# User@Host: app[app] @ 192.168.1.100 []
# Query_time: 5.123456  Lock_time: 0.000123  Rows_sent: 100  Rows_examined: 1000000
SET timestamp=1712313015;
SELECT * FROM orders WHERE user_id = 100;
```

**分析要点**:
- 执行时间: 5.123456s
- 锁等待时间: 0.000123s
- 返回行数: 100
- 扫描行数: 1000000
- SQL 语句: SELECT * FROM orders WHERE user_id = 100

---

## 6. 权限边界

### 6.1 安全的只读操作
```bash
cat, head, tail, less
grep, awk, sed, cut
sort, uniq, wc
find, ls
```

### 6.2 需要确认的操作
```bash
gzip, gunzip (压缩/解压日志)
mv, cp (移动/复制日志)
```

### 6.3 危险操作禁止执行
```bash
rm (删除日志)
> file (清空日志)
chmod, chown (修改权限)
```

---

## 7. 快速诊断脚本

```bash
#!/bin/bash
# 日志快速分析脚本

LOG_FILE="$1"
TIME_RANGE="${2:-1h}"

echo "=== 日志文件信息 ==="
ls -lh "$LOG_FILE"
echo "行数: $(wc -l < "$LOG_FILE")"

echo -e "\n=== 日志级别分布 ==="
grep -oE "(ERROR|WARN|INFO|DEBUG|FATAL)" "$LOG_FILE" 2>/dev/null | sort | uniq -c | sort -rn

echo -e "\n=== 最近 10 条错误 ==="
grep -E "ERROR|FATAL" "$LOG_FILE" | tail -10

echo -e "\n=== 错误类型分布 (Top 10) ==="
grep -E "ERROR|Exception" "$LOG_FILE" | grep -oE "[A-Z][a-zA-Z]*Exception" | sort | uniq -c | sort -rn | head -10

echo -e "\n=== 时间分布 (每小时) ==="
awk '{print substr($1, 1, 13)}' "$LOG_FILE" | uniq -c | tail -24

echo -e "\n=== IP 访问统计 (Top 10) ==="
awk '{print $1}' "$LOG_FILE" | sort | uniq -c | sort -rn | head -10
```

---

## 8. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
