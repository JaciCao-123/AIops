本文档定义了标准化的故障排查流程与命令集。适用对象：MasterAgent, Orchestrator。调用原则：先低风险检查（只读），后高风险操作（需确认）。

1. 网络 排查技能
1.1 场景：网络连通性异常
触发关键词：Connection refused, Timeout, No route to host, 网络不通

排查步骤：

基础连通性测试:
命令: ping -c 4 <TARGET_IP>
分析: 检查丢包率。若 100% loss，则检查路由或防火墙；若有延迟波动，检查带宽拥塞。
端口连通性测试:
命令: nc -zv -w 3 <TARGET_IP> <PORT> 或 telnet <TARGET_IP> <PORT>
分析: 确认服务端口是否监听。若拒绝连接，说明服务未启动或防火墙拦截。
路由追踪:
命令: traceroute -n <TARGET_IP> 或 mtr -r -c 10 <TARGET_IP>
分析: 定位网络中断点在哪一跳。
1.2 场景：DNS 解析故障
触发关键词：Unknown host, DNS resolution failed, 域名无法访问

排查步骤：

域名解析测试:
命令: nslookup <DOMAIN> 或 dig <DOMAIN>
分析: 检查返回的 IP 是否正确。若失败，检查 /etc/resolv.conf 或 DNS 服务器状态。
1.3 场景：网络流量/带宽异常
触发关键词：网络慢, 带宽占满, 吞吐量低

排查步骤：

实时网卡流量:
命令: sar -n DEV 1 5 或 ifconfig <INTERFACE>
分析: 观察 RX/TX 流量是否达到网卡上限。
连接数统计:
命令: netstat -an | awk '/^tcp/ {print $NF}' | sort | uniq -c
分析: 检查 TIME_WAIT 或 ESTABLISHED 数量是否异常过高。

2. 存储 排查技能
2.1 场景：磁盘空间不足
触发关键词：No space left on device, Disk full, 磁盘报警

排查步骤：

磁盘使用率查看:
命令: df -h
分析: 找出 Use% 超过 90% 的挂载点。
大文件定位:
命令: du -h --max-depth=1 /path/to/mount | sort -hr | head -n 10
分析: 定位占用空间最大的目录。
检查已删除未释放文件:
命令: lsof | grep deleted
分析: 若文件大小很大但磁盘空间未释放，需重启持有文件的进程。
2.2 场景：Inode 耗尽
触发关键词：No space left on device (但 df -h 显示有空间)

排查步骤：

Inode 查询:
命令: df -i
分析: 若 IUse% 达到 100%，说明小文件过多。
查找大量小文件目录:
命令: find /path -type d -exec sh -c "echo {} \$(ls -1 {} | wc -l)" \; | awk '$2 > 10000 {print}'
分析: 定位并清理小文件目录。
2.3 场景：磁盘 I/O 性能瓶颈
触发关键词：I/O wait high, 磁盘读写慢, Load 飙高

排查步骤：

I/O 状态监控:
命令: iostat -x 1 3
分析: 关注 %iowait 和 await。若 await 远大于 svctm，说明 I/O 响应慢。
查找高 I/O 进程:
命令: iotop -oP 或 pidstat -d 1
分析: 找出读写速率最高的进程 PID。

3. 虚拟机/操作系统 (VM/OS) 排查技能
3.1 场景：CPU 负载过高
触发关键词：High CPU usage, Load Average High, 服务器卡顿

排查步骤：

系统负载概览:
命令: uptime 或 top -bn1 | head -n 15
分析: 查看 load average (1/5/15分钟)，判断是短期突发还是持续高压。
高 CPU 进程定位:
命令: ps -eo pid,ppid,cmd,%cpu,%mem --sort=-%cpu | head -10
分析: 找出 CPU 消耗 Top N 的进程。
进程线程分析:
命令: top -H -p <PID>
分析: 如果是 Java 等多线程应用，需定位具体线程 ID。
3.2 场景：内存不足/泄漏
触发关键词：OOM Killer, Out of memory, Memory usage high

排查步骤：

内存使用概览:
命令: free -m
分析: 关注 available 列。若很低，说明内存紧张。
内存占用排行:
命令: ps -eo pid,ppid,cmd,%mem --sort=-%mem | head -10
分析: 定位内存泄漏或高耗内存进程。
检查 OOM 日志:
命令: grep -i "Out of memory" /var/log/messages 或 dmesg | grep -i oom
分析: 确认是否有进程被系统强制杀掉。
3.3 场景：系统僵死/假死
触发关键词：SSH 无法连接, 系统无响应

排查步骤：

检查进程状态:
命令: ps aux | awk '$8 ~ /D/ {print $0}'
分析: 查找状态为 D (Uninterruptible Sleep) 的进程，通常是 I/O 故障导致。
检查系统日志:
命令: tail -n 100 /var/log/messages 或 dmesg
分析: 搜索 Kernel panic, Hardware Error 等关键字。

4. 数据库 排查技能
4.1 场景：MySQL 连接数过多/慢查询
触发关键词：Too many connections, Database slow, Query timeout

排查步骤：

