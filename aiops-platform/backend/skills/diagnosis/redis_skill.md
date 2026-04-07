# Redis 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `Redis`, `缓存`, `内存`, `key`
- `缓存穿透`, `缓存击穿`, `缓存雪崩`
- `连接超时`, `OOM`, `持久化`
- `主从`, `哨兵`, `集群`, `Cluster`

### 1.2 适用条件
- Redis 连接问题
- 内存使用异常
- 性能下降
- 持久化问题
- 主从同步问题
- 集群状态异常

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 Redis 运行环境 (Docker/本地/远程)                   │
│  - 确定连接方式                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 检查 Redis 状态                                    │
│  - 连接测试                                                │
│  - 基本信息                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 内存分析                                           │
│  - 内存使用情况                                            │
│  - 大 Key 分析                                             │
│  - 内存碎片                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 性能分析                                           │
│  - 慢查询日志                                              │
│  - 命令统计                                                │
│  - 连接数                                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 持久化与高可用检查                                 │
│  - RDB/AOF 状态                                            │
│  - 主从同步状态                                            │
│  - 集群状态                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测与连接

```bash
# 检测 Redis 进程
ps aux | grep redis-server

# 检测 Redis 端口
netstat -tlnp | grep 6379 || ss -tlnp | grep 6379

# 检测 Docker 容器
docker ps | grep redis

# 连接测试
redis-cli ping
redis-cli -h <host> -p <port> ping
redis-cli -h <host> -p <port> -a <password> ping

# Docker 环境
docker exec <container> redis-cli ping
```

### 3.2 基本信息

```bash
# 查看服务器信息
redis-cli INFO

# 查看特定信息
redis-cli INFO server
redis-cli INFO memory
redis-cli INFO stats
redis-cli INFO replication
redis-cli INFO persistence
redis-cli INFO clients

# 查看配置
redis-cli CONFIG GET "*"
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy

# 查看当前数据库大小
redis-cli DBSIZE
```

### 3.3 内存分析

```bash
# 内存使用概览
redis-cli INFO memory

# 关键内存指标
redis-cli INFO memory | grep -E "used_memory|mem_fragmentation|maxmemory"

# 查看内存配置
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy

# 分析大 Key
redis-cli --bigkeys
redis-cli --bigkeys -i 0.1  # 每隔 0.1 秒采样

# 分析热点 Key（Redis 4.0+）
redis-cli --hotkeys

# 查看特定 Key 的内存占用
redis-cli MEMORY USAGE <key>
redis-cli MEMORY USAGE <key> SAMPLES 1000

# 内存碎片分析
redis-cli INFO memory | grep mem_fragmentation_ratio
```

### 3.4 性能分析

```bash
# 查看慢查询日志
redis-cli SLOWLOG GET
redis-cli SLOWLOG GET 10  # 最近 10 条
redis-cli SLOWLOG LEN     # 慢查询数量
redis-cli SLOWLOG RESET   # 清空慢查询日志

# 查看慢查询配置
redis-cli CONFIG GET slowlog-*
redis-cli CONFIG GET slowlog-log-slower-than
redis-cli CONFIG GET slowlog-max-len

# 命令统计
redis-cli INFO commandstats

# 实时监控命令
redis-cli MONITOR

# 查看客户端连接
redis-cli CLIENT LIST
redis-cli CLIENT LIST | wc -l  # 连接数

# 查看连接配置
redis-cli CONFIG GET maxclients
```

### 3.5 Key 分析

```bash
# 查看所有 Key（慎用，生产环境禁止）
redis-cli KEYS "*"

# 安全的方式：使用 SCAN
redis-cli SCAN 0 MATCH "user:*" COUNT 100

# 查看 Key 类型
redis-cli TYPE <key>

# 查看 Key 过期时间
redis-cli TTL <key>
redis-cli PTTL <key>  # 毫秒

# 查看 Key 编码类型
redis-cli OBJECT ENCODING <key>

# 查看 Key 引用计数
redis-cli OBJECT REFCOUNT <key>

# 查看 Key 空闲时间
redis-cli OBJECT IDLETIME <key>
```

### 3.6 持久化检查

```bash
# RDB 持久化状态
redis-cli INFO persistence | grep rdb

# AOF 持久化状态
redis-cli INFO persistence | grep aof

# 查看持久化配置
redis-cli CONFIG GET save
redis-cli CONFIG GET appendonly
redis-cli CONFIG GET appendfsync

# 手动触发 RDB
redis-cli BGSAVE
redis-cli LASTSAVE  # 查看上次保存时间

# 手动触发 AOF 重写
redis-cli BGREWRITEAOF
```

### 3.7 主从与集群

```bash
# 查看主从状态
redis-cli INFO replication

# 主从同步状态
redis-cli ROLE

# 集群状态
redis-cli CLUSTER INFO
redis-cli CLUSTER NODES

# 集群槽位分布
redis-cli CLUSTER SLOTS

# 哨兵状态
redis-cli -p 26379 SENTINEL masters
redis-cli -p 26379 SENTINEL slaves <master-name>
redis-cli -p 26379 SENTINEL master <master-name>
```

---

## 4. 常见问题与解决方案

### 4.1 内存不足 (OOM)

**现象**: Redis 内存达到上限，写入失败

**诊断步骤**:
```bash
# 1. 查看内存使用
redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human"

# 2. 查看淘汰策略
redis-cli CONFIG GET maxmemory-policy

# 3. 分析大 Key
redis-cli --bigkeys
```

