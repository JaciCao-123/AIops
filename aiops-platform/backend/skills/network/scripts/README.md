# SLB 诊断脚本

本目录包含用于阿里云负载均衡（SLB）端口连接诊断的辅助脚本。

## 脚本列表

### 1. slb_diagnosis.py

**Python 版本的 SLB 诊断脚本**

**功能特性**:
- 使用阿里云 Python SDK 进行诊断
- 支持详细的根本原因分析
- 自动生成修复命令
- 支持服务能力评估
- 支持所有后端服务器端口状态检查

**依赖包**:
```bash
pip install aliyun-python-sdk-core aliyun-python-sdk-ecs aliyun-python-sdk-slb aliyun-python-sdk-sts
```

**使用方法**:
```bash
python3 slb_diagnosis.py <LOAD_BALANCER_ID> [REGION]

# 示例
python3 slb_diagnosis.py lb-bp1bxqgw0jflid09i6xnq cn-hangzhou
```

**环境变量**:
```bash
export ALICLOUD_ACCESS_KEY='your-access-key'
export ALICLOUD_SECRET_KEY='your-secret-key'
export ALICLOUD_REGION='cn-hangzhou'
```

### 2. slb_diagnosis.sh

**Bash 版本的 SLB 诊断脚本**

**功能特性**:
- 使用阿里云 CLI 进行诊断
- 适用于命令行环境
- 支持完整的诊断流程
- 支持服务能力评估
- 支持所有后端服务器端口状态检查

**依赖**:
- 阿里云 CLI (aliyun)
- jq (JSON 处理工具)

**安装依赖**:
```bash
# macOS
brew install aliyun-cli jq

# Linux
wget https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz
tar -xzf aliyun-cli-linux-latest-amd64.tgz
sudo mv aliyun /usr/local/bin/
sudo apt-get install jq  # Debian/Ubuntu
sudo yum install jq      # CentOS/RHEL

# Windows
choco install aliyun-cli jq
```

**使用方法**:
```bash
bash slb_diagnosis.sh <LOAD_BALANCER_ID> [REGION]

# 示例
bash slb_diagnosis.sh lb-bp1bxqgw0jflid09i6xnq cn-hangzhou
```

**配置认证**:
```bash
aliyun configure
```

## 诊断流程

两个脚本都实现了以下诊断流程：

1. **Step 1**: 检查阿里云环境（CLI/SDK）
2. **Step 2**: 查询 SLB 实例状态
3. **Step 3**: 查询健康检查状态
4. **Step 4**: 查询监听配置
5. **Step 4.5**: 服务能力评估
6. **Step 5.5**: 检查所有后端服务器端口状态
7. **Step 6**: 检查异常服务器
8. **Step 7**: 详细安全组排查和根本原因分析

## 输出示例

### 正常状态

```
============================================================
阿里云 SLB 远程诊断
============================================================
SLB ID: lb-bp1bxqgw0jflid09i6xnq
区域: cn-hangzhou
诊断时间: 2026-04-06 18:00:00

=== Step 1: 检查阿里云 SDK 环境 ===
✓ 阿里云 SDK 初始化成功
✓ 认证成功

=== Step 2: 查询 SLB 实例状态 ===
✓ SLB 实例存在
  实例 ID: lb-bp1bxqgw0jflid09i6xnq
  实例状态: active

=== Step 3: 查询健康检查状态 ===
后端服务器数量: 2
健康状态:
  ✓ ServerId: i-bp14cdse1t3ahqrkuooe, Port: 80, Status: normal
  ✓ ServerId: i-bp1hja4pzmwaguaf5e6a, Port: 80, Status: normal

健康服务器: 2
异常服务器: 0

=== Step 4.5: 服务能力评估 ===
服务能力: 100.0%
正常服务器: 2/2
异常服务器: 0/2

============================================================
诊断完成
============================================================

✓ SLB 服务状态正常
```

### 异常状态（安全组问题）

```
============================================================
阿里云 SLB 远程诊断
============================================================

=== Step 3: 查询健康检查状态 ===
后端服务器数量: 2
健康状态:
  ✓ ServerId: i-bp14cdse1t3ahqrkuooe, Port: 80, Status: normal
  ✗ ServerId: i-bp1hja4pzmwaguaf5e6a, Port: 80, Status: abnormal

健康服务器: 1
异常服务器: 1

=== Step 4.5: 服务能力评估 ===
服务能力: 50.0%
正常服务器: 1/2
异常服务器: 1/2

⚠ 服务能力低于 100%，以下服务器的端口出现问题：
  - 服务器 ID: i-bp1hja4pzmwaguaf5e6a, 端口: 80, 状态: abnormal

=== Step 6: 详细安全组排查和根本原因分析 ===

--- 服务器: i-bp1hja4pzmwaguaf5e6a, 端口: 80 ---

安全组: sg-xxxxx
  安全组名称: default

  入方向规则分析:
    ✗ 根本原因: 安全组未允许 SLB 健康检查网段 (100.64.0.0/10) 访问
    影响: SLB 无法进行健康检查，导致服务器被标记为异常

    修复命令:
      aliyun ecs AuthorizeSecurityGroup \
        --SecurityGroupId sg-xxxxx \
        --IpProtocol tcp \
        --PortRange 80/80 \
        --SourceCidrIp 100.64.0.0/10 \
        --Description "Allow SLB health check"

============================================================
诊断完成
============================================================

✗ 发现 1 台异常服务器，请检查上述诊断信息

服务能力评估:
  正常服务器: 1/2
  异常服务器: 1/2
  服务能力: 50.0%
  ⚠ 警告: 服务能力下降，建议尽快处理
```

## 权限要求

运行这些脚本需要以下阿里云权限：

- **AliyunSLBReadOnlyAccess**: 负载均衡只读权限
- **AliyunECSReadOnlyAccess**: 云服务器只读权限

**添加权限**:
1. 登录阿里云控制台
2. 进入 RAM 访问控制
3. 找到对应的 RAM 用户
4. 添加权限：
   - AliyunSLBReadOnlyAccess
   - AliyunECSReadOnlyAccess

## 相关文件

- **Skill 文件**: [../lb_port_connectivity_skill.md](../lb_port_connectivity_skill.md)
- **诊断报告目录**: `/Users/jaci-j/AIops/aiops-platform/backend/data/diagnosis/`

## 更新历史

- **2026-04-06**: 
  - 创建脚本文件
  - 添加服务能力评估功能
  - 添加所有后端服务器端口状态检查
  - 添加详细安全组排查和根本原因分析

## 技术支持

如有问题，请参考：
- [阿里云 SLB 文档](https://help.aliyun.com/product/27537.html)
- [阿里云 CLI 文档](https://help.aliyun.com/document_detail/139508.html)
- [阿里云 Python SDK 文档](https://help.aliyun.com/document_detail/130146.html)
