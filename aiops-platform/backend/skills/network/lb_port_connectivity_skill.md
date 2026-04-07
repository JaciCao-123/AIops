# 阿里云负载均衡端口连接诊断技能

## ⚠️ 重要提示

**诊断方法优先级**：

1. **优先使用 Python 脚本**（推荐）✅
   - 脚本位置：`skills/network/scripts/slb_diagnosis.py`
   - 使用阿里云 Python SDK，无需安装 CLI
   - 自动读取 `.env` 文件中的认证信息
   - 支持完整的诊断流程和根本原因分析

2. **备选方案：Bash 脚本**
   - 脚本位置：`skills/network/scripts/slb_diagnosis.sh`
   - 需要安装阿里云 CLI
   - 适用于命令行环境

**推荐使用方法**：
```bash
# 直接执行 Python 脚本（推荐）
python3 skills/network/scripts/slb_diagnosis.py <LOAD_BALANCER_ID> [REGION]

# 示例
python3 skills/network/scripts/slb_diagnosis.py lb-bp1bxqgw0jflid09i6xnq cn-hangzhou
```

**环境变量配置**（`.env` 文件）：
```bash
ALICLOUD_ACCESS_KEY=your-access-key-id
ALICLOUD_SECRET_KEY=your-access-key-secret
ALICLOUD_REGION=cn-hangzhou
```

---

## 辅助脚本

本 skill 提供了两个诊断脚本，用于自动化执行诊断流程：

### Python 脚本（推荐）✅

- **脚本**: `skills/network/scripts/slb_diagnosis.py`
- **优势**:
  - ✅ 使用阿里云 Python SDK，无需安装 CLI
  - ✅ 自动读取 `.env` 文件中的认证信息
  - ✅ 支持详细的根本原因分析
  - ✅ 自动生成修复命令
  - ✅ 完整的错误处理和日志输出

- **使用方法**:
```bash
# 基本用法
python3 skills/network/scripts/slb_diagnosis.py <LOAD_BALANCER_ID> [REGION]

# 示例
python3 skills/network/scripts/slb_diagnosis.py lb-bp1bxqgw0jflid09i6xnq cn-hangzhou
```

### Bash 脚本（备选）

- **脚本**: `skills/network/scripts/slb_diagnosis.sh`
- **要求**: 需要安装阿里云 CLI
- **使用方法**:
```bash
bash skills/network/scripts/slb_diagnosis.sh <LOAD_BALANCER_ID> [REGION]
```

