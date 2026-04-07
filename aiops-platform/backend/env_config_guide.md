# 环境变量配置说明

## 📋 概述

AIOps 项目使用 `.env` 文件来管理所有敏感配置信息，包括：
- OpenAI API 配置
- Neo4j 数据库配置
- 阿里云 API 配置
- 数据库配置

## 🔧 配置文件位置

```
/Users/jaci-j/AIops/aiops-platform/backend/.env
```

## 📝 配置示例

### 完整配置示例

```env
# OpenAI API 配置
OPENAI_API_KEY=sk-2ee32cfc9a44443fae58ae7d71e844e6
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus

# Neo4j 数据库配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# 数据库配置
DATABASE_URL=sqlite:///./data/aiops.db

# 阿里云 API 配置
ALIYUN_ACCESS_KEY_ID=LTAI5t...
ALIYUN_ACCESS_KEY_SECRET=XYZ123...
ALIYUN_REGION_ID=cn-hangzhou
```

### 模板文件

项目提供了 `.env.example` 模板文件，位于：
```
/Users/jaci-j/AIops/aiops-platform/backend/.env.example
```

## 🔑 阿里云 AccessKey 配置

### 获取步骤

1. **登录阿里云控制台**
   - 访问：https://www.aliyun.com/
   - 使用您的阿里云账号登录

2. **进入 AccessKey 管理页面**
   - 点击右上角头像 → "AccessKey 管理"
   - 或直接访问：https://ram.console.aliyun.com/manage/ak

3. **创建 RAM 用户（推荐）**
   - 点击 "开始使用子用户 AccessKey"
   - 创建新用户：`aiops-monitor`
   - 添加权限：`AliyunECSReadOnlyAccess`
   - 获取 AccessKey ID 和 Secret

### 配置方法

#### 方法一：直接编辑 .env 文件

```bash
cd /Users/jaci-j/AIops/aiops-platform/backend
nano .env
```

添加以下内容：

```env
ALIYUN_ACCESS_KEY_ID=LTAI5t...
ALIYUN_ACCESS_KEY_SECRET=XYZ123...
ALIYUN_REGION_ID=cn-hangzhou
```

#### 方法二：使用环境变量（临时）

```bash
export ALIYUN_ACCESS_KEY_ID="LTAI5t..."
export ALIYUN_ACCESS_KEY_SECRET="XYZ123..."
export ALIYUN_REGION_ID="cn-hangzhou"
```

### 代码读取方式

在 `aliyun_monitor.py` 中，通过以下方式读取配置：

```python
import os

class AliyunMonitorClient:
    def __init__(self):
        self.access_key_id = os.getenv("ALIYUN_ACCESS_KEY_ID")
        self.access_key_secret = os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        self.region_id = os.getenv("ALIYUN_REGION_ID", "cn-hangzhou")
```

## 🔒 安全最佳实践

### 1. 不要提交到 Git

确保 `.env` 文件在 `.gitignore` 中：

```gitignore
# 敏感配置文件
.env
*.env
```

### 2. 使用最小权限

- ✅ 推荐：`AliyunECSReadOnlyAccess`（只读权限）
- ⚠️ 谨慎：`AliyunECSFullAccess`（完全访问权限）

### 3. 定期轮换

建议每 90 天轮换一次 AccessKey：
1. 创建新的 AccessKey
2. 更新 `.env` 文件
3. 禁用旧的 AccessKey

### 4. 监控使用

定期检查 AccessKey 的使用情况：
- 进入 RAM 控制台
- 查看用户的 "最后使用时间"
- 发现异常立即禁用

## ✅ 配置验证

### 验证步骤

配置完成后，可以运行以下脚本验证：

