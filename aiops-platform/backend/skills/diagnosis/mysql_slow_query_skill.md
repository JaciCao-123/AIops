# MySQL 慢查询分析技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 慢查询分析](#4-慢查询分析)
- [5. 优化建议](#5-优化建议)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `慢查询`, `slow query`, `SQL优化`, `查询慢`
- `MySQL`, `数据库`, `DB`, `RDS`
- `EXPLAIN`, `执行计划`, `索引`, `性能`
- `慢日志`, `slow log`, `long_query_time`

### 1.2 适用条件
- 数据库查询响应缓慢
- 需要分析慢查询日志
- SQL 性能优化
- 索引优化建议
- 查询执行计划分析

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 MySQL 运行环境 (Docker/本地/远程)                   │
│  - 确定连接方式                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 检查慢查询配置                                     │
│  - 查看慢查询日志是否开启                                   │
│  - 检查 long_query_time 设置                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 分析慢查询日志                                     │
│  - 查看最近的慢查询                                        │
│  - 统计慢查询分布                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 分析执行计划                                       │
│  - 使用 EXPLAIN 分析 SQL                                   │
│  - 识别性能瓶颈                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 提供优化建议                                       │
│  - 索引优化建议                                            │
│  - SQL 重写建议                                            │
│  - 配置调整建议                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测命令

```bash
# 检测 Docker 容器
docker ps | grep mysql

# 检测本地 MySQL 进程
ps aux | grep mysql | grep -v grep

# 检测 MySQL 端口
netstat -tlnp | grep :3306 || ss -tlnp | grep :3306
```

### 3.2 慢查询配置检查

```sql
-- 查看慢查询日志配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';
SHOW VARIABLES LIKE 'log_queries_not_using_indexes';

-- 查看慢查询日志位置
SHOW VARIABLES LIKE 'slow_query_log_file';

-- 开启慢查询日志（需要 SUPER 权限）
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
SET GLOBAL log_queries_not_using_indexes = 'ON';
```

### 3.3 慢查询日志分析

#### 使用 mysqldumpslow 分析
```bash
# 按查询时间排序，显示前 10 条
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log

# 按查询次数排序
mysqldumpslow -s c -t 10 /var/log/mysql/slow.log

# 按锁等待时间排序
mysqldumpslow -s l -t 10 /var/log/mysql/slow.log

# 按返回记录数排序
mysqldumpslow -s r -t 10 /var/log/mysql/slow.log

# Docker 环境
docker exec <container> mysqldumpslow -s t -t 10 /var/log/mysql/slow.log
```

#### 使用 performance_schema 分析（MySQL 5.7+）
```sql
-- 查看慢查询统计
SELECT 
    DIGEST_TEXT AS query,
    COUNT_STAR AS exec_count,
    AVG_TIMER_WAIT/1000000000 AS avg_latency_ms,
    SUM_ROWS_EXAMINED AS rows_examined,
    SUM_ROWS_SENT AS rows_sent
FROM performance_schema.events_statements_summary_by_digest
ORDER BY AVG_TIMER_WAIT DESC
LIMIT 10;

-- 查看全表扫描的 SQL
SELECT 
    DIGEST_TEXT AS query,
    COUNT_STAR AS exec_count,
    SUM_NO_INDEX_USED AS no_index_count
FROM performance_schema.events_statements_summary_by_digest
WHERE SUM_NO_INDEX_USED > 0
ORDER BY SUM_NO_INDEX_USED DESC
LIMIT 10;
```

### 3.4 执行计划分析

```sql
-- 查看执行计划
EXPLAIN SELECT * FROM orders WHERE user_id = 100;

-- 查看完整执行计划（MySQL 8.0+）
EXPLAIN ANALYZE SELECT * FROM orders WHERE user_id = 100;

-- 查看执行计划 JSON 格式
EXPLAIN FORMAT=JSON SELECT * FROM orders WHERE user_id = 100;
```

### 3.5 索引分析

```sql
-- 查看表索引
SHOW INDEX FROM orders;

-- 查看表统计信息
SHOW TABLE STATUS LIKE 'orders';

-- 分析表
ANALYZE TABLE orders;

-- 查看索引使用情况
SELECT 
    OBJECT_SCHEMA,
    OBJECT_NAME,
    INDEX_NAME,
    COUNT_READ,
    COUNT_FETCH
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE OBJECT_SCHEMA = 'your_database'
ORDER BY COUNT_READ DESC;

-- 查看未使用的索引
SELECT 
    OBJECT_SCHEMA,
    OBJECT_NAME,
    INDEX_NAME
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE INDEX_NAME IS NOT NULL
AND COUNT_READ = 0
AND COUNT_WRITE = 0
AND OBJECT_SCHEMA NOT IN ('mysql', 'performance_schema', 'information_schema');
```

---

## 4. 慢查询分析

### 4.1 EXPLAIN 输出解读

| 列名 | 说明 | 关注点 |
|------|------|--------|
| id | 查询标识符 | 相同 id 表示并行执行 |
| select_type | 查询类型 | 避免 DEPENDENT SUBQUERY |
| table | 表名 | - |
| partitions | 分区 | - |
| type | 访问类型 | 期望 system/const/eq_ref/ref/range |
| possible_keys | 可能使用的索引 | - |
| key | 实际使用的索引 | 不应为 NULL |
| key_len | 索引长度 | 越短越好 |
| ref | 索引比较的列 | - |
| rows | 预估扫描行数 | 越少越好 |
| filtered | 过滤百分比 | 越高越好 |
| Extra | 额外信息 | 避免 Using filesort, Using temporary |

### 4.2 type 类型说明（从优到差）

| type | 说明 | 性能 |
|------|------|------|
| system | 单行系统表 | 最优 |
| const | 单行常量 | 最优 |
| eq_ref | 唯一索引扫描 | 优 |
| ref | 非唯一索引扫描 | 良 |
| range | 索引范围扫描 | 中 |
| index | 全索引扫描 | 较差 |
| ALL | 全表扫描 | 最差 |

### 4.3 Extra 字段警告

| Extra 值 | 含义 | 建议 |
|---------|------|------|
| Using filesort | 文件排序 | 添加合适索引 |
| Using temporary | 使用临时表 | 优化 GROUP BY/ORDER BY |
| Using join buffer | 连接缓冲 | 添加索引或增加缓冲区 |
| Using where | WHERE 过滤 | 正常，但应配合索引 |
| Using index | 覆盖索引 | 良好 |
| Using index condition | 索引下推 | 良好 |

---

## 5. 优化建议

### 5.1 索引优化原则

1. **最左前缀原则**
   - 复合索引从左到右匹配
   - 查询条件应包含索引最左列

2. **选择性原则**
   - 选择区分度高的列
   - 选择性 = 不同值数量 / 总行数

```sql
-- 计算列选择性
SELECT 
    COUNT(DISTINCT column_name) / COUNT(*) AS selectivity
FROM table_name;
```

3. **覆盖索引**
   - 索引包含查询所需的所有列
   - 避免回表查询

4. **避免索引失效**
   - 避免在索引列上使用函数
   - 避免隐式类型转换
   - 避免使用 !=, <>, NOT IN
   - 避免 OR 连接不同字段

### 5.2 SQL 优化建议

```sql
-- 避免 SELECT *
SELECT id, name FROM users WHERE id = 1;

-- 避免在 WHERE 子句中使用函数
-- 不推荐
SELECT * FROM users WHERE DATE(created_at) = '2025-01-01';
-- 推荐
SELECT * FROM users WHERE created_at >= '2025-01-01' AND created_at < '2025-01-02';

-- 大分页优化
-- 不推荐
SELECT * FROM orders LIMIT 100000, 10;
-- 推荐
SELECT * FROM orders WHERE id > 100000 LIMIT 10;

-- 避免 OR 连接不同字段
-- 不推荐
SELECT * FROM users WHERE name = 'test' OR email = 'test@test.com';
-- 推荐
SELECT * FROM users WHERE name = 'test'
UNION
SELECT * FROM users WHERE email = 'test@test.com';

-- 使用 EXISTS 替代 IN
-- 不推荐
SELECT * FROM orders WHERE user_id IN (SELECT id FROM users WHERE status = 1);
-- 推荐
SELECT * FROM orders o WHERE EXISTS (SELECT 1 FROM users u WHERE u.id = o.user_id AND u.status = 1);
```

### 5.3 配置优化

```sql
-- 调整缓冲池大小（建议物理内存的 60-80%）
SET GLOBAL innodb_buffer_pool_size = 4294967296; -- 4GB

-- 调整连接数
SET GLOBAL max_connections = 500;

-- 调整查询缓存（MySQL 5.7）
SET GLOBAL query_cache_size = 67108864; -- 64MB

-- 调整排序缓冲区
SET GLOBAL sort_buffer_size = 2097152; -- 2MB

-- 调整连接缓冲区
SET GLOBAL join_buffer_size = 2097152; -- 2MB
```

---

## 6. 权限边界

### 6.1 安全的只读操作
```sql
SHOW VARIABLES, SHOW STATUS, SHOW INDEX
EXPLAIN, EXPLAIN ANALYZE
SELECT from performance_schema.*
SELECT from information_schema.*
ANALYZE TABLE
```

### 6.2 需要确认的操作
```sql
SET GLOBAL (配置修改)
CREATE INDEX, DROP INDEX
ALTER TABLE
OPTIMIZE TABLE
```

### 6.3 危险操作禁止执行
```sql
DROP TABLE, DROP DATABASE
TRUNCATE TABLE
DELETE without WHERE
UPDATE without WHERE
```

---

## 7. 诊断报告模板

```markdown
# MySQL 慢查询分析报告

## 1. 概要信息
- 数据库: [database_name]
- 分析时间: [timestamp]
- 慢查询数量: [count]

## 2. Top 10 慢查询
| 排名 | 查询摘要 | 执行次数 | 平均耗时(ms) | 扫描行数 |
|------|---------|---------|-------------|---------|
| 1 | SELECT * FROM orders WHERE... | 100 | 2500 | 100000 |

## 3. 问题 SQL 分析
### SQL 1
```sql
SELECT * FROM orders WHERE user_id = 100;
```

**执行计划**:
| type | key | rows | Extra |
|------|-----|------|-------|
| ALL | NULL | 100000 | Using where |

**问题**: 全表扫描，未使用索引

**建议**: 为 user_id 列添加索引
```sql
CREATE INDEX idx_user_id ON orders(user_id);
```

## 4. 索引建议
- orders.user_id: 添加索引
- order_items.order_id: 添加索引

## 5. 配置建议
- long_query_time: 建议调整为 1 秒
- innodb_buffer_pool_size: 建议调整为 4GB
```

---

## 8. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
