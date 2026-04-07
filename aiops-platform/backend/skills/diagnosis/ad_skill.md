# Active Directory 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `AD`, `Active Directory`, `域控`, `域控制器`
- `LDAP`, `Kerberos`, `域用户`, `域组`
- `认证`, `authentication`, `登录失败`
- `GPO`, `组策略`, `DC`

### 1.2 适用条件
- AD 用户认证问题
- 域控制器健康检查
- LDAP 查询与用户管理
- Kerberos 票据问题
- 组策略故障排查
- 域信任关系问题

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 环境检测                                           │
│  - 检测 AD 环境 (Windows/Linux)                            │
│  - 确定连接方式                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 域控制器状态检查                                   │
│  - DC 健康状态                                             │
│  - 复制状态                                                │
│  - 服务状态                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 用户/认证诊断                                      │
│  - 用户状态检查                                            │
│  - 认证测试                                                │
│  - Kerberos 票据检查                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: LDAP 查询与分析                                    │
│  - 用户查询                                                │
│  - 组查询                                                  │
│  - 属性检查                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 域控制器状态检查

#### Windows 环境命令
```powershell
# 查看域控制器信息
Get-ADDomainController
Get-ADDomainController -Discover
Get-ADDomainController -Filter *

# 查看域信息
Get-ADDomain
Get-ADForest

# 检查 DC 健康状态
dcdiag /test:DNS
dcdiag /test:Replications
dcdiag /v

# 检查 AD 服务状态
Get-Service -Name NTDS, DNS, Netlogon, KDC

# 检查 FSMO 角色
netdom query fsmo
Get-ADForest | Select-Object SchemaMaster, DomainNamingMaster
Get-ADDomain | Select-Object PDCEmulator, RIDMaster, InfrastructureMaster

# 检查全局编录
Get-ADDomainController -Discover -Service GlobalCatalog

# 检查时间同步
w32tm /query /status
w32tm /query /source
w32tm /query /peers
```

#### 复制状态检查
```powershell
# 查看复制状态
repadmin /showrepl
repadmin /showrepl /repsto
repadmin /replsummary

# 检查复制错误
repadmin /showrepl /errorsonly

# 强制复制
repadmin /syncall /APeD

# 检查复制元数据
repadmin /showmeta "CN=Users,DC=domain,DC=com"
```

### 3.2 用户诊断

#### 用户状态检查
```powershell
# 查看用户信息
Get-ADUser -Identity username
Get-ADUser -Identity username -Properties *

# 查看用户锁定状态
Get-ADUser -Filter {LockedOut -eq $true} | Select-Object Name, SamAccountName

# 查看用户密码属性
Get-ADUser -Identity username -Properties PasswordExpired, PasswordLastSet, PasswordNeverExpires

# 查看用户登录信息
Get-ADUser -Identity username -Properties LastLogonDate, BadLogonCount, LockedOut

# 查看所有禁用账户
Get-ADUser -Filter {Enabled -eq $false} | Select-Object Name, SamAccountName

# 查看密码即将过期的用户
Get-ADUser -Filter {Enabled -eq $true -and PasswordNeverExpires -eq $false} -Properties msDS-UserPasswordExpiryTimeComputed | Select-Object Name, @{Name="ExpiryDate";Expression={[DateTime]::FromFileTime($_."msDS-UserPasswordExpiryTimeComputed")}}

# 解锁用户
Unlock-ADAccount -Identity username

# 重置密码
Set-ADAccountPassword -Identity username -NewPassword (ConvertTo-SecureString -AsPlainText "NewPassword123!" -Force)

# 启用/禁用用户
Enable-ADAccount -Identity username
Disable-ADAccount -Identity username
```

#### 用户组管理
```powershell
# 查看用户所属组
Get-ADPrincipalGroupMembership -Identity username

# 查看组成员
Get-ADGroupMember -Identity "Domain Admins"
Get-ADGroupMember -Identity "GroupName" | Select-Object Name, SamAccountName

# 添加用户到组
Add-ADGroupMember -Identity "GroupName" -Members username

# 从组中移除用户
Remove-ADGroupMember -Identity "GroupName" -Members username

# 查看所有组
Get-ADGroup -Filter * | Select-Object Name, GroupScope, GroupCategory

# 查看空组
Get-ADGroup -Filter * | Where-Object { @(Get-ADGroupMember $_.SamAccountName).Count -eq 0 }
```

### 3.3 认证诊断

#### Kerberos 诊断
```powershell
# 查看当前 Kerberos 票据
klist
klist tickets

# 查看票据缓存详情
klist -li 0x3e7 purge  # 清除系统票据
klist purge            # 清除当前用户票据

# 请求新票据
klist get krbtgt/domain.com

# 测试 Kerberos 认证
kinit username@DOMAIN.COM

# 查看 SPN
setspn -Q */*
setspn -L servername

# 注册 SPN
setspn -S HTTP/webserver.domain.com domain\serviceaccount

# 检查 Kerberos 配置
Get-ADDomainController -Service KDC
```