```python
#!/usr/bin/env python3
import os
import sys

# 添加项目路径
sys.path.insert(0, '/Users/jaci-j/AIops/aiops-platform/backend')

from app.utils.aliyun_monitor import AliyunMonitorClient

# 初始化客户端
client = AliyunMonitorClient()

# 检查配置
print("=== 配置检查 ===")
print(f"AccessKey ID: {'已配置' if client.access_key_id else '未配置'}")
print(f"AccessKey Secret: {'已配置' if client.access_key_secret else '未配置'}")
print(f"Region ID: {client.region_id}")

if not client.access_key_id or not client.access_key_secret:
    print("\n❌ 请先在 .env 文件中配置阿里云凭证")
    sys.exit(1)

print("\n✅ 配置检查通过！")
```

保存为 `test_aliyun_config.py` 并运行：

```bash
python3 test_aliyun_config.py
```

## 📊 配置说明

### 环境变量列表

| 变量名 | 说明 | 示例 | 必需 |
|---------|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-xxx...` | ✅ |
| `OPENAI_BASE_URL` | OpenAI API 地址 | `https://dashscope.aliyuncs.com/...` | ✅ |
| `OPENAI_MODEL` | 使用的模型 | `qwen-plus` | ✅ |
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` | ✅ |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` | ✅ |
| `NEO4J_PASSWORD` | Neo4j 密码 | `password` | ✅ |
| `DATABASE_URL` | 数据库连接地址 | `sqlite:///./data/aiops.db` | ✅ |
| `ALIYUN_ACCESS_KEY_ID` | 阿里云 AccessKey ID | `LTAI5t...` | ⚠️ |
| `ALIYUN_ACCESS_KEY_SECRET` | 阿里云 AccessKey Secret | `XYZ123...` | ⚠️ |
| `ALIYUN_REGION_ID` | 阿里云区域 ID | `cn-hangzhou` | ⚠️ |

**说明**：
- ✅ 必需：系统启动必需的配置
- ⚠️ 可选：阿里云功能需要时才必需

## 🚀 快速配置

### 一键配置脚本

创建 `setup_env.sh`：

```bash
#!/bin/bash

echo "=== AIOps 环境配置 ==="

cd /Users/jaci-j/AIops/aiops-platform/backend

# 检查 .env 文件是否存在
if [ ! -f .env ]; then
    echo "从 .env.example 创建 .env 文件..."
    cp .env.example .env
    echo "✅ .env 文件已创建"
else
    echo "✅ .env 文件已存在"
fi

echo ""
echo "请编辑 .env 文件，配置以下信息："
echo "1. OPENAI_API_KEY - OpenAI API 密钥"
echo "2. NEO4J_PASSWORD - Neo4j 密码"
echo "3. ALIYUN_ACCESS_KEY_ID - 阿里云 AccessKey ID（可选）"
echo "4. ALIYUN_ACCESS_KEY_SECRET - 阿里云 AccessKey Secret（可选）"
echo ""
echo "编辑命令: nano .env"
```

运行：

```bash
chmod +x setup_env.sh
./setup_env.sh
nano .env
```

## 🐛 故障排查

### 问题 1：环境变量未生效

**症状**：程序提示 "阿里云 API 凭证未配置"

**解决方案**：
1. 检查 `.env` 文件是否存在
2. 检查变量名是否正确
3. 重启服务

### 问题 2：权限不足

**症状**：阿里云 API 返回权限错误

**解决方案**：
1. 检查 RAM 用户权限
2. 确认是否添加了 `AliyunECSReadOnlyAccess`
3. 重新生成 AccessKey

### 问题 3：区域错误

**症状**：无法找到实例

**解决方案**：
1. 检查 `ALIYUN_REGION_ID` 配置
2. 确认实例所在区域
3. 常见区域：
   - cn-hangzhou（华东1）
   - cn-shanghai（华东2）
   - cn-beijing（华北2）
   - cn-shenzhen（华南1）

## 📝 总结

通过 `.env` 文件管理配置的优势：

1. ✅ **安全性**：敏感信息不提交到代码仓库
2. ✅ **灵活性**：不同环境可以使用不同的配置
3. ✅ **可维护性**：集中管理所有配置
4. ✅ **标准化**：使用业界标准的环境变量方式

配置完成后，AIOps 系统就能正常使用阿里云监控功能了！
