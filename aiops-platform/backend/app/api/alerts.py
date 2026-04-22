"""
Alertmanager Webhook 接口

接收 Alertmanager 推送的告警，并进行智能聚合分析
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.agents.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertmanagerAlert(BaseModel):
    """Alertmanager 告警格式"""
    status: str = Field(..., description="告警状态: firing, resolved")
    labels: Dict[str, str] = Field(default_factory=dict, description="告警标签")
    annotations: Dict[str, str] = Field(default_factory=dict, description="告警注解")
    startsAt: str = Field(..., description="告警开始时间")
    endsAt: Optional[str] = Field(None, description="告警结束时间")
    generatorURL: Optional[str] = Field(None, description="告警生成URL")
    fingerprint: Optional[str] = Field(None, description="告警指纹")


class AlertmanagerWebhook(BaseModel):
    """Alertmanager Webhook 请求体"""
    receiver: str = Field(..., description="接收器名称")
    status: str = Field(..., description="整体状态: firing, resolved")
    alerts: List[AlertmanagerAlert] = Field(default_factory=list, description="告警列表")
    groupLabels: Dict[str, str] = Field(default_factory=dict, description="分组标签")
    commonLabels: Dict[str, str] = Field(default_factory=dict, description="公共标签")
    commonAnnotations: Dict[str, str] = Field(default_factory=dict, description="公共注解")
    externalURL: Optional[str] = Field(None, description="Alertmanager URL")
    version: str = Field(default="4", description="Webhook 版本")
    groupKey: Optional[str] = Field(None, description="分组键")


class AlertIngestResponse(BaseModel):
    """告警接入响应"""
    success: bool
    message: str
    total_alerts: int
    firing_count: int
    resolved_count: int
    cluster_result: Optional[Dict[str, Any]] = None


def convert_alertmanager_to_cluster_format(
    alerts: List[AlertmanagerAlert]
) -> List[Dict[str, str]]:
    """
    将 Alertmanager 告警转换为 cluster_alerts 所需的格式
    
    Args:
        alerts: Alertmanager 告警列表
        
    Returns:
        转换后的告警列表，格式为 [{time, node_id, raw_msg}, ...]
    """
    converted = []
    
    for alert in alerts:
        if alert.status == "resolved":
            continue
        
        time_str = alert.startsAt
        if time_str.endswith("Z"):
            time_str = time_str[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = alert.startsAt
        
        node_id = alert.labels.get("instance") or alert.labels.get("node") or alert.labels.get("pod") or "unknown"
        
        alert_name = alert.labels.get("alertname", "UnknownAlert")
        severity = alert.labels.get("severity", "warning")
        
        message_parts = [f"[{alert_name}]"]
        
        if "service" in alert.labels:
            message_parts.append(f"service={alert.labels['service']}")
        if "job" in alert.labels:
            message_parts.append(f"job={alert.labels['job']}")
        
        if alert.annotations.get("summary"):
            message_parts.append(alert.annotations["summary"])
        elif alert.annotations.get("description"):
            message_parts.append(alert.annotations["description"])
        
        for key, value in alert.labels.items():
            if key not in ["alertname", "severity", "instance", "node", "pod", "service", "job"]:
                message_parts.append(f"{key}={value}")
        
        raw_msg = " ".join(message_parts)
        
        converted.append({
            "time": time_str,
            "node_id": node_id,
            "raw_msg": raw_msg,
            "severity": severity,
            "labels": alert.labels,
            "annotations": alert.annotations,
        })
    
    return converted


async def process_alerts_with_clustering(
    alerts: List[Dict[str, str]],
    auto_cluster: bool = True
) -> Dict[str, Any]:
    """
    处理告警并进行智能聚合
    
    Args:
        alerts: 转换后的告警列表
        auto_cluster: 是否自动进行聚类
        
    Returns:
        处理结果
    """
    if not alerts:
        return {
            "success": True,
            "message": "No firing alerts to process",
            "cluster_result": None
        }
    
    if not auto_cluster or len(alerts) < 3:
        return {
            "success": True,
            "message": f"Received {len(alerts)} alerts, skipping clustering (count < 3 or auto_cluster disabled)",
            "cluster_result": None
        }
    
    try:
        registry = ToolRegistry()
        cluster_alerts_input = [
            {
                "time": a["time"],
                "node_id": a["node_id"],
                "raw_msg": a["raw_msg"]
            }
            for a in alerts
        ]
        
        result = await registry.execute(
            "cluster_alerts",
            alerts=cluster_alerts_input,
            eps=0.5,
            min_samples=2
        )
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Alert clustering completed: {result['cluster_count']} clusters from {result['total_input']} alerts",
                "cluster_result": result
            }
        else:
            logger.warning(f"Alert clustering failed: {result.get('error')}")
            return {
                "success": True,
                "message": f"Alert clustering failed: {result.get('error')}",
                "cluster_result": None
            }
            
    except Exception as e:
        logger.error(f"Error during alert clustering: {e}")
        return {
            "success": True,
            "message": f"Alert clustering error: {str(e)}",
            "cluster_result": None
        }


@router.post("/webhook", response_model=AlertIngestResponse)
async def receive_alertmanager_webhook(
    webhook: AlertmanagerWebhook,
    background_tasks: BackgroundTasks
):
    """
    接收 Alertmanager Webhook 告警
    
    Alertmanager 配置示例:
    ```yaml
    receivers:
      - name: 'aiops-receiver'
        webhook_configs:
          - url: 'http://aiops-platform:8000/api/alerts/webhook'
            send_resolved: true
    ```
    """
    logger.info(f"Received Alertmanager webhook: {webhook.status}, {len(webhook.alerts)} alerts")
    
    firing_alerts = [a for a in webhook.alerts if a.status == "firing"]
    resolved_alerts = [a for a in webhook.alerts if a.status == "resolved"]
    
    converted_alerts = convert_alertmanager_to_cluster_format(firing_alerts)
    
    cluster_result = await process_alerts_with_clustering(converted_alerts)
    
    return AlertIngestResponse(
        success=True,
        message=f"Processed {len(webhook.alerts)} alerts from Alertmanager",
        total_alerts=len(webhook.alerts),
        firing_count=len(firing_alerts),
        resolved_count=len(resolved_alerts),
        cluster_result=cluster_result.get("cluster_result")
    )


@router.post("/ingest", response_model=AlertIngestResponse)
async def ingest_alerts(
    alerts: List[Dict[str, str]],
    auto_cluster: bool = True
):
    """
    直接接入告警数据
    
    用于其他系统直接推送告警到 AIops 平台
    
    请求体格式:
    ```json
    [
        {
            "time": "2024-01-15 10:30:00",
            "node_id": "server-01",
            "raw_msg": "High CPU usage detected: 95%"
        }
    ]
    ```
    """
    logger.info(f"Received direct alert ingest: {len(alerts)} alerts")
    
    cluster_result = await process_alerts_with_clustering(alerts, auto_cluster)
    
    return AlertIngestResponse(
        success=True,
        message=f"Ingested {len(alerts)} alerts",
        total_alerts=len(alerts),
        firing_count=len(alerts),
        resolved_count=0,
        cluster_result=cluster_result.get("cluster_result")
    )


@router.get("/health")
async def alerts_health():
    """告警服务健康检查"""
    return {"status": "healthy", "service": "alerts-webhook"}