---

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 环境检测](#3-环境检测)
- [4. 诊断命令集](#4-诊断命令集)
- [5. 常见问题与解决方案](#5-常见问题与解决方案)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `负载均衡`, `SLB`, `ALB`, `CLB`, `NLB`
- `端口连不上`, `端口不通`, `连接失败`, `健康检查失败`
- `后端服务器`, `ECS`, `端口`, `监听`
- `阿里云`, `Aliyun`, `ALIYUN`

### 1.2 适用条件
- 阿里云负载均衡（SLB/ALB/NLB）健康检查失败
- 负载均衡无法连接后端服务器端口
- 后端服务端口配置问题
- 安全组/防火墙阻断
- 服务未启动或监听异常

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 收集信息                                           │
│  - 负载均衡 ID/名称                                         │
│  - 后端服务器 IP                                            │
│  - 端口号                                                  │
│  - 协议类型 (TCP/HTTP/HTTPS)                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 0.5: 环境判断                                         │
│  - 判断是本地服务器还是远程云服务                           │
│  - 检查是否具备阿里云 CLI 访问权限                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
            ┌─────────────────┴─────────────────┐
            │                                   │
    ┌───────▼────────┐                ┌────────▼────────┐
    │  本地服务器诊断  │                │  远程云服务诊断  │
    └───────┬────────┘                └────────┬────────┘
            │                                   │
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R1: 使用 Python 脚本   │
            │                  │           进行诊断           │
            │                  │  - 执行 slb_diagnosis.py     │
            │                  │  - 自动读取 .env 配置        │
            │                  │  - 使用阿里云 SDK 查询       │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R2: 查询 SLB 实例状态  │
            │                  │  - 实例是否存在              │
            │                  │  - 实例运行状态              │
            │                  │  - 后端服务器列表            │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R3: 检查健康检查状态   │
            │                  │  - 健康检查配置              │
            │                  │  - 后端服务器健康状态        │
            │                  │  - 异常原因分析              │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R3.5: 服务能力评估     │
            │                  │  - 计算服务能力百分比        │
            │                  │  - 识别异常服务器和端口      │
            │                  │  - 提供排查建议              │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R4: 检查监听配置       │
            │                  │  - 监听端口配置              │
            │                  │  - 后端端口映射              │
            │                  │  - 协议配置                  │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R4.5: 检查所有后端     │
            │                  │           服务器端口状态     │
            │                  │  - 所有服务器端口健康状态    │
            │                  │  - 端口状态汇总              │
            │                  │  - 异常端口列表              │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R5: 检查安全组规则     │
            │                  │  - 后端服务器安全组          │
            │                  │  - SLB 访问权限              │
            │                  │  - 端口开放情况              │
            │                  └──────────────────────────────┘
            │                                   ↓
            │                  ┌──────────────────────────────┐
            │                  │  Step R6: 详细安全组排查     │
            │                  │           和根本原因分析     │
            │                  │  - 入方向规则分析            │
            │                  │  - 端口匹配检查              │
            │                  │  - 协议类型检查              │
            │                  │  - 授权策略检查              │
            │                  │  - 根本原因识别              │
            │                  │  - 修复命令生成              │
            │                  └──────────────────────────────┘
            ↓                                   ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 检查后端服务器状态                                 │
│  - 服务器是否运行                                           │
│  - 服务是否启动                                             │
│  - 端口是否监听                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 检查端口监听状态                                   │
│  - 端口是否在监听                                           │
│  - 监听地址是否正确 (0.0.0.0 vs 127.0.0.1)                 │
│  - 进程状态                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 检查本地连接                                       │
│  - 本地回环测试                                            │
│  - 内网 IP 测试                                            │
│  - 从其他服务器测试                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 检查防火墙/安全组                                  │
│  - iptables/firewalld                                      │
│  - 阿里云安全组规则                                         │
│  - 云防火墙规则                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 检查负载均衡配置                                   │
│  - 监听配置                                                │
│  - 后端服务器配置                                           │
│  - 健康检查配置                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 环境检测

### 3.1 检测操作系统类型

#### Linux 系统
```bash
# 检测操作系统
cat /etc/os-release | grep -E "^ID=|^VERSION_ID="

# 检测是否有 systemd
systemctl --version 2>/dev/null

# 检测防火墙类型
which iptables firewall-cmd ufw 2>/dev/null
```

#### Windows 系统
```powershell
# 检测 Windows 版本
systeminfo | findstr /B /C:"OS Name" /C:"OS Version"

# 检测 Windows 版本（简洁）
winver

# 检测系统类型
wmic os get Caption, Version, BuildNumber

# 检测防火墙状态
netsh advfirewall show allprofiles state
```

#### 跨平台检测脚本
```bash
# Linux/macOS
if [ -f /etc/os-release ]; then
    echo "Operating System: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
elif [ "$(uname)" = "Darwin" ]; then
    echo "Operating System: macOS $(sw_vers -productVersion)"
fi

# Windows (PowerShell)
if ($PSVersionTable.PSVersion) {
    Write-Host "Operating System: $(Get-CimInstance Win32_OperatingSystem | Select-Object Caption)"
}
```

### 3.2 检测云环境

#### 检测阿里云 CLI 环境
```bash
# 检查阿里云 CLI 是否安装
which aliyun 2>/dev/null || echo "阿里云 CLI 未安装"

# 检查阿里云 CLI 版本
aliyun version 2>/dev/null

# 检查阿里云 CLI 配置
aliyun configure list 2>/dev/null

# 测试阿里云 API 连接
aliyun sts GetCallerIdentity 2>/dev/null
```

**阿里云 CLI 安装和配置**:
```bash
# Linux/macOS 安装阿里云 CLI
# 方法 1: 使用包管理器
# macOS
brew install aliyun-cli

# Linux (下载二进制文件)
wget https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz
tar -xzf aliyun-cli-linux-latest-amd64.tgz
sudo mv aliyun /usr/local/bin/

# 方法 2: 使用 Python pip
pip install aliyun-python-sdk-core aliyun-python-sdk-ecs aliyun-python-sdk-slb

# 配置阿里云 CLI
aliyun configure
# 输入 AccessKey ID
# 输入 AccessKey Secret
# 输入默认区域 (如 cn-hangzhou)
# 输入输出格式 (json)

# 验证配置
aliyun sts GetCallerIdentity
```

**Windows 安装阿里云 CLI**:
```powershell
# 方法 1: 使用 Chocolatey
choco install aliyun-cli

# 方法 2: 下载 Windows 版本
# 从 https://github.com/aliyun/aliyun-cli 下载 Windows 版本
# 解压后将 aliyun.exe 放到 PATH 环境变量中

# 配置阿里云 CLI
aliyun configure

# 验证配置
aliyun sts GetCallerIdentity
```

**环境变量配置**:
```bash
# 也可以通过环境变量配置认证信息
export ALICLOUD_ACCESS_KEY="your-access-key-id"
export ALICLOUD_SECRET_KEY="your-access-key-secret"
export ALICLOUD_REGION="cn-hangzhou"

# 或使用配置文件
# 配置文件位置: ~/.aliyun/config.json
```

#### Linux 系统
```bash
# 检测是否在阿里云环境
curl -s http://100.100.100.200/latest/meta-data/region-id 2>/dev/null

# 获取实例 ID
curl -s http://100.100.100.200/latest/meta-data/instance-id 2>/dev/null

# 获取内网 IP
curl -s http://100.100.100.200/latest/meta-data/private-ipv4 2>/dev/null

# 获取公网 IP
curl -s http://100.100.100.200/latest/meta-data/public-ipv4 2>/dev/null
```

#### Windows 系统
```powershell
# 检测是否在阿里云环境
try {
    $region = Invoke-RestMethod -Uri "http://100.100.100.200/latest/meta-data/region-id" -TimeoutSec 2
    Write-Host "阿里云区域: $region"
} catch {
    Write-Host "不在阿里云环境或无法访问元数据服务"
}

# 获取实例 ID
try {
    $instanceId = Invoke-RestMethod -Uri "http://100.100.100.200/latest/meta-data/instance-id" -TimeoutSec 2
    Write-Host "实例 ID: $instanceId"
} catch {}

# 获取内网 IP
try {
    $privateIp = Invoke-RestMethod -Uri "http://100.100.100.200/latest/meta-data/private-ipv4" -TimeoutSec 2
    Write-Host "内网 IP: $privateIp"
} catch {}

# 获取公网 IP
try {
    $publicIp = Invoke-RestMethod -Uri "http://100.100.100.200/latest/meta-data/public-ipv4" -TimeoutSec 2
    Write-Host "公网 IP: $publicIp"
} catch {}

# 或使用 PowerShell 获取本机 IP
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object IPAddress, InterfaceAlias
```

---

## 4. 诊断命令集

### 4.0 远程云服务诊断

#### 4.0.1 环境判断

**判断是否为远程云服务**:
```bash
# 判断 SLB ID 是否为阿里云实例
# 阿里云 SLB ID 格式: lb-xxxxxxxxxxxxxxxxxxxx
if [[ "<LOAD_BALANCER_ID>" =~ ^lb-[a-z0-9]{20,}$ ]]; then
    echo "检测到阿里云 SLB 实例，需要使用阿里云 CLI 进行诊断"
fi

# 检查本地是否有该实例
# 如果无法 ping 通或无法解析，则为远程云服务
ping -c 1 <LOAD_BALANCER_ID> 2>/dev/null
if [ $? -ne 0 ]; then
    echo "无法直接访问，判定为远程云服务"
fi
```

#### 4.0.2 使用 Python 脚本进行诊断（推荐）✅

**执行 Python 诊断脚本**:
```bash
# 1. 确认 Python 脚本存在
if [ -f "skills/network/scripts/slb_diagnosis.py" ]; then
    echo "✓ Python 诊断脚本存在"
else
    echo "错误: Python 诊断脚本不存在"
    echo "脚本位置: skills/network/scripts/slb_diagnosis.py"
    exit 1
fi

# 2. 检查 .env 文件配置
if [ -f ".env" ]; then
    echo "✓ .env 文件存在"
    # 检查必要的配置项
    if grep -q "ALICLOUD_ACCESS_KEY" .env && \
       grep -q "ALICLOUD_SECRET_KEY" .env; then
        echo "✓ 认证信息已配置"
    else
        echo "错误: .env 文件中缺少认证信息"
        echo "请配置以下环境变量:"
        echo "  ALICLOUD_ACCESS_KEY=your-access-key-id"
        echo "  ALICLOUD_SECRET_KEY=your-access-key-secret"
        echo "  ALICLOUD_REGION=cn-hangzhou"
        exit 1
    fi
else
    echo "错误: .env 文件不存在"
    echo "请创建 .env 文件并配置认证信息"
    exit 1
fi

# 3. 执行诊断脚本
echo "开始执行 SLB 诊断..."
python3 skills/network/scripts/slb_diagnosis.py <LOAD_BALANCER_ID> <REGION>

# 示例
# python3 skills/network/scripts/slb_diagnosis.py lb-bp1bxqgw0jflid09i6xnq cn-hangzhou
```

**脚本功能说明**:
- ✅ 自动读取 `.env` 文件中的认证信息
- ✅ 使用阿里云 Python SDK 查询 SLB 实例状态
- ✅ 检查后端服务器健康状态
- ✅ 评估服务能力
- ✅ 触发详细分析（监听数量 < 健康实例数）
- ✅ 检查安全组配置
- ✅ 生成根本原因分析和修复建议

**备选方案：使用 Bash 脚本（需要 CLI）**:
```bash
# 如果需要使用 Bash 脚本，需要先安装阿里云 CLI
# 安装方法见 3.2 检测云环境

# 执行 Bash 脚本
bash skills/network/scripts/slb_diagnosis.sh <LOAD_BALANCER_ID> <REGION>
```

#### 4.0.3 查询 SLB 实例状态

**查询 SLB 实例信息**:
```bash
# 查询 SLB 实例详情
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 查询 SLB 实例状态
aliyun slb DescribeLoadBalancers \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 提取关键信息
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq '{
    LoadBalancerId: .LoadBalancerId,
    LoadBalancerName: .LoadBalancerName,
    LoadBalancerStatus: .LoadBalancerStatus,
    Address: .Address,
    AddressType: .AddressType,
    VSwitchId: .VSwitchId,
    VpcId: .VpcId
  }'
```

**查询后端服务器列表**:
```bash
# 查询后端服务器
aliyun slb DescribeLoadBalancerBackends \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 提取后端服务器信息
aliyun slb DescribeLoadBalancerBackends \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq '.Backends.Backend[] | {
    ServerId: .ServerId,
    ServerIp: .ServerIp,
    Port: .Port,
    Weight: .Weight,
    Type: .Type
  }'
```

#### 4.0.4 检查健康检查状态

**查询健康检查状态**:
```bash
# 查询后端服务器健康状态
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 查询特定监听端口的健康状态
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --ListenerPort <PORT>

# 提取健康状态信息
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq '.BackendServers.BackendServer[] | {
    ServerId: .ServerId,
    ServerHealthStatus: .ServerHealthStatus,
    Port: .Port
  }'
```

**健康状态说明**:
- `normal`: 正常
- `abnormal`: 异常
- `uninitialized`: 未初始化

#### 4.0.5 检查监听配置

**查询监听配置**:
```bash
# 查询所有监听端口
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 查询特定监听端口配置
aliyun slb DescribeLoadBalancerListenerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --ListenerPort <PORT>

# 提取监听配置信息
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq '.Listeners.Listener[] | {
    ListenerPort: .ListenerPort,
    BackendServerPort: .BackendServerPort,
    Protocol: .Protocol,
    Bandwidth: .Bandwidth,
    Scheduler: .Scheduler,
    Status: .Status
  }'
```

**健康检查配置**:
```bash
# 查询健康检查配置
aliyun slb DescribeLoadBalancerListenerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --ListenerPort <PORT> | jq '{
    HealthCheck: .HealthCheck,
    HealthCheckConnectPort: .HealthCheckConnectPort,
    HealthCheckInterval: .HealthCheckInterval,
    HealthyThreshold: .HealthyThreshold,
    UnhealthyThreshold: .UnhealthyThreshold,
    HealthCheckConnectTimeout: .HealthCheckConnectTimeout,
    HealthCheckHttpCode: .HealthCheckHttpCode,
    HealthCheckUri: .HealthCheckUri
  }'
```

#### 4.0.6 检查后端服务器安全组

**查询后端服务器安全组**:
```bash
# 获取后端服务器 ID
BACKEND_SERVER_ID=$(aliyun slb DescribeLoadBalancerBackends \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq -r '.Backends.Backend[0].ServerId')

# 查询服务器详情
aliyun ecs DescribeInstanceAttribute \
  --InstanceId $BACKEND_SERVER_ID

# 查询服务器安全组
aliyun ecs DescribeInstanceAttribute \
  --InstanceId $BACKEND_SERVER_ID | jq '.SecurityGroupIds.SecurityGroupId'

# 查询安全组规则
SECURITY_GROUP_ID=$(aliyun ecs DescribeInstanceAttribute \
  --InstanceId $BACKEND_SERVER_ID | jq -r '.SecurityGroupIds.SecurityGroupId[0]')

aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId $SECURITY_GROUP_ID
```

**检查安全组规则是否允许 SLB 访问**:
```bash
# 检查是否允许 100.64.0.0/10 网段（SLB 健康检查网段）
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId $SECURITY_GROUP_ID | \
  jq '.Permissions.Permission[] | select(.SourceCidrIp == "100.64.0.0/10")'

# 检查是否允许特定端口
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId $SECURITY_GROUP_ID | \
  jq ".Permissions.Permission[] | select(.PortRange | contains(\"<PORT>\"))"
```

#### 4.0.7 远程诊断完整脚本

```bash
#!/bin/bash
# 阿里云 SLB 远程诊断脚本

LOAD_BALANCER_ID="${1:-lb-bp1bxqgw0jflid09i6xnq}"
REGION="${2:-cn-hangzhou}"

echo "=== 阿里云 SLB 远程诊断 ==="
echo "SLB ID: $LOAD_BALANCER_ID"
echo "区域: $REGION"
echo ""

# Step 1: 检查 CLI 环境
echo "=== Step 1: 检查阿里云 CLI 环境 ==="
if ! command -v aliyun &> /dev/null; then
    echo "✗ 阿里云 CLI 未安装"
    echo "请先安装阿里云 CLI: https://github.com/aliyun/aliyun-cli"
    exit 1
else
    echo "✓ 阿里云 CLI 已安装: $(aliyun version 2>&1 | head -1)"
fi

if ! aliyun sts GetCallerIdentity &> /dev/null; then
    echo "✗ 阿里云 CLI 认证失败"
    echo "请先配置认证信息: aliyun configure"
    exit 1
else
    echo "✓ 阿里云 CLI 认证成功"
    aliyun sts GetCallerIdentity | jq '{Account: .Account, UserId: .UserId}'
fi
echo ""

# Step 2: 查询 SLB 实例状态
echo "=== Step 2: 查询 SLB 实例状态 ==="
SLB_INFO=$(aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId $LOAD_BALANCER_ID --RegionId $REGION 2>&1)
if echo "$SLB_INFO" | jq -e '.LoadBalancerId' &> /dev/null; then
    echo "✓ SLB 实例存在"
    echo "$SLB_INFO" | jq '{
        LoadBalancerId: .LoadBalancerId,
        LoadBalancerName: .LoadBalancerName,
        LoadBalancerStatus: .LoadBalancerStatus,
        Address: .Address,
        AddressType: .AddressType
    }'
else
    echo "✗ SLB 实例不存在或无权访问"
    echo "$SLB_INFO"
    exit 1
fi
echo ""

# Step 3: 查询后端服务器
echo "=== Step 3: 查询后端服务器 ==="
BACKENDS=$(aliyun slb DescribeLoadBalancerBackends --LoadBalancerId $LOAD_BALANCER_ID --RegionId $REGION)
echo "$BACKENDS" | jq '.Backends.Backend[] | {
    ServerId: .ServerId,
    ServerIp: .ServerIp,
    Port: .Port,
    Weight: .Weight
}'
BACKEND_COUNT=$(echo "$BACKENDS" | jq '.Backends.Backend | length')
echo "后端服务器数量: $BACKEND_COUNT"
echo ""

# Step 4: 查询健康检查状态
echo "=== Step 4: 查询健康检查状态 ==="
HEALTH_STATUS=$(aliyun slb DescribeHealthStatus --LoadBalancerId $LOAD_BALANCER_ID --RegionId $REGION)
echo "$HEALTH_STATUS" | jq '.BackendServers.BackendServer[] | {
    ServerId: .ServerId,
    ServerHealthStatus: .ServerHealthStatus,
    Port: .Port
}'

# 统计健康状态
NORMAL_COUNT=$(echo "$HEALTH_STATUS" | jq '[.BackendServers.BackendServer[] | select(.ServerHealthStatus == "normal")] | length')
ABNORMAL_COUNT=$(echo "$HEALTH_STATUS" | jq '[.BackendServers.BackendServer[] | select(.ServerHealthStatus == "abnormal")] | length')
TOTAL_COUNT=$((NORMAL_COUNT + ABNORMAL_COUNT))
echo ""
echo "健康服务器: $NORMAL_COUNT"
echo "异常服务器: $ABNORMAL_COUNT"
echo ""

# Step 4.5: 服务能力评估
if [ $TOTAL_COUNT -gt 0 ]; then
    echo "=== Step 4.5: 服务能力评估 ==="
    SERVICE_CAPACITY=$(awk "BEGIN {printf \"%.1f\", ($NORMAL_COUNT / $TOTAL_COUNT) * 100}")
    echo "服务能力: $SERVICE_CAPACITY%"
    echo "正常服务器: $NORMAL_COUNT/$TOTAL_COUNT"
    echo "异常服务器: $ABNORMAL_COUNT/$TOTAL_COUNT"
    
    if [ $(awk "BEGIN {print ($SERVICE_CAPACITY < 100)}") -eq 1 ]; then
        echo ""
        echo "⚠ 服务能力低于 100%，以下服务器的端口出现问题："
        
        # 显示异常服务器的详细信息
        ABNORMAL_SERVERS=$(echo "$HEALTH_STATUS" | jq -r '.BackendServers.BackendServer[] | select(.ServerHealthStatus == "abnormal")')
        
        if [ -n "$ABNORMAL_SERVERS" ]; then
            echo "$ABNORMAL_SERVERS" | jq -r '"  - 服务器 ID: \(.ServerId), 端口: \(.Port), 状态: \(.ServerHealthStatus)"'
        fi
        
        echo ""
        echo "建议操作："
        echo "1. 登录异常服务器检查端口监听状态"
        echo "2. 检查服务进程是否运行"
        echo "3. 检查服务日志排查错误"
        echo "4. 检查防火墙和安全组配置"
    fi
    echo ""
fi

# Step 5: 查询监听配置
echo "=== Step 5: 查询监听配置 ==="
LISTENERS=$(aliyun slb DescribeLoadBalancerListeners --LoadBalancerId $LOAD_BALANCER_ID --RegionId $REGION)
echo "$LISTENERS" | jq '.Listeners.Listener[] | {
    ListenerPort: .ListenerPort,
    BackendServerPort: .BackendServerPort,
    Protocol: .Protocol,
    Status: .Status
}'
echo ""

# Step 5.5: 检查所有后端服务器的端口状态
echo "=== Step 5.5: 检查所有后端服务器的端口状态 ==="
ALL_SERVERS=$(echo "$HEALTH_STATUS" | jq -r '.BackendServers.BackendServer[]')

echo "$ALL_SERVERS" | jq -r '"服务器 ID: \(.ServerId), 端口: \(.Port), 健康状态: \(.ServerHealthStatus)"' | while read line; do
    echo "  $line"
done

echo ""
echo "端口状态汇总："
echo "  正常端口数: $NORMAL_COUNT"
echo "  异常端口数: $ABNORMAL_COUNT"

if [ $ABNORMAL_COUNT -gt 0 ]; then
    echo ""
    echo "⚠ 以下端口出现异常："
    echo "$ALL_SERVERS" | jq -r 'select(.ServerHealthStatus == "abnormal") | "  - 服务器 \(.ServerId) 的端口 \(.Port)"'
fi
echo ""

# Step 6: 检查异常服务器
if [ $ABNORMAL_COUNT -gt 0 ]; then
    echo "=== Step 6: 检查异常服务器 ==="
    ABNORMAL_SERVERS=$(echo "$HEALTH_STATUS" | jq -r '.BackendServers.BackendServer[] | select(.ServerHealthStatus == "abnormal") | .ServerId')
    
    for SERVER_ID in $ABNORMAL_SERVERS; do
        echo "--- 服务器: $SERVER_ID ---"
        
        # 查询服务器状态
        INSTANCE_INFO=$(aliyun ecs DescribeInstanceAttribute --InstanceId $SERVER_ID --RegionId $REGION)
        INSTANCE_STATUS=$(echo "$INSTANCE_INFO" | jq -r '.Status')
        echo "实例状态: $INSTANCE_STATUS"
        
        # 查询安全组
        SECURITY_GROUP_ID=$(echo "$INSTANCE_INFO" | jq -r '.SecurityGroupIds.SecurityGroupId[0]')
        echo "安全组 ID: $SECURITY_GROUP_ID"
        
        # 检查安全组规则
        SG_RULES=$(aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SECURITY_GROUP_ID --RegionId $REGION)
        SLB_ACCESS=$(echo "$SG_RULES" | jq '[.Permissions.Permission[] | select(.SourceCidrIp == "100.64.0.0/10")] | length')
        echo "允许 SLB 网段访问的规则数: $SLB_ACCESS"
        
        if [ $SLB_ACCESS -eq 0 ]; then
            echo "⚠ 警告: 安全组未允许 SLB 健康检查网段 (100.64.0.0/10) 访问"
        fi
        
        echo ""
    done
fi

# Step 7: 详细安全组排查和根本原因分析
if [ $ABNORMAL_COUNT -gt 0 ]; then
    echo "=== Step 7: 详细安全组排查和根本原因分析 ==="
    ABNORMAL_SERVERS=$(echo "$HEALTH_STATUS" | jq -r '.BackendServers.BackendServer[] | select(.ServerHealthStatus == "abnormal")')
    
    echo "$ABNORMAL_SERVERS" | jq -c '.' | while read server; do
        SERVER_ID=$(echo "$server" | jq -r '.ServerId')
        PORT=$(echo "$server" | jq -r '.Port')
        
        echo ""
        echo "--- 服务器: $SERVER_ID, 端口: $PORT ---"
        
        # 查询服务器详情
        INSTANCE_INFO=$(aliyun ecs DescribeInstanceAttribute --InstanceId $SERVER_ID --RegionId $REGION)
        SECURITY_GROUP_IDS=$(echo "$INSTANCE_INFO" | jq -r '.SecurityGroupIds.SecurityGroupId[]')
        
        # 遍历所有安全组
        for SG_ID in $SECURITY_GROUP_IDS; do
            echo ""
            echo "安全组: $SG_ID"
            
            # 查询安全组详情
            SG_INFO=$(aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId $SG_ID --RegionId $REGION)
            SG_NAME=$(echo "$SG_INFO" | jq -r '.SecurityGroupName')
            echo "  安全组名称: $SG_NAME"
            
            # 检查入方向规则
            echo ""
            echo "  入方向规则分析:"
            INGRESS_RULES=$(echo "$SG_INFO" | jq -r '.Permissions.Permission[] | select(.Direction == "ingress")')
            
            if [ -z "$INGRESS_RULES" ]; then
                echo "    ⚠ 警告: 没有入方向规则"
            else
                # 检查 SLB 健康检查网段规则
                SLB_RULES=$(echo "$INGRESS_RULES" | jq -c "select(.SourceCidrIp == \"100.64.0.0/10\")")
                
                if [ -z "$SLB_RULES" ]; then
                    echo "    ✗ 根本原因: 安全组未允许 SLB 健康检查网段 (100.64.0.0/10) 访问"
                    echo "    影响: SLB 无法进行健康检查，导致服务器被标记为异常"
                    echo ""
                    echo "    修复命令:"
                    echo "      aliyun ecs AuthorizeSecurityGroup \\"
                    echo "        --SecurityGroupId $SG_ID \\"
                    echo "        --IpProtocol tcp \\"
                    echo "        --PortRange $PORT/$PORT \\"
                    echo "        --SourceCidrIp 100.64.0.0/10 \\"
                    echo "        --Description \"Allow SLB health check\""
                else
                    # 检查端口是否匹配
                    PORT_MATCHED=$(echo "$SLB_RULES" | jq -c "select(.PortRange == \"$PORT/$PORT\" or .PortRange == \"-1/-1\")")
                    
                    if [ -z "$PORT_MATCHED" ]; then
                        echo "    ✗ 根本原因: 安全组允许 SLB 网段访问，但端口不匹配"
                        echo "    当前允许的端口:"
                        echo "$SLB_RULES" | jq -r '"      - " + .PortRange'
                        echo "    需要开放的端口: $PORT"
                        echo ""
                        echo "    修复命令:"
                        echo "      aliyun ecs AuthorizeSecurityGroup \\"
                        echo "        --SecurityGroupId $SG_ID \\"
                        echo "        --IpProtocol tcp \\"
                        echo "        --PortRange $PORT/$PORT \\"
                        echo "        --SourceCidrIp 100.64.0.0/10 \\"
                        echo "        --Description \"Allow SLB health check for port $PORT\""
                    else
                        # 检查协议类型
                        PROTOCOL=$(echo "$PORT_MATCHED" | jq -r '.IpProtocol')
                        if [ "$PROTOCOL" != "TCP" ] && [ "$PROTOCOL" != "ALL" ]; then
                            echo "    ✗ 根本原因: 协议类型不匹配"
                            echo "    当前协议: $PROTOCOL"
                            echo "    需要协议: TCP"
                            echo ""
                            echo "    修复命令:"
                            echo "      aliyun ecs AuthorizeSecurityGroup \\"
                            echo "        --SecurityGroupId $SG_ID \\"
                            echo "        --IpProtocol tcp \\"
                            echo "        --PortRange $PORT/$PORT \\"
                            echo "        --SourceCidrIp 100.64.0.0/10 \\"
                            echo "        --Description \"Allow SLB health check via TCP\""
                        else
                            # 检查授权策略
                            POLICY=$(echo "$PORT_MATCHED" | jq -r '.Policy')
                            if [ "$POLICY" != "Accept" ]; then
                                echo "    ✗ 根本原因: 授权策略为拒绝"
                                echo "    当前策略: $POLICY"
                                echo "    需要策略: Accept"
                                echo ""
                                echo "    修复命令:"
                                echo "      aliyun ecs AuthorizeSecurityGroup \\"
                                echo "        --SecurityGroupId $SG_ID \\"
                                echo "        --IpProtocol tcp \\"
                                echo "        --PortRange $PORT/$PORT \\"
                                echo "        --SourceCidrIp 100.64.0.0/10 \\"
                                echo "        --Policy Accept \\"
                                echo "        --Description \"Allow SLB health check\""
                            else
                                echo "    ✓ 安全组规则正常"
                                echo "    允许 SLB 网段 (100.64.0.0/10) 访问端口 $PORT"
                            fi
                        fi
                    fi
                fi
                
                # 检查是否有拒绝规则
                DENY_RULES=$(echo "$INGRESS_RULES" | jq -c "select(.Policy == \"Drop\" or .Policy == \"Reject\")")
                if [ -n "$DENY_RULES" ]; then
                    echo ""
                    echo "    ⚠ 警告: 发现拒绝规则，可能影响访问"
                    echo "$DENY_RULES" | jq -r '"      - 源: " + .SourceCidrIp + ", 端口: " + .PortRange + ", 策略: " + .Policy'
                fi
            fi
        done
    done
fi

echo "=== 诊断完成 ==="
```

**使用方法**:
```bash
# 保存脚本为 slb_remote_diagnosis.sh
chmod +x slb_remote_diagnosis.sh

# 执行诊断
./slb_remote_diagnosis.sh lb-bp1bxqgw0jflid09i6xnq cn-hangzhou
```

### 4.1 后端服务器状态检查

#### 检查服务器是否运行

**Linux 系统**:
```bash
# 检查服务器在线状态
ping -c 4 <SERVER_IP>

# 检查服务器负载
uptime

# 检查内存
free -h

# 检查磁盘
df -h
```

**Windows 系统**:
```powershell
# 检查服务器在线状态
ping -n 4 <SERVER_IP>

# 检查系统信息
systeminfo | findstr /C:"Available Physical Memory" /C:"Virtual Memory"

# 检查 CPU 使用率
Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 2 -MaxSamples 3

# 检查内存使用
Get-CimInstance Win32_OperatingSystem | Select-Object @{Name="TotalMemory(GB)";Expression={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}}, @{Name="FreeMemory(GB)";Expression={[math]::Round($_.FreePhysicalMemory/1MB,2)}}

# 检查磁盘使用
Get-Volume | Where-Object {$_.DriveLetter} | Select-Object DriveLetter, FileSystemLabel, @{Name="Size(GB)";Expression={[math]::Round($_.Size/1GB,2)}}, @{Name="Free(GB)";Expression={[math]::Round($_.SizeRemaining/1GB,2)}}
```

#### 检查服务状态

**Linux 系统**:
```bash
# 检查 systemd 服务状态
systemctl status nginx
systemctl status httpd
systemctl status docker

# 检查所有监听端口的服务
systemctl list-units --type=service --state=running

# 检查 Docker 容器状态
docker ps -a | grep <PORT>
```

**Windows 系统**:
```powershell
# 检查服务状态
Get-Service -Name "nginx" | Select-Object Name, Status, StartType
Get-Service -Name "Apache*" | Select-Object Name, Status, StartType
Get-Service -Name "World Wide Web Publishing Service" | Select-Object Name, Status, StartType

# 检查所有运行中的服务
Get-Service | Where-Object {$_.Status -eq "Running"} | Select-Object Name, DisplayName, Status

# 检查 IIS 站点状态
Get-Website | Select-Object Name, State, ID, PhysicalPath

# 检查特定端口的服务
Get-NetTCPConnection -LocalPort <PORT> -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, State, OwningProcess
```

### 4.2 端口监听状态检查

#### 检查端口是否监听

**Linux 系统**:
```bash
# 使用 netstat (Linux)
netstat -tuln | grep <PORT>

# 使用 ss (推荐)
ss -tuln | grep <PORT>

# 使用 lsof (macOS/Linux)
lsof -i :<PORT>

# 查看所有监听端口
ss -tuln
netstat -tuln

# 查看特定端口的详细信息
ss -tulnp | grep <PORT>
lsof -i :<PORT> -P
```

**Windows 系统**:
```powershell
# 使用 netstat
netstat -ano | findstr :<PORT>

# 使用 PowerShell (推荐)
Get-NetTCPConnection -LocalPort <PORT> -ErrorAction SilentlyContinue

# 查看所有监听端口
netstat -ano | findstr LISTENING

# 使用 PowerShell 查看所有监听端口
Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, State, OwningProcess

# 查看特定端口的详细信息
Get-NetTCPConnection -LocalPort <PORT> | Select-Object LocalAddress, LocalPort, State, OwningProcess
```

#### 检查监听地址

**Linux 系统**:
```bash
# 检查监听地址 (重要!)
# 0.0.0.0:80    → 监听所有网卡，外部可访问 ✓
# 127.0.0.1:80  → 只监听本地，外部无法访问 ✗
# :::80         → IPv6 监听所有网卡 ✓

ss -tuln | grep <PORT>
netstat -tuln | grep <PORT>

# 查看进程监听详情
lsof -i :<PORT> -P -n
```

**Windows 系统**:
```powershell
# 检查监听地址 (重要!)
# 0.0.0.0:80    → 监听所有网卡，外部可访问 ✓
# 127.0.0.1:80  → 只监听本地，外部无法访问 ✗
# [::]:80       → IPv6 监听所有网卡 ✓

# 使用 netstat
netstat -ano | findstr :<PORT>

# 使用 PowerShell (更详细)
Get-NetTCPConnection -LocalPort <PORT> | Select-Object LocalAddress, LocalPort, State, OwningProcess

# 检查是否监听所有网卡
Get-NetTCPConnection -LocalPort <PORT> | Where-Object {$_.LocalAddress -eq "0.0.0.0" -or $_.LocalAddress -eq "::"}
```

#### 检查进程状态

**Linux 系统**:
```bash
# 查看占用端口的进程
lsof -i :<PORT>
netstat -tulnp | grep <PORT>
ss -tulnp | grep <PORT>

# 查看进程详细信息
ps aux | grep <PROCESS_NAME>
ps -ef | grep <PROCESS_NAME>

# 查看进程打开的文件
lsof -p <PID>
```

**Windows 系统**:
```powershell
# 查看占用端口的进程
Get-NetTCPConnection -LocalPort <PORT> | Select-Object OwningProcess

# 根据 PID 查看进程详细信息
Get-Process -Id <PID> | Select-Object Id, ProcessName, Path

# 查看进程详细信息
Get-Process | Where-Object {$_.ProcessName -like "*<PROCESS_NAME>*"} | Select-Object Id, ProcessName, Path

# 查看进程打开的文件和连接
Get-Process -Id <PID> | Select-Object -ExpandProperty Modules

# 查看特定端口对应的进程名
$connections = Get-NetTCPConnection -LocalPort <PORT>
foreach ($conn in $connections) {
    $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    Write-Host "PID: $($conn.OwningProcess), Process: $($process.ProcessName), Path: $($process.Path)"
}
```

### 4.3 本地连接测试

#### 本地回环测试

**Linux 系统**:
```bash
# 测试本地回环
curl -v http://127.0.0.1:<PORT>/
curl -v http://localhost:<PORT>/

# 测试本地回环 (TCP)
nc -zv 127.0.0.1 <PORT>
telnet 127.0.0.1 <PORT>

# 测试本地回环 (HTTP)
curl -I http://127.0.0.1:<PORT>/
wget --spider http://127.0.0.1:<PORT>/
```

**Windows 系统**:
```powershell
# 测试本地回环 (PowerShell)
Invoke-WebRequest -Uri "http://127.0.0.1:<PORT>/" -UseBasicParsing | Select-Object StatusCode, StatusDescription

# 测试本地回环 (curl - Windows 10+)
curl http://127.0.0.1:<PORT>/

# 测试本地回环 (TCP - PowerShell)
Test-NetConnection -ComputerName 127.0.0.1 -Port <PORT>

# 测试本地回环 (TCP - telnet)
telnet 127.0.0.1 <PORT>

# 测试本地回环 (HTTP - PowerShell)
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:<PORT>/" -TimeoutSec 5 -UseBasicParsing
    Write-Host "连接成功: Status Code $($response.StatusCode)"
} catch {
    Write-Host "连接失败: $($_.Exception.Message)"
}
```

#### 内网 IP 测试

**Linux 系统**:
```bash
# 获取内网 IP
PRIVATE_IP=$(curl -s http://100.100.100.200/latest/meta-data/private-ipv4 2>/dev/null || hostname -I | awk '{print $1}')

# 测试内网 IP
curl -v http://$PRIVATE_IP:<PORT>/
nc -zv $PRIVATE_IP <PORT>
telnet $PRIVATE_IP <PORT>

# 测试内网 IP (HTTP)
curl -I http://$PRIVATE_IP:<PORT>/
```

**Windows 系统**:
```powershell
# 获取内网 IP
try {
    $PRIVATE_IP = Invoke-RestMethod -Uri "http://100.100.100.200/latest/meta-data/private-ipv4" -TimeoutSec 2
} catch {
    $PRIVATE_IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).IPAddress
}

Write-Host "内网 IP: $PRIVATE_IP"

# 测试内网 IP (PowerShell)
Test-NetConnection -ComputerName $PRIVATE_IP -Port <PORT>

# 测试内网 IP (HTTP)
try {
    $response = Invoke-WebRequest -Uri "http://$PRIVATE_IP:<PORT>/" -TimeoutSec 5 -UseBasicParsing
    Write-Host "连接成功: Status Code $($response.StatusCode)"
} catch {
    Write-Host "连接失败: $($_.Exception.Message)"
}

# 测试内网 IP (curl)
curl http://$PRIVATE_IP:<PORT>/
```

#### 从其他服务器测试

**Linux 系统**:
```bash
# 从跳板机或其他服务器测试
curl -v http://<SERVER_IP>:<PORT>/
nc -zv <SERVER_IP> <PORT>
telnet <SERVER_IP> <PORT>

# 测试 HTTP 响应
curl -I http://<SERVER_IP>:<PORT>/
curl -v --connect-timeout 5 http://<SERVER_IP>:<PORT>/
```

**Windows 系统**:
```powershell
# 从跳板机或其他服务器测试 (PowerShell)
Test-NetConnection -ComputerName <SERVER_IP> -Port <PORT>

# 测试 HTTP 响应
try {
    $response = Invoke-WebRequest -Uri "http://<SERVER_IP>:<PORT>/" -TimeoutSec 5 -UseBasicParsing
    Write-Host "连接成功: Status Code $($response.StatusCode)"
} catch {
    Write-Host "连接失败: $($_.Exception.Message)"
}

# 使用 curl (Windows 10+)
curl -I http://<SERVER_IP>:<PORT>/
curl http://<SERVER_IP>:<PORT>/

# 使用 telnet
telnet <SERVER_IP> <PORT>
```

### 4.4 防火墙检查

#### iptables 检查 (CentOS 6/7)
```bash
# 查看所有规则
iptables -L -n -v

# 查看 INPUT 链规则
iptables -L INPUT -n -v --line-numbers

# 查看特定端口规则
iptables -L -n -v | grep <PORT>

# 查看 NAT 规则
iptables -t nat -L -n -v

# 检查规则是否允许端口
iptables -L INPUT -n -v | grep -E "dpt:<PORT>|ACCEPT|DROP"
```

#### firewalld 检查 (CentOS 7+)
```bash
# 查看防火墙状态
firewall-cmd --state

# 查看所有规则
firewall-cmd --list-all

# 查看开放的端口
firewall-cmd --list-ports

# 查看开放的服务
firewall-cmd --list-services

# 检查特定端口是否开放
firewall-cmd --query-port=<PORT>/tcp

# 查看富规则
firewall-cmd --list-rich-rules
```

#### ufw 检查 (Ubuntu)
```bash
# 查看防火墙状态
ufw status verbose

# 查看规则编号
ufw status numbered

# 检查特定端口
ufw status | grep <PORT>
```

#### Windows 防火墙检查

**查看防火墙状态**:
```powershell
# 查看所有配置文件的防火墙状态
netsh advfirewall show allprofiles state

# 查看域配置文件状态
netsh advfirewall show domainprofile state

# 查看专用配置文件状态
netsh advfirewall show privateprofile state

# 查看公用配置文件状态
netsh advfirewall show publicprofile state

# 使用 PowerShell 查看防火墙状态
Get-NetFirewallProfile | Select-Object Name, Enabled
```

**查看防火墙规则**:
```powershell
# 查看所有入站规则
netsh advfirewall firewall show rule name=all dir=in

# 查看所有出站规则
netsh advfirewall firewall show rule name=all dir=out

# 查看特定端口的规则
netsh advfirewall firewall show rule name=all | findstr <PORT>

# 使用 PowerShell 查看所有规则
Get-NetFirewallRule | Select-Object DisplayName, Enabled, Direction, Action

# 查看特定端口的规则 (PowerShell)
Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true} | Get-NetFirewallPortFilter | Where-Object {$_.LocalPort -eq <PORT>}

# 查看允许的入站规则
Get-NetFirewallRule -Direction Inbound -Enabled True -Action Allow | Select-Object DisplayName, Profile
```

**检查特定端口是否开放**:
```powershell
# 检查端口是否在防火墙规则中
$portRules = Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true -and $_.Direction -eq "Inbound"} | Get-NetFirewallPortFilter | Where-Object {$_.LocalPort -eq <PORT>}

if ($portRules) {
    Write-Host "端口 <PORT> 已在防火墙规则中"
    $portRules | Select-Object LocalPort, Protocol
} else {
    Write-Host "端口 <PORT> 未在防火墙规则中"
}

# 检查特定端口规则详情
Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true} | Get-NetFirewallPortFilter | Where-Object {$_.LocalPort -eq <PORT>} | Get-NetFirewallRule | Select-Object DisplayName, Profile, Action
```

**Windows 防火墙日志检查**:
```powershell
# 查看防火墙日志位置
netsh advfirewall show currentprofile logging

# 查看防火墙日志 (默认位置)
Get-Content "$env:SystemRoot\System32\LogFiles\Firewall\pfirewall.log" -Tail 50

# 查看特定 IP 的日志
Get-Content "$env:SystemRoot\System32\LogFiles\Firewall\pfirewall.log" | Select-String "<IP_ADDRESS>"
```

### 4.5 阿里云安全组检查

#### 使用阿里云 CLI 检查
```bash
# 安装阿里云 CLI
# pip install aliyun-python-sdk-core aliyun-python-sdk-ecs

# 查看安全组规则
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId <SECURITY_GROUP_ID> \
  --RegionId <REGION_ID>

# 查看实例的安全组
aliyun ecs DescribeInstanceAttribute \
  --InstanceId <INSTANCE_ID> \
  --RegionId <REGION_ID>

# 查询安全组列表
aliyun ecs DescribeSecurityGroups \
  --RegionId <REGION_ID>
```

#### 安全组规则检查要点
```markdown
检查项:
1. 入方向规则是否允许负载均衡的内网 IP 段访问
2. 端口范围是否正确
3. 授权对象是否包含:
   - 负载均衡的内网 IP
   - 负载均衡所在网段 (如 100.64.0.0/10)
   - 0.0.0.0/0 (不推荐，仅测试用)
4. 协议类型是否正确 (TCP/UDP)
5. 优先级是否合适
```

### 4.6 负载均衡配置检查

#### 使用阿里云 CLI 检查负载均衡
```bash
# 查看负载均衡实例
aliyun slb DescribeLoadBalancers \
  --RegionId <REGION_ID>

# 查看负载均衡详情
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 查看监听配置
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 查看后端服务器
aliyun slb DescribeLoadBalancerBackends \
  --LoadBalancerId <LOAD_BALANCER_ID>

# 查看健康检查状态
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID>
```

#### 健康检查配置检查
```bash
# 查看健康检查配置
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --ListenerPort <PORT>

# 健康检查关键参数
# - HealthCheck: on/off
# - HealthCheckConnectPort: 健康检查端口
# - HealthCheckInterval: 检查间隔 (秒)
# - HealthyThreshold: 健康阈值
# - UnhealthyThreshold: 不健康阈值
# - HealthCheckConnectTimeout: 超时时间 (秒)
# - HealthCheckHttpCode: HTTP 状态码
# - HealthCheckUri: 健康检查 URI
```

### 4.7 网络连通性检查

#### 从负载均衡角度测试
```bash
# 获取负载均衡内网 IP
# 在阿里云控制台或使用 CLI 查询

# 从后端服务器测试负载均衡
ping -c 4 <LOAD_BALANCER_PRIVATE_IP>

# 测试负载均衡端口
nc -zv <LOAD_BALANCER_PRIVATE_IP> <LB_PORT>

# 测试负载均衡 HTTP
curl -I http://<LOAD_BALANCER_PRIVATE_IP>:<LB_PORT>/
```

#### 网络路由检查
```bash
# 查看路由表
ip route show
route -n

# 追踪路由
traceroute <LOAD_BALANCER_IP>
tracepath <LOAD_BALANCER_IP>

# 查看网络接口
ip addr show
ifconfig -a

# 查看 ARP 表
arp -a
ip neigh show
```

### 4.8 日志检查

#### 系统日志
```bash
# 查看系统日志
journalctl -u nginx -f
journalctl -u httpd -f
journalctl -u docker -f

# 查看系统消息日志
tail -f /var/log/messages
tail -f /var/log/syslog

# 查看防火墙日志
journalctl -u firewalld -f
tail -f /var/log/firewalld
```

#### 应用日志
```bash
# Nginx 日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Apache 日志
tail -f /var/log/httpd/access_log
tail -f /var/log/httpd/error_log

# 应用自定义日志
tail -f /path/to/app.log
```

---

## 5. 常见问题与解决方案

### 5.1 服务未启动

**现象**: 端口未监听，连接被拒绝

**诊断步骤**:
```bash
# 1. 检查端口监听
ss -tuln | grep <PORT>

# 2. 检查服务状态
systemctl status <SERVICE_NAME>

# 3. 检查进程
ps aux | grep <PROCESS_NAME>
```

**解决方案**:
```bash
# 启动服务
systemctl start <SERVICE_NAME>

# 设置开机自启
systemctl enable <SERVICE_NAME>

# 检查服务日志
journalctl -u <SERVICE_NAME> -n 50
```

### 5.2 监听地址错误

**现象**: 本地可访问，外部无法访问

**诊断步骤**:
```bash
# 检查监听地址
ss -tuln | grep <PORT>

# 如果显示 127.0.0.1:PORT，则只监听本地
# 应该显示 0.0.0.0:PORT 或 :::PORT
```

**解决方案**:
```nginx
# Nginx 配置修改
server {
    listen 80;          # 监听所有网卡 ✓
    # listen 127.0.0.1:80;  # 只监听本地 ✗
}
```

```python
# Python Flask 配置修改
app.run(host='0.0.0.0', port=5000)  # 监听所有网卡 ✓
# app.run(host='127.0.0.1', port=5000)  # 只监听本地 ✗
```

```bash
# 重启服务
systemctl restart nginx
systemctl restart httpd
```

### 5.3 防火墙阻断

**现象**: 本地可访问，外部连接超时

**诊断步骤**:
```bash
# 1. 检查防火墙状态
firewall-cmd --state
ufw status

# 2. 检查端口规则
firewall-cmd --list-ports | grep <PORT>
iptables -L -n -v | grep <PORT>

# 3. 临时关闭防火墙测试
systemctl stop firewalld  # 仅测试用
```

**解决方案**:
```bash
# firewalld 开放端口
firewall-cmd --permanent --add-port=<PORT>/tcp
firewall-cmd --reload

# iptables 开放端口
iptables -I INPUT -p tcp --dport <PORT> -j ACCEPT
service iptables save

# ufw 开放端口
ufw allow <PORT>/tcp
```

**Windows 解决方案**:
```powershell
# 使用 PowerShell 开放端口
New-NetFirewallRule -DisplayName "Allow Port <PORT>" -Direction Inbound -LocalPort <PORT> -Protocol TCP -Action Allow

# 使用 netsh 开放端口
netsh advfirewall firewall add rule name="Allow Port <PORT>" dir=in action=allow protocol=tcp localport=<PORT>

# 开放端口给特定 IP (负载均衡网段)
New-NetFirewallRule -DisplayName "Allow SLB Port <PORT>" -Direction Inbound -LocalPort <PORT> -Protocol TCP -Action Allow -RemoteAddress 100.64.0.0/10
```

### 5.4 安全组规则缺失

**现象**: 本地和防火墙都正常，但负载均衡健康检查失败

**诊断步骤**:
```bash
# 1. 获取实例安全组 ID
aliyun ecs DescribeInstanceAttribute \
  --InstanceId <INSTANCE_ID> \
  --RegionId <REGION_ID> | grep SecurityGroupId

# 2. 查看安全组规则
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId <SECURITY_GROUP_ID> \
  --RegionId <REGION_ID>
```

**解决方案**:
```bash
# 添加安全组规则 (允许负载均衡访问)
aliyun ecs AuthorizeSecurityGroup \
  --SecurityGroupId <SECURITY_GROUP_ID> \
  --RegionId <REGION_ID> \
  --IpProtocol tcp \
  --PortRange <PORT>/<PORT> \
  --SourceCidrIp 100.64.0.0/10 \
  --Description "Allow SLB access"

# 或允许特定负载均衡 IP
aliyun ecs AuthorizeSecurityGroup \
  --SecurityGroupId <SECURITY_GROUP_ID> \
  --RegionId <REGION_ID> \
  --IpProtocol tcp \
  --PortRange <PORT>/<PORT> \
  --SourceCidrIp <LOAD_BALANCER_PRIVATE_IP>/32 \
  --Description "Allow specific SLB access"
```

**重要提示**:
- 负载均衡健康检查通常来自 `100.64.0.0/10` 网段
- 需要允许该网段访问健康检查端口
- 健康检查端口可能与业务端口不同

### 5.5 端口监听数量不匹配

**现象**: 正常监听到的后端服务端口数量小于后端服务器数量，服务能力下降

**诊断步骤**:

#### 1. 检查后端服务器健康状态

```bash
# 查询所有后端服务器的健康状态
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --RegionId <REGION_ID>

# 统计健康和异常服务器数量
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq '{
    TotalServers: (.BackendServers.BackendServer | length),
    NormalServers: [.BackendServers.BackendServer[] | select(.ServerHealthStatus == "normal")] | length,
    AbnormalServers: [.BackendServers.BackendServer[] | select(.ServerHealthStatus != "normal")] | length
  }'
```

#### 2. 识别异常服务器

```bash
# 列出所有异常服务器
aliyun slb DescribeHealthStatus \
  --LoadBalancerId <LOAD_BALANCER_ID> | jq '.BackendServers.BackendServer[] | select(.ServerHealthStatus != "normal") | {
    ServerId: .ServerId,
    Port: .Port,
    Status: .ServerHealthStatus
  }'
```

#### 3. 检查异常服务器的端口监听状态

**Linux 系统**:
```bash
# 登录异常服务器，检查端口监听
ssh <ABNORMAL_SERVER_IP>

# 检查端口是否监听
ss -tuln | grep <PORT>
netstat -tuln | grep <PORT>

# 检查监听地址
# 0.0.0.0:80    → 监听所有网卡，外部可访问 ✓
# 127.0.0.1:80  → 只监听本地，外部无法访问 ✗
ss -tuln | grep <PORT>

# 检查进程状态
lsof -i :<PORT>
ps aux | grep <PROCESS_NAME>
```

**Windows 系统**:
```powershell
# 登录异常服务器，检查端口监听
Enter-PSSession -ComputerName <ABNORMAL_SERVER_IP>

# 检查端口是否监听
Get-NetTCPConnection -LocalPort <PORT> -ErrorAction SilentlyContinue

# 检查监听地址
# 0.0.0.0:80    → 监听所有网卡，外部可访问 ✓
# 127.0.0.1:80  → 只监听本地，外部无法访问 ✗
Get-NetTCPConnection -LocalPort <PORT> | Select-Object LocalAddress, LocalPort, State, OwningProcess

# 检查进程状态
Get-NetTCPConnection -LocalPort <PORT> | Select-Object OwningProcess
Get-Process -Id <PID> | Select-Object Id, ProcessName, Path
```

#### 4. 检查异常服务器的安全组配置

**如果端口监听正常，需要检查安全组配置**:

```bash
# 查询异常服务器的安全组 ID
aliyun ecs DescribeInstanceAttribute \
  --InstanceId <ABNORMAL_INSTANCE_ID> \
  --RegionId <REGION_ID> | jq '.SecurityGroupIds.SecurityGroupId[]'

# 查询安全组详情
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId <SECURITY_GROUP_ID> \
  --RegionId <REGION_ID>

# 检查入方向规则是否允许 SLB 健康检查网段访问
aliyun ecs DescribeSecurityGroupAttribute \
  --SecurityGroupId <SECURITY_GROUP_ID> \
  --RegionId <REGION_ID> | jq '.Permissions.Permission[] | select(.Direction == "ingress") | {
    PortRange: .PortRange,
    SourceCidrIp: .SourceCidrIp,
    IpProtocol: .IpProtocol,
    Policy: .Policy
  }'
```

**关键检查点**:
1. **SLB 健康检查网段**: 安全组是否允许 `100.64.0.0/10` 网段访问
2. **端口匹配**: 安全组规则中的端口范围是否包含健康检查端口
3. **协议类型**: 协议类型是否为 TCP 或 ALL
4. **授权策略**: 策略是否为 Accept（允许）

**详细安全组排查脚本**:
```bash
#!/bin/bash
# 详细安全组排查脚本

LOAD_BALANCER_ID="<LOAD_BALANCER_ID>"
REGION="<REGION_ID>"

# 获取异常服务器列表
ABNORMAL_SERVERS=$(aliyun slb DescribeHealthStatus \
  --LoadBalancerId $LOAD_BALANCER_ID \
  --RegionId $REGION | jq -r '.BackendServers.BackendServer[] | select(.ServerHealthStatus != "normal")')

echo "$ABNORMAL_SERVERS" | jq -c '.' | while read server; do
    SERVER_ID=$(echo "$server" | jq -r '.ServerId')
    PORT=$(echo "$server" | jq -r '.Port')
    
    echo ""
    echo "=== 检查服务器: $SERVER_ID, 端口: $PORT ==="
    
    # 查询服务器详情
    INSTANCE_INFO=$(aliyun ecs DescribeInstanceAttribute \
      --InstanceId $SERVER_ID \
      --RegionId $REGION)
    
    SECURITY_GROUP_IDS=$(echo "$INSTANCE_INFO" | jq -r '.SecurityGroupIds.SecurityGroupId[]')
    
    # 遍历所有安全组
    for SG_ID in $SECURITY_GROUP_IDS; do
        echo ""
        echo "安全组: $SG_ID"
        
        # 查询安全组详情
        SG_INFO=$(aliyun ecs DescribeSecurityGroupAttribute \
          --SecurityGroupId $SG_ID \
          --RegionId $REGION)
        
        SG_NAME=$(echo "$SG_INFO" | jq -r '.SecurityGroupName')
        echo "  安全组名称: $SG_NAME"
        
        # 检查入方向规则
        echo ""
        echo "  入方向规则分析:"
        INGRESS_RULES=$(echo "$SG_INFO" | jq -r '.Permissions.Permission[] | select(.Direction == "ingress")')
        
        if [ -z "$INGRESS_RULES" ]; then
            echo "    ⚠ 警告: 没有入方向规则"
        else
            # 检查 SLB 健康检查网段规则
            SLB_RULES=$(echo "$INGRESS_RULES" | jq -c "select(.SourceCidrIp == \"100.64.0.0/10\")")
            
            if [ -z "$SLB_RULES" ]; then
                echo "    ✗ 根本原因: 安全组未允许 SLB 健康检查网段 (100.64.0.0/10) 访问"
                echo "    影响: SLB 无法进行健康检查，导致服务器被标记为异常"
                echo ""
                echo "    修复命令:"
                echo "      aliyun ecs AuthorizeSecurityGroup \\"
                echo "        --SecurityGroupId $SG_ID \\"
                echo "        --IpProtocol tcp \\"
                echo "        --PortRange $PORT/$PORT \\"
                echo "        --SourceCidrIp 100.64.0.0/10 \\"
                echo "        --Description \"Allow SLB health check\""
            else
                # 检查端口是否匹配
                PORT_MATCHED=$(echo "$SLB_RULES" | jq -c "select(.PortRange == \"$PORT/$PORT\" or .PortRange == \"-1/-1\")")
                
                if [ -z "$PORT_MATCHED" ]; then
                    echo "    ✗ 根本原因: 安全组允许 SLB 网段访问，但端口不匹配"
                    echo "    当前允许的端口:"
                    echo "$SLB_RULES" | jq -r '"      - " + .PortRange'
                    echo "    需要开放的端口: $PORT"
                    echo ""
                    echo "    修复命令:"
                    echo "      aliyun ecs AuthorizeSecurityGroup \\"
                    echo "        --SecurityGroupId $SG_ID \\"
                    echo "        --IpProtocol tcp \\"
                    echo "        --PortRange $PORT/$PORT \\"
                    echo "        --SourceCidrIp 100.64.0.0/10 \\"
                    echo "        --Description \"Allow SLB health check for port $PORT\""
                else
                    # 检查协议类型
                    PROTOCOL=$(echo "$PORT_MATCHED" | jq -r '.IpProtocol')
                    if [ "$PROTOCOL" != "TCP" ] && [ "$PROTOCOL" != "ALL" ]; then
                        echo "    ✗ 根本原因: 协议类型不匹配"
                        echo "    当前协议: $PROTOCOL"
                        echo "    需要协议: TCP"
                        echo ""
                        echo "    修复命令:"
                        echo "      aliyun ecs AuthorizeSecurityGroup \\"
                        echo "        --SecurityGroupId $SG_ID \\"
                        echo "        --IpProtocol tcp \\"
                        echo "        --PortRange $PORT/$PORT \\"
                        echo "        --SourceCidrIp 100.64.0.0/10 \\"
                        echo "        --Description \"Allow SLB health check via TCP\""
                    else
                        # 检查授权策略
                        POLICY=$(echo "$PORT_MATCHED" | jq -r '.Policy')
                        if [ "$POLICY" != "Accept" ]; then
                            echo "    ✗ 根本原因: 授权策略为拒绝"
                            echo "    当前策略: $POLICY"
                            echo "    需要策略: Accept"
                            echo ""
                            echo "    修复命令:"
                            echo "      aliyun ecs AuthorizeSecurityGroup \\"
                            echo "        --SecurityGroupId $SG_ID \\"
                            echo "        --IpProtocol tcp \\"
                            echo "        --PortRange $PORT/$PORT \\"
                            echo "        --SourceCidrIp 100.64.0.0/10 \\"
                            echo "        --Policy Accept \\"
                            echo "        --Description \"Allow SLB health check\""
                        else
                            echo "    ✓ 安全组规则正常"
                            echo "    允许 SLB 网段 (100.64.0.0/10) 访问端口 $PORT"
                        fi
                    fi
                fi
            fi
            
            # 检查是否有拒绝规则
            DENY_RULES=$(echo "$INGRESS_RULES" | jq -c "select(.Policy == \"Drop\" or .Policy == \"Reject\")")
            if [ -n "$DENY_RULES" ]; then
                echo ""
                echo "    ⚠ 警告: 发现拒绝规则，可能影响访问"
                echo "$DENY_RULES" | jq -r '"      - 源: " + .SourceCidrIp + ", 端口: " + .PortRange + ", 策略: " + .Policy'
            fi
        fi
    done
done
```

**解决方案**:

根据排查结果，采取相应的修复措施：

1. **端口未监听**:
   ```bash
   # 启动服务
   systemctl start <SERVICE_NAME>
   
   # 检查服务状态
   systemctl status <SERVICE_NAME>
   ```

2. **监听地址错误**:
   ```bash
   # 修改服务配置，监听所有网卡
   # 例如 Nginx:
   # listen 80;  # 而不是 listen 127.0.0.1:80;
   
   # 重启服务
   systemctl restart <SERVICE_NAME>
   ```

3. **安全组规则缺失**:
   ```bash
   # 添加安全组规则，允许 SLB 健康检查网段访问
   aliyun ecs AuthorizeSecurityGroup \
     --SecurityGroupId <SECURITY_GROUP_ID> \
     --RegionId <REGION_ID> \
     --IpProtocol tcp \
     --PortRange <PORT>/<PORT> \
     --SourceCidrIp 100.64.0.0/10 \
     --Description "Allow SLB health check"
   ```

4. **安全组端口不匹配**:
   ```bash
   # 添加特定端口的规则
   aliyun ecs AuthorizeSecurityGroup \
     --SecurityGroupId <SECURITY_GROUP_ID> \
     --RegionId <REGION_ID> \
     --IpProtocol tcp \
     --PortRange <PORT>/<PORT> \
     --SourceCidrIp 100.64.0.0/10 \
     --Description "Allow SLB health check for port <PORT>"
   ```

**服务能力评估**:

当发现端口监听数量不匹配时，需要评估服务能力：

```bash
# 计算服务能力
TOTAL_SERVERS=<总服务器数>
NORMAL_SERVERS=<正常服务器数>
SERVICE_CAPACITY=$((NORMAL_SERVERS * 100 / TOTAL_SERVERS))

echo "服务能力: $SERVICE_CAPACITY%"
echo "正常服务器: $NORMAL_SERVERS/$TOTAL_SERVERS"

if [ $SERVICE_CAPACITY -lt 50 ]; then
    echo "⚠ 严重警告: 服务能力严重不足，请立即处理"
elif [ $SERVICE_CAPACITY -lt 80 ]; then
    echo "⚠ 警告: 服务能力下降，建议尽快处理"
else
    echo "ℹ 提示: 服务能力轻微下降，建议及时处理"
fi
```

**排查流程图**:

```
┌─────────────────────────────────────────────────────────────┐
│  检测到端口监听数量 < 后端服务器数量                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 识别异常服务器                                     │
│  - 查询健康状态                                             │
│  - 列出异常服务器 ID 和端口                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 检查异常服务器端口监听状态                         │
│  - 登录异常服务器                                           │
│  - 检查端口是否监听                                         │
│  - 检查监听地址是否正确                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
            ┌─────────────────┴─────────────────┐
            │                                   │
    ┌───────▼────────┐                ┌────────▼────────┐
    │  端口未监听     │                │  端口正常监听   │
    └───────┬────────┘                └────────┬────────┘
            │                                   │
            ↓                                   ↓
    ┌───────────────────┐            ┌─────────────────────┐
    │  检查服务状态     │            │  检查安全组配置     │
    │  - 启动服务       │            │  - SLB 网段规则     │
    │  - 检查配置       │            │  - 端口匹配         │
    │  - 查看日志       │            │  - 协议类型         │
    └───────────────────┘            │  - 授权策略         │
                                      └─────────────────────┘
                                                ↓
                                      ┌─────────────────────┐
                                      │  根据排查结果       │
                                      │  生成修复命令       │
                                      └─────────────────────┘
                                                ↓
                                      ┌─────────────────────┐
                                      │  执行修复并验证     │
                                      │  - 添加安全组规则   │
                                      │  - 重启服务         │
                                      │  - 验证健康状态     │
                                      └─────────────────────┘
```

**重要提示**:
- 当端口监听数量小于后端服务器数量时，必须检查安全组配置
- 安全组排查应重点关注 SLB 健康检查网段 (100.64.0.0/10) 的访问权限
- 需要同时检查端口、协议和授权策略是否正确
- 修复后应立即验证健康检查状态是否恢复正常

### 5.6 健康检查配置错误

**现象**: 服务正常，但健康检查失败

**诊断步骤**:
```bash
# 1. 查看健康检查配置
aliyun slb DescribeLoadBalancerListeners \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --ListenerPort <PORT>

# 2. 手动测试健康检查
curl -v http://127.0.0.1:<HEALTH_CHECK_PORT><HEALTH_CHECK_URI>

# 3. 检查返回状态码
curl -I http://127.0.0.1:<HEALTH_CHECK_PORT><HEALTH_CHECK_URI>
```

**常见问题**:

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 健康检查端口错误 | 配置的端口与服务监听端口不一致 | 修改健康检查端口 |
| 健康检查 URI 不存在 | 配置的 URI 返回 404 | 创建健康检查页面或修改 URI |
| 状态码不匹配 | 服务返回的状态码不在配置范围内 | 修改健康检查状态码配置 |
| 超时时间过短 | 服务响应慢 | 增加超时时间 |
| 检查间隔过短 | 服务压力大 | 增加检查间隔 |

**解决方案**:
```bash
# 修改健康检查配置
aliyun slb SetLoadBalancerHTTPListenerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --ListenerPort <PORT> \
  --HealthCheckConnectPort <PORT> \
  --HealthCheckUri /health \
  --HealthCheckHttpCode http_2xx,http_3xx \
  --HealthCheckTimeout 5 \
  --HealthCheckInterval 5 \
  --HealthyThreshold 2 \
  --UnhealthyThreshold 3
```

### 5.7 后端服务器权重为 0

**现象**: 服务器状态异常，权重为 0

**诊断步骤**:
```bash
# 查看后端服务器状态
aliyun slb DescribeLoadBalancerBackends \
  --LoadBalancerId <LOAD_BALANCER_ID>
```

**解决方案**:
```bash
# 设置服务器权重
aliyun slb SetBackendServers \
  --LoadBalancerId <LOAD_BALANCER_ID> \
  --BackendServers '[{"ServerId":"<INSTANCE_ID>","Weight":"100"}]'
```

### 5.8 后端服务器不在同一 VPC

**现象**: 负载均衡和后端服务器网络不通

**诊断步骤**:
```bash
# 1. 检查实例 VPC
aliyun ecs DescribeInstanceAttribute \
  --InstanceId <INSTANCE_ID> | grep VpcId

# 2. 检查负载均衡 VPC
aliyun slb DescribeLoadBalancerAttribute \
  --LoadBalancerId <LOAD_BALANCER_ID> | grep VpcId

# 3. 检查网络连通性
ping <LOAD_BALANCER_PRIVATE_IP>
```

**解决方案**:
- 确保后端服务器与负载均衡在同一 VPC
- 或配置云企业网 (CEN) 实现跨 VPC 通信
- 或使用经典网络负载均衡

---

## 6. 权限边界

### 6.1 安全的只读操作

**Linux 系统**:
```bash
# 系统状态检查
ss, netstat, lsof, ps, uptime, free, df

# 网络测试
ping, traceroute, tracepath, nc -zv, curl, telnet

# 日志查看
journalctl, tail, cat, grep

# 阿里云查询
aliyun slb Describe*
aliyun ecs Describe*
```

**Windows 系统**:
```powershell
# 系统状态检查
Get-NetTCPConnection, Get-Process, Get-Service, systeminfo

# 网络测试
Test-NetConnection, ping, curl (Windows 10+), telnet

# 日志查看
Get-Content, Get-EventLog, Get-WinEvent

# 阿里云查询
aliyun slb Describe*
aliyun ecs Describe*
```

### 6.2 需要确认的操作

**Linux 系统**:
```bash
# 服务管理
systemctl start/stop/restart <SERVICE>

# 防火墙修改
firewall-cmd --add-port
iptables -I
ufw allow

# 阿里云配置修改
aliyun slb Set*
aliyun ecs AuthorizeSecurityGroup
```

**Windows 系统**:
```powershell
# 服务管理
Start-Service, Stop-Service, Restart-Service

# 防火墙修改
New-NetFirewallRule, netsh advfirewall firewall add rule

# 阿里云配置修改
aliyun slb Set*
aliyun ecs AuthorizeSecurityGroup
```

### 6.3 危险操作禁止执行

**Linux 系统**:
```bash
# 危险操作
iptables -F (清空规则)
systemctl disable firewalld (禁用防火墙)
ufw disable (禁用防火墙)
aliyun ecs RevokeSecurityGroup (删除安全组规则)
```

**Windows 系统**:
```powershell
# 危险操作
netsh advfirewall set allprofiles state off (禁用防火墙)
Remove-NetFirewallRule (删除防火墙规则)
Stop-Service -Name "Windows Firewall" (停止防火墙服务)
aliyun ecs RevokeSecurityGroup (删除安全组规则)
```

---

## 7. 快速诊断脚本

```bash
#!/bin/bash
# 阿里云负载均衡端口连接快速诊断

PORT="${1:-80}"
PRIVATE_IP=$(curl -s http://100.100.100.200/latest/meta-data/private-ipv4 2>/dev/null || hostname -I | awk '{print $1}')

echo "=== 诊断信息 ==="
echo "端口: $PORT"
echo "内网 IP: $PRIVATE_IP"
echo ""

echo "=== Step 1: 检查端口监听 ==="
if ss -tuln | grep -q ":$PORT "; then
    echo "✓ 端口 $PORT 正在监听"
    ss -tuln | grep ":$PORT "
else
    echo "✗ 端口 $PORT 未监听"
    echo ""
    echo "可能原因:"
    echo "  1. 服务未启动"
    echo "  2. 服务监听不同端口"
    echo "  3. 服务启动失败"
    exit 1
fi
echo ""

echo "=== Step 2: 检查监听地址 ==="
LISTEN_ADDR=$(ss -tuln | grep ":$PORT " | awk '{print $4}' | cut -d: -f1)
if [ "$LISTEN_ADDR" = "0.0.0.0" ] || [ "$LISTEN_ADDR" = "*" ] || [ "$LISTEN_ADDR" = "::" ]; then
    echo "✓ 监听地址正确: $LISTEN_ADDR (外部可访问)"
else
    echo "✗ 监听地址错误: $LISTEN_ADDR (外部无法访问)"
    echo "  应该监听 0.0.0.0 或 ::: 而不是 127.0.0.1"
fi
echo ""

echo "=== Step 3: 本地连接测试 ==="
if curl -s --connect-timeout 3 http://127.0.0.1:$PORT/ > /dev/null 2>&1; then
    echo "✓ 本地回环连接成功"
else
    echo "✗ 本地回环连接失败"
fi

if curl -s --connect-timeout 3 http://$PRIVATE_IP:$PORT/ > /dev/null 2>&1; then
    echo "✓ 内网 IP 连接成功"
else
    echo "✗ 内网 IP 连接失败"
fi
echo ""

echo "=== Step 4: 防火墙检查 ==="
if command -v firewall-cmd &> /dev/null; then
    if firewall-cmd --state 2>/dev/null | grep -q "running"; then
        echo "防火墙状态: 运行中"
        if firewall-cmd --list-ports 2>/dev/null | grep -q "$PORT"; then
            echo "✓ 端口 $PORT 已在防火墙开放"
        else
            echo "✗ 端口 $PORT 未在防火墙开放"
            echo "  执行: firewall-cmd --permanent --add-port=$PORT/tcp && firewall-cmd --reload"
        fi
    else
        echo "防火墙状态: 未运行"
    fi
elif command -v ufw &> /dev/null; then
    if ufw status 2>/dev/null | grep -q "active"; then
        echo "防火墙状态: 运行中"
        if ufw status 2>/dev/null | grep -q "$PORT"; then
            echo "✓ 端口 $PORT 已在防火墙开放"
        else
            echo "✗ 端口 $PORT 未在防火墙开放"
            echo "  执行: ufw allow $PORT/tcp"
        fi
    else
        echo "防火墙状态: 未运行"
    fi
else
    echo "未检测到防火墙"
fi
echo ""

echo "=== Step 5: 进程信息 ==="
PROCESS=$(lsof -i :$PORT -t 2>/dev/null | head -1)
if [ -n "$PROCESS" ]; then
    echo "占用端口的进程:"
    ps -p $PROCESS -o pid,comm,args
else
    echo "未找到占用端口的进程"
fi
echo ""

echo "=== 诊断完成 ==="
echo ""
echo "如果本地测试都正常，请检查:"
echo "  1. 阿里云安全组规则是否允许负载均衡访问"
echo "  2. 负载均衡健康检查配置是否正确"
echo "  3. 负载均衡和后端服务器是否在同一 VPC"
```

### Windows 快速诊断脚本

```powershell
# 阿里云负载均衡端口连接快速诊断 (Windows)
# 使用方法: .\lb_diagnosis.ps1 -Port 80

param(
    [Parameter(Mandatory=$false)]
    [int]$Port = 80
)

# 获取内网 IP
try {
    $PrivateIP = Invoke-RestMethod -Uri "http://100.100.100.200/latest/meta-data/private-ipv4" -TimeoutSec 2
} catch {
    $PrivateIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike "*Loopback*"} | Select-Object -First 1).IPAddress
}

Write-Host "=== 诊断信息 ===" -ForegroundColor Cyan
Write-Host "端口: $Port"
Write-Host "内网 IP: $PrivateIP"
Write-Host ""

# Step 1: 检查端口监听
Write-Host "=== Step 1: 检查端口监听 ===" -ForegroundColor Cyan
$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($connections) {
    Write-Host "✓ 端口 $Port 正在监听" -ForegroundColor Green
    $connections | Select-Object LocalAddress, LocalPort, State, OwningProcess | Format-Table
} else {
    Write-Host "✗ 端口 $Port 未监听" -ForegroundColor Red
    Write-Host ""
    Write-Host "可能原因:"
    Write-Host "  1. 服务未启动"
    Write-Host "  2. 服务监听不同端口"
    Write-Host "  3. 服务启动失败"
    exit 1
}
Write-Host ""

# Step 2: 检查监听地址
Write-Host "=== Step 2: 检查监听地址 ===" -ForegroundColor Cyan
$listenAddrs = $connections | Select-Object -ExpandProperty LocalAddress -Unique
$correctListen = $false
foreach ($addr in $listenAddrs) {
    if ($addr -eq "0.0.0.0" -or $addr -eq "::") {
        Write-Host "✓ 监听地址正确: $addr (外部可访问)" -ForegroundColor Green
        $correctListen = $true
    } elseif ($addr -eq "127.0.0.1" -or $addr -eq "::1") {
        Write-Host "✗ 监听地址错误: $addr (外部无法访问)" -ForegroundColor Red
        Write-Host "  应该监听 0.0.0.0 或 ::: 而不是 127.0.0.1"
    }
}
Write-Host ""

# Step 3: 本地连接测试
Write-Host "=== Step 3: 本地连接测试 ===" -ForegroundColor Cyan

# 测试本地回环
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 3 -UseBasicParsing
    Write-Host "✓ 本地回环连接成功 (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "✗ 本地回环连接失败: $($_.Exception.Message)" -ForegroundColor Red
}

# 测试内网 IP
try {
    $response = Invoke-WebRequest -Uri "http://$PrivateIP:$Port/" -TimeoutSec 3 -UseBasicParsing
    Write-Host "✓ 内网 IP 连接成功 (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "✗ 内网 IP 连接失败: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Step 4: 防火墙检查
Write-Host "=== Step 4: 防火墙检查 ===" -ForegroundColor Cyan
$firewallProfiles = Get-NetFirewallProfile | Select-Object Name, Enabled
foreach ($profile in $firewallProfiles) {
    Write-Host "$($profile.Name) 配置文件: $($profile.Enabled)"
}

# 检查端口规则
$portRules = Get-NetFirewallRule | Where-Object {$_.Enabled -eq $true -and $_.Direction -eq "Inbound"} | Get-NetFirewallPortFilter | Where-Object {$_.LocalPort -eq $Port}

if ($portRules) {
    Write-Host "✓ 端口 $Port 已在防火墙规则中" -ForegroundColor Green
    $portRules | Get-NetFirewallRule | Select-Object DisplayName, Profile, Action | Format-Table
} else {
    Write-Host "✗ 端口 $Port 未在防火墙规则中" -ForegroundColor Red
    Write-Host "  执行: New-NetFirewallRule -DisplayName 'Allow Port $Port' -Direction Inbound -LocalPort $Port -Protocol TCP -Action Allow"
}
Write-Host ""

# Step 5: 进程信息
Write-Host "=== Step 5: 进程信息 ===" -ForegroundColor Cyan
$processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pid in $processIds) {
    $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "PID: $pid, 进程名: $($process.ProcessName), 路径: $($process.Path)"
    }
}
Write-Host ""

# 诊断完成
Write-Host "=== 诊断完成 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "如果本地测试都正常，请检查:"
Write-Host "  1. 阿里云安全组规则是否允许负载均衡访问"
Write-Host "  2. 负载均衡健康检查配置是否正确"
Write-Host "  3. 负载均衡和后端服务器是否在同一 VPC"
```

**使用方法**:
```powershell
# 保存脚本为 lb_diagnosis.ps1
# 执行脚本
.\lb_diagnosis.ps1 -Port 80

# 或直接运行
powershell -ExecutionPolicy Bypass -File lb_diagnosis.ps1 -Port 8080
```

---

## 8. 诊断报告模板

```markdown
# 阿里云负载均衡端口连接诊断报告

## 1. 基本信息
- 诊断时间: YYYY-MM-DD HH:MM:SS
- 操作系统: [Linux/Windows/macOS]
- 后端服务器 IP: <SERVER_IP>
- 端口号: <PORT>
- 负载均衡 ID: <LOAD_BALANCER_ID>

## 2. 诊断结果

### 2.1 端口监听状态
- 状态: [正常/异常]
- 监听地址: [0.0.0.0/127.0.0.1/其他]
- 进程: <PROCESS_NAME> (PID: <PID>)

### 2.2 本地连接测试
- 本地回环: [成功/失败]
- 内网 IP: [成功/失败]

### 2.3 防火墙状态
- 防火墙类型: [firewalld/ufw/iptables/Windows Firewall/无]
- 端口规则: [已开放/未开放]

### 2.4 安全组规则
- 安全组 ID: <SECURITY_GROUP_ID>
- 端口规则: [已配置/未配置]
- 授权对象: [负载均衡 IP/网段/其他]

## 3. 问题定位
- 根本原因: [服务未启动/监听地址错误/防火墙阻断/安全组缺失/其他]
- 影响范围: [单台服务器/多台服务器]

## 4. 解决方案
1. [具体步骤 1]
2. [具体步骤 2]
3. [具体步骤 3]

## 5. 预防措施
1. [预防措施 1]
2. [预防措施 2]
```

---

## 9. 版本信息

- 版本: 1.2.0
- 更新时间: 2025-04-06
- 维护者: AIOps Team

### 更新日志

#### v1.2.0 (2025-04-06)
- 新增远程云服务诊断支持
- 添加阿里云 CLI 环境检测和配置说明
- 添加远程 SLB 实例诊断流程
- 添加完整的远程诊断脚本
- 支持通过阿里云 API 查询 SLB 状态、健康检查、监听配置
- 支持远程检查后端服务器安全组规则
- 更新诊断流程，区分本地服务器和远程云服务

#### v1.1.0 (2025-04-06)
- 新增 Windows 操作系统支持
- 添加 Windows PowerShell 诊断命令
- 添加 Windows 防火墙检查和配置
- 添加 Windows 快速诊断脚本
- 更新诊断报告模板，支持多操作系统
- 更新权限边界，包含 Windows 操作

#### v1.0.0 (2025-04-06)
- 初始版本
- 支持 Linux 系统诊断
- 阿里云负载均衡端口连接诊断