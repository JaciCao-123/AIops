import os
import json
import shlex
import subprocess
import asyncio
import re
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from pathlib import Path

from ..utils.file_manager import IntermediateFileManager
from ..utils.logger import get_logger
from ..core.config import settings

logger = get_logger("tool_registry")

SERVICENOW_AVAILABLE = False
try:
    from ..utils.servicenow_client import ServiceNowClient, get_servicenow_client
    SERVICENOW_AVAILABLE = True
except ImportError:
    logger.warning("ServiceNow client not available")


# 风险等级常量
RISK_SAFE = "L0"      # 安全：只读操作，无风险
RISK_LOW = "L1"       # 低风险：白名单内的写操作
RISK_MEDIUM = "L2"    # 中风险：需要确认的操作
RISK_HIGH = "L3"      # 高风险：禁止执行的操作

# 路径白名单（用于 rm 操作降级）
PATH_WHITELIST = [
    "/tmp/",
    "/var/log/app/",
    "/var/log/nginx/",
    "/var/cache/",
    "/home/app/logs/",
    "/app/logs/",
    "/data/tmp/",
]

# 核心生产节点列表（模拟）
CORE_PRODUCTION_NODES = [
    "prod-db-master",
    "prod-db-slave",
    "prod-redis-master",
    "prod-api-gateway",
    "prod-order-service",
]


