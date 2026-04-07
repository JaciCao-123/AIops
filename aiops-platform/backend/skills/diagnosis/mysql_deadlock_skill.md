# MySQL 死锁排查技能

## 目录
- [0. 环境检测](#0-环境检测必须首先执行)
- [1. 死锁诊断流程](#1-死锁诊断流程)
- [2. 诊断命令集](#2-诊断命令集)
- [3. 死锁日志分析](#3-死锁日志分析)
- [4. 常见场景与解决方案](#4-常见场景与解决方案)
- [5. 预防措施](#5-预防措施)
- [6. 紧急处理命令](#6-紧急处理命令)
- [7. 权限边界](#7-权限边界)

---

## 适用场景
- 数据库死锁导致事务失败
- 锁等待超时 (Lock wait timeout exceeded)
- 事务阻塞导致应用响应缓慢
- 高并发场景下的锁竞争问题

## 触发关键词
- 死锁, deadlock, lock, 锁等待, lock wait
- 事务, transaction, 阻塞, blocking
- MySQL, 数据库, DB, RDS
- 行锁, 表锁, 间隙锁, gap lock
- 超时, timeout, 回滚, rollback

---

## 0. 环境检测（必须首先执行）

### 0.1 检测流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  1. 检测 MySQL 运行环境                                     │
│  2. 确定连接方式                                           │
│  3. 选择正确的命令执行方式                                 │
└─────────────────────────────────────────────────────────────┘
```

### 0.2 环境检测命令

#### 检测 MySQL 运行方式
```bash
# 检测 Docker 容器
docker ps | grep mysql

# 检测本地 MySQL 进程
ps aux | grep mysql | grep -v grep

# 检测 MySQL 端口
netstat -tlnp | grep :3306 || ss -tlnp | grep :3306

# 检测 MySQL 客户端
which mysql
```

### 0.3 连接方式决策树

```
用户查询: "本地 MySQL 死锁"
    │
    ├─ 是否在 Docker 容器中？
    │   ├─ 是 → 使用 docker exec 执行命令
    │   │        docker exec <container_name> mysql -u <user> -p<password> -e "SQL命令"
    │   │
    │   └─ 否 ↓
    │
    ├─ 是否有本地 MySQL 客户端？
    │   ├─ 是 → 直接执行 mysql 命令
    │   │        mysql -u <user> -p<password> -e "SQL命令"
    │   │
    │   └─ 否 ↓
    │
    └─ 是否需要远程连接？
        ├─ 是 → 使用 SSH + mysql 命令
        │        ssh <user>@<host> "mysql -u <db_user> -p<password> -e 'SQL命令'"
        │
        └─ 否 → 报错：无法连接到 MySQL
```

### 0.4 重要提示

⚠️ **本地 MySQL 连接注意事项**：

1. **不要使用 SSH 连接本地 MySQL**
   - ❌ 错误: `target_host=localhost` + SSH
   - ✅ 正确: 直接执行 `mysql` 命令或 `docker exec`

2. **Docker 环境处理**
   - 先检测容器名称: `docker ps | grep mysql`
   - 使用容器内执行: `docker exec <container> mysql ...`

3. **工具调用参数**
   - 本地 MySQL: `target_host` 留空或设为 `None`
   - Docker MySQL: 使用 `docker exec` 命令
   - 远程 MySQL: 使用 SSH 连接

---

## 1. 死锁诊断流程

### 1.1 流程图

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测（必须首先执行）                           │
│  - 检测 MySQL 运行环境                                      │
│  - 确定连接方式                                            │
│  - 选择正确的命令执行方式                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 确认死锁状态                                       │
│  - 检查 SHOW ENGINE INNODB STATUS                          │
│  - 查看死锁日志                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 分析锁等待链                                       │
│  - 识别阻塞事务和被阻塞事务                                 │
│  - 分析锁类型和锁定的资源                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 定位根因                                           │
│  - 检查事务隔离级别                                         │
│  - 分析 SQL 执行顺序                                        │
│  - 检查索引设计                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 提供解决方案                                       │
│  - 优化 SQL 和索引                                          │
│  - 调整事务顺序                                             │
│  - 修改隔离级别（如适用）                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 诊断命令集

### 2.1 死锁检测命令

#### 查看当前死锁信息
```sql
-- 查看 InnoDB 死锁状态
SHOW ENGINE INNODB STATUS\G
```

#### 查看当前锁等待（MySQL 8.0+）
```sql
-- MySQL 8.0+ 使用 performance_schema
SELECT 
    OBJECT_SCHEMA,
    OBJECT_NAME,
    LOCK_TYPE,
    LOCK_MODE,
    LOCK_STATUS,
    THREAD_ID,
    PROCESSLIST_ID
FROM performance_schema.data_locks
WHERE OBJECT_SCHEMA NOT IN ('mysql', 'performance_schema', 'information_schema')
ORDER BY OBJECT_SCHEMA, OBJECT_NAME;

-- 查看锁等待关系（MySQL 8.0+）
SELECT 
    waiting.THREAD_ID AS waiting_thread,
    waiting.PROCESSLIST_ID AS waiting_processlist,
    waiting.OBJECT_NAME AS waiting_object,
    blocking.THREAD_ID AS blocking_thread,
    blocking.PROCESSLIST_ID AS blocking_processlist,
    blocking.OBJECT_NAME AS blocking_object
FROM performance_schema.data_lock_waits
JOIN performance_schema.data_locks AS waiting 
    ON waiting.ENGINE_TRANSACTION_ID = data_lock_waits.WAITING_TRANSACTION_ID
JOIN performance_schema.data_locks AS blocking 
    ON blocking.ENGINE_TRANSACTION_ID = data_lock_waits.BLOCKING_TRANSACTION_ID;
```

⚠️ **注意**: MySQL 8.0 移除了 `information_schema.innodb_lock_waits` 表，请使用 `performance_schema.data_locks` 和 `performance_schema.data_lock_waits`。

#### 查看当前锁等待（MySQL 5.7 兼容）
```sql
-- MySQL 5.7 使用 information_schema
SELECT 
    requesting_trx_id AS waiting_trx_id,
    requested_lock_id AS waiting_lock_id,
    blocking_trx_id AS blocking_trx_id,
    blocking_lock_id AS blocking_lock_id
FROM information_schema.innodb_lock_waits;

-- 查看 InnoDB 状态（5.7 和 8.0 都支持）
SHOW ENGINE INNODB STATUS;
```

#### 查看当前活跃事务
```sql
-- 查看当前运行的事务（MySQL 5.7 和 8.0）
SELECT 
    trx_id,
    trx_state,
    trx_started,
    trx_mysql_thread_id,
    trx_query,
    trx_rows_locked,
    trx_lock_structs,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds
FROM information_schema.innodb_trx
ORDER BY trx_started;

-- 查看长事务（超过 60 秒）
SELECT 
    trx_id,
    trx_state,
    trx_mysql_thread_id,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds
FROM information_schema.innodb_trx
WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 60;
```

### 2.2 配置检查命令

#### 检查事务隔离级别
```sql
-- MySQL 8.0+
SELECT @@GLOBAL.transaction_isolation, @@SESSION.transaction_isolation;

-- MySQL 5.7
SELECT @@GLOBAL.tx_isolation, @@SESSION.tx_isolation;

-- 查看自动提交设置
SELECT @@autocommit;

-- 查看 InnoDB 锁等待超时
SHOW VARIABLES LIKE 'innodb_lock_wait_timeout';
```

#### 检查死锁日志配置
```sql
-- 查看死锁日志是否开启
SHOW VARIABLES LIKE 'innodb_print_all_deadlocks';

-- 开启死锁日志记录（需要 SUPER 权限）
SET GLOBAL innodb_print_all_deadlocks = ON;
```

### 2.3 表和索引分析

```sql
-- 查看表结构和索引
SHOW CREATE TABLE 表名;

-- 查看表索引
SHOW INDEX FROM 表名;

-- 分析表统计信息
ANALYZE TABLE 表名;

-- 查看表引擎和行格式
SELECT 
    TABLE_NAME,
    ENGINE,
    ROW_FORMAT,
    TABLE_ROWS,
    AVG_ROW_LENGTH,
    DATA_LENGTH,
    INDEX_LENGTH
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
AND TABLE_NAME = '表名';
```

---

## 3. 死锁日志分析

### 3.1 死锁日志示例

```
LATEST DETECTED DEADLOCK
------------------------
2025-04-02 10:30:15 0x7f8b4c0b4700
*** (1) TRANSACTION:
TRANSACTION 123456, ACTIVE 2 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 100, OS thread handle 140234567890, query id 1000 localhost root updating
UPDATE orders SET status = 'paid' WHERE order_id = 1001
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 58 page no 4 n bits 72 index PRIMARY of table `test`.`orders` 
trx id 123456 lock_mode X locks rec but not gap waiting
Record lock, heap no 3 PHYSICAL RECORD: n_fields 5; compact format; info bits 0
...

*** (2) TRANSACTION:
TRANSACTION 123457, ACTIVE 1 sec starting index read
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1136, 2 row lock(s)
MySQL thread id 101, OS thread handle 140234567891, query id 1001 localhost root updating
UPDATE orders SET amount = 200 WHERE order_id = 1002
*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 58 page no 4 n bits 72 index PRIMARY of table `test`.`orders` 
trx id 123457 lock_mode X locks rec but not gap
...
*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 58 page no 4 n bits 72 index PRIMARY of table `test`.`orders` 
trx id 123457 lock_mode X locks rec but not gap waiting
...
```

### 3.2 关键信息解读

| 字段 | 含义 |
|------|------|
| `TRANSACTION 123456` | 事务 ID |
| `ACTIVE 2 sec` | 事务活跃时间 |
| `lock_mode X` | 排他锁 (Exclusive Lock) |
| `lock_mode S` | 共享锁 (Shared Lock) |
| `locks rec but not gap` | 行锁，非间隙锁 |
| `locks rec and gap` | 行锁+间隙锁 |
| `gap lock` | 间隙锁 |
| `waiting` | 正在等待锁 |
| `HOLDS THE LOCK(S)` | 持有的锁 |
| `WE ROLL BACK TRANSACTION (X)` | MySQL 自动回滚的事务 |

### 3.3 死锁分析步骤（重要）

#### 步骤 1: 提取涉及的表和操作

从死锁日志中提取以下关键信息：

```
*** (1) TRANSACTION:
UPDATE accounts SET balance = balance + 100 WHERE id = 1
→ 表: deadlock_test.accounts
→ 操作: UPDATE
→ 条件: id = 1

*** (2) TRANSACTION:
UPDATE accounts SET balance = balance - 100 WHERE id = 2
→ 表: deadlock_test.accounts
→ 操作: UPDATE
→ 条件: id = 2
```

#### 步骤 2: 分析锁等待链

```
事务A (trx_id: 20025):
  - 持有锁: accounts 表 id=2 的行锁
  - 等待锁: accounts 表 id=1 的行锁

事务B (trx_id: 20026):
  - 持有锁: accounts 表 id=1 的行锁
  - 等待锁: accounts 表 id=2 的行锁

形成循环等待 → 死锁！
```

#### 步骤 3: 确定死锁类型

| 死锁类型 | 特征 | 解决方案 |
|---------|------|---------|
| **交叉更新** | 两个事务以不同顺序更新相同行 | 统一更新顺序 |
| **间隙锁冲突** | 一个插入，一个范围锁定 | 添加索引或调整隔离级别 |
| **外键约束** | 父子表操作冲突 | 为外键添加索引 |
| **自增锁** | 并发插入自增列 | 调整 innodb_autoinc_lock_mode |

#### 步骤 4: 立即解决死锁

**⚠️ 重要提示: KILL 命令需要人工审批**

终止事务的 `KILL` 命令属于高风险操作，必须经过人工确认后才能执行。

**方案 A: 终止长事务（需要人工确认）**

```sql
-- 1. 查找长事务
SELECT 
    trx_id,
    trx_mysql_thread_id AS thread_id,
    trx_state,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds
FROM information_schema.innodb_trx
ORDER BY trx_started;

-- 2. 终止长事务（需要人工执行或确认）
-- ⚠️ 此命令需要人工审批，请使用 ask_user_confirmation 工具获取确认
-- 或直接提供命令让用户手动执行：
-- KILL <thread_id>;
```

**方案 B: 终止阻塞事务（需要人工确认）**

```sql
-- 查找阻塞源
SELECT 
    blocking.trx_id AS blocking_trx,
    blocking.trx_mysql_thread_id AS blocking_thread,
    waiting.trx_id AS waiting_trx,
    waiting.trx_mysql_thread_id AS waiting_thread
FROM information_schema.innodb_trx blocking
JOIN information_schema.innodb_trx waiting 
    ON blocking.trx_id != waiting.trx_id
WHERE blocking.trx_started < waiting.trx_started;

-- 终止阻塞事务（需要人工执行或确认）
-- ⚠️ 此命令需要人工审批，请使用 ask_user_confirmation 工具获取确认
-- 或直接提供命令让用户手动执行：
-- KILL <blocking_thread>;
```

**正确的处理流程**：

1. **诊断阶段**: 执行查询命令，找出需要终止的 thread_id
2. **报告阶段**: 在诊断报告中明确列出需要执行的 KILL 命令
3. **人工确认**: 使用 `ask_user_confirmation` 工具询问用户是否执行
4. **执行阶段**: 
   - 如果用户确认，设置 `risk_level: "high"` 执行 KILL 命令
   - 如果用户拒绝，提供手动执行的 SQL 语句

**工具调用示例**：

```json
// 步骤 1: 查找需要终止的事务
{
  "tool": "execute_command",
  "parameters": {
    "command": "docker exec <container> mysql -u <user> -p<password> -e \"SELECT trx_mysql_thread_id AS thread_id, trx_state, TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds FROM information_schema.innodb_trx WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 30\""
  }
}

// 步骤 2: 询问用户确认（推荐方式）
{
  "tool": "ask_user_confirmation",
  "parameters": {
    "message": "发现长事务 thread_id=68 已运行 1870 秒，是否终止该事务？",
    "options": ["确认终止", "取消操作", "手动执行"]
  }
}

// 步骤 3a: 用户确认后执行（高风险操作）
{
  "tool": "execute_command",
  "parameters": {
    "command": "docker exec <container> mysql -u <user> -p<password> -e \"KILL 68\"",
    "risk_level": "high"
  }
}

// 步骤 3b: 用户选择手动执行（提供 SQL 语句）
// 在诊断报告中提供：
// "请在 MySQL 客户端手动执行以下命令：KILL 68;"
```

### 3.4 诊断报告模板（必须包含）

诊断完成后，必须生成包含以下内容的报告：

```markdown
# MySQL 死锁诊断报告

## 1. 死锁概要
- 检测时间: YYYY-MM-DD HH:MM:SS
- 死锁类型: [交叉更新/间隙锁/外键约束/其他]
- 涉及事务: 事务A (ID: xxx), 事务B (ID: xxx)

## 2. 涉及的表和操作（必须包含）

### 事务 A (trx_id: xxx, thread_id: xxx)
- **表名**: database_name.table_name
- **操作类型**: UPDATE/INSERT/DELETE
- **SQL 语句**: UPDATE accounts SET balance = balance + 100 WHERE id = 1
- **持有锁**: accounts 表 id=2 的行锁
- **等待锁**: accounts 表 id=1 的行锁

### 事务 B (trx_id: xxx, thread_id: xxx)
- **表名**: database_name.table_name
- **操作类型**: UPDATE/INSERT/DELETE
- **SQL 语句**: UPDATE accounts SET balance = balance - 100 WHERE id = 2
- **持有锁**: accounts 表 id=1 的行锁
- **等待锁**: accounts 表 id=2 的行锁

## 3. 锁等待链图示
```
事务A → 持有 id=2 锁 → 等待 id=1 锁
          ↑                    ↓
事务B ← 等待 id=2 锁 ← 持有 id=1 锁

形成循环等待 → 死锁！
```

## 4. 根因分析
- **直接原因**: 两个事务以相反顺序更新相同行
- **深层原因**: 
  - 事务隔离级别: REPEATABLE-READ
  - 缺少统一的行访问顺序
  - 长事务未及时提交

## 5. 立即解决方案（必须包含）

⚠️ **以下 KILL 命令需要人工审批后才能执行**

### 方案 1: 终止长事务（推荐）
```sql
-- 终止事务 A
KILL <thread_id_A>;

-- 或终止事务 B
KILL <thread_id_B>;
```

### 方案 2: 等待事务自动回滚
MySQL 会自动选择一个事务回滚（通常是事务 B）

### 方案 3: 手动执行（用户自行执行）
请在 MySQL 客户端手动执行以下命令：
```sql
KILL <thread_id>;
```

## 6. 长期预防措施
1. 统一更新顺序（按主键升序）
2. 减小事务粒度
3. 添加缺失索引
4. 考虑调整隔离级别
```

### 3.5 死锁日志解析示例（重要）

#### 原始日志示例

```
LATEST DETECTED DEADLOCK
------------------------
2026-04-02 05:56:37 281472255246080
*** (1) TRANSACTION:
TRANSACTION 20025, ACTIVE 2 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 3 lock struct(s), heap size 1128, 2 row lock(s), undo log entries 1
MySQL thread id 12, OS thread handle 281472562016000, query id 31 localhost root updating
UPDATE accounts SET balance = balance + 100 WHERE id = 1

*** (1) HOLDS THE LOCK(S):
RECORD LOCKS space id 26 page no 4 n bits 72 index PRIMARY of table `deadlock_test`.`accounts` 
trx id 20025 lock_mode X locks rec but not gap
Record lock, heap no 3 PHYSICAL RECORD: n_fields 8; compact format; info bits 0
 0: len 4; hex 80000002; asc     ;;  -- 这是 id=2

*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 26 page no 4 n bits 72 index PRIMARY of table `deadlock_test`.`accounts` 
trx id 20025 lock_mode X locks rec but not gap waiting
Record lock, heap no 2 PHYSICAL RECORD: n_fields 8; compact format; info bits 0
 0: len 4; hex 80000001; asc     ;;  -- 这是 id=1

*** (2) TRANSACTION:
TRANSACTION 20026, ACTIVE 1 sec starting index read
mysql tables in use 1, locked 1
3 lock struct(s), heap size 1128, 2 row lock(s)
MySQL thread id 13, OS thread handle 281472562016001, query id 32 localhost root updating
UPDATE accounts SET balance = balance - 100 WHERE id = 2

*** (2) HOLDS THE LOCK(S):
RECORD LOCKS space id 26 page no 4 n bits 72 index PRIMARY of table `deadlock_test`.`accounts` 
trx id 20026 lock_mode X locks rec but not gap
Record lock, heap no 2 PHYSICAL RECORD: n_fields 8; compact format; info bits 0
 0: len 4; hex 80000001; asc     ;;  -- 这是 id=1

*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 26 page no 4 n bits 72 index PRIMARY of table `deadlock_test`.`accounts` 
trx id 20026 lock_mode X locks rec but not gap waiting
Record lock, heap no 3 PHYSICAL RECORD: n_fields 8; compact format; info bits 0
 0: len 4; hex 80000002; asc     ;;  -- 这是 id=2

*** WE ROLL BACK TRANSACTION (2)
```

#### 解析结果

| 项目 | 事务 A | 事务 B |
|------|--------|--------|
| trx_id | 20025 | 20026 |
| thread_id | 12 | 13 |
| SQL | `UPDATE ... WHERE id=1` | `UPDATE ... WHERE id=2` |
| 持有锁 | id=2 | id=1 |
| 等待锁 | id=1 | id=2 |
| 结果 | 继续执行 | 已回滚 |

---

## 4. 常见场景与解决方案

### 4.1 场景一：交叉更新

**问题**：
```sql
-- 事务 A
UPDATE orders SET status = 'paid' WHERE order_id = 1;
UPDATE orders SET status = 'paid' WHERE order_id = 2;

-- 事务 B（同时执行）
UPDATE orders SET status = 'shipped' WHERE order_id = 2;
UPDATE orders SET status = 'shipped' WHERE order_id = 1;
```

**解决方案**：
- 统一更新顺序（按主键升序）
- 使用乐观锁替代悲观锁
- 减小事务粒度

**代码示例（Python）**：
```python
# 错误示例：不同顺序更新
def transfer_wrong(db, from_id, to_id, amount):
    db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, from_id))
    db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))

# 正确示例：统一按 ID 排序后更新
def transfer_correct(db, from_id, to_id, amount):
    first_id, second_id = sorted([from_id, to_id])
    if first_id == from_id:
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, first_id))
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, second_id))
    else:
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, first_id))
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, second_id))
```

### 4.2 场景二：间隙锁冲突

**问题**：
```sql
-- 事务 A：在间隙中插入
INSERT INTO orders (order_id, status) VALUES (1001, 'pending');

