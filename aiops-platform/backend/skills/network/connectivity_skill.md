# 网络连通性诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `网络不通`, `连接超时`, `ping`, `telnet`
- `网络`, `连接`, `端口`, `防火墙`
- `DNS`, `解析`, `域名`
- `timeout`, `connection refused`, `network unreachable`

### 1.2 适用条件
- 服务无法访问
- 网络连接超时
- 端口不通
- DNS 解析问题
- 防火墙阻断
- 跨网络通信问题

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 确认目标信息                                       │
│  - 目标 IP/域名                                            │
│  - 目标端口                                                │
│  - 协议类型 (TCP/UDP)                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: DNS 解析检查                                       │
│  - nslookup / dig                                          │
│  - 检查域名解析是否正常                                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 网络连通性检查                                     │
│  - ping (ICMP)                                             │
│  - traceroute / tracepath                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 端口连通性检查                                     │
│  - telnet / nc                                             │
│  - nmap                                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 防火墙/安全组检查                                  │
│  - iptables                                                │
│  - 云安全组规则                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 6: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 DNS 解析检查

```bash
# 使用 nslookup 查询
nslookup example.com
nslookup example.com 8.8.8.8  # 指定 DNS 服务器

# 使用 dig 查询（更详细）
dig example.com
dig example.com +short  # 只显示 IP
dig example.com @8.8.8.8  # 指定 DNS 服务器
dig example.com ANY  # 查询所有记录类型

# 使用 host 查询
host example.com
host -t A example.com  # 查询 A 记录
host -t MX example.com  # 查询 MX 记录

# 检查 /etc/hosts
cat /etc/hosts | grep example.com

# 检查 DNS 配置
cat /etc/resolv.conf
```

### 3.2 网络连通性检查

```bash
# ICMP ping 测试
ping -c 4 192.168.1.1
ping -c 4 example.com

# 指定包大小
ping -s 1000 -c 4 192.168.1.1

# 持续 ping
ping 192.168.1.1

# 路由追踪
traceroute 192.168.1.1
traceroute -I 192.168.1.1  # 使用 ICMP
traceroute -T -p 80 192.168.1.1  # 使用 TCP 80 端口

# tracepath（不需要 root）
tracepath 192.168.1.1

# mtr（持续追踪）
mtr 192.168.1.1
mtr -r -c 10 192.168.1.1  # 报告模式
```

### 3.3 端口连通性检查

```bash
# 使用 telnet
telnet 192.168.1.1 80
telnet example.com 443

# 使用 nc (netcat)
nc -zv 192.168.1.1 80  # 单端口
nc -zv 192.168.1.1 80 443 3306  # 多端口
nc -zv 192.168.1.1 80-85  # 端口范围
nc -u -zv 192.168.1.1 53  # UDP 端口

# 使用 nmap 扫描
nmap -p 80 192.168.1.1  # 单端口
nmap -p 80,443,3306 192.168.1.1  # 多端口
nmap -p 1-1000 192.168.1.1  # 端口范围
nmap -sU -p 53 192.168.1.1  # UDP 扫描
nmap -sT -p- 192.168.1.1  # 全端口 TCP 扫描

# 使用 curl 测试 HTTP
curl -v http://192.168.1.1:80
curl -v https://example.com:443
curl -v --connect-timeout 5 http://192.168.1.1:80

# 使用 wget 测试
wget --spider http://192.168.1.1:80
```

### 3.4 网络状态检查

```bash
# 查看网络接口
ip addr show
ifconfig -a

# 查看路由表
ip route show
route -n
netstat -rn

# 查看网络连接
netstat -an | grep ESTABLISHED
netstat -tuln  # 监听端口
ss -tuln  # 更现代的替代

# 查看网络统计
netstat -i
cat /proc/net/dev

# 查看 ARP 表
arp -a
ip neigh show
```

### 3.5 防火墙检查

```bash
# iptables 规则查看
iptables -L -n -v
iptables -L INPUT -n -v
iptables -L OUTPUT -n -v

# 查看 NAT 规则
iptables -t nat -L -n -v

# firewalld 检查（CentOS 7+）
firewall-cmd --list-all
firewall-cmd --list-ports
firewall-cmd --list-services

# ufw 检查（Ubuntu）
ufw status verbose
ufw status numbered

# 查看云安全组（需要云 CLI）
# 阿里云
aliyun ecs DescribeSecurityGroupAttribute --SecurityGroupId sg-xxx

# AWS
aws ec2 describe-security-groups --group-ids sg-xxx
```

### 3.6 抓包分析