#### 认证测试
```powershell
# 测试用户认证
Test-ADServiceAccount -Identity username

# 检查凭据
$cred = Get-Credential
Test-Credential -Credential $cred

# 查看登录失败日志
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4625} -MaxEvents 10

# 查看账户锁定日志
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4740} -MaxEvents 10

# 查看登录成功日志
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4624} -MaxEvents 10
```

### 3.4 LDAP 查询

#### PowerShell LDAP 查询
```powershell
# 基础 LDAP 查询
Get-ADUser -LDAPFilter "(objectClass=user)"
Get-ADUser -LDAPFilter "(sAMAccountName=username)"

# 模糊查询
Get-ADUser -LDAPFilter "(name=*john*)"

# 查询特定属性
Get-ADUser -LDAPFilter "(objectClass=user)" -Properties mail, telephoneNumber | Select-Object Name, mail, telephoneNumber

# 查询组
Get-ADGroup -LDAPFilter "(objectClass=group)"
Get-ADGroup -LDAPFilter "(name=*admin*)"

# 查询计算机
Get-ADComputer -LDAPFilter "(objectClass=computer)"
Get-ADComputer -LDAPFilter "(operatingSystem=*Windows 10*)"

# 查询禁用的账户
Get-ADUser -LDAPFilter "(&(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=2))"

# 查询密码永不过期的账户
Get-ADUser -LDAPFilter "(&(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=65536))"
```

#### Linux 环境 LDAP 查询
```bash
# 安装 LDAP 工具
# Ubuntu/Debian
apt-get install ldap-utils

# CentOS/RHEL
yum install openldap-clients

# 基础 LDAP 查询
ldapsearch -x -H ldap://dc.domain.com -D "CN=admin,DC=domain,DC=com" -W -b "DC=domain,DC=com" "(objectClass=user)"

# 查询特定用户
ldapsearch -x -H ldap://dc.domain.com -D "CN=admin,DC=domain,DC=com" -W -b "DC=domain,DC=com" "(sAMAccountName=username)"

# 查询所有用户
ldapsearch -x -H ldap://dc.domain.com -D "CN=admin,DC=domain,DC=com" -W -b "DC=domain,DC=com" "(objectClass=user)" sAMAccountName

# 查询所有组
ldapsearch -x -H ldap://dc.domain.com -D "CN=admin,DC=domain,DC=com" -W -b "DC=domain,DC=com" "(objectClass=group)" cn

# 测试 LDAP 连接
ldapsearch -x -H ldap://dc.domain.com -b "" -s base "(objectclass=*)" namingContexts
```

### 3.5 组策略诊断

```powershell
# 查看组策略状态
Get-GPO -All
Get-GPO -Name "Default Domain Policy"

# 查看组策略结果
gpresult /R
gpresult /H gpreport.html
gpresult /Z

# 查看用户组策略
gpresult /R /USER username

# 强制更新组策略
gpupdate /force

# 检查组策略复制
Get-GPO -All | ForEach-Object { $_ | Get-GPOReport -ReportType XML }

# 查看组策略链接
Get-GPInheritance -Target "OU=Users,DC=domain,DC=com"

# 查看组策略权限
Get-GPPermission -Name "Default Domain Policy" -All
```

### 3.6 域信任关系

```powershell
# 查看域信任
Get-ADTrust -Filter *
Get-ADTrust -Identity trusted.domain.com

# 验证信任关系
netdom trust trusted.domain.com /domain:domain.com /verify

# 修复信任关系
netdom resetpwd /s:dc.domain.com /ud:domain\admin /pd:*

# 查看信任属性
Get-ADTrust -Identity trusted.domain.com | Select-Object Name, TrustType, TrustDirection, TrustAttributes
```

---

## 4. 常见问题与解决方案

### 4.1 用户无法登录

**现象**: 用户登录失败

**诊断步骤**:
```powershell
# 1. 检查用户状态
Get-ADUser -Identity username -Properties Enabled, LockedOut, PasswordExpired, AccountExpirationDate

# 2. 检查账户锁定
Get-ADUser -Identity username -Properties LockedOut, BadLogonCount

# 3. 查看登录失败日志
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4625} -MaxEvents 10 | Where-Object {$_.Message -like "*username*"}
```

**解决方案**:
```powershell
# 解锁账户
Unlock-ADAccount -Identity username

# 重置密码
Set-ADAccountPassword -Identity username -NewPassword (ConvertTo-SecureString -AsPlainText "NewPassword123!" -Force) -Reset

# 启用账户
Enable-ADAccount -Identity username
```

### 4.2 账户频繁锁定

**现象**: 用户账户频繁被锁定

**诊断步骤**:
```powershell
# 1. 查看锁定事件
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4740} -MaxEvents 20

# 2. 查看登录失败来源
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4625} -MaxEvents 50 | Select-Object TimeCreated, @{Name='CallerComputer';Expression={$_.Properties[13].Value}}, @{Name='TargetUser';Expression={$_.Properties[5].Value}}

# 3. 检查用户登录脚本/映射驱动器
Get-ADUser -Identity username -Properties homeDirectory, scriptPath
```