-- 事务 B：锁定范围
SELECT * FROM orders WHERE order_id > 1000 AND order_id < 1010 FOR UPDATE;
```

**解决方案**：
- 创建合适的索引避免全表扫描
- 调整隔离级别为 READ COMMITTED（需评估影响）
- 优化查询条件

### 4.3 场景三：外键约束死锁

**问题**：
```sql
-- 父表更新时锁定子表
UPDATE parent SET status = 'inactive' WHERE id = 1;
-- 子表同时插入
INSERT INTO child (parent_id, value) VALUES (1, 'test');
```

**解决方案**：
- 为外键列添加索引
- 批量操作时暂时禁用外键检查
- 优化事务顺序

---

## 5. 预防措施

### 5.1 索引优化

```sql
-- 检查缺失索引
SELECT 
    TABLE_NAME,
    COLUMN_NAME,
    CARDINALITY
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, SEQ_IN_INDEX;

-- 建议添加索引（示例）
ALTER TABLE orders ADD INDEX idx_status (status);
ALTER TABLE orders ADD INDEX idx_created_at (created_at);
```

### 5.2 事务优化建议

1. **减小事务粒度**
   - 避免长事务
   - 将大事务拆分为小事务
   - 及时提交事务

2. **统一访问顺序**
   - 按主键顺序访问
   - 避免交叉更新

3. **合理使用锁**
   - 避免使用 `SELECT ... FOR UPDATE`
   - 考虑使用乐观锁
   - 使用适当的隔离级别

### 5.3 监控配置

```sql
-- 设置合理的锁等待超时（默认 50 秒）
SET GLOBAL innodb_lock_wait_timeout = 30;

