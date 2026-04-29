"""
ServiceNow Client - 统一连接器

提供 ServiceNow REST API 的统一连接管理
"""

import os
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from functools import wraps

from .logger import get_logger

logger = get_logger("servicenow_client")

try:
    from ..core.config import settings
    SETTINGS_AVAILABLE = True
except ImportError:
    SETTINGS_AVAILABLE = False


@dataclass
class ServiceNowConfig:
    """ServiceNow 配置"""
    instance_url: str
    username: str
    password: str
    api_key: str = ""
    api_version: str = "v2"
    timeout: int = 30
    
    @property
    def api_url(self) -> str:
        return f"{self.instance_url}/api/now/{self.api_version}"
    
    @classmethod
    def from_env(cls) -> Optional["ServiceNowConfig"]:
        """从环境变量或 settings 加载配置"""
        if SETTINGS_AVAILABLE:
            instance = settings.SERVICENOW_INSTANCE
            username = settings.SERVICENOW_USERNAME
            password = settings.SERVICENOW_PASSWORD
            api_key = settings.SERVICENOW_API_KEY
        else:
            instance = os.getenv("SERVICENOW_INSTANCE", "")
            username = os.getenv("SERVICENOW_USERNAME", "")
            password = os.getenv("SERVICENOW_PASSWORD", "")
            api_key = os.getenv("SERVICENOW_API_KEY", "")
        
        if not all([instance, username, password]):
            return None
        
        instance_url = f"https://{instance}" if not instance.startswith("http") else instance
        
        return cls(
            instance_url=instance_url.rstrip("/"),
            username=username,
            password=password,
            api_key=api_key,
            api_version=os.getenv("SERVICENOW_API_VERSION", "v2"),
            timeout=int(os.getenv("SERVICENOW_TIMEOUT", "30"))
        )