**解决方案**:
- 检查是否有旧密码缓存在应用程序中
- 检查移动设备邮件同步
- 检查映射驱动器凭据
- 检查计划任务凭据

### 4.3 Kerberos 认证失败

**现象**: Kerberos 认证失败，服务无法访问

**诊断步骤**:
```powershell
# 1. 检查票据
klist

# 2. 检查 SPN
setspn -Q HTTP/webserver.domain.com

# 3. 检查时间同步
w32tm /query /status
```

**解决方案**:
```powershell
# 清除票据缓存
klist purge

# 重新获取票据
klist get krbtgt/domain.com

# 修复 SPN
setspn -S HTTP/webserver.domain.com domain\serviceaccount

# 同步时间
w32tm /resync
```

### 4.4 域控制器复制问题

**现象**: DC 之间数据不同步

**诊断步骤**:
```powershell
# 1. 检查复制状态
repadmin /showrepl
repadmin /replsummary

# 2. 检查复制错误
repadmin /showrepl /errorsonly

# 3. 检查 DNS
dcdiag /test:DNS
```

**解决方案**:
```powershell
# 强制复制
repadmin /syncall /APeD

# 重新注册 DNS
ipconfig /registerdns

# 检查并修复复制
repadmin /replicate targetDC sourceDC DC=domain,DC=com
```

### 4.5 组策略不生效

**现象**: 组策略未应用到用户/计算机

**诊断步骤**:
```powershell
# 1. 查看组策略结果
gpresult /R

# 2. 检查组策略继承
Get-GPInheritance -Target "OU=Users,DC=domain,DC=com"

# 3. 检查组策略链接状态
Get-GPO -All | Select-Object DisplayName, GpoStatus
```

**解决方案**:
```powershell
# 强制更新组策略
gpupdate /force

# 检查 OU 链接
Get-GPInheritance -Target "OU=Users,DC=domain,DC=com"

# 启用被禁用的 GPO
Set-GPO -Name "GPO Name" -Status AllSettingsEnabled
```

---

## 5. 权限边界

### 5.1 安全的只读操作
```powershell
Get-ADUser
Get-ADGroup
Get-ADGroupMember
Get-ADComputer
Get-ADDomainController
Get-ADDomain
Get-ADForest
Get-GPO
gpresult
klist
ldapsearch
```

### 5.2 需要确认的操作
```powershell
Unlock-ADAccount
Set-ADAccountPassword
Enable-ADAccount / Disable-ADAccount
Add-ADGroupMember / Remove-ADGroupMember
gpupdate /force
```

### 5.3 危险操作禁止执行
```powershell
Remove-ADUser
Remove-ADGroup
Remove-ADDomainController
Remove-GPO
netdom remove
```

---

## 6. 快速诊断脚本

```powershell
# AD 快速诊断脚本

$domain = Get-ADDomain
$forest = Get-ADForest

Write-Host "=== AD 域信息 ===" -ForegroundColor Cyan
Write-Host "域名: $($domain.DNSRoot)"
Write-Host "NetBIOS: $($domain.NetBIOSName)"
Write-Host "域功能级别: $($domain.DomainMode)"
Write-Host "林功能级别: $($forest.ForestMode)"

Write-Host "`n=== 域控制器状态 ===" -ForegroundColor Cyan
$dc = Get-ADDomainController
Write-Host "当前 DC: $($dc.Name)"
Write-Host "站点: $($dc.Site)"
Write-Host "IP: $($dc.IPv4Address)"

Write-Host "`n=== AD 服务状态 ===" -ForegroundColor Cyan
Get-Service -Name NTDS, DNS, Netlogon, KDC | Select-Object Name, Status, StartType

Write-Host "`n=== 用户统计 ===" -ForegroundColor Cyan
$users = Get-ADUser -Filter *
$enabled = ($users | Where-Object {$_.Enabled}).Count
$disabled = ($users | Where-Object {!$_.Enabled}).Count
$locked = (Get-ADUser -Filter {LockedOut -eq $true}).Count
Write-Host "总用户数: $($users.Count)"
Write-Host "启用: $enabled"
Write-Host "禁用: $disabled"
Write-Host "锁定: $locked"

Write-Host "`n=== 最近登录失败 ===" -ForegroundColor Cyan
Get-WinEvent -FilterHashtable @{LogName='Security'; ID=4625} -MaxEvents 5 -ErrorAction SilentlyContinue | 
    Select-Object TimeCreated, @{Name='User';Expression={$_.Properties[5].Value}}, @{Name='Source';Expression={$_.Properties[13].Value}}

Write-Host "`n=== 复制状态 ===" -ForegroundColor Cyan
repadmin /replsummary 2>&1 | Select-String -Pattern "最大|失败|错误"
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
