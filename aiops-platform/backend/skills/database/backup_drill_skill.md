# 数据库备份恢复演练 Skill

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 演练流程](#2-演练流程)
- [3. 备份完整性验证](#3-备份完整性验证)
- [4. MySQL 恢复演练](#4-mysql-恢复演练)
- [5. PostgreSQL 恢复演练](#5-postgresql-恢复演练)
- [6. Redis 恢复演练](#6-redis-恢复演练)
- [7. 数据一致性校验](#7-数据一致性校验)
- [8. 演练报告与审计](#8-演练报告与审计)
- [9. 权限边界](#9-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `备份演练`, `恢复测试`, `backup drill`, `restore test`, `灾备验证`
- `备份有效性`, `备份数据验证`, `恢复演练`, `数据恢复测试`
- `定期演练`, `DR drill`, `灾难恢复演练`, `备份可用性`
- `mysqldump 恢复`, `pg_restore 测试`, `RDS 备份恢复`

### 1.2 适用条件
- 需要验证备份文件是否可正常恢复
- 定期执行数据恢复演练（建议每月/每季度）
- 新增备份策略后需要验证
- 数据库升级/迁移前验证备份可靠性
- 合规要求（等保、ISO 27001）需要定期演练记录

### 1.3 前置条件
- 已配置自动备份策略（全量+增量/ binlog）
- 有独立的恢复测试环境（或使用临时实例）
- 备份文件存储在可靠位置（OSS/S3/NAS）
- 具备数据库管理员权限
- 演练时间窗口已协调（避免影响生产）

---

## 2. 演练流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 演练准备                                           │
│  - 确认演练范围（全库/单表/增量）                            │
│  - 准备恢复目标环境                                         │
│  - 通知相关人员                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 备份文件检查                                       │
│  - 验证备份文件存在且完整                                    │
│  - 检查备份时间戳（是否为最新）                              │
│  - 验证备份文件大小合理性                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 执行恢复操作                                       │
│  - 在测试环境/临时实例执行恢复                               │
│  - 记录恢复耗时                                             │
│  - 记录恢复过程中的错误                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 数据验证                                           │
│  - 校验表数量和行数                                         │
│  - 抽样验证关键业务数据                                     │
│  - 执行查询功能测试                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 清理与报告                                         │
│  - 清理测试环境数据                                         │
│  - 生成演练报告                                             │
│  - 更新演练记录                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 备份完整性验证

### 3.1 备份文件基本检查

```bash
#!/bin/bash
# 备份文件完整性检查脚本

BACKUP_DIR="/data/backups/mysql"
LOG_FILE="/var/log/backup_drill/check_$(date +%Y%m%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========== 备份完整性检查开始 =========="

# 1. 检查备份目录是否存在
if [ ! -d "$BACKUP_DIR" ]; then
    log "[ERROR] 备份目录不存在: $BACKUP_DIR"
    exit 1
fi

# 2. 检查最近一次全量备份
LATEST_FULL=$(ls -t "$BACKUP_DIR"/*full*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST_FULL" ]; then
    log "[ERROR] 未找到全量备份文件"
    exit 1
fi

log "[OK] 最新全量备份: $LATEST_FULL"
log "     文件大小: $(du -h "$LATEST_FULL" | cut -f1)"
log "     备份时间: $(stat -c '%y' "$LATEST_FULL")"

# 3. 验证 gzip 文件完整性
if gzip -t "$LATEST_FULL" 2>/dev/null; then
    log "[OK] gzip 文件完整性验证通过"
else
    log "[ERROR] gzip 文件损坏"
    exit 1
fi

# 4. 检查备份文件大小（应 > 1MB）
FILE_SIZE=$(stat -c%s "$LATEST_FULL")
if [ "$FILE_SIZE" -lt 1048576 ]; then
    log "[WARN] 备份文件过小，可能不完整: ${FILE_SIZE} bytes"
else
    log "[OK] 备份文件大小正常: $(( FILE_SIZE / 1024 / 1024 )) MB"
fi

# 5. 检查最近增量/binlog 备份
LATEST_BINLOG=$(ls -t "$BACKUP_DIR"/binlog.* 2>/dev/null | head -1)
if [ -n "$LATEST_BINLOG" ]; then
    log "[OK] 最新 Binlog: $(basename "$LATEST_BINLOG")"
    log "     时间: $(stat -c '%y' "$LATEST_BINLOG")"
else
    log "[WARN] 未找到 Binlog 备份"
fi

log "========== 备份完整性检查完成 =========="
```

### 3.2 RDS/OSS 备份检查（阿里云）

```bash
#!/bin/bash
# 阿里云 RDS 备份检查

INSTANCE_ID="{{ rds_instance_id }}"
REGION="{{ region_id }}"

echo "========== RDS 备份状态检查 =========="

# 1. 查看备份策略
aliyun rds DescribeBackupPolicy \
    --DBInstanceId "$INSTANCE_ID" \
    --region "$REGION"

# 2. 列出最近的备份集
aliyun rws DescribeBackups \
    --DBInstanceId "$INSTANCE_ID" \
    --region "$REGION" \
    --BackupMode "Automated" \
    --PageSize 5 \
    --output cols=BackupId,BackupStartTime,BackupEndTime,BackupSize,BackupMethod rows[]

# 3. 检查日志备份状态
aliyun rds DescribeBinlogFiles \
    --DBInstanceId "$INSTANCE_ID" \
    --region "$REGION" \
    --PageSize 5 \
    --output cols=LogFileStartTime,LogFileEndTime,FileSize,DownloadLink rows[]
```

---

## 4. MySQL 恢复演练

### 4.1 全量备份恢复（mysqldump 格式）

```bash
#!/bin/bash
# MySQL 全量备份恢复演练脚本

set -e

SOURCE_HOST="production-db.example.com"
TARGET_HOST="drill-test-db.example.com"  # 恢复测试环境
MYSQL_USER="root"
MYSQL_PASS="{{ lookup('env', 'MYSQL_DRILL_PASS') }}"
BACKUP_FILE="/data/backups/mysql/full_$(date +%Y%m%d).sql.gz"
DRILL_DB="drill_test_$(date +%Y%m%d)"
REPORT_FILE="/var/log/backup_drill/mysql_drill_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$REPORT_FILE"
}

log "========== MySQL 恢复演练开始 =========="
START_TIME=$(date +%s)

# Step 1: 创建演练数据库
log "Step 1: 创建演练数据库..."
mysql -h "$TARGET_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" -e "
    CREATE DATABASE IF NOT EXISTS $DRILL_DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
" 2>>"$REPORT_FILE"
log "[OK] 数据库创建成功: $DRILL_DB"

# Step 2: 解压并导入备份
log "Step 2: 导入备份文件..."
IMPORT_START=$(date +%s)

if [ -f "$BACKUP_FILE" ]; then
    gunzip -c "$BACKUP_FILE" | mysql -h "$TARGET_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" "$DRILL_DB" 2>>"$REPORT_FILE"
    
    IMPORT_END=$(date +%s)
    IMPORT_DURATION=$(( IMPORT_END - IMPORT_START ))
    log "[OK] 备份导入完成，耗时: ${IMPORT_DURATION} 秒"
else
    log "[ERROR] 备份文件不存在: $BACKUP_FILE"
    exit 1
fi

# Step 3: 验证表数量
log "Step 3: 验证表数量..."
TABLE_COUNT=$(mysql -h "$TARGET_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" -N -e "
    SELECT COUNT(*) FROM information_schema.TABLES 
    WHERE TABLE_SCHEMA = '$DRILL_DB' AND TABLE_TYPE = 'BASE TABLE';
" 2>>"$REPORT_FILE")

log "[INFO] 恢复表数量: $TABLE_COUNT"

if [ "$TABLE_COUNT" -eq 0 ]; then
    log "[ERROR] 未恢复任何表！"
    exit 1
fi

# Step 4: 验证总行数
log "Step 4: 统计总行数..."
TOTAL_ROWS=$(mysql -h "$TARGET_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" -N -e "
    SELECT SUM(TABLE_ROWS) FROM information_schema.TABLES 
    WHERE TABLE_SCHEMA = '$DRILL_DB' AND TABLE_TYPE = 'BASE TABLE';
" 2>>"$REPORT_FILE")

log "[INFO] 总行数约: $TOTAL_ROWS"

# Step 5: 抽样验证关键表
log "Step 5: 抽样验证关键表..."
KEY_TABLES=("users" "orders" "products")

for table in "${KEY_TABLES[@]}"; do
    if mysql -h "$TARGET_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" -N -e "
        SELECT COUNT(*) FROM $DRILL_DB.$table;
    " >>"$REPORT_FILE" 2>&1; then
        ROWS=$(tail -1 "$REPORT_FILE")
        log "[OK] 表 $table: $ROWS 行"
    else
        log "[WARN] 表 $table 不存在或查询失败"
    fi
done

# Step 6: 功能性测试
log "Step 6: 执行功能性查询..."
TEST_QUERIES=(
    "SELECT COUNT(*) FROM $DRILL_DB.users WHERE status = 'active'"
    "SELECT MAX(created_at) FROM $DRILL_DB.orders"
    "SELECT DISTINCT category FROM $DRILL_DB.products LIMIT 10"
)

for query in "${TEST_QUERIES[@]}"; do
    if mysql -h "$TARGET_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASS" -N -e "$query" >>"$REPORT_FILE" 2>&1; then
        RESULT=$(tail -1 "$REPORT_FILE")
        log "[OK] 查询成功: $RESULT"
    else
        log "[FAIL] 查询失败: $query"
    fi
done

END_TIME=$(date +%s)
TOTAL_DURATION=$(( END_TIME - START_TIME ))

log "========== MySQL 恢复演练完成 =========="
log "总耗时: ${TOTAL_DURATION} 秒 ($(( TOTAL_DURATION / 60 )) 分钟)"
log "恢复表数: $TABLE_COUNT"
log "估算行数: $TOTAL_ROWS"
log "演练数据库: $DRILL_DB"
```

### 4.2 基于时间点的恢复（PITR）演练

```bash
#!/bin/bash
# MySQL PITR (Point-in-Time Recovery) 演练

RECOVERY_TARGET_TIME="2024-01-15 14:30:00"  # 目标恢复时间点
BACKUP_BASE="/data/backups/mysql"
BINLOG_DIR="$BACKUP_DIR/binlogs"
DRILL_DB="pitr_drill_$(date +%Y%m%d)"

log "========== PITR 演练开始 =========="
log "目标恢复时间: $RECOVERY_TARGET_TIME"

# Step 1: 找到最接近目标时间的全量备份
log "Step 1: 定位基础全量备份..."
BASE_BACKUP=$(ls -t "$BACKUP_BASE"/*full*$(date -d "$RECOVERY_TARGET_TIME" +%Y%m%d)*.sql.gz | head -1)

if [ -z "$BASE_BACKUP" ]; then
    # 回退到上一个可用备份
    BASE_BACKUP=$(ls -t "$BACKUP_BASE"/*full*.sql.gz | head -1)
    log "[WARN] 未找到精确匹配，使用最新备份: $(basename "$BASE_BACKUP")"
fi

log "[OK] 基础备份: $(basename "$BASE_BACKUP")"

# Step 2: 恢复全量备份
log "Step 2: 恢复全量备份..."
gunzip -c "$BASE_BACKUP" | mysql -u root -p"$MYSQL_PASS" "$DRILL_DB"

# Step 3: 应用 Binlog 到目标时间点
log "Step 3: 应用 Binlog 到目标时间点..."

# 获取备份后的 Binlog 文件列表
BINLOG_FILES=$(ls -1 "$BINLOG_DIR"/mysql-bin.* | sort)

for binlog in $BINLOG_FILES; do
    log "应用 Binlog: $(basename "$binlog")"
    mysqlbinlog \
        --stop-datetime="$RECOVERY_TARGET_TIME" \
        --database="$ORIGINAL_DB" \
        "$binlog" | mysql -u root -p"$MYSQL_PASS" "$DRILL_DB"
done

# Step 4: 验证恢复时间点
log "Step 4: 验证恢复时间点..."
RECOVERED_TIME=$(mysql -u root -p"$MYSQL_PASS" -N -e "
    SELECT MAX(updated_at) FROM $DRILL_DB.orders;
")

log "[OK] 数据库最大时间戳: $RECOVERED_TIME"
log "[INFO] 目标时间: $RECOVERY_TARGET_TIME"

if [[ "$RECOVERED_TIME" < "$RECOVERY_TARGET_TIME" ]]; then
    log "[OK] 恢复时间点正确（数据未超过目标时间）"
else
    log "[WARN] 恢复时间可能超过目标时间"
fi

log "========== PITR 演练完成 =========="
```

### 4.3 物理备份恢复（XtraBackup）演练

```bash
#!/bin/bash
# Percona XtraBackup 恢复演练

XTRABACKUP_DIR="/data/backups/xtrabackup"
DATA_DIR="/var/lib/mysql_drill"
MYSQL_SOCKET="/tmp/mysql_drill.sock"
MYSQL_PORT=3307

log "========== XtraBackup 恢复演练开始 =========="

# Step 1: 准备备份（Apply Log）
log "Step 1: 准备备份（回滚未提交事务）..."
xtrabackup --prepare \
    --target-dir="$XTRABACKUP_DIR/latest_full" \
    2>>"$REPORT_FILE"

log "[OK] 备份准备完成"

# Step 2: 复制数据文件到目标目录
log "Step 2: 复制数据文件..."
xtrabackup --copy-back \
    --target-dir="$XTRABACKUP_DIR/latest_full" \
    --datadir="$DATA_DIR" \
    2>>"$REPORT_FILE"

# Step 3: 修改权限
log "Step 3: 修改文件权限..."
chown -R mysql:mysql "$DATA_DIR"

# Step 4: 启动临时 MySQL 实例
log "Step 4: 启动测试实例（端口 $MYSQL_PORT）..."
mysqld_safe \
    --datadir="$DATA_DIR" \
    --socket="$MYSQL_SOCKET" \
    --port="$MYSQL_PORT" \
    --user=mysql &

sleep 10

# Step 5: 验证实例启动
log "Step 5: 验证实例状态..."
mysql -S "$MYSQL_SOCKET" -e "SELECT 1" && log "[OK] 实例启动成功" || {
    log "[ERROR] 实例启动失败"
    tail -50 "$DATA_DIR/../error.log"
    exit 1
}

# Step 6: 数据验证
log "Step 6: 执行数据验证..."
mysql -S "$MYSQL_SOCKET" -e "
    SHOW DATABASES;
    SELECT COUNT(*) AS table_count FROM information_schema.TABLES 
    WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys');
"

# Step 7: 清理
log "Step 7: 停止测试实例并清理..."
mysqladmin -S "$MYSQL_SOCKET" shutdown
rm -rf "$DATA_DIR"/*

log "========== XtraBackup 恢复演练完成 =========="
```

---

## 5. PostgreSQL 恢复演练

### 5.1 pg_dump 恢复演练

```bash
#!/bin/bash
# PostgreSQL 备份恢复演练脚本

PG_HOST="localhost"
PG_USER="postgres"
PG_PASS="{{ lookup('env', 'POSTGRES_DRILL_PASS') }}"
PG_PORT=5432
BACKUP_FILE="/data/backups/postgres/full_$(date +%Y%m%d).dump"
DRILL_DB="drill_test_$(date +%Y%m%d)"

export PGPASSWORD="$PG_PASS"

log "========== PostgreSQL 恢复演练开始 =========="
START_TIME=$(date +%s)

# Step 1: 创建演练数据库
log "Step 1: 创建演练数据库..."
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -c "
    CREATE DATABASE $DRILL_DB TEMPLATE template0 ENCODING 'UTF8';
" 2>>"$REPORT_FILE"

# Step 2: 恢复备份
log "Step 2: 恢复备份文件..."
IMPORT_START=$(date +%s)

if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" 2>>"$REPORT_FILE"
elif [[ "$BACKUP_FILE" == *.dump ]]; then
    pg_restore -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" \
        --verbose --no-owner --no-acl "$BACKUP_FILE" 2>>"$REPORT_FILE"
else
    psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" -f "$BACKUP_FILE" 2>>"$REPORT_FILE"
fi

IMPORT_END=$(date +%s)
IMPORT_DURATION=$(( IMPORT_END - IMPORT_START ))
log "[OK] 备份恢复完成，耗时: ${IMPORT_DURATION} 秒"

# Step 3: 验证表数量
log "Step 3: 验证表数量..."
TABLE_COUNT=$(psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" -t -c "
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
" | tr -d ' ')

log "[INFO] 恢复表数量: $TABLE_COUNT"

# Step 4: 验证序列值
log "Step 4: 检查序列状态..."
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" -c "
    SELECT schemaname, sequencename, last_value 
    FROM pg_sequences ORDER BY schemaname, sequencename;
" >>"$REPORT_FILE"

# Step 5: 验证索引
log "Step 5: 检查索引状态..."
INDEX_COUNT=$(psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" -t -c "
    SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';
" | tr -d ' ')

log "[INFO] 索引数量: $INDEX_COUNT"

# Step 6: 功能性测试
log "Step 6: 执行查询测试..."
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$DRILL_DB" -c "
    -- 示例：验证业务表可查询
    SELECT count(*) FROM users LIMIT 1;
    SELECT max(created_at) FROM orders;
" >>"$REPORT_FILE" 2>&1

END_TIME=$(date +%s)
TOTAL_DURATION=$(( END_TIME - START_TIME ))

log "========== PostgreSQL 恢复演练完成 =========="
log "总耗时: ${TOTAL_DURATION} 秒"
log "恢复表数: $TABLE_COUNT"
log "索引数量: $INDEX_COUNT"
```

### 5.2 WAL 归档恢复演练（PITR）

```bash
#!/bin/bash
# PostgreSQL WAL 归档恢复演练

RECOVERY_TARGET_TIME="2024-01-15 14:30:00"
PG_DATA="/var/lib/postgresql/data/drill"
WAL_ARCHIVE="/data/wal_archive"
PG_PORT=5433

log "========== PostgreSQL PITR 演练开始 =========="

# Step 1: 从基础备份恢复
log "Step 1: 恢复基础备份..."
rm -rf "$PG_DATA"/*
tar -xzf /data/backups/postgres/base_backup.tar.gz -C "$PG_DATA"

# Step 2: 配置 recovery
log "Step 2: 配置恢复参数..."
cat >> "$PG_DATA/postgresql.conf" <<EOF
recovery_target_time = '$RECOVERY_TARGET_TIME'
recovery_target_action = 'promote'
restore_command = 'cp $WAL_ARCHIVE/%f %p'
EOF

touch "$PG_DATA/recovery.signal"

# Step 3: 启动恢复
log "Step 3: 启动 PostgreSQL 并执行恢复..."
pg_ctl start -D "$PG_DATA" -o "-p $PG_PORT" -l "$PG_DATA/recovery.log"

# Step 4: 监控恢复进度
log "Step 4: 监控恢复进度..."
sleep 30

# 检查恢复是否完成
pg_isready -h localhost -p "$PG_PORT"

# Step 5: 验证恢复时间点
log "Step 5: 验证恢复时间点..."
psql -h localhost -p "$PG_PORT" -U postgres -c "
    SELECT now() as current_time;
    SELECT max(updated_at) as max_data_time FROM orders;
"

# Step 6: 清理
log "Step 6: 停止并清理..."
pg_ctl stop -D "$PG_DATA" -m immediate

log "========== PostgreSQL PITR 演练完成 =========="
```

---

## 6. Redis 恢复演练

### 6.1 RDB/AOF 恢复演练

```bash
#!/bin/bash
# Redis 备份恢复演练脚本

REDIS_PROD_PORT=6379
REDIS_DRILL_PORT=6380
REDIS_DRILL_DIR="/var/lib/redis/drill"
BACKUP_DIR="/data/backups/redis"
DUMP_FILE="$BACKUP_DIR/dump_$(date +%Y%m%d).rdb"

log "========== Redis 恢复演练开始 =========="

# Step 1: 停止测试实例（如果运行中）
log "Step 1: 准备测试环境..."
redis-cli -p "$REDIS_DRILL_PORT" shutdown nosave 2>/dev/null || true
rm -rf "$REDIS_DRILL_DIR"/*

# Step 2: 复制备份文件
log "Step 2: 复制备份文件..."
cp "$DUMP_FILE" "$REDIS_DRILL_DIR/dump.rdb"

if [ $? -ne 0 ]; then
    log "[ERROR] 备份文件复制失败"
    exit 1
fi

log "[OK] 备份文件已复制"

# Step 3: 启动测试实例
log "Step 3: 启动测试实例（端口 $REDIS_DRILL_PORT）..."
redis-server \
    --port "$REDIS_DRILL_PORT" \
    --dir "$REDIS_DRILL_DIR" \
    --daemonize yes \
    --logfile "$REDIS_DRILL_DIR/redis_drill.log"

sleep 3

# Step 4: 验证实例状态
log "Step 4: 验证实例状态..."
if redis-cli -p "$REDIS_DRILL_PORT" ping | grep -q PONG; then
    log "[OK] Redis 实例启动成功"
else
    log "[ERROR] Redis 实例启动失败"
    cat "$REDIS_DRILL_DIR/redis_drill.log"
    exit 1
fi

# Step 5: 数据验证
log "Step 5: 执行数据验证..."

# 5.1 检查 Key 数量
KEY_COUNT=$(redis-cli -p "$REDIS_DRILL_PORT" dbsize)
log "[INFO] Key 数量: $KEY_COUNT"

# 5.2 检查内存使用
MEMORY_USAGE=$(redis-cli -p "$REDIS_DRILL_PORT" info memory | grep used_memory_human)
log "[INFO] 内存使用: $MEMORY_USAGE"

# 5.3 验证关键 Key 类型
log "验证关键 Key:"
CRITICAL_KEYS=("session:user:*" "cache:product:*" "rate:limit:*")

for pattern in "${CRITICAL_KEYS[@]}"; do
    COUNT=$(redis-cli -p "$REDIS_DRILL_PORT" keys "$pattern" 2>/dev/null | wc -l)
    log "  $pattern: $COUNT 个 key"
done

# 5.4 抽样读取 Key 内容
log "抽样读取 Key 内容:"
SAMPLE_KEY=$(redis-cli -p "$REDIS_DRILL_PORT" randomkey)
if [ -n "$SAMPLE_KEY" ]; then
    KEY_TYPE=$(redis-cli -p "$REDIS_DRILL_PORT" type "$SAMPLE_KEY")
    case "$KEY_TYPE" in
        string)
            VALUE=$(redis-cli -p "$REDIS_DRILL_PORT" get "$SAMPLE_KEY" | cut -c1-100)
            log "  [$KEY_TYPE] $SAMPLE_KEY: $VALUE..."
            ;;
        hash)
            VALUE=$(redis-cli -p "$REDIS_DRILL_PORT" hgetall "$SAMPLE_KEY" | head -5)
            log "  [$KEY_TYPE] $SAMPLE_KEY: $VALUE ..."
            ;;
        list|set|zset)
            COUNT=$(redis-cli -p "$REDIS_DRILL_PORT" "$KEY_TYPE" "$SAMPLE_KEY")
            log "  [$KEY_TYPE] $SAMPLE_KEY: $COUNT 个元素"
            ;;
    esac
fi

# Step 6: 性能测试
log "Step 6: 执行简单性能测试..."
BENCHMARK_RESULT=$(redis-cli -p "$REDIS_DRILL_PORT" ping -c 1000 | grep requests)
log "[INFO] 性能基准: $BENCHMARK_RESULT"

# Step 7: 清理
log "Step 7: 清理测试环境..."
redis-cli -p "$REDIS_DRILL_PORT" shutdown nosave

log "========== Redis 恢复演练完成 =========="
```

### 6.2 AOF 恢复演练

```bash
#!/bin/bash
# Redis AOF 恢复演练

AOF_BACKUP="/data/backups/redis/appendonly.aof"
DRILL_DIR="/var/lib/redis/aof_drill"
REDIS_PORT=6381

log "========== Redis AOF 恢复演练开始 =========="

# Step 1: 检查 AOF 文件完整性
log "Step 1: 检查 AOF 文件..."
if redis-check-aof "$AOF_BACKUP"; then
    log "[OK] AOF 文件完整"
else
    log "[WARN] AOF 文件可能损坏，尝试修复..."
    redis-check-aof --fix "$AOF_BACKUP"
fi

# Step 2: 启动实例加载 AOF
log "Step 2: 使用 AOF 启动实例..."
mkdir -p "$DRILL_DIR"
cp "$AOF_BACKUP" "$DRILL_DIR/appendonly.aof"

redis-server \
    --port "$REDIS_PORT" \
    --dir "$DRILL_DIR" \
    --appendonly yes \
    --appendfilename "appendonly.aof" \
    --daemonize yes

sleep 5

# Step 3: 验证数据
log "Step 3: 验证 AOF 恢复结果..."
KEY_COUNT=$(redis-cli -p "$REDIS_PORT" dbsize)
log "[INFO] 从 AOF 恢复的 Key 数量: $KEY_COUNT"

# Step 4: 对比 RDB vs AOF 恢复差异
log "Step 4: 记录恢复统计信息..."
redis-cli -p "$REDIS_PORT" info persistence >>"$REPORT_FILE"

# 清理
redis-cli -p "$REDIS_PORT" shutdown nosave

log "========== Redis AOF 恢复演练完成 =========="
```

---

## 7. 数据一致性校验

### 7.1 行级校验脚本（MySQL）

```python
#!/usr/bin/env python3
"""
MySQL 数据一致性校验工具
用于对比源库和恢复库的数据差异
"""

import mysql.connector
import hashlib
import sys
from datetime import datetime
from typing import Dict, List, Tuple


class DataConsistencyChecker:
    def __init__(self, source_config: dict, target_config: dict):
        self.source_conn = mysql.connector.connect(**source_config)
        self.target_conn = mysql.connector.connect(**target_config)
        
    def check_table_count(self, database: str) -> Dict[str, int]:
        """检查表数量"""
        query = """
            SELECT TABLE_NAME, TABLE_ROWS 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """
        
        source_cursor = self.source_conn.cursor(dictionary=True)
        target_cursor = self.target_conn.cursor(dictionary=True)
        
        source_cursor.execute(query, (database,))
        target_cursor.execute(query, (database,))
        
        source_tables = {row['TABLE_NAME']: row['TABLE_ROWS'] for row in source_cursor}
        target_tables = {row['TABLE_NAME']: row['TABLE_ROWS'] for row in target_cursor}
        
        result = {
            'matching': [],
            'missing_in_target': [],
            'row_diff': []
        }
        
        for table, rows in source_tables.items():
            if table not in target_tables:
                result['missing_in_target'].append(table)
            else:
                diff = abs(rows - (target_tables[table] or 0))
                tolerance = max(rows * 0.05, 100)  # 5% 容差或至少 100 行
                
                if diff <= tolerance:
                    result['matching'].append({
                        'table': table,
                        'source_rows': rows,
                        'target_rows': target_tables[table]
                    })
                else:
                    result['row_diff'].append({
                        'table': table,
                        'source_rows': rows,
                        'target_rows': target_tables[table],
                        'diff': diff
                    })
        
        return result
    
    def sample_data_verify(
        self, 
        database: str, 
        tables: List[str], 
        sample_size: int = 100
    ) -> Dict:
        """抽样验证数据内容"""
        results = {}
        
        for table in tables:
            try:
                # 获取主键列
                pk_query = """
                    SELECT COLUMN_NAME 
                    FROM information_schema.KEY_COLUMN_USAGE 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s 
                    AND CONSTRAINT_NAME = 'PRIMARY'
                    LIMIT 1
                """
                
                cursor = self.source_conn.cursor()
                cursor.execute(pk_query, (database, table))
                pk_row = cursor.fetchone()
                pk_col = pk_row[0] if pk_row else None
                
                if not pk_col:
                    continue
                
                # 抽样获取主键值
                sample_query = f"SELECT {pk_col} FROM {database}.{table} ORDER BY RAND() LIMIT {sample_size}"
                
                source_cursor = self.source_conn.cursor()
                target_cursor = self.target_conn.cursor()
                
                source_cursor.execute(sample_query)
                sample_pks = [row[0] for row in source_cursor]
                
                match_count = 0
                mismatch_records = []
                
                for pk_value in sample_pks:
                    # 获取源数据和目标数据的 hash
                    source_hash = self._get_record_hash(database, table, pk_col, pk_value, self.source_conn)
                    target_hash = self._get_record_hash(database, table, pk_col, pk_value, self.target_conn)
                    
                    if source_hash == target_hash:
                        match_count += 1
                    else:
                        mismatch_records.append(pk_value)
                
                results[table] = {
                    'sample_size': len(sample_pks),
                    'matched': match_count,
                    'mismatched': len(mismatch_records),
                    'match_rate': round(match_count / len(sample_pks) * 100, 2) if sample_pks else 0,
                    'mismatch_samples': mismatch_records[:10]  # 只返回前 10 个样本
                }
                
            except Exception as e:
                results[table] = {'error': str(e)}
        
        return results
    
    def _get_record_hash(self, db: str, table: str, pk_col: str, pk_value, conn):
        """获取单条记录的 MD5 hash"""
        cursor = conn.cursor()
        query = f"SELECT * FROM {db}.{table} WHERE {pk_col} = %s"
        cursor.execute(query, (pk_value,))
        row = cursor.fetchone()
        
        if row:
            record_str = '|'.join(str(val) if val is not None else 'NULL' for val in row)
            return hashlib.md5(record_str.encode()).hexdigest()
        return None
    
    def generate_report(self, database: str, output_file: str):
        """生成校验报告"""
        report = []
        report.append("=" * 60)
        report.append(f"数据一致性校验报告")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"校验数据库: {database}")
        report.append("=" * 60)
        
        # 表数量检查
        table_result = self.check_table_count(database)
        report.append("\n## 表数量检查")
        report.append(f"- 匹配表数: {len(table_result['matching'])}")
        report.append(f"- 目标库缺失表: {len(table_result['missing_in_target'])}")
        report.append(f"- 行数差异表: {len(table_result['row_diff'])}")
        
        if table_result['missing_in_target']:
            report.append("\n缺失的表:")
            for t in table_result['missing_in_target']:
                report.append(f"  - {t}")
        
        if table_result['row_diff']:
            report.append("\n行数差异较大的表:")
            for item in table_result['row_diff']:
                report.append(f"  - {item['table']}: 源={item['source_rows']}, 目标={item['target_rows']}, 差异={item['diff']}")
        
        # 数据抽样验证
        tables_to_check = [item['table'] for item in table_result['matching'][:20]]  # 前 20 张表
        if tables_to_check:
            sample_result = self.sample_data_verify(database, tables_to_check)
            
            report.append("\n## 数据抽样验证")
            for table, data in sample_result.items():
                if 'error' not in data:
                    status = "✅ 通过" if data['match_rate'] >= 95 else "⚠️ 存在差异"
                    report.append(f"\n{table}: {status}")
                    report.append(f"  抽样数: {data['sample_size']}, 匹配率: {data['match_rate']}%")
                    
                    if data['mismatched'] > 0:
                        report.append(f"  不匹配样本: {data['mismatch_samples']}")
        
        # 写入文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))
        
        print(f"报告已保存至: {output_file}")
        return '\n'.join(report)


if __name__ == '__main__':
    source_config = {
        'host': 'production-db',
        'user': 'root',
        'password': '{{ lookup('"'env'", '"MYSQL_PASS'"') }}',
        'database': 'information_schema'
    }
    
    target_config = {
        'host': 'drill-test-db',
        'user': 'root',
        'password': '{{ lookup('"'env'", '"MYSQL_DRILL_PASS'"') }}',
        'database': 'information_schema'
    }
    
    checker = DataConsistencyChecker(source_config, target_config)
    report = checker.generate_report('my_database', '/var/log/backup_drill/consistency_report.txt')
    print(report)
```

### 7.2 Checksum 校验（快速验证）

```sql
-- MySQL 表级 Checksum 对比
-- 在源库和目标库分别执行，对比结果

-- 方法 1: 使用 CHECKSUM TABLE
CHECKSUM TABLE users;
CHECKSUM TABLE orders;
CHECKSUM TABLE products;

-- 方法 2: 使用 MD5 聚合（适合大表）
SELECT 
    CONCAT_WS('|', 
        COUNT(*) as cnt,
        COALESCE(SUM(CRC32(CONCAT_WS('|', id, name, email, status))), 0),
        MAX(id),
        MIN(id),
        MAX(updated_at)
    ) as checksum_val
FROM users;

-- 方法 3: 分块 Checksum（超大型表）
SELECT 
    FLOOR(id / 100000) as chunk,
    COUNT(*) as row_count,
    SUM(CRC32(*)) as chunk_checksum
FROM large_table
GROUP BY chunk
ORDER BY chunk;
```

---

## 8. 演练报告与审计

### 8.1 演练报告模板

```markdown
# 数据库备份恢复演练报告

## 基本信息
- **演练日期**: YYYY-MM-DD HH:MM
- **演练负责人**: XXX
- **演练类型**: 全量恢复 / PITR / 增量恢复
- **演练范围**: MySQL / PostgreSQL / Redis
- **演练环境**: 测试实例 (drill-test-db)

## 备份信息
| 项目 | 详情 |
|------|------|
| 备份类型 | mysqldump / XtraBackup / pg_dump / RDB |
| 备份文件 | full_YYYYMMDD.sql.gz |
| 备份大小 | X GB |
| 备份时间 | YYYY-MM-DD HH:MM |
| 备份保留期 | 30 天 |

## 恢复过程
| 步骤 | 操作 | 开始时间 | 结束时间 | 耗时 | 状态 |
|------|------|----------|----------|------|------|
| 1 | 创建演练数据库 | - | - | X 秒 | ✅ 成功 |
| 2 | 导入备份文件 | - | - | X 分钟 | ✅ 成功 |
| 3 | 应用 Binlog/WAL | - | - | X 分钟 | ✅ 成功 |
| 4 | 数据验证 | - | - | X 秒 | ✅ 成功 |

## 恢复结果
| 检查项 | 期望值 | 实际值 | 结果 |
|--------|--------|--------|------|
| 表数量 | 150 | 148 | ⚠️ 差异 2 |
| 总行数 | ~1000万 | ~998万 | ✅ 正常 |
| 关键表数据 | 一致 | 一致 | ✅ 通过 |
| 查询功能 | 可用 | 可用 | ✅ 通过 |
| RTO 达标 | < 30分钟 | 25分钟 | ✅ 达标 |

## 发现的问题
1. **问题描述**: 表 A 缺失
   - **原因**: 备份时表正在被 DDL 操作锁定
   - **影响**: 低（非核心表）
   - **改进措施**: 调整备份窗口避开业务高峰

2. **问题描述**: 恢复速度较慢
   - **原因**: 单线程导入效率低
   - **影响**: 中（影响 RTO）
   - **改进措施**: 考虑使用 myloader 并行导入

## 改进建议
- [ ] 优化备份策略：增加表级锁等待超时配置
- [ ] 提升恢复速度：评估并行恢复方案
- [ ] 自动化演练：集成到 CI/CD 流程

## 结论
**演练结果**: ✅ 通过 / ❌ 失败  
**备份有效性**: ✅ 验证有效 / ❌ 需要修复  
**下次演练计划**: YYYY-MM-DD

---
**审批人**: ________________ **日期**: ________________
```

### 8.2 演练自动化调度

```yaml
# Ansible Playbook: 定期备份演练任务
# 文件: ansible/playbooks/backup_drill.yml

- name: Database Backup Drill Automation
  hosts: localhost
  connection: local
  vars:
    drill_schedule: "monthly"
    notification_email: "ops-team@example.com"
    retention_days: 90
  
  tasks:
    - name: Execute MySQL Backup Drill
      block:
        - name: Run MySQL restore test
          shell: >
            bash /opt/scripts/backup_drill/mysql_drill.sh
            2>&1 | tee /var/log/backup_drill/mysql_{{ ansible_date_time.iso8601_basic_short }}.log
          register: drill_result
          ignore_errors: true
        
        - name: Parse drill result
          set_fact:
            drill_status: "{{ 'SUCCESS' if drill_result.rc == 0 else 'FAILED' }}"
            drill_log: "/var/log/backup_drill/mysql_{{ ansible_date_time.iso8601_basic_short }}.log"
        
        - name: Send drill notification
          mail:
            to: "{{ notification_email }}"
            subject: "数据库备份演练报告 - {{ drill_status }}"
            body: |
              演练日期: {{ ansible_date_time.date }}
              演练结果: {{ drill_status }}
              详细日志: {{ drill_log }}
              
              请查看附件获取完整报告。
            attach:
              - "{{ drill_log }}"
          
      rescue:
        - name: Handle drill failure
          debug:
            msg: "演练失败，请手动检查日志"
```

### 8.3 演练记录持久化

```python
#!/usr/bin/env python3
"""
备份演练记录管理器
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DrillRecordManager:
    def __init__(self, data_dir: str = "data/backup_drills"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def save_drill_record(self, record: Dict) -> str:
        """保存演练记录"""
        record_id = f"drill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        record["record_id"] = record_id
        record["created_at"] = datetime.now().isoformat()
        
        filepath = self.data_dir / f"{record_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        
        return record_id
    
    def get_drill_history(
        self, 
        limit: int = 10, 
        db_type: Optional[str] = None
    ) -> List[Dict]:
        """获取演练历史"""
        records = []
        
        for filepath in sorted(self.data_dir.glob("*.json"), reverse=True)[:limit]:
            with open(filepath, 'r', encoding='utf-8') as f:
                record = json.load(f)
            
            if db_type and record.get("db_type") != db_type:
                continue
            
            records.append(record)
        
        return records
    
    def calculate_success_rate(self, days: int = 90) -> Dict:
        """计算近期成功率"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        total = 0
        success = 0
        
        for filepath in self.data_dir.glob("*.json"):
            with open(filepath, 'r', encoding='utf-8') as f:
                record = json.load(f)
            
            created = datetime.fromisoformat(record["created_at"])
            if created < cutoff:
                continue
            
            total += 1
            if record.get("result") == "success":
                success += 1
        
        rate = round(success / total * 100, 2) if total > 0 else 0
        
        return {
            "period_days": days,
            "total_drills": total,
            "successful": success,
            "failed": total - success,
            "success_rate": f"{rate}%"
        }


# 使用示例
manager = DrillRecordManager()

# 保存演练记录
record = manager.save_drill_record({
    "db_type": "MySQL",
    "drill_type": "full_restore",
    "backup_file": "full_20240115.sql.gz",
    "backup_size_gb": 12.5,
    "restore_duration_sec": 1847,
    "tables_restored": 152,
    "rows_estimated": 10500000,
    "validation_passed": True,
    "issues_found": ["table_x missing"],
    "result": "success",
    "executed_by": "system"
})

print(f"演练记录已保存: {record}")

# 查看历史成功率
stats = manager.calculate_success_rate(days=90)
print(f"近 90 天演练成功率: {stats['success_rate']} ({stats['successful']}/{stats['total_drills']})")
```

---

## 9. 权限边界

### 9.1 操作权限要求

| 操作 | 所需权限 | 风险等级 |
|------|----------|----------|
| 查看备份文件 | 文件系统只读权限 | 🟢 低 |
| 创建演练数据库 | CREATE DATABASE | 🟢 低 |
| 导入备份数据 | INSERT, CREATE, ALTER | 🟡 中 |
| 验证数据内容 | SELECT | 🟢 低 |
| 删除演练数据库 | DROP DATABASE | 🔴 高 |
| PITR 恢复 | SUPER, REPLICATION SLAVE | 🔴 高 |

### 9.2 安全注意事项

```bash
# 1. 演练前确认
cat <<'EOF'
========== 演练安全检查清单 ==========
□ 确认当前不在生产数据库上操作
□ 确认演练环境已隔离
□ 确认有足够磁盘空间
□ 确认已通知相关人员
□ 确认业务低峰期
□ 确认回滚方案就绪
======================================
EOF

read -p "以上项目全部确认？(yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "取消演练"
    exit 1
fi
```

### 9.3 自动清理机制

```bash
#!/bin/bash
# 演练环境自动清理脚本

DRILL_DB_PREFIX="drill_test_"
RETENTION_DAYS=7

log "清理超过 $RETENTION_DAYS 天的演练数据库..."

mysql -u root -p"$MYSQL_PASS" -N -e "
    SELECT SCHEMA_NAME 
    FROM information_schema.SCHEMATA 
    WHERE SCHEMA_NAME LIKE '${DRILL_DB_PREFIX}%' 
      AND CREATE_TIME < NOW() - INTERVAL $RETENTION_DAYS DAY;
" | while read DBNAME; do
    echo "删除旧演练数据库: $DBNAME"
    mysql -u root -p"$MYSQL_PASS" -e "DROP DATABASE \`$DBNAME\`;"
done

log "清理完成"
```

---

## 附录：常用命令速查

| 任务 | MySQL | PostgreSQL | Redis |
|------|-------|------------|-------|
| 全量备份 | `mysqldump -A` | `pg_dumpall` | `BGSAVE` |
| 单库备份 | `mysqldump db` | `pg_dump db` | -- |
| 恢复全量 | `mysql < dump.sql` | `psql < dump.sql` | 复制 dump.rdb |
| 恢复单库 | `mysql db < dump.sql` | `psql -d db < dump.sql` | -- |
| 查看 Binlog | `SHOW BINARY LOGS` | -- | -- |
| 查看 WAL | -- | `pg_waldump` | -- |
| PITR 恢复 | `mysqlbinlog \| mysql` | 配置 recovery.target_time | -- |
| 校验表 | `CHECKSUM TABLE` | -- | -- |
| 校验备份 | `gzip -t file.gz` | `pg_restore --list` | `redis-check-rdb` |
