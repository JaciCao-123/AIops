# 备份管理技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 备份策略](#3-备份策略)
- [4. 备份命令集](#4-备份命令集)
- [5. 恢复操作](#5-恢复操作)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `备份`, `backup`, `恢复`, `restore`
- `快照`, `snapshot`, `归档`, `archive`
- `数据保护`, `灾备`, `DR`
- `MySQL 备份`, `文件备份`, `增量备份`

### 1.2 适用条件
- 数据库备份与恢复
- 文件系统备份
- 增量/全量备份
- 备份验证
- 灾难恢复

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 评估备份需求                                       │
│  - 确定备份对象                                            │
│  - 确定备份类型                                            │
│  - 确定备份频率                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 检查现有备份                                       │
│  - 查看备份列表                                            │
│  - 验证备份完整性                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 执行备份                                           │
│  - 全量备份                                                │
│  - 增量备份                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 验证备份                                           │
│  - 完整性检查                                              │
│  - 恢复测试                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 备份管理                                           │
│  - 清理过期备份                                            │
│  - 异地备份                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 备份策略

### 3.1 备份类型

| 类型 | 说明 | 优点 | 缺点 |
|------|------|------|------|
| **全量备份** | 完整复制所有数据 | 恢复简单快速 | 占用空间大, 时间长 |
| **增量备份** | 只备份变化的数据 | 占用空间小, 速度快 | 恢复复杂, 需要链式恢复 |
| **差异备份** | 备份自上次全量以来的变化 | 恢复较快 | 占用空间中等 |

### 3.2 备份策略建议

```
┌─────────────────────────────────────────────────────────────┐
│  推荐备份策略: 3-2-1 原则                                   │
│  - 3 份备份副本                                            │
│  - 2 种不同存储介质                                        │
│  - 1 份异地备份                                            │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 备份频率建议

| 数据类型 | 全量备份 | 增量备份 | 保留周期 |
|---------|---------|---------|---------|
| 数据库 | 每日 | 每小时 | 30 天 |
| 配置文件 | 每周 | - | 90 天 |
| 用户数据 | 每日 | 每 4 小时 | 60 天 |
| 日志文件 | 每周 | 每日 | 7 天 |

---

## 4. 备份命令集

### 4.1 MySQL 数据库备份

#### mysqldump 备份
```bash
# 全库备份
mysqldump -u root -p --all-databases > all_databases.sql

# 单库备份
mysqldump -u root -p database_name > database_name.sql

# 多库备份
mysqldump -u root -p --databases db1 db2 db3 > databases.sql

# 单表备份
mysqldump -u root -p database_name table_name > table_name.sql

# 只备份表结构
mysqldump -u root -p --no-data database_name > schema.sql

# 只备份数据
mysqldump -u root -p --no-create-info database_name > data.sql

# 压缩备份
mysqldump -u root -p database_name | gzip > database_name.sql.gz

# 远程备份
mysqldump -h remote_host -u root -p database_name > database_name.sql

# Docker 环境
docker exec mysql_container mysqldump -u root -ppassword database_name > backup.sql
```

#### XtraBackup 备份（热备份）
```bash
# 安装 XtraBackup
# Ubuntu
apt-get install percona-xtrabackup-80

# 全量备份
xtrabackup --backup --target-dir=/backup/full --user=root --password=password

# 增量备份
xtrabackup --backup --target-dir=/backup/inc1 --incremental-basedir=/backup/full --user=root --password=password

# 准备备份
xtrabackup --prepare --target-dir=/backup/full

# 恢复
xtrabackup --copy-back --target-dir=/backup/full --datadir=/var/lib/mysql
```

#### mydumper 备份（多线程）
```bash
# 安装
apt-get install mydumper

# 全库备份
mydumper -u root -p password -o /backup/dump

# 多线程备份
mydumper -u root -p password -o /backup/dump -t 8

# 压缩备份
mydumper -u root -p password -o /backup/dump -c
```

### 4.2 PostgreSQL 备份

```bash
# pg_dump 单库备份
pg_dump -U postgres database_name > database_name.sql

# pg_dumpall 全库备份
pg_dumpall -U postgres > all_databases.sql

# 自定义格式（压缩）
pg_dump -U postgres -Fc database_name > database_name.dump

# 并行备份
pg_dump -U postgres -Fc -j 4 database_name > database_name.dump

# 远程备份
pg_dump -h remote_host -U postgres database_name > database_name.sql
```

### 4.3 Redis 备份

```bash
# RDB 备份
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# AOF 备份
redis-cli BGREWRITEAOF
cp /var/lib/redis/appendonly.aof /backup/redis-$(date +%Y%m%d).aof

# Docker 环境
docker exec redis redis-cli BGSAVE
docker cp redis:/data/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

### 4.4 文件系统备份

#### tar 备份
```bash
# 全量备份
tar -czvf /backup/data-$(date +%Y%m%d).tar.gz /data

# 排除特定目录
tar -czvf /backup/data.tar.gz --exclude='/data/logs' /data

# 增量备份
tar -czvf /backup/data-inc.tar.gz -g /backup/snapshot.snar /data

# 验证备份
tar -tzvf /backup/data.tar.gz
```

#### rsync 同步备份
```bash
# 本地同步
rsync -avz /data/ /backup/data/

# 远程同步
rsync -avz -e ssh /data/ user@remote:/backup/data/

# 增量同步（只传输变化）
rsync -avz --delete /data/ user@remote:/backup/data/

# 排除文件
rsync -avz --exclude='*.log' /data/ /backup/data/

# 显示进度
rsync -avz --progress /data/ /backup/data/
```

### 4.5 云存储备份

```bash
# AWS S3
aws s3 sync /data s3://bucket/backup/data/
aws s3 cp backup.tar.gz s3://bucket/backup/

# 阿里云 OSS
ossutil cp /data oss://bucket/backup/data/ -r
ossutil cp backup.tar.gz oss://bucket/backup/

# 腾讯云 COS  
coscmd upload -r /data /backup/data/
```

---

## 5. 恢复操作

### 5.1 MySQL 恢复

```bash
# 恢复全库
mysql -u root -p < all_databases.sql

# 恢复单库
mysql -u root -p database_name < database_name.sql

# 恢复压缩备份
gunzip < database_name.sql.gz | mysql -u root -p database_name

# 恢复到 Docker
docker exec -i mysql_container mysql -u root -ppassword database_name < backup.sql

# XtraBackup 恢复
xtrabackup --prepare --target-dir=/backup/full
xtrabackup --copy-back --target-dir=/backup/full --datadir=/var/lib/mysql
chown -R mysql:mysql /var/lib/mysql
```

### 5.2 PostgreSQL 恢复

```bash
# 恢复 SQL 备份
psql -U postgres database_name < database_name.sql

# 恢复自定义格式
pg_restore -U postgres -d database_name database_name.dump

# 恢复全库
psql -U postgres -f all_databases.sql
```

### 5.3 Redis 恢复

```bash
# 停止 Redis
systemctl stop redis

# 恢复 RDB
cp /backup/redis-backup.rdb /var/lib/redis/dump.rdb
chown redis:redis /var/lib/redis/dump.rdb

# 恢复 AOF
cp /backup/redis-backup.aof /var/lib/redis/appendonly.aof
chown redis:redis /var/lib/redis/appendonly.aof

# 启动 Redis
systemctl start redis
```

### 5.4 文件恢复

```bash
# tar 恢复
tar -xzvf /backup/data.tar.gz -C /

# rsync 恢复
rsync -avz /backup/data/ /data/

# 从云存储恢复
aws s3 sync s3://bucket/backup/data/ /data/
```

---

## 6. 权限边界

### 6.1 安全的只读操作
```bash
ls, cat, head, tail
mysqldump (只备份)
pg_dump (只备份)
redis-cli --rdb
tar -tzvf (查看备份)
```

### 6.2 需要确认的操作
```bash
mysqldump (大数据库)
tar -czvf (创建备份)
rsync (同步数据)
rm (删除旧备份)
```

### 6.3 危险操作禁止执行
```bash
DROP DATABASE
TRUNCATE TABLE
rm -rf /data
恢复操作覆盖现有数据
```

---

## 7. 备份验证脚本

```bash
#!/bin/bash
# 备份验证脚本

BACKUP_DIR="/backup"
LOG_FILE="/var/log/backup_verify.log"

echo "=== 备份验证 $(date) ===" | tee -a $LOG_FILE

# 检查备份目录
if [ ! -d "$BACKUP_DIR" ]; then
  echo "❌ 备份目录不存在: $BACKUP_DIR" | tee -a $LOG_FILE
  exit 1
fi

# 检查最新备份
LATEST_BACKUP=$(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST_BACKUP" ]; then
  echo "❌ 未找到备份文件" | tee -a $LOG_FILE
  exit 1
fi

echo "最新备份: $LATEST_BACKUP" | tee -a $LOG_FILE

# 检查备份大小
BACKUP_SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
echo "备份大小: $BACKUP_SIZE" | tee -a $LOG_FILE

# 验证备份完整性
if gunzip -t "$LATEST_BACKUP" 2>/dev/null; then
  echo "✅ 备份文件完整" | tee -a $LOG_FILE
else
  echo "❌ 备份文件损坏" | tee -a $LOG_FILE
  exit 1
fi

# 检查备份时间
BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))
echo "备份时间: ${BACKUP_AGE} 小时前" | tee -a $LOG_FILE

if [ $BACKUP_AGE -gt 24 ]; then
  echo "⚠️  警告: 备份超过 24 小时" | tee -a $LOG_FILE
fi

echo "=== 验证完成 ===" | tee -a $LOG_FILE
```

---

## 8. 自动备份脚本

```bash
#!/bin/bash
# MySQL 自动备份脚本

DB_HOST="localhost"
DB_USER="root"
DB_PASS="password"
BACKUP_DIR="/backup/mysql"
RETENTION_DAYS=30

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份文件名
BACKUP_FILE="$BACKUP_DIR/mysql_$(date +%Y%m%d_%H%M%S).sql.gz"

# 执行备份
echo "开始备份: $(date)"
mysqldump -h $DB_HOST -u $DB_USER -p$DB_PASS --all-databases | gzip > $BACKUP_FILE

if [ $? -eq 0 ]; then
  echo "备份成功: $BACKUP_FILE"
  
  # 清理旧备份
  find $BACKUP_DIR -name "mysql_*.sql.gz" -mtime +$RETENTION_DAYS -delete
  echo "已清理 $RETENTION_DAYS 天前的备份"
else
  echo "备份失败!"
  exit 1
fi

# 验证备份
if gunzip -t $BACKUP_FILE 2>/dev/null; then
  echo "备份验证通过"
else
  echo "备份验证失败!"
  exit 1
fi
```

---

## 9. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
