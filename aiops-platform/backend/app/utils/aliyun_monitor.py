import os
from typing import Dict, Any, Optional
from datetime import datetime
from ..core.config import settings


class AliyunMonitorClient:
    """
    阿里云监控平台客户端
    用于检查云主机状态
    """
    
    def __init__(self):
        self.access_key_id = settings.ALIYUN_ACCESS_KEY_ID
        self.access_key_secret = settings.ALIYUN_ACCESS_KEY_SECRET
        self.region_id = settings.ALIYUN_REGION_ID
    
    async def check_instance_status(self, instance_ip: str) -> Dict[str, Any]:
        """
        检查云主机状态
        
        Args:
            instance_ip: 实例 IP 地址
            
        Returns:
            实例状态信息
        """
        if not self.access_key_id or not self.access_key_secret:
            return {
                "success": False,
                "error": "阿里云 API 凭证未配置",
                "message": "请设置环境变量 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET"
            }
        
        try:
            import json
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkecs.request.v20140526 import DescribeInstancesRequest
            
            client = AcsClient(
                self.access_key_id,
                self.access_key_secret,
                self.region_id
            )
            
            request = DescribeInstancesRequest.DescribeInstancesRequest()
            request.set_PageSize(100)
            
            response = client.do_action_with_exception(request)
            response_dict = json.loads(response)
            
            instances = response_dict.get("Instances", {}).get("Instance", [])
            
            for instance in instances:
                public_ip = instance.get("PublicIpAddress", {}).get("IpAddress", [])
                private_ip = instance.get("InnerIpAddress", {}).get("IpAddress", [])
                
                if instance_ip in public_ip or instance_ip in private_ip:
                    return {
                        "success": True,
                        "instance_id": instance.get("InstanceId"),
                        "instance_name": instance.get("InstanceName"),
                        "status": instance.get("Status"),
                        "status_translated": self._translate_status(instance.get("Status")),
                        "creation_time": instance.get("CreationTime"),
                        "expired_time": instance.get("ExpiredTime"),
                        "region_id": instance.get("RegionId"),
                        "zone_id": instance.get("ZoneId"),
                        "instance_type": instance.get("InstanceType"),
                        "os_name": instance.get("OSName"),
                        "public_ip": public_ip,
                        "private_ip": private_ip
                    }
            
            return {
                "success": False,
                "error": f"未找到 IP 为 {instance_ip} 的实例",
                "message": "该 IP 可能不属于当前阿里云账号"
            }
            
        except ImportError:
            return {
                "success": False,
                "error": "阿里云 SDK 未安装",
                "message": "请安装: pip install aliyun-python-sdk-core aliyun-python-sdk-ecs"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "查询阿里云实例状态失败"
            }
    
    async def get_instance_operation_logs(
        self,
        instance_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取实例操作日志
        
        Args:
            instance_id: 实例 ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            操作日志信息
        """
        if not self.access_key_id or not self.access_key_secret:
            return {
                "success": False,
                "error": "阿里云 API 凭证未配置"
            }
        
        try:
            import json
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkecs.request.v20140526 import DescribeInstanceHistoryEventsRequest
            
            client = AcsClient(
                self.access_key_id,
                self.access_key_secret,
                self.region_id
            )
            
            request = DescribeInstanceHistoryEventsRequest.DescribeInstanceHistoryEventsRequest()
            request.set_InstanceEventCycleStatus("Executed")
            request.set_InstanceEventType("SystemFailure.Reboot,InstanceFailure.Reboot")
            
            if start_time:
                request.set_EventPublishTimeStart(start_time)
            if end_time:
                request.set_EventPublishTimeEnd(end_time)
            
            response = client.do_action_with_exception(request)
            response_dict = json.loads(response)
            
            events = response_dict.get("InstanceSystemEventSet", {}).get("InstanceSystemEventType", [])
            
            instance_events = [
                event for event in events
                if event.get("InstanceId") == instance_id
            ]
            
            return {
                "success": True,
                "instance_id": instance_id,
                "events": instance_events,
                "event_count": len(instance_events)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _translate_status(self, status: str) -> str:
        """
        翻译实例状态
        
        Args:
            status: 英文状态
            
        Returns:
            中文状态
        """
        status_map = {
            "Running": "运行中",
            "Stopped": "已停止",
            "Starting": "启动中",
            "Stopping": "停止中",
            "Pending": "创建中",
            "Deleted": "已删除"
        }
        return status_map.get(status, status)
    
    async def check_host_unreachable(self, instance_ip: str) -> Dict[str, Any]:
        """
        检查主机不可达的原因（根据 debug_skill.md）
        
        Args:
            instance_ip: 实例 IP 地址
            
        Returns:
            检查结果
        """
        status_result = await self.check_instance_status(instance_ip)
        
        if not status_result.get("success"):
            return status_result
        
        instance_status = status_result.get("status")
        instance_name = status_result.get("instance_name", instance_ip)
        
        if instance_status == "Stopped":
            logs_result = await self.get_instance_operation_logs(
                status_result.get("instance_id")
            )
            
            last_stop_event = None
            if logs_result.get("success") and logs_result.get("events"):
                last_stop_event = logs_result["events"][0]
            
            return {
                "success": True,
                "is_stopped": True,
                "instance_ip": instance_ip,
                "instance_name": instance_name,
                "status": "已停止",
                "stop_time": last_stop_event.get("EventPublishTime") if last_stop_event else None,
                "operator": last_stop_event.get("EventId") if last_stop_event else "系统",
                "message": f"实例 {instance_name} ({instance_ip}) 已停止",
                "recommendation": "请登录阿里云控制台启动实例，或联系相关负责人确认是否需要启动"
            }
        elif instance_status == "Running":
            return {
                "success": True,
                "is_stopped": False,
                "instance_ip": instance_ip,
                "instance_name": instance_name,
                "status": "运行中",
                "message": f"实例 {instance_name} ({instance_ip}) 正在运行中，网络问题可能由其他原因导致",
                "recommendation": "建议检查安全组规则、网络配置或应用服务状态"
            }
        else:
            return {
                "success": True,
                "is_stopped": False,
                "instance_ip": instance_ip,
                "instance_name": instance_name,
                "status": status_result.get("status_translated"),
                "message": f"实例 {instance_name} ({instance_ip}) 当前状态: {status_result.get('status_translated')}"
            }
