# Neo4j 备份策略配置

## 📊 当前环境

- **Neo4j版本**: 4.4.48
- **运行方式**: Docker容器
- **容器名称**: neo4j
- **数据卷**: `neo4j_data` (Docker volume)
- **备份方式**: tar.gz压缩包（文件系统快照）

---

## ✅ 已完成的配置

### 1. 备份目录
```bash
/Users/jaci-j/AIops/backups/neo4j
```

### 2. 脚本目录
```bash
/Users/jaci-j/AIops/scripts/
├── neo4j_backup.sh    # 备份脚本
└── neo4j_restore.sh   # 恢复脚本
```

### 3. 日志目录
```bash
/Users/jaci-j/AIops/logs/
└── neo4j_backup.log   # 备份日志
```

---

## 🎯 备份策略

### 备份类型
| 类型 | 格式 | 保留时间 |
|------|------|---------|
| 完整备份 | tar.gz | 7天 |

### 备份时间
- 每天凌晨2:00（建议）

### 备份原理
1. 停止Neo4j数据库
2. 使用tar打包数据目录
3. 重启Neo4j数据库
4. 清理7天前的备份

---

## 🚀 使用方法

### 手动备份

```bash
/Users/jaci-j/AIops/scripts/neo4j_backup.sh
```

**输出示例：**
```
[Thu Mar 19 11:16:42 CST 2026] 开始备份 Neo4j...
[Thu Mar 19 11:16:42 CST 2026] 停止Neo4j数据库...
[Thu Mar 19 11:16:48 CST 2026] 执行备份（复制数据文件）...
[Thu Mar 19 11:17:11 CST 2026] ✓ 备份文件已创建: neo4j_backup_20260319_111642.tar.gz
[Thu Mar 19 11:17:11 CST 2026] ✓ 备份大小:  13M
[Thu Mar 19 11:17:21 CST 2026] ✓ Neo4j已重启
[Thu Mar 19 11:17:21 CST 2026] 备份流程完成
```

### 查看备份列表

```bash
ls -lh /Users/jaci-j/AIops/backups/neo4j/
```

### 恢复数据库

```bash
/Users/jaci-j/AIops/scripts/neo4j_restore.sh <备份文件名>
```

**示例：**
```bash
# 查看可用备份
ls /Users/jaci-j/AIops/backups/neo4j/

# 恢复指定备份
/Users/jaci-j/AIops/scripts/neo4j_restore.sh neo4j_backup_20260319_111642.tar.gz
```

---

## ⏰ 定时任务配置

### 问题说明
macOS默认禁止crontab定时任务。需要使用launchd替代方案。

### 方案1：使用launchd（推荐）

1. 创建plist文件：
```bash
cat > ~/Library/LaunchAgents/com.neo4j.backup.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neo4j.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/jaci-j/AIops/scripts/neo4j_backup.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/jaci-j/AIops/logs/neo4j_backup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/jaci-j/AIops/logs/neo4j_backup.log</string>
</dict>
</plist>
EOF
```

2. 加载定时任务：
```bash
launchctl load ~/Library/LaunchAgents/com.neo4j.backup.plist
```

3. 验证：
```bash
launchctl list | grep neo4j
```

### 方案2：使用cron（需要特殊权限）

```bash
# 编辑crontab（如果系统允许）
crontab -e

# 添加定时任务
0 2 * * * /Users/jaci-j/AIops/scripts/neo4j_backup.sh >> /Users/jaci-j/AIops/logs/neo4j_backup.log 2>&1
```

### 方案3：使用定时服务（如CronniX）

下载并安装[CronniX](https://www.macupdate.com/app/mac/16424/cronnix/)图形界面工具。

---

## 🔧 故障排除

### 备份失败

1. 检查Neo4j容器状态：
```bash
docker ps | grep neo4j
```

2. 手动重启Neo4j：
```bash
docker restart neo4j
```

3. 重新执行备份：
```bash
/Users/jaci-j/AIops/scripts/neo4j_backup.sh
```

### 恢复失败

1. 检查备份文件是否存在：
```bash
ls -lh /Users/jaci-j/AIops/backups/neo4j/
```

2. 检查恢复日志：
```bash
cat /Users/jaci-j/AIops/logs/neo4j_restore.log
```

3. 手动恢复：
```bash
docker stop neo4j
docker run --rm -v neo4j_data:/data -v /Users/jaci-j/AIops/backups/neo4j:/backup ubuntu:latest tar xzf /backup/<备份文件> -C /data
docker start neo4j
```

### 容器无法启动

1. 检查日志：
```bash
docker logs neo4j
```

2. 检查数据卷权限：
```bash
docker run --rm -v neo4j_data:/data ubuntu:latest ls -la /data
```

---

## 📝 备份脚本内容

### neo4j_backup.sh

```bash
#!/bin/bash
NEO4J_CONTAINER="neo4j"
BACKUP_DIR="/Users/jaci-j/AIops/backups/neo4j"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="neo4j_backup_${DATE}"
RETENTION_DAYS=7

echo "[$(date)] 开始备份 Neo4j..."

echo "[$(date)] 停止Neo4j数据库..."
docker stop $NEO4J_CONTAINER
sleep 5

echo "[$(date)] 执行备份（复制数据文件）..."
docker run --rm \
  -v neo4j_data:/data \
  -v $BACKUP_DIR:/backup \
  ubuntu:latest \
  tar czf /backup/${BACKUP_NAME}.tar.gz -C /data .

if [ -f "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" ]; then
    echo "[$(date)] ✓ 备份文件已创建: $BACKUP_NAME.tar.gz"
    echo "[$(date)] ✓ 备份大小: $(du -h $BACKUP_DIR/${BACKUP_NAME}.tar.gz | cut -f1)"
else
    echo "[$(date)] ✗ 备份失败"
fi

echo "[$(date)] 重启Neo4j数据库..."
docker start $NEO4J_CONTAINER
sleep 10

if docker ps | grep -q $NEO4J_CONTAINER; then
    echo "[$(date)] ✓ Neo4j已重启"
else
    echo "[$(date)] ✗ Neo4j重启失败"
fi

echo "[$(date)] 清理过期备份（保留最近${RETENTION_DAYS}天）..."
find $BACKUP_DIR -name "neo4j_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] 当前备份列表："
ls -lh $BACKUP_DIR | grep neo4j_backup

echo "[$(date)] 备份流程完成"
```

---

## ⚠️ 注意事项

1. **备份期间服务中断**：备份过程中Neo4j会停止约10-20秒
2. **存储空间**：监控备份目录大小，及时清理过期备份
3. **定期测试恢复**：建议每月测试一次恢复流程
4. **备份完整性**：恢复后验证数据完整性

---

## 📞 快速命令参考

| 操作 | 命令 |
|------|------|
| 手动备份 | `/Users/jaci-j/AIops/scripts/neo4j_backup.sh` |
| 查看备份 | `ls -lh /Users/jaci-j/AIops/backups/neo4j/` |
| 恢复备份 | `/Users/jaci-j/AIops/scripts/neo4j_restore.sh <文件名>` |
| 查看Neo4j状态 | `docker ps \| grep neo4j` |
| 查看Neo4j日志 | `docker logs neo4j` |
| 重启Neo4j | `docker restart neo4j` |

---

## ✅ 验证清单

- [x] 备份目录已创建
- [x] 备份脚本已创建并可执行
- [x] 首次备份测试成功（12M）
- [ ] 定时任务已配置（launchd方案）
- [ ] 恢复流程已验证