连接数检查:
命令: mysql -e "show processlist;" | wc -l 或 mysql -e "show status like 'Threads_connected';"
分析: 对比 max_connections 参数，确认是否耗尽。
慢查询分析:
命令: mysql -e "show full processlist;"
分析: 找出 Time 值大、State 为 Sending data 或 Copying to tmp table 的 SQL。
锁等待检查:
命令: mysql -e "SELECT * FROM information_schema.INNODB_TRX;"
分析: 查看是否有长时间未提交的事务阻塞其他会话。
4.2 场景：Redis 缓存问题
触发关键词：Redis connection refused, 内存溢出, 缓存穿透

排查步骤：

连接与内存状态:
命令: redis-cli info memory | grep used_memory_human 和 redis-cli info clients
分析: 确认内存是否打满 maxmemory 或连接数是否达到上限。
慢日志查询:
命令: redis-cli slowlog get 10
分析: 检查是否存在 O(N) 复杂度过高的命令（如 keys *）。

5. 中间件 排查技能
5.1 场景：Nginx/Web 服务异常
触发关键词：502 Bad Gateway, 504 Gateway Timeout, 服务不可用

排查步骤：

错误日志分析:
命令: tail -n 50 /var/log/nginx/error.log
分析: 502 通常表示后端服务挂了或端口不通；504 表示后端处理超时。
并发连接状态:
命令: nginx_status (需开启 stub_status 模块) 或 netstat -nlp | grep :80
分析: 确认 Nginx 进程是否存活，连接数是否达到 worker_connections 上限。
5.2 场景：消息队列 积压
触发关键词：消息堆积, Consumer Lag, 处理延迟

排查步骤：

队列状态查看:
命令: rabbitmqctl list_queues name messages consumers
分析: 检查 messages 数量是否异常堆积，consumers 是否为 0（消费者挂了）。
Kafka 消费组滞后:
命令: kafka-consumer-groups.sh --bootstrap-server <IP>:9092 --describe --group <GROUP_ID>
分析: 关注 LAG 列，数值大表示消费跟不上生产。
5.3 场景：JVM 应用 突然变慢
触发关键词：Java 进程 CPU 高, Full GC频繁, Heap Space

排查步骤：

线程堆栈 Dump:
命令: jstack -l <PID> > /tmp/thread_dump.txt
分析: 配合 top -H -p <PID> 找到的占用 CPU 最高的线程 ID (转为16进制)，在 dump 文件中定位代码位置。
堆内存分析:
命令: jmap -histo <PID> | head -n 20
分析: 查看实例数量最多的对象，排查是否存在内存泄漏。


6. Kubernetes (K8S) 排查技能
6.1 场景：Pod 启动失败/异常重启
触发关键词：CrashLoopBackOff, ImagePullBackOff, ErrImagePull

排查步骤：

查看 Pod 详情:
命令: kubectl describe pod <POD_NAME> -n <NAMESPACE>
分析: 重点查看 Events 部分。若是 ImagePullBackOff，检查镜像地址/Secret；若是 CrashLoopBackOff，检查应用启动报错。
查看容器日志:
命令: kubectl logs <POD_NAME> -n <NAMESPACE> --tail=100
分析: 查看应用标准输出的错误信息。如果容器重启过，加 --previous 参数查看上一次容器的日志。
6.2 场景：Service 无法访问
触发关键词：Service unreachable, No endpoints

排查步骤：

检查 Endpoints:
命令: kubectl get endpoints <SVC_NAME> -n <NAMESPACE>
分析: 如果 Endpoints 列表为空，说明 Selector 标签未匹配到健康的 Pod，或者 Pod 不在 Ready 状态。
检查 Pod 标签与端口:
命令: kubectl get pods -n <NAMESPACE> --show-labels 和 kubectl get svc <SVC_NAME> -o wide
分析: 确认 Service 的 Selector 与 Pod 的 Label 一致，且 Port 配置正确。
6.3 场景：节点状态异常
触发关键词：Node NotReady, 节点驱逐

排查步骤：

节点详情:
命令: kubectl describe node <NODE_NAME>
分析: 查看 Conditions 状态，如 MemoryPressure, DiskPressure, Ready 等。
Kubelet 服务状态:
命令: systemctl status kubelet 和 journalctl -u kubelet -n 50
分析: 节点 NotReady 最常见原因是 Kubelet 服务挂了或证书过期。
🚀 如何集成到你的 Multi-Agent 系统
在 Stage 2 (诊断计划生成) 中，MasterAgent 可以这样利用该文件：

意图匹配：Stage 1 传递意图 {"intent": "磁盘问题", "entity": "/data 分区"}
RAG 检索：Agent 基于 Intent 检索 skill.md，定位到 "2. 存储 -> 2.1 场景：磁盘空间不足"。
生成计划：
Agent 提取 Action：df -h 和 du -sh。
Agent 生成 diagnosis_plan.json：
json

[
  {"step": 1, "action": "check_disk_usage", "command": "df -h", "risk": "low"},
  {"step": 2, "action": "locate_large_files", "command": "du -h --max-depth=1 /data | sort -hr | head -n 10", "risk": "low"}
]
Stage 3 (执行)：Orchestrator 读取 JSON，将命令转换为 Ansible Playbook 并执行。