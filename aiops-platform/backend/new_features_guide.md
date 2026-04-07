# 新功能使用指南

## 📋 概述

本次更新实现了两个重要功能：

1. **中间文件存储**: 所有中间文件（ansible yaml、output 等）都存储到 `data/` 目录
2. **阿里云监控集成**: 当主机不可达时，自动检查阿里云平台主机状态

## 🗂️ 中间文件存储

### 目录结构

```
data/
├── diagnosis/          # 诊断计划
│   ├── diagnosis_plan_20260324_143025.json
│   └── ...
├── playbooks/          # Ansible Playbooks
│   ├── playbook_8.136.226.231_20260324_143025.yaml
│   └── ...
├── outputs/            # 执行输出
│   ├── output_8.136.226.231_20260324_143025.txt
│   └── ...
├── logs/               # 完整日志
│   ├── full_result_20260324_143025.json
│   └── ...
└── aiops.db           # 数据库文件
```

### 文件命名规则

所有文件都使用时间戳命名，格式为：`{类型}_{时间戳}.{扩展名}`

例如：
- `diagnosis_plan_20260324_143025.json`
- `playbook_8.136.226.231_20260324_143025.yaml`
- `output_8.136.226.231_20260324_143025.txt`
- `full_result_20260324_143025.json`

### 存储内容

#### 1. 诊断计划 (diagnosis_plan_*.json)

```json
{
  "check_type": "disk",
  "reasoning": "为什么选择这些检查步骤",
  "commands": [
    "df -h",
    "du -h --max-depth=1 / | sort -rh | head -n 10",
    "lsof | grep deleted"
  ],
  "expected_findings": [
    "磁盘使用率是否超过阈值",
    "是否有大文件占用空间",
    "是否有被删除但未释放的文件"
  ],
  "next_steps_if_anomaly_found": "如果发现异常，下一步应该做什么",
  "saved_to": "data/diagnosis/diagnosis_plan_20260324_143025.json"
}
```

#### 2. 执行输出 (output_*.txt)

```
=== CMD_0: df -h ===
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda1        40G   15G   23G  40% /
...

=== CMD_1: du -h --max-depth=1 / | sort -rh | head -n 10 ===
1.5G    /var
800M    /usr
...
```

#### 3. 完整结果 (full_result_*.json)

包含整个处理流程的所有信息：
- 用户查询
- 意图识别结果
- 诊断计划
- 执行结果
- 知识库查询结果
- 最终决策

### 使用示例

```python
from app.utils.file_manager import IntermediateFileManager

# 初始化文件管理器
file_manager = IntermediateFileManager()

# 保存诊断计划
diagnosis_plan = {
    "check_type": "disk",
    "commands": ["df -h", "du -sh /*"]
}
filepath = file_manager.save_diagnosis_plan(diagnosis_plan)
print(f"诊断计划已保存到: {filepath}")

# 加载诊断计划
loaded_plan = file_manager.load_diagnosis_plan("diagnosis_plan_20260324_143025.json")

# 列出所有诊断计划
plans = file_manager.list_diagnosis_plans()
print(f"共有 {len(plans)} 个诊断计划")
```

## ☁️ 阿里云监控集成

### 功能说明

当检测到主机不可达时，系统会自动：
1. 调用阿里云 API 查询主机状态
2. 如果主机已停止，返回关机时间和操作人信息
3. 如果主机正在运行，提供其他排查建议

### 配置步骤

#### 1. 安装阿里云 SDK

```bash
pip install aliyun-python-sdk-core aliyun-python-sdk-ecs
```

#### 2. 配置环境变量

在 `.env` 文件中添加：

```env
ALIYUN_ACCESS_KEY_ID=your_aliyun_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_aliyun_access_key_secret
ALIYUN_REGION_ID=cn-hangzhou
```

#### 3. 获取阿里云 AccessKey