class ToolRegistry:
    """
    工具注册中心
    注册所有可被 LLM 调用的工具，并提供统一的执行接口
    """
    
    def __init__(self, file_manager: IntermediateFileManager = None):
        self.tools: Dict[str, Callable] = {}
        self.file_manager = file_manager or IntermediateFileManager()
        self._pending_approvals: Dict[str, Dict] = {}
        self._servicenow_client: Optional[Any] = None
        self._last_pending_command: Dict = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """
        注册默认工具
        """
        self.register("execute_command", self._execute_command)
        self.register("save_diagnosis_plan", self._save_diagnosis_plan)
        self.register("save_execution_output", self._save_execution_output)
        self.register("query_knowledge_graph", self._query_knowledge_graph)
        self.register("query_rag", self._query_rag)
        self.register("generate_playbook", self._generate_playbook)
        self.register("ask_user_confirmation", self._ask_user_confirmation)
        self.register("send_approval_email", self._send_approval_email)
        self.register("check_approval_status", self._check_approval_status)
        self.register("execute_approved_command", self._execute_approved_command)
        self.register("wait_for_approval", self._wait_for_approval)
        self.register("submit_diagnosis_result", self._submit_diagnosis_result)
        self.register("parse_logs", self._parse_logs)
        self.register("load_metrics_and_detect_anomalies", self._load_metrics_and_detect_anomalies)
        self.register("build_service_graph", self._build_service_graph)
        self.register("gnn_root_cause_analysis", self._gnn_root_cause_analysis)
        self.register("generate_rca_report", self._generate_rca_report)
        self.register("list_data_sources", self._list_data_sources)
        self.register("load_data_from_source", self._load_data_from_source)
        self.register("detect_log_anomalies", self._detect_log_anomalies)
        self.register("cluster_alerts", self._cluster_alerts)
        self.register("analyze_trace", self._analyze_trace)
        self.register("analyze_service_dependency", self._analyze_service_dependency)
        self.register("query_grafana_logs", self._query_grafana_logs)
        self.register("mcp_call", self._mcp_call)
        
        # ServiceNow 工具
        if SERVICENOW_AVAILABLE:
            self.register("query_servicenow_ci", self._query_servicenow_ci)
            self.register("query_servicenow_changes", self._query_servicenow_changes)
            self.register("query_servicenow_incidents", self._query_servicenow_incidents)
            self.register("analyze_change_as_root_cause", self._analyze_change_as_root_cause)
            self.register("get_servicenow_node_health", self._get_servicenow_node_health)
    
    def register(self, name: str, func: Callable):
        """
        注册工具
        """
        self.tools[name] = func
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """
        获取工具
        """
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """
        列出所有工具
        """
        return list(self.tools.keys())
    
    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "available_tools": self.list_tools()
            }
        
        try:
            result = await tool(**kwargs)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name,
                "params": kwargs
            }
    
    async def _execute_command(
        self,
        command: str,
        target_host: str = None,
        risk_level: str = "low",
        timeout: int = 60,
        ssh_user: str = None
    ) -> Dict[str, Any]:
        """
        执行命令（本地或远程）- 分级安全控制版本
        
        Args:
            command: 要执行的命令
            target_host: 目标主机地址，为 None 时在本地执行
            risk_level: 风险等级（已废弃，由安全检查自动判定）
            timeout: 超时时间
            ssh_user: SSH 用户名，优先级高于环境变量
            
        Returns:
            执行结果
        """
        security_check = self._check_command_security(command, target_host)
        
        # L3 高风险：直接拒绝执行
        if security_check["risk_level"] == RISK_HIGH:
            logger.warning(f"Command blocked (L3): {command[:100]}... Reason: {security_check['reason']}")
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": f"安全拒绝 (L3): {security_check['reason']}",
                "risk_level": RISK_HIGH,
                "reason": security_check["reason"],
                "suggestion": security_check["suggestion"]
            }
        
        # L2 中风险：返回模拟的"需用户确认"结果
        if security_check["risk_level"] == RISK_MEDIUM and security_check.get("requires_confirmation"):
            logger.info(f"Command requires confirmation (L2): {command[:100]}...")
            self._last_pending_command = {
                "command": command,
                "target_host": target_host or "",
                "risk": security_check.get("risk_level", RISK_MEDIUM),
                "reason": security_check.get("reason", ""),
            }
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": "需要用户确认",
                "risk_level": RISK_MEDIUM,
                "reason": security_check["reason"],
                "requires_confirmation": True,
                "suggestion": security_check["suggestion"],
                "confirmation_hint": "请使用 ask_user_confirmation 工具获取用户确认后再执行此命令"
            }
        
        # L0/L1：正常执行
        logger.info(f"Executing command ({security_check['risk_level']}): {command[:100]}...")
        
        try:
            if target_host:
                effective_ssh_user = ssh_user or settings.SSH_USER or "root"
                ssh_opts = f"-o ConnectTimeout={settings.SSH_CONNECT_TIMEOUT}"
                if not settings.SSH_STRICT_HOST_KEY_CHECK:
                    ssh_opts += " -o StrictHostKeyChecking=no"
                escaped_command = shlex.quote(command)
                ssh_command = f"ssh {ssh_opts} -i {settings.SSH_KEY_PATH} {effective_ssh_user}@{target_host} {escaped_command}"
                exec_command = ssh_command
            else:
                exec_command = command
            
            result = subprocess.run(
                exec_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout + "\n" + result.stderr
            
            return {
                "success": result.returncode == 0,
                "target_host": target_host,
                "command": command,
                "risk_level": security_check["risk_level"],
                "output": output,
                "return_code": result.returncode,
                "security_check": {
                    "risk_level": security_check["risk_level"],
                    "reason": security_check["reason"]
                }
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": "Command execution timeout",
                "risk_level": security_check["risk_level"]
            }
        except Exception as e:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": str(e),
                "risk_level": security_check["risk_level"]
            }
    
    def _is_core_production_node(self, target_host: str) -> bool:
        """
        判断是否为核心生产节点（模拟实现）
        
        实际生产环境中应从 CMDB 或配置中心获取
        """
        if not target_host:
            return False
        
        target_lower = target_host.lower()
        for node in CORE_PRODUCTION_NODES:
            if node in target_lower or target_lower in node:
                return True
        
        return False
    
    def _check_path_in_whitelist(self, command: str) -> tuple:
        """
        检查 rm 命令的路径是否在白名单中
        
        Returns:
            (in_whitelist, path)
        """
        rm_match = re.search(r'\brm\s+(-[rf]+\s+)*([^\s;|&]+)', command)
        if rm_match:
            path = rm_match.group(2)
            for whitelist_path in PATH_WHITELIST:
                if path.startswith(whitelist_path):
                    return True, path
        return False, None
    
    def _check_command_security(
        self, 
        command: str, 
        target_host: str = None
    ) -> Dict[str, Any]:
        """
        分级安全检查（上下文感知）
        
        Args:
            command: 要检查的命令
            target_host: 目标主机（用于上下文感知）
            
        Returns:
            {
                "safe": bool,           # 是否允许执行
                "risk_level": str,      # 风险等级 L0/L1/L2/L3
                "reason": str,          # 原因说明
                "requires_confirmation": bool,  # 是否需要用户确认
                "suggestion": str       # 建议操作
            }
        """
        command_lower = command.lower().strip()
        is_core_node = self._is_core_production_node(target_host)
        
        if len(command) > 2000:
            return {
                "safe": False,
                "risk_level": RISK_HIGH,
                "reason": "命令长度超过 2000 字符限制",
                "requires_confirmation": False,
                "suggestion": "请缩短命令长度"
            }
        
        # ==================== L3 高风险检查 ====================
        # 这些操作直接拦截，不允许执行
        
        # 注入攻击检测
        injection_patterns = [
            (r';\s*rm\s', "检测到命令链注入（分号+删除）"),
            (r'\$\(', "检测到命令替换注入 $(...)"),
            (r'`[^`]+`', "检测到反引号命令替换"),
            (r'\|\s*rm\s', "检测到管道注入（管道+删除）"),
            (r'&&\s*rm\s', "检测到命令链注入（AND+删除）"),
            (r'\bexport\s+.*=\$\(.*\)', "检测到环境变量注入"),
            (r'nc\s+-[elp]', "检测到反向 Shell 模式"),
            (r'/dev/tcp/', "检测到 /dev/tcp 反向 Shell"),
            (r'bash\s+-i', "检测到交互式 Shell 注入"),
            (r'python[23]?\s+-c\s+.*import\s+socket', "检测到 Python 反向 Shell"),
        ]
        
        for pattern, reason in injection_patterns:
            if re.search(pattern, command_lower):
                return {
                    "safe": False,
                    "risk_level": RISK_HIGH,
                    "reason": reason,
                    "requires_confirmation": False,
                    "suggestion": "此操作存在安全风险，已被拦截"
                }
        
        # 危险命令检测（L3）
        high_risk_patterns = [
            (r'\brm\s+-rf\s+/', "禁止递归删除根目录"),
            (r'\brm\s+-rf\s+~', "禁止递归删除用户目录"),
            (r'\brm\s+-rf\s+/etc', "禁止删除系统配置目录"),
            (r'\brm\s+-rf\s+/usr', "禁止删除系统程序目录"),
            (r'\brm\s+-rf\s+/var', "禁止删除系统数据目录"),
            (r'\bdd\s+if=', "禁止使用 dd 命令"),
            (r'\bshutdown\b', "禁止执行关机命令"),
            (r'\breboot\b', "禁止执行重启命令"),
            (r'\binit\s+[06]', "禁止执行 init 0/6"),
            (r'\bmkfs\b', "禁止格式化磁盘"),
            (r'\bfdisk\b', "禁止磁盘分区操作"),
            (r'\bdrop\s+(database|table)', "禁止删除数据库/表"),
            (r'\btruncate\s+table', "禁止清空表"),
            (r'>\s*/dev/sd', "禁止直接写入磁盘设备"),
            (r'>\s*/dev/hd', "禁止直接写入磁盘设备"),
            (r':\(\)\{', "检测到 fork bomb 攻击模式"),
            (r'(wget|curl)\s+.*\|\s*(bash|sh)', "禁止从远程下载并执行脚本"),
            (r'/etc/passwd', "禁止访问 /etc/passwd"),
            (r'/etc/shadow', "禁止访问 /etc/shadow"),
        ]
        
        for pattern, reason in high_risk_patterns:
            if re.search(pattern, command_lower):
                return {
                    "safe": False,
                    "risk_level": RISK_HIGH,
                    "reason": reason,
                    "requires_confirmation": False,
                    "suggestion": "此操作风险极高，已被系统拦截"
                }
        
        # 核心节点检查：如果是核心生产节点，所有写操作提升为 L3
        if is_core_node:
            write_keywords = ["rm", "mv", "chmod", "chown", "kill", "pkill", 
                           "systemctl", "service", "docker", "kubectl", "iptables"]
            for kw in write_keywords:
                if command_lower.startswith(kw):
                    return {
                        "safe": False,
                        "risk_level": RISK_HIGH,
                        "reason": f"核心生产节点 [{target_host}] 禁止执行写操作: {kw}",
                        "requires_confirmation": False,
                        "suggestion": "核心生产节点操作需要通过变更流程审批"
                    }
        
        # ==================== L2 中风险检查 ====================
        # 这些操作需要用户确认才能执行
        
        medium_risk_patterns = [
            (r'\bsystemctl\s+(stop|start|restart|reload|kill)', "systemctl 服务操作"),
            (r'\bservice\s+\w+\s+(stop|start|restart)', "service 服务操作"),
            (r'\bdocker\s+(stop|start|restart|rm|rmi)', "Docker 容器/镜像操作"),
            (r'\bkubectl\s+(delete|scale|rollout)', "Kubernetes 资源操作"),
            (r'\biptables\b', "防火墙规则修改"),
            (r'\bfirewall-cmd\b', "防火墙规则修改"),
            (r'\bkill\s+-9\b', "强制终止进程"),
            (r'\bpkill\s+-9\b', "强制终止进程组"),
            (r'\bmv\s+', "文件移动操作"),
            (r'\bcp\s+', "文件复制操作"),
            (r'\bchmod\s+', "权限修改操作"),
            (r'\bchown\s+', "所有者修改操作"),
        ]
        
        for pattern, operation in medium_risk_patterns:
            if re.search(pattern, command_lower):
                return {
                    "safe": True,
                    "risk_level": RISK_MEDIUM,
                    "reason": f"检测到中风险操作: {operation}",
                    "requires_confirmation": True,
                    "suggestion": "此操作可能影响服务，建议使用 ask_user_confirmation 工具获取用户确认"
                }
        
        # ==================== rm 命令特殊处理 ====================
        # 检查路径白名单
        
        if command_lower.startswith("rm"):
            in_whitelist, path = self._check_path_in_whitelist(command)
            if in_whitelist:
                return {
                    "safe": True,
                    "risk_level": RISK_LOW,
                    "reason": f"删除操作路径 [{path}] 在白名单中，已降级为低风险",
                    "requires_confirmation": False,
                    "suggestion": "白名单路径删除操作可安全执行"
                }
            else:
                return {
                    "safe": True,
                    "risk_level": RISK_MEDIUM,
                    "reason": "删除操作需要确认目标路径",
                    "requires_confirmation": True,
                    "suggestion": "建议使用 ask_user_confirmation 工具确认删除操作"
                }
        
        # ==================== L0 安全命令检查 ====================
        # 只读操作，无风险
        
        safe_commands = [
            "ls", "cat", "head", "tail", "grep", "awk", "sed", "cut", "less", "more",
            "df", "du", "free", "top", "htop", "ps", "uptime", "w", "who", "last",
            "netstat", "ss", "lsof", "iostat", "vmstat", "sar", "mpstat",
            "ping", "traceroute", "nslookup", "dig", "host", "curl", "wget --spider",
            "journalctl", "dmesg", "uname", "hostname", "date", "cal",
            "systemctl status", "systemctl list-", "systemctl show",
            "service.*status", "docker ps", "docker logs", "docker inspect", "docker stats",
            "kubectl get", "kubectl describe", "kubectl logs", "kubectl top",
            "git status", "git log", "git diff", "git branch",
            "find", "locate", "which", "whereis", "type",
            "env", "printenv", "set", "export -p",
            "id", "groups", "whoami",
        ]
        
        for safe_cmd in safe_commands:
            if re.match(f"^{safe_cmd}", command_lower) or command_lower.startswith(safe_cmd):
                return {
                    "safe": True,
                    "risk_level": RISK_SAFE,
                    "reason": "只读操作，无风险",
                    "requires_confirmation": False,
                    "suggestion": "安全命令，可直接执行"
                }
        
        # ==================== 默认处理 ====================
        # 未知命令，标记为中风险
        
        return {
            "safe": True,
            "risk_level": RISK_MEDIUM,
            "reason": "未识别的命令类型，需要人工确认",
            "requires_confirmation": True,
            "suggestion": "建议使用 ask_user_confirmation 工具确认此操作"
        }
    
    async def _save_diagnosis_plan(
        self,
        plan_name: str,
        check_type: str,
        commands: List[str],
        reasoning: str = "",
        expected_findings: List[str] = None
    ) -> Dict[str, Any]:
        """
        保存诊断计划
        """
        plan = {
            "plan_name": plan_name,
            "check_type": check_type,
            "commands": commands,
            "reasoning": reasoning,
            "expected_findings": expected_findings or [],
            "created_at": datetime.now().isoformat()
        }
        
        query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.file_manager.save_diagnosis_plan(plan, query_id)
        
        return {
            "success": True,
            "plan": plan,
            "saved_to": filepath
        }
    
    async def _save_execution_output(
        self,
        output: str,
        command: str = "",
        target_host: str = None
    ) -> Dict[str, Any]:
        """
        保存执行输出
        """
        query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.file_manager.save_execution_output(output, target_host or "local", query_id)
        
        return {
            "success": True,
            "target_host": target_host,
            "command": command,
            "saved_to": filepath
        }
    
    async def _query_knowledge_graph(
        self,
        service: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        查询知识图谱
        """
        try:
            from ..api.knowledge import get_knowledge_client
            client = get_knowledge_client()
            result = await client.query_topology(service=service, depth=depth)
            return {
                "success": True,
                "service": service,
                "topology": result
            }
        except Exception as e:
            return {
                "success": False,
                "service": service,
                "error": str(e)
            }
    
    async def _query_rag(
        self,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        查询 RAG 知识库
        """
        try:
            from ..api.knowledge import get_knowledge_client
            client = get_knowledge_client()
            result = await client.query_rag(query=query, top_k=top_k)
            return {
                "success": True,
                "query": query,
                "results": result
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
    
    async def _generate_playbook(
        self,
        target_host: str,
        tasks: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        生成 Ansible Playbook
        """
        try:
            import yaml
            
            playbook = [{
                "name": f"Diagnosis for {target_host}",
                "hosts": target_host,
                "gather_facts": False,
                "tasks": [
                    {
                        "name": task.get("name", f"Task {i}"),
                        "ansible.builtin.shell": task.get("command", ""),
                        "register": f"result_{i}"
                    }
                    for i, task in enumerate(tasks)
                ]
            }]
            
            query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.file_manager.save_playbook(playbook, target_host, query_id)
            
            return {
                "success": True,
                "target_host": target_host,
                "playbook": playbook,
                "saved_to": filepath
            }
        except Exception as e:
            return {
                "success": False,
                "target_host": target_host,
                "error": str(e)
            }
    
    async def _ask_user_confirmation(
        self,
        operation: str,
        risk: str,
        impact: str = "",
        command: str = "",
        target_host: str = ""
    ) -> Dict[str, Any]:
        """
        请求用户确认（高风险操作）— 自动发送邮件审批
        """
        from ..utils.email_sender import email_sender as _email_sender

        if not command and self._last_pending_command:
            command = self._last_pending_command.get("command", "")
            if not target_host:
                target_host = self._last_pending_command.get("target_host", "")

        to_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USER or ""
        commands_list = [command] if command else []
        final_target_host = target_host or "远程服务器"

        if to_email and operation:
            try:
                result = await _email_sender.send_approval_request(
                    to_email=to_email,
                    operation=operation,
                    risk=risk,
                    impact=impact,
                    commands=commands_list,
                    target_host=final_target_host,
                )
                if result.get("success"):
                    return {
                        "success": True,
                        "email_sent": True,
                        "approval_id": result.get("approval_id", ""),
                        "to_email": to_email,
                        "operation": operation,
                        "risk": risk,
                        "impact": impact,
                        "message": f"审批邮件已发送至 {to_email}，审批ID: {result.get('approval_id','')}。回复邮件含 APPROVE 或 批准 即批准执行。",
                        "next_step": "请使用 check_approval_status 工具检查审批状态，approval_id 为上述值。",
                    }
            except Exception as e:
                logger.error(f"Failed to send approval email: {e}")

        return {
            "success": True,
            "requires_confirmation": True,
            "operation": operation,
            "risk": risk,
            "impact": impact,
            "message": f"需要用户确认: {operation} (风险: {risk})",
            "email_sent": False,
            "email_error": "SMTP 不可用，请手动确认",
        }
    
    async def _send_approval_email(
        self,
        to_email: str,
        operation: str,
        risk: str,
        impact: str,
        commands: List[str],
        target_host: str
    ) -> Dict[str, Any]:
        """
        发送审批请求邮件
        """
        try:
            from ..utils.email_sender import email_sender
            
            result = await email_sender.send_approval_request(
                to_email=to_email,
                operation=operation,
                risk=risk,
                impact=impact,
                commands=commands,
                target_host=target_host
            )
            
            if result.get("success"):
                approval_id = result.get("approval_id")
                self._pending_approvals[approval_id] = {
                    "operation": operation,
                    "commands": commands,
                    "target_host": target_host,
                    "status": "pending"
                }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _check_approval_status(
        self,
        approval_id: str
    ) -> Dict[str, Any]:
        """
        检查审批状态
        """
        try:
            from ..utils.email_sender import email_sender
            
            result = await email_sender.check_approval(approval_id)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        等待审批完成（短轮询，每次 10 秒，默认 60 秒超时）
        """
        try:
            from ..utils.email_sender import email_sender
            
            result = await email_sender.wait_for_approval(
                approval_id=approval_id,
                timeout_seconds=timeout_seconds,
                poll_interval=10,
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _submit_diagnosis_result(
        self,
        problem_type: str,
        root_cause: str,
        impact: str,
        recommendation: str,
        risk_level: str = "MEDIUM",
        confidence: str = "MEDIUM",
        analysis_summary: str = "",
        **kwargs
    ) -> Dict[str, Any]:
        """
        提交诊断结果，标志着诊断流程的结束
        这是 ReAct 流程的终止工具，LLM 在分析完成后必须调用此工具提交最终诊断结果
        """
        return {
            "success": True,
            "is_final": True,
            "problem_type": problem_type,
            "root_cause": root_cause,
            "impact": impact,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "confidence": confidence,
            "analysis_summary": analysis_summary,
            "message": "诊断结果已提交",
            "extra_params": kwargs
        }
    
    async def _execute_approved_command(
        self,
        approval_id: str,
        wait_for_approval: bool = True,
        timeout_seconds: int = 3600
    ) -> Dict[str, Any]:
        """
        等待审批并执行命令（已审批通过的命令直接执行，跳过安全检查）
        """
        try:
            from ..utils.email_sender import email_sender
            
            if wait_for_approval:
                result = await email_sender.wait_for_approval(
                    approval_id=approval_id,
                    timeout_seconds=timeout_seconds
                )
                
                if not result.get("success"):
                    return result
                
                if not result.get("approved"):
                    return {
                        "success": True,
                        "approved": False,
                        "message": "操作被拒绝"
                    }
                
                approval = result.get("approval", {})
                commands = approval.get("commands", [])
                target_host = approval.get("target_host", "")
                
                execution_results = []
                for cmd in commands:
                    exec_result = await self._execute_direct(
                        command=cmd,
                        target_host=target_host
                    )
                    execution_results.append(exec_result)
                
                return {
                    "success": True,
                    "approved": True,
                    "executed": True,
                    "execution_results": execution_results
                }
            else:
                return await self._check_approval_status(approval_id)
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_direct(
        self,
        command: str,
        target_host: str = ""
    ) -> Dict[str, Any]:
        """
        直接执行命令（跳过安全检查，仅用于已审批通过的命令）
        """
        try:
            if target_host:
                effective_ssh_user = settings.SSH_USER or "jaci"
                ssh_opts = f"-o ConnectTimeout={settings.SSH_CONNECT_TIMEOUT}"
                if not settings.SSH_STRICT_HOST_KEY_CHECK:
                    ssh_opts += " -o StrictHostKeyChecking=no"
                escaped_command = shlex.quote(command)
                exec_command = f"ssh {ssh_opts} -i {settings.SSH_KEY_PATH} {effective_ssh_user}@{target_host} {escaped_command}"
            else:
                exec_command = command

            result = subprocess.run(
                exec_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            output = result.stdout + "\n" + result.stderr

            return {
                "success": result.returncode == 0,
                "target_host": target_host,
                "command": command,
                "output": output,
                "return_code": result.returncode,
                "bypass_security": True,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": "Command execution timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": str(e),
            }
    
    async def _parse_logs(
        self,
        log_path: str,
        time_range: List[str] = None,
        error_only: bool = False
    ) -> Dict[str, Any]:
        """
        解析日志数据
        """
        try:
            path = Path(log_path)
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Log path not found: {log_path}"
                }
            
            logs = []
            log_parquet_path = path / "log-parquet"
            
            if log_parquet_path.exists():
                import pandas as pd
                for parquet_file in log_parquet_path.glob("*.parquet"):
                    try:
                        df = pd.read_parquet(parquet_file)
                        for _, row in df.iterrows():
                            logs.append(row.to_dict())
                    except Exception as e:
                        logger.error(f"Error loading {parquet_file}: {e}")
            
            error_logs = [l for l in logs if 'error' in str(l).lower() or 'exception' in str(l).lower()]
            
            return {
                "success": True,
                "total_logs": len(logs),
                "error_logs": len(error_logs),
                "sample_logs": logs[:5] if logs else [],
                "log_path": log_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_metrics_and_detect_anomalies(
        self,
        metric_path: str,
        services: List[str] = None,
        anomaly_threshold: float = 0.95
    ) -> Dict[str, Any]:
        """
        加载指标数据并检测异常
        """
        try:
            from ..algorithm.gnn_rca import GNNRootCauseAnalyzer
            
            analyzer = GNNRootCauseAnalyzer(data_path=metric_path)
            result = analyzer.detect_anomalies(threshold=anomaly_threshold)
            
            return {
                "success": True,
                "anomaly_services": result.get("anomaly_services", []),
                "anomaly_scores": result.get("anomaly_scores", {}),
                "threshold": anomaly_threshold
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _build_service_graph(
        self,
        services: List[str],
        dependencies: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        构建服务依赖图
        """
        try:
            from ..algorithm.gnn_rca import GNNRootCauseAnalyzer
            
            analyzer = GNNRootCauseAnalyzer()
            graph = analyzer.build_service_graph(services, dependencies)
            
            return {
                "success": True,
                "num_nodes": graph.num_nodes if hasattr(graph, 'num_nodes') else len(services),
                "num_edges": graph.num_edges if hasattr(graph, 'num_edges') else len(dependencies or []),
                "services": services
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _gnn_root_cause_analysis(
        self,
        data_path: str,
        anomaly_services: List[str] = None,
        top_k: int = 3,
        model_type: str = "GAT"
    ) -> Dict[str, Any]:
        """
        使用 GNN 进行根因分析
        """
        try:
            from ..algorithm.gnn_rca import GNNRootCauseAnalyzer
            
            analyzer = GNNRootCauseAnalyzer(data_path=data_path, model_type=model_type)
            result = analyzer.analyze(top_k=top_k)
            
            return {
                "success": True,
                "root_causes": result.get("root_causes", []),
                "propagation_path": result.get("propagation_path", []),
                "confidence": result.get("confidence", "MEDIUM")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_rca_report(
        self,
        rca_result: Dict[str, Any],
        logs: List[Dict] = None,
        metrics: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        生成根因分析报告
        """
        try:
            report = {
                "title": "GNN 根因分析报告",
                "generated_at": datetime.now().isoformat(),
                "root_causes": rca_result.get("root_causes", []),
                "propagation_path": rca_result.get("propagation_path", []),
                "confidence": rca_result.get("confidence", "MEDIUM"),
                "logs_analyzed": len(logs) if logs else 0,
                "metrics_analyzed": list(metrics.keys()) if metrics else []
            }
            
            query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.file_manager.save_file(
                json.dumps(report, ensure_ascii=False, indent=2),
                f"rca_report_{query_id}.json"
            )
            
            return {
                "success": True,
                "report": report,
                "saved_to": filepath
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _list_data_sources(self) -> Dict[str, Any]:
        """
        列出所有可用的数据源
        """
        try:
            from ..utils.data_source_manager import data_source_manager
            
            sources = data_source_manager.list_available_sources()
            
            return {
                "success": True,
                "data_sources": sources,
                "default_source": settings.DEFAULT_DATA_SOURCE
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_data_from_source(
        self,
        source_name: str,
        data_type: str,
        time_range: List[str] = None,
        filters: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        从指定数据源加载数据
        """
        try:
            from ..utils.data_source_manager import data_source_manager
            
            time_range_tuple = tuple(time_range) if time_range else None
            
            result = await data_source_manager.load_data(
                source_name=source_name,
                data_type=data_type,
                time_range=time_range_tuple,
                filters=filters,
                **kwargs
            )
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "source_name": source_name,
                "data_type": data_type
            }
    
    async def _query_grafana_logs(
        self,
        query: str,
        start: str = "",
        end: str = "",
        limit: int = 100,
        datasource: str = "",
    ) -> Dict[str, Any]:
        """
        通过 Grafana 代理查询 Loki 日志

        使用 Grafana 的 Data Source Proxy API 查询 Loki 日志数据，
        无需直接暴露 Loki 端口（3100），请求经过 Grafana 认证代理。

        Args:
            query: LogQL 查询语句，如 '{app="aiops-backend"} |= "error"'
            start: 开始时间，"1h ago" / "2d ago" / ISO 格式，空=1小时前
            end:   结束时间，"now" / ISO 格式，空=当前
            limit: 最大返回条数（默认 100，最大 5000）
            datasource: Grafana 数据源名称（默认 "Loki"）

        Returns:
            {
                "success": true,
                "datasource": "Loki",
                "query": '{app="... "} |= "error"',
                "time_range": "2024-... → 2024-...",
                "result_count": 42,
                "results": [
                    {"timestamp": "...", "line": "ERROR: ...", "labels": {...}}
                ],
                "stats": {"query_time_ms": 235}
            }
        """
        try:
            from .grafana_log_client import GrafanaLogClient

            client = GrafanaLogClient()
            try:
                result = await client.query_logs(
                    query=query,
                    start=start,
                    end=end,
                    limit=limit,
                    datasource=datasource,
                )
                return result
            finally:
                await client.close()

        except ImportError as e:
            return {
                "success": False,
                "error": f"Grafana log client not available: {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }
    
    async def _mcp_call(
        self,
        tool: str,
        params: dict = {},
    ) -> Dict[str, Any]:
        """
        通过 MCP (Model Context Protocol) 调用可观测数据工具

        Agent 通过此工具统一获取 Grafana/Prometheus 的可观测数据，
        无需了解底层数据源的差异。

        Args:
            tool: MCP Server 上注册的工具名，可选值：
                - query_metrics:      通过 Grafana 代理查询 Prometheus 指标
                - query_metrics_range: 查询 Prometheus 范围数据
                - query_logs:         通过 Grafana 代理查询 Loki 日志
                - list_dashboards:    列出 Grafana 仪表盘
                - get_dashboard:      获取仪表盘详情
                - list_alerts:        列出 Grafana 告警
                - get_rag_overview:   RAG 服务健康快照（推荐用于 RAG 故障诊断）
                - get_gpu_overview:   主机与 GPU 健康快照（推荐用于 GPU 资源检查）
                - get_vllm_overview:  vLLM 推理引擎健康快照（推荐用于本地模型/推理性能检查）
            params: 工具参数 dict，具体取决于 tool 类型

        Returns:
            工具执行的响应结果
        """
        try:
            from ..mcp.client import McpClient

            client = McpClient()
            try:
                result = await client.call_tool(tool, params)
                return result
            finally:
                await client.close()

        except ImportError as e:
            # fallback: 如果 MCP Client 不可用，尝试直接调用 Grafana 客户端
            logger.warning(f"MCP client unavailable, trying direct call: {e}")
            if tool == "query_logs":
                return await self._query_grafana_logs(**params)
            return {
                "success": False,
                "error": f"MCP module not available: {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": tool,
            }
    
    async def _detect_log_anomalies(
        self,
        logs: List[str] = None,
        data_path: str = None,
        model_path: str = None,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        使用 DeepLog 模型检测日志异常（仅推理，不训练）
        
        Args:
            logs: 原始日志列表（优先）
            data_path: 结构化日志文件路径
            model_path: 模型文件路径
            top_k: 预测的 Top-k 事件数
            
        Returns:
            检测结果
        """
        try:
            import sys
            log_analysis_dir = Path(__file__).parent.parent.parent.parent.parent / "time_sequence_detection" / "Log_Analysis_LSTM"
            
            if log_analysis_dir.exists():
                sys.path.insert(0, str(log_analysis_dir.parent))
                from Log_Analysis_LSTM.skill import LogAnalysisSkill
                
                default_model_path = log_analysis_dir / "models" / "deeplog_model.pth"
                effective_model_path = model_path or str(default_model_path)
                
                skill = LogAnalysisSkill(
                    model_path=effective_model_path,
                    top_k=top_k,
                    auto_load=True
                )
                
                if logs:
                    result = await skill.detect_logs(logs)
                else:
                    default_data_path = log_analysis_dir / "data" / "cleaned" / "logs_structured.csv"
                    effective_data_path = data_path or str(default_data_path)
                    result = await skill.detect_from_file(data_path=effective_data_path)
                
                anomalies_summary = []
                for anomaly in result.anomalies[:10]:
                    anomalies_summary.append({
                        "timestamp": anomaly.timestamp,
                        "expected_events": anomaly.expected_events,
                        "actual_event": anomaly.actual_event,
                        "actual_template": anomaly.actual_template
                    })
                
                return {
                    "success": True,
                    "total_logs": result.total_logs,
                    "total_predictions": result.total_predictions,
                    "anomalies_detected": result.anomalies_detected,
                    "anomaly_rate": result.anomaly_rate,
                    "anomaly_event_stats": result.anomaly_event_stats,
                    "anomalies_sample": anomalies_summary
                }
            else:
                return {
                    "success": False,
                    "error": f"Log analysis module not found at {log_analysis_dir}",
                    "hint": "Please ensure the Log_Analysis_LSTM directory exists and model is trained"
                }
                
        except FileNotFoundError as e:
            return {
                "success": False,
                "error": f"Model file not found: {str(e)}",
                "hint": "Please run training scripts first: python 1_generate_data.py && python 2_parse_logs.py && python 3_train_model.py"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _cluster_alerts(
        self,
        alerts: List[Dict[str, str]],
        eps: float = 0.5,
        min_samples: int = 2,
        w_time: float = 0.05,
        w_sem: float = 1.0,
        w_topo: float = 0.2
    ) -> Dict[str, Any]:
        """
        智能告警聚合（Drain + TF-IDF + Word2Vec + DBSCAN）
        
        Args:
            alerts: 告警列表，每条包含 time, node_id, raw_msg
            eps: DBSCAN 邻域半径，默认 0.5
            min_samples: DBSCAN 最小样本数，默认 2
            w_time: 时间距离权重
            w_sem: 语义距离权重
            w_topo: 拓扑距离权重
            
        Returns:
            聚合结果
        """
        try:
            import sys
            alert_cluster_dir = Path(__file__).parent.parent.parent.parent.parent / "time_sequence_detection" / "alert_aggregation_Drain_DBSCAN"
            
            if not alert_cluster_dir.exists():
                return {
                    "success": False,
                    "error": f"Alert cluster module not found at {alert_cluster_dir}",
                    "hint": "Please ensure the alert_aggregation_Drain_DBSCAN directory exists"
                }
            
            sys.path.insert(0, str(alert_cluster_dir))
            
            from config import DEFAULT_W2V_MODEL_PATH
            from skill import AlertClusterSkill
            
            model_path = alert_cluster_dir / "models" / "it_word2vec.model"
            
            if not model_path.exists():
                return {
                    "success": False,
                    "error": f"Word2Vec model not found at {model_path}",
                    "hint": "Please run training first: cd alert_aggregation_Drain_DBSCAN && python main.py"
                }
            
            skill = AlertClusterSkill(
                w2v_model_path=str(model_path),
                auto_load=True,
                eps=eps,
                min_samples=min_samples,
                w_time=w_time,
                w_sem=w_sem,
                w_topo=w_topo,
            )
            
            result = await skill.execute(alerts)
            
            clusters_summary = []
            for cluster in result.clusters:
                clusters_summary.append({
                    "cluster_id": cluster.cluster_id,
                    "alert_count": cluster.alert_count,
                    "representative_alert": cluster.representative_alert,
                    "affected_nodes": cluster.affected_nodes,
                })
            
            compression_ratio = result.total_input / max(len(result.clusters), 1)
            
            return {
                "success": True,
                "total_input": result.total_input,
                "noise_count": result.noise_count,
                "cluster_count": len(result.clusters),
                "clusters": clusters_summary,
                "compression_ratio": f"{compression_ratio:.1f}:1",
                "parameters": {
                    "eps": eps,
                    "min_samples": min_samples,
                    "w_time": w_time,
                    "w_sem": w_sem,
                    "w_topo": w_topo,
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _analyze_trace(
        self,
        trace_id: str = None,
        service_name: str = None,
        error_only: bool = False,
        slow_only: bool = False,
        min_duration_ms: int = None,
        lookback: str = "1h",
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        分布式链路追踪分析工具
        
        基于 OpenTelemetry + Tempo 的分布式追踪分析能力：
        1. 通过 Trace ID 查询完整调用链
        2. 搜索错误链路或慢请求链路
        3. 分析服务调用关系和性能瓶颈
        4. 识别错误传播路径
        
        Args:
            trace_id: Trace ID，如果提供则查询特定调用链
            service_name: 服务名称，用于过滤搜索结果
            error_only: 是否只搜索包含错误的链路
            slow_only: 是否只搜索慢请求链路
            min_duration_ms: 最小持续时间阈值（毫秒）
            lookback: 回溯时间范围，如 "1h", "30m", "24h"
            limit: 返回结果数量限制
            
        Returns:
            链路分析结果
        """
        try:
            from ..observability.tempo_query import TempoQueryClient
            from ..observability.config import get_observability_config
            
            config = get_observability_config()
            
            async with TempoQueryClient(config=config) as client:
                if trace_id:
                    trace = await client.query_trace_by_id(trace_id)
                    if not trace:
                        return {
                            "success": False,
                            "error": f"Trace {trace_id} not found"
                        }
                    
                    performance = await client.analyze_trace_performance(trace_id)
                    
                    return {
                        "success": True,
                        "trace_id": trace_id,
                        "trace": trace.to_dict(),
                        "span_tree": trace.get_span_tree(),
                        "performance_analysis": performance,
                        "services_involved": trace.services_involved,
                        "error_count": len(trace.error_spans),
                        "total_duration_ms": trace.total_duration_ms
                    }
                
                else:
                    if error_only:
                        result = await client.search_error_traces(
                            service_name=service_name,
                            lookback=lookback,
                            limit=limit
                        )
                    elif slow_only or min_duration_ms:
                        min_duration = f"{min_duration_ms}ms" if min_duration_ms else "500ms"
                        result = await client.search_slow_traces(
                            min_duration=min_duration,
                            service_name=service_name,
                            lookback=lookback,
                            limit=limit
                        )
                    else:
                        result = await client.search_traces(
                            service_name=service_name,
                            lookback=lookback,
                            limit=limit
                        )
                    
                    return {
                        "success": True,
                        "total_traces": result.total,
                        "traces": result.traces[:limit],
                        "metrics": result.metrics,
                        "search_params": {
                            "service_name": service_name,
                            "error_only": error_only,
                            "slow_only": slow_only,
                            "min_duration_ms": min_duration_ms,
                            "lookback": lookback
                        }
                    }
                    
        except ImportError as e:
            return {
                "success": False,
                "error": f"Observability module not available: {e}",
                "hint": "Please ensure app/observability module is properly configured"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _analyze_service_dependency(
        self,
        lookback: str = "24h",
        service_filter: List[str] = None
    ) -> Dict[str, Any]:
        """
        服务依赖关系分析工具
        
        从 Trace 数据中提取服务调用关系，构建服务依赖图
        
        Args:
            lookback: 回溯时间范围
            service_filter: 服务过滤列表，只分析指定的服务
            
        Returns:
            服务依赖图数据
        """
        try:
            from ..observability.tempo_query import TempoQueryClient
            from ..observability.config import get_observability_config
            import numpy as np
            from collections import defaultdict
            
            config = get_observability_config()
            
            async with TempoQueryClient(config=config) as client:
                result = await client.search_traces(lookback=lookback, limit=500)
                
                edges = defaultdict(lambda: {"count": 0, "errors": 0, "latencies": []})
                services = set()
                
                for trace_data in result.traces:
                    trace_id = trace_data.get("traceID")
                    if not trace_id:
                        continue
                    
                    trace = await client.query_trace_by_id(trace_id)
                    if not trace:
                        continue
                    
                    for span in trace.spans:
                        services.add(span.service_name)
                        
                        if span.parent_span_id:
                            parent = next(
                                (s for s in trace.spans if s.span_id == span.parent_span_id),
                                None
                            )
                            if parent:
                                src = parent.service_name
                                dst = span.service_name
                                
                                if service_filter:
                                    if src not in service_filter and dst not in service_filter:
                                        continue
                                
                                key = (src, dst)
                                edges[key]["count"] += 1
                                if span.is_error:
                                    edges[key]["errors"] += 1
                                if span.duration_ms:
                                    edges[key]["latencies"].append(span.duration_ms)
                
                edge_list = []
                for (src, dst), data in edges.items():
                    latencies = data["latencies"]
                    edge_list.append({
                        "source": src,
                        "target": dst,
                        "call_count": data["count"],
                        "error_count": data["errors"],
                        "error_rate": round(data["errors"] / data["count"] * 100, 2) if data["count"] > 0 else 0,
                        "avg_latency_ms": round(np.mean(latencies), 2) if latencies else 0,
                        "p99_latency_ms": round(np.percentile(latencies, 99), 2) if len(latencies) > 10 else 0
                    })
                
                edge_list.sort(key=lambda x: x["call_count"], reverse=True)
                
                return {
                    "success": True,
                    "nodes": [{"id": s, "name": s} for s in sorted(services)],
                    "edges": edge_list,
                    "total_services": len(services),
                    "total_edges": len(edge_list),
                    "lookback": lookback
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== ServiceNow 工具 ====================
    
    async def _get_servicenow_client(self):
        """获取或初始化 ServiceNow 客户端"""
        if not SERVICENOW_AVAILABLE:
            return None
        
        if self._servicenow_client is None:
            self._servicenow_client = get_servicenow_client()
        
        if not self._servicenow_client.is_connected:
            await self._servicenow_client.connect()
        
        return self._servicenow_client
    
    async def _query_servicenow_ci(
        self,
        ci_name: str = None,
        ci_type: str = None,
        ip_address: str = None,
        status: str = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        查询 ServiceNow CMDB 配置项
        
        Args:
            ci_name: 配置项名称
            ci_type: 配置项类型 (server, network_device, application, database, cluster)
            ip_address: IP 地址
            status: 运行状态 (operational, non_operational)
            limit: 返回数量限制
        """
        if not SERVICENOW_AVAILABLE:
            return {
                "success": False,
                "error": "ServiceNow client not available. Please install dependencies and configure environment variables."
            }
        
        try:
            client = await self._get_servicenow_client()
            if client is None or not client.is_connected:
                return {
                    "success": False,
                    "error": f"ServiceNow connection failed: {client.connection_error if client else 'Not configured'}"
                }
            
            return await client.query_ci(
                ci_name=ci_name,
                ci_type=ci_type,
                ip_address=ip_address,
                status=status,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to query ServiceNow CI: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _query_servicenow_changes(
        self,
        ci_name: str = None,
        change_number: str = None,
        change_type: str = None,
        state: str = None,
        lookback_hours: int = 72,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        查询 ServiceNow 变更记录
        
        Args:
            ci_name: 关联的配置项名称
            change_number: 变更编号
            change_type: 变更类型 (normal, emergency, standard)
            state: 变更状态
            lookback_hours: 回溯时间（小时）
            limit: 返回数量限制
        """
        if not SERVICENOW_AVAILABLE:
            return {
                "success": False,
                "error": "ServiceNow client not available"
            }
        
        try:
            client = await self._get_servicenow_client()
            if client is None or not client.is_connected:
                return {
                    "success": False,
                    "error": f"ServiceNow connection failed: {client.connection_error if client else 'Not configured'}"
                }
            
            return await client.query_changes(
                ci_name=ci_name,
                change_number=change_number,
                change_type=change_type,
                state=state,
                lookback_hours=lookback_hours,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to query ServiceNow changes: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _query_servicenow_incidents(
        self,
        ci_name: str = None,
        incident_number: str = None,
        priority: str = None,
        state: str = None,
        lookback_hours: int = 72,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        查询 ServiceNow 事件工单
        
        Args:
            ci_name: 关联的配置项名称
            incident_number: 工单编号
            priority: 优先级 (1-critical, 2-high, 3-moderate, 4-low)
            state: 工单状态
            lookback_hours: 回溯时间（小时）
            limit: 返回数量限制
        """
        if not SERVICENOW_AVAILABLE:
            return {
                "success": False,
                "error": "ServiceNow client not available"
            }
        
        try:
            client = await self._get_servicenow_client()
            if client is None or not client.is_connected:
                return {
                    "success": False,
                    "error": f"ServiceNow connection failed: {client.connection_error if client else 'Not configured'}"
                }
            
            return await client.query_incidents(
                ci_name=ci_name,
                incident_number=incident_number,
                priority=priority,
                state=state,
                lookback_hours=lookback_hours,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Failed to query ServiceNow incidents: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _analyze_change_as_root_cause(
        self,
        node_name: str,
        problem_time: str = None,
        lookback_hours: int = 72
    ) -> Dict[str, Any]:
        """
        分析变更是否可能是问题的根因
        
        当查询到某个节点疑似有问题时，调用此工具检查该节点最近是否发生过变更，
        并分析这个变更是否可能是导致问题的根因。
        
        Args:
            node_name: 节点名称
            problem_time: 问题发生时间
            lookback_hours: 回溯时间（小时）
            
        Returns:
            变更根因分析报告
        """
        if not SERVICENOW_AVAILABLE:
            return {
                "success": False,
                "error": "ServiceNow client not available"
            }
        
        try:
            client = await self._get_servicenow_client()
            if client is None or not client.is_connected:
                return {
                    "success": False,
                    "error": f"ServiceNow connection failed: {client.connection_error if client else 'Not configured'}"
                }
            
            return await client.analyze_change_as_root_cause(
                node_name=node_name,
                problem_time=problem_time,
                lookback_hours=lookback_hours
            )
        except Exception as e:
            logger.error(f"Failed to analyze change as root cause: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _get_servicenow_node_health(
        self,
        node_name: str = None,
        ip_address: str = None,
        lookback_hours: int = 72
    ) -> Dict[str, Any]:
        """
        获取节点综合健康状态
        
        整合 CMDB 信息、关联工单、变更历史，生成健康报告。
        
        Args:
            node_name: 节点名称或主机名
            ip_address: IP 地址
            lookback_hours: 回溯时间（小时）
            
        Returns:
            综合健康报告
        """
        if not SERVICENOW_AVAILABLE:
            return {
                "success": False,
                "error": "ServiceNow client not available"
            }
        
        try:
            client = await self._get_servicenow_client()
            if client is None or not client.is_connected:
                return {
                    "success": False,
                    "error": f"ServiceNow connection failed: {client.connection_error if client else 'Not configured'}"
                }
            
            return await client.get_node_health(
                node_name=node_name,
                ip_address=ip_address,
                lookback_hours=lookback_hours
            )
        except Exception as e:
            logger.error(f"Failed to get node health: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        获取 LLM function calling 格式的工具定义
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "执行 shell 命令，用于诊断和排查问题。本地命令不需要设置 target_host，远程命令需要设置 target_host 使用 SSH 连接",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "要执行的 shell 命令"
                            },
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器 IP 或主机名。本地命令不需要设置此参数；Docker 命令使用 docker exec 不需要设置此参数；只有远程服务器才需要设置"
                            },
                            "risk_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "description": "操作风险等级，默认为 low"
                            },
                            "ssh_user": {
                                "type": "string",
                                "description": "SSH 用户名，如果用户查询中提到了用户名则使用该用户名，否则使用默认配置"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_diagnosis_plan",
                    "description": "保存诊断计划到中间文件，用于记录和后续分析",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "plan_name": {
                                "type": "string",
                                "description": "计划名称，如 'disk_space_check'"
                            },
                            "check_type": {
                                "type": "string",
                                "description": "检查类型，如 disk, network, memory, general"
                            },
                            "commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要执行的命令列表"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "选择这些命令的原因"
                            }
                        },
                        "required": ["plan_name", "check_type", "commands"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_execution_output",
                    "description": "保存命令执行输出到中间文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "output": {
                                "type": "string",
                                "description": "命令执行输出内容"
                            },
                            "command": {
                                "type": "string",
                                "description": "执行的命令"
                            },
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器（可选）"
                            }
                        },
                        "required": ["output"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_knowledge_graph",
                    "description": "查询知识图谱获取服务拓扑关系和依赖信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service": {
                                "type": "string",
                                "description": "服务名称"
                            },
                            "depth": {
                                "type": "integer",
                                "description": "查询深度，默认为 2"
                            }
                        },
                        "required": ["service"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_rag",
                    "description": "查询 RAG 知识库获取相关文档和历史案例",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "查询问题或关键词"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "返回结果数量，默认为 5"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_playbook",
                    "description": "生成 Ansible Playbook 用于自动化批量执行",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器"
                            },
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "command": {"type": "string"}
                                    }
                                },
                                "description": "任务列表"
                            }
                        },
                        "required": ["target_host", "tasks"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_user_confirmation",
                    "description": "向用户请求确认高风险操作，如重启服务、删除文件等",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "description": "要执行的操作描述"
                            },
                            "risk": {
                                "type": "string",
                                "description": "风险说明"
                            },
                            "impact": {
                                "type": "string",
                                "description": "可能的影响"
                            }
                        },
                        "required": ["operation", "risk"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "send_approval_email",
                    "description": "发送审批请求邮件，用于高风险操作的人工审批。邮件包含操作详情和审批ID，用户回复 APPROVE 或 REJECT 进行审批",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to_email": {
                                "type": "string",
                                "description": "接收审批邮件的邮箱地址"
                            },
                            "operation": {
                                "type": "string",
                                "description": "要执行的操作描述"
                            },
                            "risk": {
                                "type": "string",
                                "description": "风险等级: low, medium, high"
                            },
                            "impact": {
                                "type": "string",
                                "description": "操作可能的影响"
                            },
                            "commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要执行的命令列表"
                            },
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器"
                            }
                        },
                        "required": ["to_email", "operation", "risk", "impact", "commands", "target_host"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_approval_status",
                    "description": "检查审批状态，查看用户是否已回复邮件进行审批",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "approval_id": {
                                "type": "string",
                                "description": "审批ID，在发送审批邮件时返回"
                            }
                        },
                        "required": ["approval_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_approved_command",
                    "description": "等待用户审批并执行命令。如果用户批准则执行，否则返回拒绝信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "approval_id": {
                                "type": "string",
                                "description": "审批ID"
                            },
                            "wait_for_approval": {
                                "type": "boolean",
                                "description": "是否等待审批，默认为 true"
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "等待超时时间（秒），默认为 3600 秒"
                            }
                        },
                        "required": ["approval_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_diagnosis_result",
                    "description": "【重要】提交最终诊断结果并结束诊断流程。当完成所有检查、分析出问题根因后，必须调用此工具提交诊断结论。这是诊断流程的终止标志。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "problem_type": {
                                "type": "string",
                                "enum": ["disk", "memory", "cpu", "network", "service", "configuration", "unknown", "none"],
                                "description": "问题类型"
                            },
                            "root_cause": {
                                "type": "string",
                                "description": "根本原因分析，详细说明导致问题的原因"
                            },
                            "impact": {
                                "type": "string",
                                "description": "影响范围，说明受影响的服务器、服务或用户"
                            },
                            "recommendation": {
                                "type": "string",
                                "description": "建议的修复操作或下一步行动"
                            },
                            "risk_level": {
                                "type": "string",
                                "enum": ["LOW", "MEDIUM", "HIGH"],
                                "description": "修复操作的风险等级"
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["HIGH", "MEDIUM", "LOW"],
                                "description": "诊断结论的置信度"
                            },
                            "analysis_summary": {
                                "type": "string",
                                "description": "分析过程摘要，包括执行的检查命令和关键发现"
                            }
                        },
                        "required": ["problem_type", "root_cause", "impact", "recommendation"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "parse_logs",
                    "description": "解析日志数据，统计日志数量和错误日志",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "log_path": {
                                "type": "string",
                                "description": "日志数据路径"
                            },
                            "time_range": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "时间范围 [开始时间, 结束时间]"
                            },
                            "error_only": {
                                "type": "boolean",
                                "description": "是否只解析错误日志，默认为 false"
                            }
                        },
                        "required": ["log_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "load_metrics_and_detect_anomalies",
                    "description": "加载指标数据并使用 Isolation Forest 检测异常服务",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metric_path": {
                                "type": "string",
                                "description": "指标数据路径"
                            },
                            "services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要分析的服务列表"
                            },
                            "anomaly_threshold": {
                                "type": "number",
                                "description": "异常检测阈值，默认 0.95"
                            }
                        },
                        "required": ["metric_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "build_service_graph",
                    "description": "构建服务依赖图，用于 GNN 分析",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "服务列表"
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source": {"type": "string"},
                                        "target": {"type": "string"}
                                    }
                                },
                                "description": "服务依赖关系列表"
                            }
                        },
                        "required": ["services"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "gnn_root_cause_analysis",
                    "description": "使用 GNN 模型进行根因分析，返回 Top-K 根因候选",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_path": {
                                "type": "string",
                                "description": "数据路径"
                            },
                            "anomaly_services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "异常服务列表"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "返回的根因数量，默认 3"
                            },
                            "model_type": {
                                "type": "string",
                                "enum": ["GAT", "GCN", "GraphSAGE"],
                                "description": "GNN 模型类型，默认 GAT"
                            }
                        },
                        "required": ["data_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_rca_report",
                    "description": "生成根因分析报告",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rca_result": {
                                "type": "object",
                                "description": "GNN 分析结果"
                            },
                            "logs": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "分析的日志数据"
                            },
                            "metrics": {
                                "type": "object",
                                "description": "分析的指标数据"
                            }
                        },
                        "required": ["rca_result"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_data_sources",
                    "description": "列出所有可用的数据源，包括本地文件系统、监控系统、日志平台等。在加载数据前应先调用此工具查看可用数据源。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "load_data_from_source",
                    "description": "从指定数据源加载日志、指标或链路追踪数据。支持多种数据源：local(本地文件), prometheus, elasticsearch, loki, jaeger, aliyun_monitor。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_name": {
                                "type": "string",
                                "enum": ["local", "prometheus", "elasticsearch", "loki", "jaeger", "aliyun_monitor"],
                                "description": "数据源名称"
                            },
                            "data_type": {
                                "type": "string",
                                "enum": ["logs", "metrics", "traces"],
                                "description": "数据类型"
                            },
                            "time_range": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "时间范围 [开始时间, 结束时间]，格式: YYYY-MM-DD HH:MM:SS"
                            },
                            "filters": {
                                "type": "object",
                                "description": "过滤条件，如服务名、日志级别等"
                            },
                            "data_path": {
                                "type": "string",
                                "description": "数据路径（仅用于 local 数据源）"
                            },
                            "query": {
                                "type": "string",
                                "description": "查询语句（用于 prometheus/elasticsearch/loki）"
                            },
                            "service": {
                                "type": "string",
                                "description": "服务名称（用于 jaeger）"
                            }
                        },
                        "required": ["source_name", "data_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_call",
                    "description": "通过 MCP (Model Context Protocol) 调用可观测数据工具，查询 Grafana/Prometheus/Loki 的指标、日志和告警。支持查询服务拓扑(traces_service_graph_request_total)、PromQL 指标、Loki 日志、Grafana 告警，以及 RAG/GPU/vLLM 健康快照",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tool": {
                                "type": "string",
                                "enum": ["query_metrics", "query_metrics_range", "query_logs", "list_dashboards", "get_dashboard", "list_alerts", "get_rag_overview", "get_gpu_overview", "get_vllm_overview"],
                                "description": "MCP 工具名。query_metrics=查询 Prometheus 指标, query_metrics_range=范围查询, query_logs=查询 Loki 日志, list_dashboards=列出仪表盘, get_dashboard=获取仪表盘详情, list_alerts=列出告警, get_rag_overview=RAG服务健康快照(请求量/缓存命中率/质量/耗时/错误日志), get_gpu_overview=主机与GPU健康快照(CPU/内存/磁盘/GPU利用率/显存/温度/功耗), get_vllm_overview=vLLM推理引擎健康快照(引擎状态/KV Cache/QPS/TTFT/Token)"
                            },
                            "params": {
                                "type": "object",
                                "description": "工具参数。对于 query_metrics/query_metrics_range: {query: PromQL语句, time/start/end: 时间}; 对于 query_logs: {query: LogQL语句, start: 时间, limit: 条数}; 对于 list_alerts: {state: 告警状态}; 对于 get_rag_overview/get_gpu_overview/get_vllm_overview: {lookback: 回看窗口如 1h}"
                            }
                        },
                        "required": ["tool", "params"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "detect_log_anomalies",
                    "description": "使用 DeepLog 模型检测日志序列异常。基于 LSTM 学习日志事件的正常模式，预测下一个最可能出现的日志事件，如果实际事件不在预测的 Top-k 列表中则判定为异常。仅做推理，不进行训练。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "logs": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "原始日志列表，每行一条日志。如果提供此参数则优先使用"
                            },
                            "data_path": {
                                "type": "string",
                                "description": "结构化日志文件路径（CSV格式），如果不提供 logs 则使用此路径"
                            },
                            "model_path": {
                                "type": "string",
                                "description": "模型文件路径，默认使用预训练模型"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "预测的 Top-k 事件数，默认为 3。值越小检测越敏感"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cluster_alerts",
                    "description": "智能告警聚合工具。使用 Drain + TF-IDF + Word2Vec + DBSCAN 对告警进行聚类压缩，适用于告警风暴场景。将大量相似告警聚合为少数几个聚类，便于快速定位问题。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "alerts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "time": {"type": "string", "description": "告警时间，格式: YYYY-MM-DD HH:MM:SS"},
                                        "node_id": {"type": "string", "description": "告警来源节点ID"},
                                        "raw_msg": {"type": "string", "description": "原始告警消息"}
                                    }
                                },
                                "description": "告警列表，每条告警包含 time, node_id, raw_msg 三个字段"
                            },
                            "eps": {
                                "type": "number",
                                "description": "DBSCAN 邻域半径，默认 0.5。值越小聚类越严格，值越大聚类越宽松"
                            },
                            "min_samples": {
                                "type": "integer",
                                "description": "DBSCAN 最小样本数，默认 2。小于此数量的告警会被视为噪声"
                            },
                            "w_time": {
                                "type": "number",
                                "description": "时间距离权重，默认 0.05"
                            },
                            "w_sem": {
                                "type": "number",
                                "description": "语义距离权重，默认 1.0"
                            },
                            "w_topo": {
                                "type": "number",
                                "description": "拓扑距离权重，默认 0.2"
                            }
                        },
                        "required": ["alerts"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_trace",
                    "description": "分布式链路追踪分析工具。基于 OpenTelemetry + Tempo 查询和分析分布式调用链，用于故障定位和性能瓶颈识别。支持：1) 通过 Trace ID 查询完整调用链；2) 搜索错误链路或慢请求；3) 分析服务调用关系。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "trace_id": {
                                "type": "string",
                                "description": "Trace ID，如果提供则查询特定调用链的详细信息"
                            },
                            "service_name": {
                                "type": "string",
                                "description": "服务名称，用于过滤搜索结果"
                            },
                            "error_only": {
                                "type": "boolean",
                                "description": "是否只搜索包含错误的链路，默认 false"
                            },
                            "slow_only": {
                                "type": "boolean",
                                "description": "是否只搜索慢请求链路，默认 false"
                            },
                            "min_duration_ms": {
                                "type": "integer",
                                "description": "最小持续时间阈值（毫秒），用于过滤慢请求"
                            },
                            "lookback": {
                                "type": "string",
                                "description": "回溯时间范围，如 '1h', '30m', '24h'，默认 '1h'"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制，默认 20"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_service_dependency",
                    "description": "服务依赖关系分析工具。从分布式追踪数据中提取服务调用关系，构建服务依赖图，用于理解微服务架构和识别故障传播路径。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lookback": {
                                "type": "string",
                                "description": "回溯时间范围，如 '1h', '24h'，默认 '24h'"
                            },
                            "service_filter": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "服务过滤列表，只分析指定的服务"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_servicenow_ci",
                    "description": "查询 ServiceNow CMDB 配置项信息。用于获取服务器、网络设备、应用等配置项的详细信息，包括名称、IP地址、运行状态、位置等。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ci_name": {
                                "type": "string",
                                "description": "配置项名称（支持模糊匹配）"
                            },
                            "ci_type": {
                                "type": "string",
                                "enum": ["server", "network_device", "application", "database", "cluster"],
                                "description": "配置项类型"
                            },
                            "ip_address": {
                                "type": "string",
                                "description": "IP 地址"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["operational", "non_operational"],
                                "description": "运行状态"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制，默认 10"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_servicenow_changes",
                    "description": "查询 ServiceNow 变更记录。用于获取节点的变更历史，包括变更类型、状态、时间、描述等信息。常用于故障排查时检查最近是否有变更操作。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ci_name": {
                                "type": "string",
                                "description": "关联的配置项名称"
                            },
                            "change_number": {
                                "type": "string",
                                "description": "变更编号"
                            },
                            "change_type": {
                                "type": "string",
                                "enum": ["normal", "emergency", "standard"],
                                "description": "变更类型"
                            },
                            "state": {
                                "type": "string",
                                "enum": ["new", "assess", "authorize", "scheduled", "implement", "review", "closed"],
                                "description": "变更状态"
                            },
                            "lookback_hours": {
                                "type": "integer",
                                "description": "回溯时间（小时），默认 72"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制，默认 20"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_servicenow_incidents",
                    "description": "查询 ServiceNow 事件工单。用于获取节点关联的事件工单信息，包括优先级、状态、描述等。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ci_name": {
                                "type": "string",
                                "description": "关联的配置项名称"
                            },
                            "incident_number": {
                                "type": "string",
                                "description": "工单编号"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["1-critical", "2-high", "3-moderate", "4-low"],
                                "description": "优先级"
                            },
                            "state": {
                                "type": "string",
                                "enum": ["new", "in_progress", "on_hold", "resolved", "closed"],
                                "description": "工单状态"
                            },
                            "lookback_hours": {
                                "type": "integer",
                                "description": "回溯时间（小时），默认 72"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回结果数量限制，默认 20"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_change_as_root_cause",
                    "description": "分析变更是否可能是问题的根因。当查询到某个节点疑似有问题时，调用此工具检查该节点最近是否发生过变更，并分析这个变更是否可能是导致问题的根因。这是故障诊断的关键步骤。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "node_name": {
                                "type": "string",
                                "description": "节点名称"
                            },
                            "problem_time": {
                                "type": "string",
                                "description": "问题发生时间（可选）"
                            },
                            "lookback_hours": {
                                "type": "integer",
                                "description": "回溯时间（小时），默认 72"
                            }
                        },
                        "required": ["node_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_servicenow_node_health",
                    "description": "获取节点综合健康状态。整合 CMDB 信息、关联工单、变更历史，生成健康评分和报告。用于快速了解节点的整体健康状况。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "node_name": {
                                "type": "string",
                                "description": "节点名称或主机名"
                            },
                            "ip_address": {
                                "type": "string",
                                "description": "IP 地址"
                            },
                            "lookback_hours": {
                                "type": "integer",
                                "description": "回溯时间（小时），默认 72"
                            }
                        },
                        "required": []
                    }
                }
            }
        ]
