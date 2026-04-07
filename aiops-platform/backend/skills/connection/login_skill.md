说明：

本文档定义了各类节点的连接方式、协议及凭据引用路径。
Agent 在生成执行脚本时，需根据此文档动态组装连接参数。
安全原则：所有 password 或 token 字段均指向本地环境变量或 Vault 路径，不存储明文。

1. 操作系统与虚拟机 (Linux/VM/Host)
1.1 标准主机连接
节点类型: linux_host
协议: SSH
默认端口: 22
连接模板:
{  "ansible_connection": "ssh",  "ansible_user": "{{ lookup('env', 'SSH_USER') }}",  "ansible_ssh_private_key_file": "/keys/id_rsa",  "ansible_ssh_common_args": "-o StrictHostKeyChecking=no"}
Bash 登录指令生成:
ssh -i /keys/id_rsa -p 22 <USER>@<HOST_IP>
1.2 网络设备
节点类型: network_switch
协议: SSH (需特定 Ansible 模块)
连接模板:
{  "ansible_connection": "network_cli",  "ansible_network_os": "cisco.ios.ios",  "ansible_user": "{{ vault_network_user }}",  "ansible_password": "{{ vault_network_pass }}"}

2. 数据库
2.1 MySQL/MariaDB
节点类型: mysql_db
协议: TCP (MySQL Protocol)
默认端口: 3306
客户端工具: mysql (CLI)
连接指令生成:
mysql -h <HOST_IP> -P 3306 -u <USER> -p'<PASSWORD>' -e "SHOW PROCESSLIST;"
Ansible 模块配置:
community.mysql.mysql_query:  login_host: "<HOST_IP>"  login_user: "{{ db_user }}"  login_password: "{{ db_pass }}"  query: "SELECT 1"
2.2 Redis
节点类型: redis_cache
协议: TCP
默认端口: 6379
连接指令生成:
redis-cli -h <HOST_IP> -p 6379 -a '<PASSWORD>' INFO

3. 中间件
3.1 RabbitMQ
节点类型: rabbitmq_node
协议: HTTP API / CLI
默认端口: 15672 (API), 5672 (AMQP)
连接指令生成:
# 本地 CLI 方式 (通过 SSH 后执行)rabbitmqctl status# 远程 API 方式curl -u <USER>:<PASSWORD> http://<HOST_IP>:15672/api/overview
3.2 Nginx/Tomcat (应用层)
节点类型: web_server
访问方式: 通常通过 SSH 进入宿主机操作，或通过 HTTP 接口探测。
特定命令: 无需独立登录指令，依赖主机 SSH 权限执行 nginx -t 或查看日志。

4. Kubernetes (K8S) 集群
4.1 标准 K8S 集群
节点类型: k8s_cluster
协议: HTTPS (Kube-apiserver)
默认端口: 6443
认证方式: kubeconfig 文件 或 ServiceAccount Token
连接指令生成:
# 使用 Kubeconfigexport KUBECONFIG=/etc/rancher/k3s/k3s.yamlkubectl get pods -n <NAMESPACE># 使用 Token (远程调用)kubectl --server=https://<K8S_API_IP>:6443 --token=<TOKEN> --insecure-skip-tls-verify get nodes
Ansible 模块配置:
kubernetes.core.k8s_info:  kubeconfig: "/path/to/kubeconfig"  api_key: "{{ k8s_token }}"  host: "https://<K8S_API_IP>:6443"  validate_certs: false  kind: Pod

5. 云平台/管理节点
5.1 vCenter/ESXi
节点类型: vmware_host
协议: HTTPS (SOAP/REST)
连接方式: 通过 Ansible vmware_guest 模块
连接参数:
hostname: "<VCENTER_IP>"username: "{{ vcenter_user }}"password: "{{ vcenter_pass }}"validate_certs: no

6. SSH 连接故障排查流程
当 SSH 连接失败时，按以下步骤进行排查和恢复：