-- 开启死锁日志
SET GLOBAL innodb_print_all_deadlocks = ON;

-- 配置慢查询日志
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 2;
```

---

## 6. 紧急处理命令

### 6.1 查找并终止阻塞事务

```sql
-- 查找阻塞的事务
SELECT 
    trx_id,
    trx_mysql_thread_id,
    trx_state,
    TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds,
    trx_query
FROM information_schema.innodb_trx
WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 30
ORDER BY trx_started;
```

⚠️ **KILL 命令需要人工审批后才能执行**

### 6.2 查看当前连接

```sql
-- 查看所有连接
SHOW PROCESSLIST;

-- 查看完整连接信息
SELECT 
    ID,
    USER,
    HOST,
    DB,
    COMMAND,
    TIME,
    STATE,
    LEFT(INFO, 100) AS QUERY
FROM information_schema.PROCESSLIST
WHERE COMMAND != 'Sleep'
ORDER BY TIME DESC;
```

---

## 7. 权限边界

### 7.1 安全操作（可直接执行）
- `SHOW ENGINE INNODB STATUS`
- `SHOW PROCESSLIST`
- 查询 `information_schema` 表
- 查询 `performance_schema` 表

### 7.2 需确认操作
- `KILL` 终止连接
- `SET GLOBAL` 修改配置
- `ALTER TABLE` 修改表结构
- `ANALYZE TABLE` 分析表

### 7.3 禁止操作
- `DROP TABLE` / `DROP DATABASE`
- `TRUNCATE TABLE`
- `DELETE` 无 WHERE 条件
- 直接修改系统表

---

## 8. 完整工具调用示例

### 8.1 环境检测（必须首先执行）

```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "docker ps | grep mysql",
    "risk_level": "low"
  }
}
```

### 8.2 获取死锁日志

```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "docker exec <container_name> mysql -u <user> -p<password> -e \"SHOW ENGINE INNODB STATUS\\G\"",
    "risk_level": "low"
  }
}
```

### 8.3 查看活跃事务

```json
{
  "tool": "execute_command",
  "parameters": {
    "command": "docker exec <container_name> mysql -u <user> -p<password> -e \"SELECT trx_id, trx_mysql_thread_id, trx_state, TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds FROM information_schema.innodb_trx\"",
    "risk_level": "low"
  }
}
```

### 8.4 提交诊断结果

```json
{
  "tool": "submit_diagnosis_result",
  "parameters": {
    "problem_type": "MySQL 死锁",
    "root_cause": "交叉更新导致死锁，涉及表 deadlock_test.accounts",
    "impact": "两个事务阻塞，影响账户余额更新操作",
    "recommendation": "1. 终止长事务 (KILL thread_id)\n2. 统一更新顺序\n3. 减小事务粒度",
    "risk_level": "MEDIUM",
    "confidence": "HIGH"
  }
}
```

**注意**: Docker 环境不需要设置 `target_host` 参数。