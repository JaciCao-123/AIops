# MySQL 死锁诊断报告

## 诊断概要

- **诊断时间**: 2025-04-02
- **数据库**: MySQL 8.0 (Docker: ops_rag_mysql)
- **用户**: ops_user
- **数据库实例**: ops_db

---

## 1. 连接信息

```
✅ 数据库连接成功
- 容器名称: ops_rag_mysql
- 端口: 3306
- 用户: ops_user@%
- 当前活跃连接: 2
```

---

## 2. 配置检查

### 2.1 事务隔离级别

```
全局隔离级别: REPEATABLE-READ
会话隔离级别: REPEATABLE-READ
自动提交: ON (1)
锁等待超时: 50 秒
```

**分析**: 使用默认的 REPEATABLE-READ 隔离级别，可能产生间隙锁。

### 2.2 InnoDB 行锁状态

```
当前行锁等待数: 0
历史行锁等待次数: 4
总锁等待时间: 101,314 ms
平均锁等待时间: 25,328 ms (约 25 秒)
最大锁等待时间: 50,166 ms (约 50 秒)
```

**分析**: 
- ✅ 当前无活跃死锁
- ⚠️ 历史上有 4 次锁等待，平均等待时间较长（25 秒）
- ⚠️ 最大锁等待时间接近超时阈值（50 秒）

---

## 3. 数据库对象

### 3.1 数据库列表

```
- information_schema
- ops_db (主要业务库)
- performance_schema
```

### 3.2 ops_db 表结构

```
- alert_events (告警事件)
- app_deployments (应用部署)
- dbaas_instances (数据库实例)
- inventory (库存)
- server_metrics (服务器指标)
- slow_query_logs (慢查询日志)
- suppliers (供应商)
- purchase_orders (采购订单)
- purchase_order_items (采购订单项)
- purchase_payments (采购付款)
- purchase_requisition_items (采购申请项)
- purchase_requisitions (采购申请)
```

---

## 4. 诊断结果

### 4.1 当前状态

- ✅ **无活跃死锁**: 当前行锁等待数为 0
- ✅ **连接正常**: 数据库连接稳定
- ⚠️ **历史锁等待**: 存在历史锁等待记录

### 4.2 潜在风险

1. **长事务风险**
   - 平均锁等待时间 25 秒，可能存在长事务
   - 建议检查应用层事务逻辑

2. **间隙锁风险**
   - REPEATABLE-READ 隔离级别可能产生间隙锁
   - 建议检查范围查询和插入操作

3. **权限限制**
   - ops_user 缺少 PROCESS 权限
   - 无法查看完整 InnoDB 状态

---

## 5. 建议措施

### 5.1 短期措施

1. **开启死锁日志**
   ```sql
   SET GLOBAL innodb_print_all_deadlocks = ON;
   ```

2. **监控长事务**
   ```sql
   SELECT 
       trx_id,
       trx_state,
       TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds
   FROM information_schema.innodb_trx
   WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 10;
   ```

### 5.2 中期措施

1. **优化事务设计**
   - 减小事务粒度
   - 统一访问顺序
   - 避免长事务

2. **添加索引**
   ```sql
   -- 检查缺失索引
   SELECT 
       TABLE_NAME,
       COLUMN_NAME,
       CARDINALITY
   FROM information_schema.STATISTICS
   WHERE TABLE_SCHEMA = 'ops_db'
   ORDER BY TABLE_NAME, SEQ_IN_INDEX;
   ```

### 5.3 长期措施

1. **调整隔离级别**（如适用）
   - 评估是否可以降级为 READ-COMMITTED
   - 减少间隙锁产生

2. **权限优化**
   - 为 ops_user 授予 PROCESS 权限
   - 或创建专用监控账号

---

## 6. 监控命令

### 6.1 实时监控

```sql
-- 查看当前连接
SHOW PROCESSLIST;

-- 查看锁状态
SHOW STATUS LIKE 'Innodb_row_lock%';

-- 查看活跃事务
SELECT * FROM information_schema.innodb_trx;
```

### 6.2 定期检查

```sql
-- 查看慢查询
SELECT * FROM slow_query_logs ORDER BY query_time DESC LIMIT 10;

-- 查看表锁
SHOW OPEN TABLES WHERE In_use > 0;
```

---

## 7. 权限边界说明

### 7.1 已执行的安全操作

- ✅ `SHOW PROCESSLIST` - 查看连接
- ✅ `SHOW STATUS` - 查看状态
- ✅ `SHOW DATABASES` - 查看数据库
- ✅ `SHOW TABLES` - 查看表

### 7.2 需要更高权限的操作

- ⚠️ `SHOW ENGINE INNODB STATUS` - 需要 PROCESS 权限
- ⚠️ `SET GLOBAL` - 需要 SUPER 权限

---

## 8. 总结

### 诊断结论

✅ **当前数据库状态正常**，无活跃死锁。

⚠️ **存在历史锁等待记录**，建议：
1. 开启死锁日志监控
2. 检查应用层事务逻辑
3. 优化索引设计
4. 考虑调整隔离级别

### 下一步行动

1. 联系 DBA 授予 PROCESS 权限以获取完整诊断信息
2. 开启死锁日志记录
3. 监控长事务
4. 定期检查锁状态

---

**报告生成时间**: 2025-04-02
**诊断工具**: MySQL 死锁排查 Skill v1.0.0
