import os
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime


class AnsiblePlaybookGenerator:
    """
    根据 login_skill.md 和 debug_skill.md 生成 Ansible Playbook
    """
    
    def __init__(self):
        self.vault_ssh_user = "jaci"
        self.vault_ssh_key_path = "~/.ssh/id_rsa"
        self.debug_skill_reference = "debug_skill.md"
    
    def generate_diagnosis_playbook(
        self,
        target_host: str,
        symptoms: List[str],
        metrics: List[str]
    ) -> Dict[str, Any]:
        """
        生成诊断用的 Ansible Playbook
        
        Args:
            target_host: 目标服务器 IP
            symptoms: 故障现象列表
            metrics: 需要检查的指标列表
            
        Returns:
            包含 playbook 内容和元数据的字典
        """
        playbook = {
            "skill_meta": {
                "generated_from": "login_skill.md#section-2.1",
                "timestamp": datetime.now().isoformat(),
                "target_host": target_host,
                "symptoms": symptoms,
                "metrics": metrics
            },
            "connection": {
                "plugin": "ansible.builtin.ssh",
                "inventory": {
                    "hosts": {
                        "target_server": {
                            "ansible_host": target_host,
                            "ansible_user": self.vault_ssh_user,
                            "ansible_ssh_private_key_file": self.vault_ssh_key_path
                        }
                    }
                },
                "vars": {
                    "ansible_python_interpreter": "/usr/bin/python3",
                    "host_key_checking": False,
                    "timeout": 30,
                    "pipelining": True
                }
            },
            "playbook": self._build_playbook_tasks(symptoms, metrics)
        }
        
        return playbook
    
    def _build_playbook_tasks(self, symptoms: List[str], metrics: List[str]) -> List[Dict]:
        """
        构建 playbook 任务列表
        根据 debug_skill.md 中的排查方法生成检查任务
        """
        tasks = []
        
        tasks.append({
            "name": "Step 1: Connectivity Test",
            "ansible.builtin.ping": {},
            "register": "ping_result"
        })
        
        metrics_str = " ".join(metrics).lower()
        symptoms_str = " ".join(symptoms).lower()
        
        if "memory" in metrics_str or "high_memory_usage" in symptoms_str or "oom" in symptoms_str or "内存" in symptoms_str:
            tasks.extend(self._build_memory_check_tasks())
        
        if "cpu" in metrics_str or "cpu_high" in symptoms_str or "cpu" in symptoms_str:
            tasks.extend(self._build_cpu_check_tasks())
        
        if "disk" in metrics_str or "disk_full" in symptoms_str or "磁盘" in symptoms_str or "空间" in symptoms_str:
            tasks.extend(self._build_disk_check_tasks())
        
        if "shm" in metrics_str or "/dev/shm" in metrics_str or "shm" in symptoms_str:
            tasks.extend(self._build_shm_check_tasks())
        
        if "network" in metrics_str or "connection" in symptoms_str or "timeout" in symptoms_str or "网络" in symptoms_str or "连接" in symptoms_str:
            tasks.extend(self._build_network_check_tasks())
        
        if len(tasks) == 1:
            tasks.extend(self._build_general_check_tasks())
        
        return [
            {
                "name": "AIOps Auto Diagnosis",
                "hosts": "target_server",
                "gather_facts": False,
                "tasks": tasks
            }
        ]
    
    def _build_memory_check_tasks(self) -> List[Dict]:
        """
        构建内存检查任务
        基于 debug_skill.md 第3节：Out of Memory
        """
        return [
            {
                "name": "Check Memory Usage",
                "ansible.builtin.command": "free -h",
                "changed_when": False,
                "register": "memory_output"
            },
            {
                "name": "Check Memory Details",
                "ansible.builtin.shell": "cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable|Buffers|Cached'",
                "changed_when": False,
                "register": "memory_details"
            },
            {
                "name": "Check Top Memory Processes",
                "ansible.builtin.shell": "ps aux --sort=-%mem | head -n 10",
                "changed_when": False,
                "register": "top_memory_processes"
            },
            {
                "name": "Check OOM Events",
                "ansible.builtin.shell": "dmesg -T | grep -i 'out of memory' | tail -n 20 || dmesg | grep -i 'out of memory' | tail -n 20",
                "changed_when": False,
                "register": "oom_events",
                "ignore_errors": True
            },
            {
                "name": "Check Killed Processes",
                "ansible.builtin.shell": "dmesg -T | grep -i 'killed process' | tail -n 20 || dmesg | grep -i 'killed process' | tail -n 20",
                "changed_when": False,
                "register": "killed_processes",
                "ignore_errors": True
            },
            {
                "name": "Check Swap Usage",
                "ansible.builtin.command": "swapon --show",
                "changed_when": False,
                "register": "swap_output"
            },
            {
                "name": "Check System Logs for Errors",
                "ansible.builtin.shell": "tail -n 100 /var/log/messages 2>/dev/null | grep -i error || tail -n 100 /var/log/syslog 2>/dev/null | grep -i error || echo 'No system logs found'",
                "changed_when": False,
                "register": "system_logs",
                "ignore_errors": True
            }
        ]
    
    def _build_cpu_check_tasks(self) -> List[Dict]:
        """
        构建 CPU 检查任务
        """
        return [
            {
                "name": "Check System Load",
                "ansible.builtin.command": "uptime",
                "changed_when": False,
                "register": "uptime_output"
            },
            {
                "name": "Check Top CPU Processes",
                "ansible.builtin.shell": "ps aux --sort=-%cpu | head -n 10",
                "changed_when": False,
                "register": "top_cpu_processes"
            },
            {
                "name": "Check CPU Info",
                "ansible.builtin.shell": "lscpu | grep -E 'CPU\\(s\\)|CPU MHz|CPU max MHz'",
                "changed_when": False,
                "register": "cpu_info"
            }
        ]
    
    def _build_disk_check_tasks(self) -> List[Dict]:
        """
        构建磁盘检查任务
        基于 debug_skill.md 第1节：Disk Full
        """
        return [
            {
                "name": "Check Disk Usage",
                "ansible.builtin.command": "df -h",
                "changed_when": False,
                "register": "disk_output"
            },
            {
                "name": "Check Inode Usage",
                "ansible.builtin.command": "df -i",
                "changed_when": False,
                "register": "inode_output"
            },
            {
                "name": "Check Large Directories",
                "ansible.builtin.shell": "du -h --max-depth=1 / 2>/dev/null | sort -rh | head -n 10",
                "changed_when": False,
                "register": "large_directories",
                "ignore_errors": True
            },
            {
                "name": "Check Deleted Files Still Open",
                "ansible.builtin.shell": "lsof | grep deleted 2>/dev/null | head -n 20 || echo 'No deleted files found'",
                "changed_when": False,
                "register": "deleted_files",
                "ignore_errors": True
            },
            {
                "name": "Check Large Files in Var",
                "ansible.builtin.shell": "du -sh /var/* 2>/dev/null | sort -rh | head -n 10",
                "changed_when": False,
                "register": "var_files",
                "ignore_errors": True
            }
        ]
    
    def _build_shm_check_tasks(self) -> List[Dict]:
        """
        构建 /dev/shm 检查任务
        """
        return [
            {
                "name": "Check SHM Usage",
                "ansible.builtin.command": "df -h /dev/shm",
                "changed_when": False,
                "register": "shm_output"
            },
            {
                "name": "Check SHM Files",
                "ansible.builtin.shell": "ls -lh /dev/shm/ 2>/dev/null | head -n 20",
                "changed_when": False,
                "register": "shm_files",
                "ignore_errors": True
            },
            {
                "name": "Check SHM Usage by Process",
                "ansible.builtin.shell": "lsof /dev/shm 2>/dev/null | head -n 20 || echo 'lsof not available'",
                "changed_when": False,
                "register": "shm_processes",
                "ignore_errors": True
            },
            {
                "name": "Check SHM Mount Options",
                "ansible.builtin.shell": "mount | grep shm",
                "changed_when": False,
                "register": "shm_mount"
            },
            {
                "name": "Check Shared Memory Segments",
                "ansible.builtin.shell": "ipcs -m 2>/dev/null || echo 'ipcs not available'",
                "changed_when": False,
                "register": "shm_segments",
                "ignore_errors": True
            }
        ]
    
    def _build_network_check_tasks(self) -> List[Dict]:
        """
        构建网络检查任务
        基于 debug_skill.md 第2节：Network Broken
        """
        return [
            {
                "name": "Check Network Connections",
                "ansible.builtin.shell": "netstat -tulnp | grep LISTEN || ss -tulnp | grep LISTEN",
                "changed_when": False,
                "register": "network_connections",
                "ignore_errors": True
            },
            {
                "name": "Check Connection States",
                "ansible.builtin.shell": "netstat -n | awk '/^tcp/ {print $NF}' | sort | uniq -c | sort -rn",
                "changed_when": False,
                "register": "connection_states",
                "ignore_errors": True
            },
            {
                "name": "Check Network Interfaces",
                "ansible.builtin.command": "ip addr show",
                "changed_when": False,
                "register": "network_interfaces"
            },
            {
                "name": "Check DNS Resolution",
                "ansible.builtin.shell": "cat /etc/resolv.conf",
                "changed_when": False,
                "register": "dns_config"
            },
            {
                "name": "Check Hosts File",
                "ansible.builtin.shell": "cat /etc/hosts",
                "changed_when": False,
                "register": "hosts_file"
            },
            {
                "name": "Check Firewall Status",
                "ansible.builtin.shell": "iptables -L -n 2>/dev/null | head -n 20 || echo 'iptables not available'",
                "changed_when": False,
                "register": "firewall_status",
                "ignore_errors": True
            }
        ]
    
    def _build_general_check_tasks(self) -> List[Dict]:
        """
        构建通用检查任务
        """
        return [
            {
                "name": "Check System Uptime",
                "ansible.builtin.command": "uptime",
                "changed_when": False,
                "register": "uptime_output"
            },
            {
                "name": "Check Memory Usage",
                "ansible.builtin.command": "free -m",
                "changed_when": False,
                "register": "memory_output"
            },
            {
                "name": "Check Disk Usage",
                "ansible.builtin.command": "df -h",
                "changed_when": False,
                "register": "disk_output"
            },
            {
                "name": "Check Top Processes",
                "ansible.builtin.shell": "ps aux --sort=-%cpu | head -n 10",
                "changed_when": False,
                "register": "top_processes"
            },
            {
                "name": "Check System Logs",
                "ansible.builtin.shell": "journalctl -p err -n 50 --no-pager",
                "changed_when": False,
                "register": "system_logs",
                "ignore_errors": True
            }
        ]
    
    def save_playbook(self, playbook: Dict[str, Any], filepath: str) -> str:
        """
        保存 playbook 到文件
        
        Args:
            playbook: playbook 内容
            filepath: 文件路径
            
        Returns:
            保存的文件路径
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(playbook, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        return filepath
    
    def parse_ansible_output(self, output: str) -> Dict[str, Any]:
        """
        解析 Ansible 执行输出
        
        Args:
            output: Ansible 执行输出
            
        Returns:
            解析后的结果
        """
        result = {
            "success": False,
            "memory_usage": None,
            "cpu_usage": None,
            "disk_usage": None,
            "shm_usage": None,
            "anomalies": [],
            "raw_output": output
        }
        
        if "FAILED" in output or "unreachable" in output or "timed out" in output.lower() or "connection refused" in output.lower():
            result["anomalies"].append("连接失败或主机不可达")
            return result
        
        result["success"] = True
        
        lines = output.split('\n')
        
        for line in lines:
            if "Mem:" in line and "free -m" in output:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        total = int(parts[1])
                        used = int(parts[2])
                        if total > 0:
                            result["memory_usage"] = round(used / total * 100, 2)
                            if result["memory_usage"] > 80:
                                result["anomalies"].append(f"内存使用率过高: {result['memory_usage']}%")
                    except (ValueError, IndexError):
                        pass
            
            if "load average" in line.lower():
                try:
                    load_part = line.split("load average:")[1].strip()
                    load_1 = float(load_part.split(',')[0].strip())
                    result["cpu_usage"] = load_1
                    if load_1 > 4:
                        result["anomalies"].append(f"系统负载过高: {load_1}")
                except (ValueError, IndexError):
                    pass
            
            if "/dev/shm" in line and "%" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.endswith('%'):
                        try:
                            usage = int(part[:-1])
                            if usage >= 90:
                                result["shm_usage"] = usage
                                result["anomalies"].append(f"/dev/shm 使用率过高: {usage}%")
                        except ValueError:
                            pass
            
            if "Use%" in line or "Mounted on" in line:
                continue
            if "%" in line and "/" in line and "/dev/shm" not in line:
                parts = line.split()
                for part in parts:
                    if part.endswith('%'):
                        try:
                            usage = int(part[:-1])
                            if usage > 80:
                                result["anomalies"].append(f"磁盘使用率过高: {usage}%")
                                if result["disk_usage"] is None:
                                    result["disk_usage"] = usage
                        except ValueError:
                            pass
        
        return result