6.1 检查网络连通性
步骤 1: 测试基础网络连通性
  命令: ping -c 4 <HOST_IP>
  预期结果: 收到 ICMP 回复，丢包率 < 50%
  判断:
    - 成功 → 网络层正常，进入步骤 6.2
    - 失败 → 网络故障，检查防火墙/安全组/路由

步骤 2: 测试端口可达性
  命令: nc -zv <HOST_IP> 22 或 telnet <HOST_IP> 22
  预期结果: Connected to <HOST_IP> 22
  判断:
    - 成功 → 端口开放，可能是认证问题
    - 失败 → 端口不可达，进入步骤 6.3（使用替代连接方式）

6.2 检查 SSH 认证问题
步骤 3: 验证密钥权限
  命令: ls -la <SSH_KEY_PATH>
  预期结果: 权限应为 600 (-rw-------)
  修复: chmod 600 <SSH_KEY_PATH>

步骤 4: 尝试使用密码登录（如有）
  命令: ssh -o PreferredAuthentications=password <USER>@<HOST_IP>

6.3 使用替代连接方式（当网络/SSH 服务异常时）
当 ping 和端口测试均失败时，使用以下备用连接方式：

方式 A: 云厂商 Workbench/控制台
适用场景: 云服务器（阿里云、腾讯云、AWS、Azure 等）
操作步骤:
  1. 登录云厂商控制台
  2. 找到目标实例 <HOST_IP>
  3. 使用"远程连接"/"Workbench"/"VNC"功能
  4. 使用控制台提供的凭据登录（通常是 root 密码或临时密钥）
  5. 登录后执行诊断命令检查 SSH 服务状态

方式 B: VNC/远程桌面（物理机/虚拟机）
适用场景: 自有数据中心、VMware vSphere、Proxmox
操作步骤:
  1. 通过 vCenter/Proxmox 管理界面找到虚拟机
  2. 打开控制台/VNC 会话
  3. 使用本地账户登录系统
  4. 进入系统后检查 SSH 服务

6.4 登录后检查 SSH 服务状态
步骤 5: 检查 SSHD 服务状态
  命令: systemctl status sshd 或 service sshd status
  判断:
    - active (running) → 服务正常，检查防火墙
    - inactive/dead → 服务未启动，执行启动命令

步骤 6: 启动/重启 SSHD 服务
  命令: systemctl start sshd && systemctl enable sshd
  验证: systemctl status sshd 确认状态为 active

步骤 7: 检查防火墙规则
  命令: iptables -L -n | grep 22 或 firewall-cmd --list-ports
  判断:
    - 端口 22 未开放 → 添加规则:
      - iptables: iptables -I INPUT -p tcp --dport 22 -j ACCEPT
      - firewalld: firewall-cmd --add-port=22/tcp --permanent && firewall-cmd --reload
    - 端口 22 已开放 → 检查 SELinux/AppArmor

步骤 8: 检查 SSH 配置文件
  文件: /etc/ssh/sshd_config
  关键配置项:
    - Port 22 （确认监听端口）
    - ListenAddress 0.0.0.0 （确认监听地址）
    - PasswordAuthentication yes/no （根据安全策略）
    - PermitRootLogin yes/no （根据安全策略）
  修改后重载: systemctl reload sshd

6.5 验证恢复
步骤 9: 从运维机重新尝试 SSH 连接
  命令: ssh -i <SSH_KEY_PATH> -p 22 <USER>@<HOST_IP> "echo 'SSH OK'"
  预期结果: 输出 "SSH OK"
  判断:
    - 成功 → 故障恢复完成
    - 失败 → 记录错误日志，升级至 L2 支持

7. 凭据映射表
此部分供 Orchestrator 解析变量使用

变量名	类型	说明	示例来源
{{ ssh_key_path }}	SSH Key	运维机上的私钥路径	/home/aiops/.ssh/id_rsa
{{ vault_db_root_pass }}	Password	数据库 Root 密码	Vault: secret/data/mysql
{{ k8s_token }}	Token	K8S 集群访问令牌	Env: K8S_API_TOKEN