**解决方案**:
```bash
# 1. 调整内存上限
redis-cli CONFIG SET maxmemory 4gb

# 2. 设置淘汰策略
# volatile-lru: 淘汰设置了过期时间的最近最少使用的 key
# allkeys-lru: 淘汰所有最近最少使用的 key
# volatile-lfu: 淘汰设置了过期时间的最不经常使用的 key
# allkeys-lfu: 淘汰所有最不经常使用的 key
# volatile-random: 随机淘汰设置了过期时间的 key
# allkeys-random: 随机淘汰所有 key
# volatile-ttl: 淘汰即将过期的 key
# noeviction: 不淘汰，内存满时返回错误
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# 3. 清理特定前缀的 Key
redis-cli --scan --pattern "cache:*" | xargs redis-cli DEL
```

### 4.2 缓存穿透

**现象**: 大量请求查询不存在的 Key，直接打到数据库

**诊断步骤**:
```bash
# 1. 监控请求
redis-cli MONITOR | grep "GET"

# 2. 查看命中率
redis-cli INFO stats | grep keyspace
```

**解决方案**:
```bash
# 1. 缓存空值
SET nonexistent_key "" EX 60

# 2. 使用布隆过滤器（Redis 4.0+）
# 需要安装 RedisBloom 模块
BF.ADD filter item1
BF.EXISTS filter item1
```

### 4.3 缓存击穿

**现象**: 热点 Key 过期瞬间大量请求打到数据库

**诊断步骤**:
```bash
# 1. 查看热点 Key
redis-cli --hotkeys

# 2. 查看热点 Key 的 TTL
redis-cli TTL hot_key
```

**解决方案**:
```bash
# 1. 设置热点 Key 永不过期
redis-cli PERSIST hot_key

# 2. 使用互斥锁
SET lock:key 1 NX EX 10

# 3. 逻辑过期（在 Value 中存储过期时间）
```

### 4.4 缓存雪崩

**现象**: 大量 Key 同时过期，请求全部打到数据库

**诊断步骤**:
```bash
# 1. 查看即将过期的 Key
redis-cli --scan | while read key; do
  ttl=$(redis-cli TTL "$key")
  if [ "$ttl" -gt 0 ] && [ "$ttl" -lt 60 ]; then
    echo "$key: $ttl"
  fi
done
```

**解决方案**:
```bash
# 1. 设置随机过期时间
# 在应用层设置过期时间时添加随机值

# 2. 设置永不过期，后台异步更新
```

### 4.5 连接数过多

**现象**: 客户端连接数达到上限

**诊断步骤**:
```bash
# 1. 查看当前连接数
redis-cli CLIENT LIST | wc -l

# 2. 查看连接配置
redis-cli CONFIG GET maxclients

# 3. 查看空闲连接
redis-cli CLIENT LIST | grep -E "idle=[0-9]{4,}"
```

**解决方案**:
```bash
# 1. 增加最大连接数
redis-cli CONFIG SET maxclients 10000

# 2. 关闭空闲连接
redis-cli CLIENT LIST | grep -E "idle=[0-9]{4,}" | awk '{print $2}' | cut -d= -f2 | xargs -I {} redis-cli CLIENT KILL ID {}

# 3. 设置超时
redis-cli CONFIG SET timeout 300
```

### 4.6 主从同步延迟

**现象**: 主从数据不一致

**诊断步骤**:
```bash
# 1. 查看主从状态
redis-cli INFO replication

# 2. 查看同步偏移量
redis-cli INFO replication | grep offset
```

**解决方案**:
```bash
# 1. 检查网络延迟
# 2. 优化主从配置
redis-cli CONFIG SET repl-timeout 60
redis-cli CONFIG SET repl-backlog-size 256mb

# 3. 检查从节点负载
```

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
INFO, CONFIG GET, DBSIZE
SLOWLOG GET, CLIENT LIST
MEMORY USAGE, --bigkeys, --hotkeys
MONITOR (只观察)
```

### 5.2 需要确认的操作
```bash
CONFIG SET
FLUSHDB, FLUSHALL
DEL (批量删除)
CLIENT KILL
BGSAVE, BGREWRITEAOF
```

### 5.3 危险操作禁止执行
```bash
FLUSHALL
FLUSHDB
KEYS * (生产环境)
DEBUG RELOAD
SHUTDOWN
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
# Redis 快速诊断脚本

HOST="${1:-localhost}"
PORT="${2:-6379}"
REDIS_CLI="redis-cli -h $HOST -p $PORT"

echo "=== Redis 连接测试 ==="
$REDIS_CLI ping

echo -e "\n=== 基本信息 ==="
$REDIS_CLI INFO server | grep -E "redis_version|uptime_in_days|connected_clients"

echo -e "\n=== 内存使用 ==="
$REDIS_CLI INFO memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

echo -e "\n=== 连接数 ==="
echo "当前连接数: $($REDIS_CLI CLIENT LIST | wc -l)"
echo "最大连接数: $($REDIS_CLI CONFIG GET maxclients | tail -1)"

echo -e "\n=== 命令统计 ==="
$REDIS_CLI INFO stats | grep -E "total_commands_processed|instantaneous_ops_per_sec|keyspace_hits|keyspace_misses"

echo -e "\n=== 持久化状态 ==="
$REDIS_CLI INFO persistence | grep -E "rdb_last_save_time|rdb_changes_since_last_save|aof_enabled"

echo -e "\n=== 慢查询 (最近 5 条) ==="
$REDIS_CLI SLOWLOG GET 5
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