```bash
# tcpdump 抓包
tcpdump -i eth0 -n host 192.168.1.1
tcpdump -i eth0 -n port 80
tcpdump -i eth0 -n host 192.168.1.1 and port 80
tcpdump -i eth0 -n -w capture.pcap  # 保存到文件

# 查看抓包内容
tcpdump -r capture.pcap -n
tcpdump -r capture.pcap -n -A  # ASCII 显示
```

---

## 4. 常见问题与解决方案

### 4.1 DNS 解析失败

**现象**: 无法解析域名

**诊断步骤**:
```bash
# 1. 检查 DNS 配置
cat /etc/resolv.conf

# 2. 测试 DNS 服务器
nslookup example.com 8.8.8.8

# 3. 检查 hosts 文件
cat /etc/hosts
```

**解决方案**:
```bash
# 临时修改 DNS
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 永久修改（Ubuntu）
vim /etc/systemd/resolved.conf
# DNS=8.8.8.8 8.8.4.4

# 添加 hosts 记录
echo "192.168.1.1 example.com" >> /etc/hosts
```

### 4.2 连接超时

**现象**: Connection timed out

**诊断步骤**:
```bash
# 1. 测试网络连通性
ping 192.168.1.1

# 2. 追踪路由
traceroute 192.168.1.1

# 3. 检查端口
nc -zv 192.168.1.1 80 -w 5

# 4. 检查防火墙
iptables -L -n
```

**常见原因**:
| 原因 | 解决方案 |
|------|---------|
| 目标主机不可达 | 检查目标主机是否在线 |
| 防火墙阻断 | 检查防火墙规则 |
| 路由问题 | 检查路由表和网关 |
| 云安全组限制 | 检查云安全组规则 |

### 4.3 连接被拒绝

**现象**: Connection refused

**诊断步骤**:
```bash
# 1. 检查目标端口是否监听
netstat -tuln | grep 80
ss -tuln | grep 80

# 2. 检查服务状态
systemctl status nginx
docker ps

# 3. 检查进程
ps aux | grep nginx
```

**常见原因**:
| 原因 | 解决方案 |
|------|---------|
| 服务未启动 | 启动服务 |
| 服务监听不同端口 | 检查服务配置 |
| 服务只监听本地 | 修改监听地址为 0.0.0.0 |
| 端口被占用 | 查找并处理占用进程 |

### 4.4 网络延迟高

**现象**: 网络响应慢

**诊断步骤**:
```bash
# 1. 测试延迟
ping -c 10 192.168.1.1

# 2. 追踪路由查看延迟节点
mtr -r -c 10 192.168.1.1

# 3. 检查带宽
iperf3 -c 192.168.1.1

# 4. 检查丢包
ping -c 100 192.168.1.1 | grep "packet loss"
```

**常见原因**:
| 原因 | 解决方案 |
|------|---------|
| 网络拥塞 | 调整流量或扩容 |
| 路由绕行 | 优化路由配置 |
| MTU 问题 | 调整 MTU 大小 |
| DNS 解析慢 | 使用更快的 DNS 或缓存 |

### 4.5 MTU 问题

**现象**: 大包无法传输，小包正常

**诊断步骤**:
```bash
# 1. 查看当前 MTU
ip link show eth0

# 2. 测试 MTU
ping -M do -s 1472 192.168.1.1  # 1472 + 28 = 1500

# 3. 查看路径 MTU
tracepath 192.168.1.1
```

**解决方案**:
```bash
# 临时修改 MTU
ip link set dev eth0 mtu 1400

# 永久修改
vim /etc/sysconfig/network-scripts/ifcfg-eth0
# MTU=1400
```

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
ping, traceroute, tracepath, mtr
nslookup, dig, host
nc -zv (端口扫描)
netstat, ss, ip
curl, wget
```

### 5.2 需要确认的操作
```bash
iptables (修改规则)
firewall-cmd (修改规则)
ufw (修改规则)
ip link set (修改网络配置)
```

### 5.3 危险操作禁止执行
```bash
iptables -F (清空规则)
ip link set eth0 down (关闭网卡)
route del default (删除默认路由)
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
# 网络连通性快速诊断

TARGET="$1"
PORT="${2:-80}"

echo "=== DNS 解析 ==="
nslookup $TARGET 2>/dev/null || echo "DNS 解析失败"

echo -e "\n=== Ping 测试 ==="
ping -c 4 $TARGET

echo -e "\n=== 路由追踪 ==="
traceroute -m 15 $TARGET 2>/dev/null || tracepath $TARGET

echo -e "\n=== 端口测试 ($PORT) ==="
nc -zv -w 3 $TARGET $PORT 2>&1

echo -e "\n=== HTTP 测试 ==="
curl -v --connect-timeout 5 http://$TARGET:$PORT 2>&1 | head -20

echo -e "\n=== 防火墙状态 ==="
iptables -L INPUT -n 2>/dev/null | head -10
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