def require_connection(func):
    """装饰器：确保连接已建立"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self._connected:
            if not await self.connect():
                return {
                    "success": False,
                    "error": "ServiceNow connection not established"
                }
        return await func(self, *args, **kwargs)
    return wrapper


class ServiceNowClient:
    """
    ServiceNow 统一连接器
    
    提供 CMDB、Incident、Change、Problem 等 API 的统一访问
    """
    
    _instance: Optional["ServiceNowClient"] = None
    _initialized: bool = False
    
    def __new__(cls, config: ServiceNowConfig = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: ServiceNowConfig = None):
        if self._initialized:
            return
        
        self.config = config or ServiceNowConfig.from_env()
        self.session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._connection_error: Optional[str] = None
        
        if self.config:
            logger.info(f"ServiceNow Client initialized for {self.config.instance_url}")
        else:
            logger.warning("ServiceNow Client not configured. Set SERVICENOW_* environment variables.")
        
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> "ServiceNowClient":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def is_configured(cls) -> bool:
        """检查是否已配置"""
        return ServiceNowConfig.from_env() is not None
    
    async def connect(self) -> bool:
        """建立连接"""
        if not self.config:
            self._connection_error = "ServiceNow not configured"
            return False
        
        try:
            if self.session is None or self.session.closed:
                auth = aiohttp.BasicAuth(
                    self.config.username,
                    self.config.password
                )
                self.session = aiohttp.ClientSession(
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                )
            
            # 测试连接
            async with self.session.get(
                f"{self.config.api_url}/table/cmdb_ci_server",
                params={"sysparm_limit": 1}
            ) as response:
                if response.status in [200, 401]:
                    if response.status == 401:
                        self._connection_error = "Authentication failed"
                        return False
                    self._connected = True
                    self._connection_error = None
                    logger.info("ServiceNow connection established successfully")
                    return True
                else:
                    self._connection_error = f"Unexpected status: {response.status}"
                    return False
        except aiohttp.ClientError as e:
            self._connection_error = f"Connection error: {str(e)}"
            logger.error(f"ServiceNow connection failed: {e}")
            return False
        except Exception as e:
            self._connection_error = f"Unexpected error: {str(e)}"
            logger.error(f"ServiceNow connection failed: {e}")
            return False
    
    async def close(self):
        """关闭连接"""
        if self.session and not self.session.closed:
            await self.session.close()
        self._connected = False
        self.session = None
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    @property
    def connection_error(self) -> Optional[str]:
        return self._connection_error
    
    @require_connection
    async def _get(
        self,
        table: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行 GET 请求"""
        try:
            async with self.session.get(
                f"{self.config.api_url}/table/{table}",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"success": True, "data": data.get("result", [])}
                else:
                    text = await response.text()
                    return {
                        "success": False,
                        "error": f"API error: {response.status}",
                        "details": text[:500]
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @require_connection
    async def _post(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行 POST 请求"""
        try:
            async with self.session.post(
                f"{self.config.api_url}/table/{table}",
                json=data
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    return {"success": True, "data": data.get("result", {})}
                else:
                    text = await response.text()
                    return {
                        "success": False,
                        "error": f"API error: {response.status}",
                        "details": text[:500]
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== CMDB 配置项查询 ====================
    
    @require_connection
    async def query_ci(
        self,
        ci_name: str = None,
        ci_type: str = None,
        ip_address: str = None,
        status: str = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        查询 CMDB 配置项
        
        Args:
            ci_name: 配置项名称（支持模糊匹配）
            ci_type: 配置项类型 (server, network_device, application, database, cluster)
            ip_address: IP 地址
            status: 运行状态 (operational, non_operational)
            limit: 返回数量限制
            
        Returns:
            查询结果
        """
        query_parts = []
        
        if ci_name:
            query_parts.append(f"nameLIKE{ci_name}")
        
        type_mapping = {
            "server": "cmdb_ci_server",
            "network_device": "cmdb_ci_netgear",
            "application": "cmdb_ci_appl",
            "database": "cmdb_ci_database",
            "cluster": "cmdb_ci_cluster"
        }
        table = type_mapping.get(ci_type, "cmdb_ci") if ci_type else "cmdb_ci"
        
        if ip_address:
            query_parts.append(f"ip_address={ip_address}")
        
        if status:
            status_mapping = {"operational": "1", "non_operational": "2"}
            if status in status_mapping:
                query_parts.append(f"operational_status={status_mapping[status]}")
        
        params = {
            "sysparm_query": "^".join(query_parts) if query_parts else "",
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        
        result = await self._get(table, params)
        
        if result["success"]:
            cis = result["data"]
            return {
                "success": True,
                "count": len(cis),
                "cis": [
                    {
                        "sys_id": ci.get("sys_id"),
                        "name": ci.get("name"),
                        "short_description": ci.get("short_description"),
                        "ip_address": ci.get("ip_address"),
                        "operational_status": ci.get("operational_status"),
                        "location": ci.get("location"),
                        "managed_by": ci.get("managed_by"),
                        "sys_class_name": ci.get("sys_class_name"),
                    }
                    for ci in cis
                ]
            }
        
        return result
    
    # ==================== 变更记录查询 ====================
    
    @require_connection
    async def query_changes(
        self,
        ci_name: str = None,
        change_number: str = None,
        change_type: str = None,
        state: str = None,
        start_time: str = None,
        end_time: str = None,
        lookback_hours: int = 72,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        查询变更记录
        
        Args:
            ci_name: 关联的配置项名称
            change_number: 变更编号
            change_type: 变更类型 (normal, emergency, standard)
            state: 变更状态
            start_time: 开始时间
            end_time: 结束时间
            lookback_hours: 回溯时间（小时），默认 72 小时
            limit: 返回数量限制
            
        Returns:
            变更记录列表
        """
        query_parts = []
        
        if change_number:
            query_parts.append(f"number={change_number}")
        
        if ci_name:
            query_parts.append(f"cmdb_ci.nameLIKE{ci_name}")
        
        if change_type:
            query_parts.append(f"type={change_type}")
        
        if state:
            state_mapping = {
                "new": "-5",
                "assess": "1",
                "authorize": "2",
                "scheduled": "3",
                "implement": "4",
                "review": "5",
                "closed": "7"
            }
            if state in state_mapping:
                query_parts.append(f"state={state_mapping[state]}")
        
        if start_time:
            query_parts.append(f"start_date>={start_time}")
        elif lookback_hours:
            lookback = datetime.utcnow() - timedelta(hours=lookback_hours)
            query_parts.append(f"start_date>={lookback.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if end_time:
            query_parts.append(f"start_date<={end_time}")
        
        params = {
            "sysparm_query": "^".join(query_parts) if query_parts else "",
            "sysparm_limit": limit,
            "sysparm_display_value": "true",
            "sysparm_fields": "sys_id,number,short_description,description,type,state,start_date,end_date,cmdb_ci.name,assigned_to,opened_at,closed_at"
        }
        
        result = await self._get("change_request", params)
        
        if result["success"]:
            changes = result["data"]
            return {
                "success": True,
                "count": len(changes),
                "ci_name": ci_name,
                "lookback_hours": lookback_hours,
                "changes": [
                    {
                        "sys_id": ch.get("sys_id"),
                        "number": ch.get("number"),
                        "short_description": ch.get("short_description"),
                        "description": ch.get("description", "")[:500] if ch.get("description") else "",
                        "type": ch.get("type"),
                        "state": ch.get("state"),
                        "start_date": ch.get("start_date"),
                        "end_date": ch.get("end_date"),
                        "ci_name": ch.get("cmdb_ci.name"),
                        "assigned_to": ch.get("assigned_to"),
                        "opened_at": ch.get("opened_at"),
                        "closed_at": ch.get("closed_at"),
                    }
                    for ch in changes
                ]
            }
        
        return result
    
    # ==================== 事件工单查询 ====================
    
    @require_connection
    async def query_incidents(
        self,
        ci_name: str = None,
        incident_number: str = None,
        priority: str = None,
        state: str = None,
        lookback_hours: int = 72,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        查询事件工单
        
        Args:
            ci_name: 关联的配置项名称
            incident_number: 工单编号
            priority: 优先级 (1-critical, 2-high, 3-moderate, 4-low)
            state: 工单状态 (new, in_progress, on_hold, resolved, closed)
            lookback_hours: 回溯时间（小时）
            limit: 返回数量限制
            
        Returns:
            事件工单列表
        """
        query_parts = []
        
        if incident_number:
            query_parts.append(f"number={incident_number}")
        
        if ci_name:
            query_parts.append(f"cmdb_ci.nameLIKE{ci_name}")
        
        if priority:
            query_parts.append(f"priority={priority}")
        
        if state:
            state_mapping = {
                "new": "1",
                "in_progress": "2",
                "on_hold": "3",
                "resolved": "6",
                "closed": "7"
            }
            if state in state_mapping:
                query_parts.append(f"state={state_mapping[state]}")
        
        if lookback_hours:
            lookback = datetime.utcnow() - timedelta(hours=lookback_hours)
            query_parts.append(f"opened_at>={lookback.strftime('%Y-%m-%d %H:%M:%S')}")
        
        params = {
            "sysparm_query": "^".join(query_parts) if query_parts else "",
            "sysparm_limit": limit,
            "sysparm_display_value": "true",
            "sysparm_fields": "sys_id,number,short_description,description,priority,state,cmdb_ci.name,assigned_to,opened_at,resolved_at,closed_at"
        }
        
        result = await self._get("incident", params)
        
        if result["success"]:
            incidents = result["data"]
            return {
                "success": True,
                "count": len(incidents),
                "ci_name": ci_name,
                "lookback_hours": lookback_hours,
                "incidents": incidents
            }
        
        return result
    
    # ==================== 问题记录查询 ====================
    
    @require_connection
    async def query_problems(
        self,
        ci_name: str = None,
        problem_number: str = None,
        priority: str = None,
        state: str = None,
        lookback_hours: int = 168,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        查询问题记录
        
        Args:
            ci_name: 关联的配置项名称
            problem_number: 问题编号
            priority: 优先级
            state: 问题状态
            lookback_hours: 回溯时间（小时），默认 7 天
            limit: 返回数量限制
            
        Returns:
            问题记录列表
        """
        query_parts = []
        
        if problem_number:
            query_parts.append(f"number={problem_number}")
        
        if ci_name:
            query_parts.append(f"cmdb_ci.nameLIKE{ci_name}")
        
        if priority:
            query_parts.append(f"priority={priority}")
        
        if state:
            state_mapping = {
                "new": "101",
                "assess": "102",
                "root_cause_analysis": "103",
                "fix_in_progress": "104",
                "resolved": "105",
                "closed": "107"
            }
            if state in state_mapping:
                query_parts.append(f"state={state_mapping[state]}")
        
        if lookback_hours:
            lookback = datetime.utcnow() - timedelta(hours=lookback_hours)
            query_parts.append(f"opened_at>={lookback.strftime('%Y-%m-%d %H:%M:%S')}")
        
        params = {
            "sysparm_query": "^".join(query_parts) if query_parts else "",
            "sysparm_limit": limit,
            "sysparm_display_value": "true"
        }
        
        result = await self._get("problem", params)
        
        if result["success"]:
            return {
                "success": True,
                "count": len(result["data"]),
                "problems": result["data"]
            }
        
        return result
    
    # ==================== 综合健康检查 ====================
    
    @require_connection
    async def get_node_health(
        self,
        node_name: str = None,
        ip_address: str = None,
        lookback_hours: int = 72
    ) -> Dict[str, Any]:
        """
        获取节点综合健康状态
        
        整合 CI 信息、关联工单、变更历史
        
        Args:
            node_name: 节点名称或主机名
            ip_address: IP 地址
            lookback_hours: 回溯时间（小时）
            
        Returns:
            综合健康报告
        """
        # 1. 查询 CI 信息
        ci_result = await self.query_ci(
            ci_name=node_name,
            ip_address=ip_address,
            limit=1
        )
        
        if not ci_result["success"] or not ci_result.get("cis"):
            return {
                "success": False,
                "error": "Node not found in ServiceNow CMDB",
                "node_name": node_name,
                "ip_address": ip_address
            }
        
        ci = ci_result["cis"][0]
        ci_name = ci.get("name")
        
        # 2. 并行查询关联信息
        incidents_task = self.query_incidents(
            ci_name=ci_name,
            lookback_hours=lookback_hours,
            limit=10
        )
        changes_task = self.query_changes(
            ci_name=ci_name,
            lookback_hours=lookback_hours,
            limit=10
        )
        problems_task = self.query_problems(
            ci_name=ci_name,
            lookback_hours=lookback_hours,
            limit=10
        )
        
        incidents, changes, problems = await asyncio.gather(
            incidents_task, changes_task, problems_task
        )
        
        # 3. 计算健康评分
        health_score = 100
        
        active_incidents = [
            i for i in incidents.get("incidents", [])
            if i.get("state") not in ["Resolved", "Closed", "6", "7"]
        ]
        if active_incidents:
            health_score -= len(active_incidents) * 10
        
        open_problems = [
            p for p in problems.get("problems", [])
            if p.get("state") not in ["Resolved", "Closed", "105", "107"]
        ]
        if open_problems:
            health_score -= len(open_problems) * 15
        
        recent_changes = [
            c for c in changes.get("changes", [])
            if c.get("state") in ["Implement", "Scheduled", "4", "3"]
        ]
        if recent_changes:
            health_score -= len(recent_changes) * 5
        
        health_score = max(0, health_score)
        
        return {
            "success": True,
            "node": {
                "name": ci.get("name"),
                "sys_id": ci.get("sys_id"),
                "type": ci.get("sys_class_name"),
                "ip_address": ci.get("ip_address"),
                "operational_status": ci.get("operational_status"),
                "location": ci.get("location"),
                "managed_by": ci.get("managed_by"),
            },
            "health_score": health_score,
            "health_status": "healthy" if health_score >= 80 else "warning" if health_score >= 50 else "critical",
            "active_incidents": active_incidents,
            "open_problems": open_problems,
            "recent_changes": recent_changes,
            "summary": {
                "total_incidents": len(active_incidents),
                "total_problems": len(open_problems),
                "total_changes": len(recent_changes),
                "lookback_hours": lookback_hours
            }
        }
    
    # ==================== 变更根因分析 ====================
    
    @require_connection
    async def analyze_change_as_root_cause(
        self,
        node_name: str,
        problem_time: str = None,
        lookback_hours: int = 72
    ) -> Dict[str, Any]:
        """
        分析变更是否可能是问题的根因
        
        Args:
            node_name: 节点名称
            problem_time: 问题发生时间
            lookback_hours: 回溯时间（小时）
            
        Returns:
            变更根因分析报告
        """
        # 查询最近的变更
        changes_result = await self.query_changes(
            ci_name=node_name,
            lookback_hours=lookback_hours,
            limit=20
        )
        
        if not changes_result["success"]:
            return changes_result
        
        changes = changes_result.get("changes", [])
        
        if not changes:
            return {
                "success": True,
                "node_name": node_name,
                "has_recent_changes": False,
                "changes": [],
                "analysis": {
                    "is_likely_root_cause": False,
                    "reason": "No recent changes found for this node",
                    "confidence": "HIGH"
                }
            }
        
        # 分析变更与问题的时间关系
        analysis_result = {
            "success": True,
            "node_name": node_name,
            "has_recent_changes": True,
            "changes": changes,
            "analysis": {}
        }
        
        # 按时间排序变更
        sorted_changes = sorted(
            changes,
            key=lambda x: x.get("start_date") or x.get("opened_at") or "",
            reverse=True
        )
        
        # 查找最近的变更
        most_recent_change = sorted_changes[0] if sorted_changes else None
        
        if most_recent_change:
            change_time = most_recent_change.get("start_date") or most_recent_change.get("opened_at")
            
            analysis_result["analysis"] = {
                "most_recent_change": {
                    "number": most_recent_change.get("number"),
                    "description": most_recent_change.get("short_description"),
                    "type": most_recent_change.get("type"),
                    "state": most_recent_change.get("state"),
                    "start_date": change_time,
                    "assigned_to": most_recent_change.get("assigned_to")
                },
                "is_likely_root_cause": True,
                "reason": f"Found recent change '{most_recent_change.get('number')}' on this node. "
                         f"Change type: {most_recent_change.get('type')}, "
                         f"Description: {most_recent_change.get('short_description')}",
                "confidence": "MEDIUM",
                "recommendation": f"建议检查变更 {most_recent_change.get('number')} 的详细内容，"
                                 f"确认是否与当前问题相关。变更负责人: {most_recent_change.get('assigned_to')}"
            }
            
            # 如果有紧急变更，提高置信度
            if most_recent_change.get("type") == "Emergency":
                analysis_result["analysis"]["confidence"] = "HIGH"
                analysis_result["analysis"]["reason"] += " (紧急变更，风险较高)"
        
        return analysis_result


# 全局单例
_servicenow_client: Optional[ServiceNowClient] = None


def get_servicenow_client() -> ServiceNowClient:
    """获取 ServiceNow 客户端单例"""
    global _servicenow_client
    if _servicenow_client is None:
        _servicenow_client = ServiceNowClient()
    return _servicenow_client