1. 登录阿里云控制台
2. 访问 [AccessKey 管理页面](https://ram.console.aliyun.com/manage/ak)
3. 创建 AccessKey 或使用现有的
4. 确保该 AccessKey 有 ECS 只读权限

### 使用示例

#### 场景 1: 主机已停止

**用户查询**: "8.136.226.231网络连接超时"

**系统行为**:
1. 尝试 SSH 连接失败
2. 自动调用阿里云 API 检查主机状态
3. 返回结果：

```json
{
  "success": true,
  "is_stopped": true,
  "instance_ip": "8.136.226.231",
  "instance_name": "test-server-01",
  "status": "已停止",
  "stop_time": "2026-03-24 10:30:00",
  "operator": "user@example.com",
  "message": "实例 test-server-01 (8.136.226.231) 已停止",
  "recommendation": "请登录阿里云控制台启动实例，或联系相关负责人确认是否需要启动"
}
```

#### 场景 2: 主机正在运行

**用户查询**: "8.136.226.231网络连接超时"

**系统行为**:
1. 尝试 SSH 连接失败
2. 自动调用阿里云 API 检查主机状态
3. 返回结果：

```json
{
  "success": true,
  "is_stopped": false,
  "instance_ip": "8.136.226.231",
  "instance_name": "test-server-01",
  "status": "运行中",
  "message": "实例 test-server-01 (8.136.226.231) 正在运行中，网络问题可能由其他原因导致",
  "recommendation": "建议检查安全组规则、网络配置或应用服务状态"
}
```

### API 使用示例

```python
from app.utils.aliyun_monitor import AliyunMonitorClient

# 初始化客户端
client = AliyunMonitorClient()

# 检查主机状态
result = await client.check_host_unreachable("8.136.226.231")

if result.get("success"):
    if result.get("is_stopped"):
        print(f"主机已停止，停止时间: {result['stop_time']}")
        print(f"操作人: {result['operator']}")
    else:
        print(f"主机正在运行，状态: {result['status']}")
else:
    print(f"检查失败: {result.get('error')}")
```

## 🔄 工作流程

### 完整流程

```
用户查询
  ↓
意图识别
  ↓
Master Agent 生成诊断计划
  ↓
保存诊断计划到 data/diagnosis/
  ↓
执行诊断命令
  ↓
SSH 连接失败？
  ├─ 是 → 调用阿里云 API 检查主机状态
  │        ↓
  │      返回主机状态信息
  │
  └─ 否 → 执行命令
           ↓
         保存输出到 data/outputs/
           ↓
         解析结果
           ↓
         知识库查询
           ↓
         Master Agent 决策
           ↓
         保存完整结果到 data/logs/
           ↓
         返回最终结果
```

### 异常处理

1. **SSH 连接超时**: 自动调用阿里云 API 检查主机状态
2. **主机不可达**: 自动调用阿里云 API 检查主机状态
3. **API 调用失败**: 返回错误信息，不影响其他功能

## 📊 数据管理

### 查看存储的文件

```bash
# 查看诊断计划
ls -lh data/diagnosis/

# 查看执行输出
ls -lh data/outputs/

# 查看完整日志
ls -lh data/logs/
```

### 清理旧文件

```bash
# 删除 7 天前的文件
find data/diagnosis -name "*.json" -mtime +7 -delete
find data/outputs -name "*.txt" -mtime +7 -delete
find data/logs -name "*.json" -mtime +7 -delete
```

### 备份重要文件

```bash
# 备份所有中间文件
tar -czf aiops_data_backup_$(date +%Y%m%d).tar.gz data/
```

## 🔒 安全建议

1. **AccessKey 保护**:
   - 不要将 AccessKey 提交到代码仓库
   - 定期轮换 AccessKey
   - 使用最小权限原则

2. **文件权限**:
   - data/ 目录设置为 700 权限
   - 敏感文件设置为 600 权限

3. **日志管理**:
   - 定期清理旧日志
   - 不要在日志中记录敏感信息

## 🎯 最佳实践

1. **定期检查**:
   - 定期检查 data/ 目录大小
   - 清理不需要的中间文件

2. **监控告警**:
   - 监控阿里云 API 调用次数
   - 设置文件存储空间告警

3. **性能优化**:
   - 对于频繁查询的主机，可以考虑缓存状态信息
   - 定期归档旧的中间文件

## 🐛 故障排查

### 问题 1: 阿里云 API 调用失败

**可能原因**:
- AccessKey 未配置
- AccessKey 权限不足
- 网络连接问题

**解决方案**:
1. 检查 `.env` 文件中的配置
2. 确认 AccessKey 有 ECS 只读权限
3. 检查网络连接

### 问题 2: 文件存储失败

**可能原因**:
- data/ 目录权限不足
- 磁盘空间不足

**解决方案**:
1. 检查 data/ 目录权限
2. 清理磁盘空间

### 问题 3: SSH 连接超时

**可能原因**:
- 主机已关机
- 网络问题
- 防火墙拦截

**解决方案**:
1. 查看阿里云检查结果
2. 检查网络配置
3. 检查安全组规则

## 📝 总结

本次更新实现了：

1. ✅ **中间文件存储**: 所有中间文件都存储到 data/ 目录，便于审计和回溯
2. ✅ **阿里云监控集成**: 自动检查主机状态，提供更准确的故障诊断
3. ✅ **智能异常处理**: 当 SSH 连接失败时，自动调用阿里云 API 检查
4. ✅ **完整的日志记录**: 记录完整的处理流程，便于问题排查

这些功能使得 AIOps 系统更加智能和可靠，能够更好地处理各种故障场景。
