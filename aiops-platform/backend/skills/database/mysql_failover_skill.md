# MySQL 主从故障人工切换 Skill

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 异常检测](#3-异常检测)
- [4. 主从切换](#4-主从切换)
- [5. 数据同步验证](#5-数据同步验证)
- [6. 测试验证](#6-测试验证)
- [7. 权限边界](#7-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `主库故障`, `master down`, `主库宕机`, `主库不可用`
- `主从切换`, `failover`, `手动切换`, `人工切换`
- `写入失败`, `连接主库失败`, `主库无响应`
- `从库提升`, `slave promote`, `主从角色互换`

### 1.2 适用条件
- 持续写入进程检测到主库异常
- 主库 MySQL 服务不可用（进程崩溃/服务器宕机/网络中断）
- 主从架构未配置自动切换（无 MHA/Orchestrator）
- 需要人工介入进行主从切换

### 1.3 前置条件
- 已部署 MySQL 主从复制架构
- 从库复制状态正常（IO/SQL 线程运行中）
- 有 SSH 访问权限到主从服务器
- 有 MySQL root 或管理员权限

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 异常检测                                           │
│  - 检测写入进程报错                                          │
│  - 检测主库连通性                                            │
│  - 检测主库 MySQL 服务状态                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 从库状态评估                                        │
│  - 检查从库复制状态                                          │
│  - 确认从库数据完整性                                        │
│  - 评估数据延迟                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 执行主从切换                                        │
│  - 停止从库复制                                              │
│  - 提升从库为新主库                                          │
│  - 更新应用连接配置                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 数据同步验证                                        │
│  - 验证新主库可写                                            │
│  - 配置原主库为新从库（可选）                                 │
│  - 验证数据一致性                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 测试验证                                            │
│  - 测试写入进程恢复                                          │
│  - 验证数据完整性                                            │
│  - 记录切换日志                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 异常检测

### 3.1 写入进程异常检测

**写入进程常见报错**:
```
ERROR 2003 (HY000): Can't connect to MySQL server on '47.114.77.62'
ERROR 2013 (HY000): Lost connection to MySQL server during query
ERROR 2006 (HY000): MySQL server has gone away
```

**检测脚本**:
```bash
#!/bin/bash
# 检测主库连通性

MASTER_HOST="47.114.77.62"
MASTER_PORT="3306"
MYSQL_USER="root"
MYSQL_PASS="Root@123456"

# 方法1: TCP 端口检测
check_tcp() {
    timeout 5 bash -c "cat < /dev/null > /dev/tcp/${MASTER_HOST}/${MASTER_PORT}" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "[CRITICAL] 主库 TCP 端口 ${MASTER_PORT} 不可达"
        return 1
    fi
    echo "[OK] 主库 TCP 端口可达"
    return 0
}

# 方法2: MySQL 连接检测
check_mysql() {
    mysql -h "${MASTER_HOST}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "SELECT 1" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "[CRITICAL] 主库 MySQL 连接失败"
        return 1
    fi
    echo "[OK] 主库 MySQL 连接正常"
    return 0
}

# 方法3: 写入测试
check_write() {
    mysql -h "${MASTER_HOST}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "
        INSERT INTO test_replication.health_check (check_time) VALUES (NOW());
    " 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "[CRITICAL] 主库写入失败"
        return 1
    fi
    echo "[OK] 主库写入正常"
    return 0
}

# 执行检测
echo "========== 主库健康检查 =========="
check_tcp
TCP_STATUS=$?
check_mysql
MYSQL_STATUS=$?
check_write
WRITE_STATUS=$?

# 判断主库状态
if [ $TCP_STATUS -ne 0 ] || [ $MYSQL_STATUS -ne 0 ] || [ $WRITE_STATUS -ne 0 ]; then
    echo ""
    echo "[ALERT] 主库异常，需要切换到从库！"
    exit 1
fi

echo ""
echo "[OK] 主库状态正常"
exit 0
```

### 3.2 主库服务状态检测

```bash
# SSH 到主库服务器检测 MySQL 服务状态
ssh jaci@47.114.77.62 "
    echo '=== MySQL 服务状态 ==='
    systemctl status mysqld 2>/dev/null || service mysql status 2>/dev/null
    
    echo ''
    echo '=== MySQL 进程 ==='
    ps aux | grep -E 'mysqld|mysql' | grep -v grep
    
    echo ''
    echo '=== MySQL 错误日志 (最近20行) ==='
    tail -20 /var/log/mysqld.log 2>/dev/null || tail -20 /var/log/mysql/error.log 2>/dev/null
"
```

### 3.3 从库状态评估

```sql
-- 在从库执行，评估从库是否可以提升为主库

-- 1. 检查复制状态
SHOW SLAVE STATUS\G

-- 关键指标:
-- Slave_IO_Running: Yes
-- Slave_SQL_Running: Yes
-- Seconds_Behind_Master: 0 (越小越好，0表示完全同步)
-- Last_IO_Error: (应为空)
-- Last_SQL_Error: (应为空)

-- 2. 检查已执行的 GTID
SELECT @@GLOBAL.GTID_EXECUTED;

-- 3. 检查 Relay Log 是否已全部应用
SHOW PROCESSLIST;
-- 状态应为 "Slave has read all relay log; waiting for more updates"
```

---

## 4. 主从切换

### 4.1 切换前检查清单

| 检查项 | 命令 | 期望结果 |
|--------|------|----------|
| 从库 IO 线程 | `SHOW SLAVE STATUS` | Slave_IO_Running: Yes |
| 从库 SQL 线程 | `SHOW SLAVE STATUS` | Slave_SQL_Running: Yes |
| 复制延迟 | `SHOW SLAVE STATUS` | Seconds_Behind_Master: 0 |
| 从库数据完整性 | `SELECT COUNT(*) FROM db.table` | 与主库一致 |
| 从库只读状态 | `SHOW VARIABLES LIKE 'read_only'` | ON |

### 4.2 执行切换

#### Step 1: 确保从库已同步所有数据

```bash
# 在从库执行
mysql -u root -p'Root@123456' -e "
    -- 检查复制延迟
    SHOW SLAVE STATUS\G
    
    -- 等待 Relay Log 全部应用（如果 Seconds_Behind_Master > 0）
    -- 可以多次执行直到延迟为 0
"
```

#### Step 2: 停止从库复制并提升为主库

```sql
-- 在从库 (8.136.226.231) 执行

-- 1. 停止复制
STOP SLAVE;

-- 2. 重置从库身份
RESET SLAVE ALL;

-- 3. 关闭只读模式
SET GLOBAL read_only = OFF;
SET GLOBAL super_read_only = OFF;

-- 4. 验证新主库状态
SHOW MASTER STATUS;
SHOW VARIABLES LIKE 'read_only';

-- 5. 创建复制账号（供后续原主库作为从库使用）
CREATE USER IF NOT EXISTS 'repl_user'@'%' IDENTIFIED WITH mysql_native_password BY 'Repl@Pass1234';
GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'%';
FLUSH PRIVILEGES;
```

#### Step 3: 更新应用连接配置

```bash
# 更新写入进程的数据库连接配置
# 原配置: MASTER_HOST=47.114.77.62
# 新配置: MASTER_HOST=8.136.226.231

# 方法1: 环境变量
export DB_HOST="8.136.226.231"

# 方法2: 配置文件
sed -i 's/47.114.77.62/8.136.226.231/g' /path/to/config.ini

# 方法3: 重启写入进程
systemctl restart data-writer
```

### 4.3 切换脚本

```bash
#!/bin/bash
# MySQL 主从切换脚本

OLD_MASTER="47.114.77.62"
NEW_MASTER="8.136.226.231"
MYSQL_USER="root"
MYSQL_PASS="Root@123456"
REPL_USER="repl_user"
REPL_PASS="Repl@Pass1234"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Step 1: 检查从库状态
log "Step 1: 检查从库状态..."
SLAVE_STATUS=$(mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -N -e "
    SELECT CONCAT(
        Slave_IO_Running, '|',
        Slave_SQL_Running, '|',
        Seconds_Behind_Master
    ) FROM (
        SHOW SLAVE STATUS
    ) AS t
" 2>/dev/null)

IO_RUNNING=$(echo $SLAVE_STATUS | cut -d'|' -f1)
SQL_RUNNING=$(echo $SLAVE_STATUS | cut -d'|' -f2)
DELAY=$(echo $SLAVE_STATUS | cut -d'|' -f3)

log "从库状态: IO=${IO_RUNNING}, SQL=${SQL_RUNNING}, Delay=${DELAY}s"

if [ "$IO_RUNNING" != "Yes" ] || [ "$SQL_RUNNING" != "Yes" ]; then
    log "[ERROR] 从库复制状态异常，无法切换！"
    exit 1
fi

# Step 2: 停止复制
log "Step 2: 停止从库复制..."
mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "
    STOP SLAVE;
    RESET SLAVE ALL;
    SET GLOBAL read_only = OFF;
    SET GLOBAL super_read_only = OFF;
" 2>/dev/null

# Step 3: 获取新主库位点
log "Step 3: 获取新主库位点..."
MASTER_STATUS=$(mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -N -e "
    SHOW MASTER STATUS
" 2>/dev/null)

BINLOG_FILE=$(echo $MASTER_STATUS | awk '{print $1}')
BINLOG_POS=$(echo $MASTER_STATUS | awk '{print $2}')

log "新主库位点: ${BINLOG_FILE}:${BINLOG_POS}"

# Step 4: 验证新主库可写
log "Step 4: 验证新主库可写..."
mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "
    CREATE DATABASE IF NOT EXISTS failover_test;
    CREATE TABLE IF NOT EXISTS failover_test.switch_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        switch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        old_master VARCHAR(50),
        new_master VARCHAR(50)
    );
    INSERT INTO failover_test.switch_log (old_master, new_master) 
    VALUES ('${OLD_MASTER}', '${NEW_MASTER}');
" 2>/dev/null

if [ $? -eq 0 ]; then
    log "[OK] 新主库写入测试成功"
else
    log "[ERROR] 新主库写入测试失败！"
    exit 1
fi

log "=========================================="
log "主从切换完成！"
log "旧主库: ${OLD_MASTER}"
log "新主库: ${NEW_MASTER}"
log "位点: ${BINLOG_FILE}:${BINLOG_POS}"
log "=========================================="
```

---

## 5. 数据同步验证

### 5.1 数据一致性检查

```sql
-- 在新旧主库分别执行，对比结果

-- 1. 表记录数对比
SELECT 
    TABLE_SCHEMA,
    TABLE_NAME,
    TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
ORDER BY TABLE_SCHEMA, TABLE_NAME;

-- 2. 数据校验（使用 checksum）
CHECKSUM TABLE test_replication.users;

-- 3. 关键业务表数据对比
SELECT COUNT(*) as total_users FROM test_replication.users;
SELECT MAX(id) as max_id FROM test_replication.users;
SELECT MIN(created_at) as min_time, MAX(created_at) as max_time FROM test_replication.users;
```

### 5.2 配置原主库为新从库（可选）

当原主库恢复后，可以将其配置为新主库的从库：

```sql
-- 在原主库 (47.114.77.62) 恢复后执行

-- 1. 停止可能的写入
SET GLOBAL read_only = ON;
SET GLOBAL super_read_only = ON;

-- 2. 配置复制
CHANGE MASTER TO
    MASTER_HOST='8.136.226.231',
    MASTER_USER='repl_user',
    MASTER_PASSWORD='Repl@Pass1234',
    MASTER_AUTO_POSITION=1;  -- 使用 GTID 自动定位

-- 3. 启动复制
START SLAVE;

-- 4. 检查复制状态
SHOW SLAVE STATUS\G
```

### 5.3 数据同步验证脚本

```bash
#!/bin/bash
# 数据同步验证脚本

NEW_MASTER="8.136.226.231"
OLD_MASTER="47.114.77.62"
MYSQL_USER="root"
MYSQL_PASS="Root@123456"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 对比表记录数
compare_table_counts() {
    local db=$1
    local table=$2
    
    NEW_COUNT=$(mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -N -e "
        SELECT COUNT(*) FROM ${db}.${table}
    " 2>/dev/null)
    
    OLD_COUNT=$(mysql -h "${OLD_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -N -e "
        SELECT COUNT(*) FROM ${db}.${table}
    " 2>/dev/null)
    
    if [ "$NEW_COUNT" == "$OLD_COUNT" ]; then
        log "[OK] ${db}.${table}: 新主库=${NEW_COUNT}, 原主库=${OLD_COUNT}"
    else
        log "[WARN] ${db}.${table}: 新主库=${NEW_COUNT}, 原主库=${OLD_COUNT} (不一致)"
    fi
}

log "========== 数据同步验证 =========="

# 验证关键表
compare_table_counts "test_replication" "users"

# 验证新主库写入
log "验证新主库写入能力..."
mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "
    INSERT INTO test_replication.users (name, email) VALUES ('Failover_Test', 'test@failover.com');
    SELECT * FROM test_replication.users WHERE name = 'Failover_Test';
" 2>/dev/null

if [ $? -eq 0 ]; then
    log "[OK] 新主库写入正常"
else
    log "[ERROR] 新主库写入失败"
fi

log "========== 验证完成 =========="
```

---

## 6. 测试验证

### 6.1 写入进程恢复测试

```bash
#!/bin/bash
# 写入进程恢复测试

NEW_MASTER="8.136.226.231"
MYSQL_USER="root"
MYSQL_PASS="Root@123456"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "========== 写入进程恢复测试 =========="

# 测试1: 连接测试
log "测试1: 连接新主库..."
mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "SELECT 1" 2>/dev/null
if [ $? -eq 0 ]; then
    log "[OK] 连接成功"
else
    log "[ERROR] 连接失败"
    exit 1
fi

# 测试2: 写入测试
log "测试2: 写入测试..."
for i in {1..10}; do
    mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -e "
        INSERT INTO test_replication.users (name, email) 
        VALUES ('Recovery_Test_${i}', 'recovery${i}@test.com');
    " 2>/dev/null
    
    if [ $? -eq 0 ]; then
        log "[OK] 写入第 ${i} 条记录成功"
    else
        log "[ERROR] 写入第 ${i} 条记录失败"
    fi
    sleep 1
done

# 测试3: 查询测试
log "测试3: 查询测试..."
COUNT=$(mysql -h "${NEW_MASTER}" -u "${MYSQL_USER}" -p"${MYSQL_PASS}" -N -e "
    SELECT COUNT(*) FROM test_replication.users WHERE name LIKE 'Recovery_Test_%'
" 2>/dev/null)

log "写入恢复测试记录数: ${COUNT}"

if [ "$COUNT" -eq 10 ]; then
    log "[OK] 写入进程恢复成功！"
else
    log "[WARN] 部分记录丢失"
fi

log "========== 测试完成 =========="
```

### 6.2 完整性验证清单

| 验证项 | 命令 | 期望结果 |
|--------|------|----------|
| 新主库连接 | `mysql -h NEW_MASTER -e "SELECT 1"` | 成功 |
| 新主库写入 | `INSERT INTO test_table VALUES (...)` | 成功 |
| 新主库读取 | `SELECT COUNT(*) FROM test_table` | 返回正确数量 |
| 原主库只读 | `SHOW VARIABLES LIKE 'read_only'` | ON (如果已恢复) |
| 复制状态 | `SHOW SLAVE STATUS` (原主库) | IO/SQL: Yes |
| 数据一致性 | `CHECKSUM TABLE` | 两库一致 |

### 6.3 切换报告模板

```markdown
# MySQL 主从切换报告

## 基本信息
- 切换时间: YYYY-MM-DD HH:MM:SS
- 操作人员: XXX
- 切换原因: 主库故障

## 切换详情
| 项目 | 切换前 | 切换后 |
|------|--------|--------|
| 主库 IP | 47.114.77.62 | 8.136.226.231 |
| 主库角色 | Master | Slave (待配置) |
| 从库角色 | Slave | Master |

## 验证结果
- [ ] 新主库连接正常
- [ ] 新主库写入正常
- [ ] 数据一致性验证通过
- [ ] 写入进程恢复
- [ ] 应用服务正常

## 切换位点
- Binlog File: mysql-bin.000001
- Binlog Position: 2354
- GTID Executed: xxx

## 后续事项
1. 监控新主库性能
2. 配置原主库为新从库
3. 更新监控告警配置
4. 通知相关团队
```

---

## 7. 权限边界

### 7.1 操作权限要求

| 操作 | 所需权限 | 风险等级 |
|------|----------|----------|
| 检查主库状态 | SELECT, PROCESS | 🟢 低 |
| 检查从库状态 | REPLICATION CLIENT | 🟢 低 |
| 停止复制 | REPLICATION SLAVE ADMIN | 🟡 中 |
| 提升从库 | SUPER, REPLICATION SLAVE ADMIN | 🔴 高 |
| 创建复制账号 | CREATE USER, GRANT OPTION | 🔴 高 |
| 更新应用配置 | 应用服务器写权限 | 🟡 中 |

### 7.2 安全检查

```bash
# 切换前必须确认
echo "========== 安全检查 =========="
echo "1. 确认主库确实不可用"
echo "2. 确认从库数据已完全同步"
echo "3. 确认有回滚方案"
echo "4. 确认已通知相关人员"
echo ""
read -p "是否确认以上事项？(yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "取消切换"
    exit 1
fi
```

### 7.3 回滚方案

如果切换失败，执行以下回滚：

```bash
# 1. 恢复原主库
ssh jaci@47.114.77.62 "sudo systemctl start mysqld"

# 2. 将新主库恢复为从库
mysql -h 8.136.226.231 -u root -p'Root@123456' -e "
    STOP SLAVE;
    RESET SLAVE ALL;
    SET GLOBAL read_only = ON;
    SET GLOBAL super_read_only = ON;
"

# 3. 恢复应用配置
sed -i 's/8.136.226.231/47.114.77.62/g' /path/to/config.ini
systemctl restart data-writer
```

---

## 8. 监控告警配置

### 8.1 主库健康监控

```bash
# 添加到 crontab，每分钟检测
* * * * * /path/to/mysql_health_check.sh >> /var/log/mysql_health.log 2>&1
```

### 8.2 告警脚本

```bash
#!/bin/bash
# mysql_alert.sh - 主库故障告警

MASTER_HOST="47.114.77.62"
ALERT_WEBHOOK="https://your-webhook-url"

check_master() {
    mysql -h "${MASTER_HOST}" -u root -p'Root@123456' -e "SELECT 1" 2>/dev/null
    return $?
}

if ! check_master; then
    curl -X POST "${ALERT_WEBHOOK}" \
        -H "Content-Type: application/json" \
        -d '{
            "alert": "MySQL Master Down",
            "master": "'${MASTER_HOST}'",
            "time": "'$(date -Iseconds)'",
            "action": "需要人工切换到从库"
        }'
fi
```

---

## 9. 相关 Skill 引用

- 主从复制配置: `@reference: database/database_ha_skill.md`
- 连接管理: `@reference: connection/login_skill.md`
- 故障排查: `@reference: diagnosis/debug_skill.md`
- 备份恢复: `@reference: backup/backup_skill.md`
