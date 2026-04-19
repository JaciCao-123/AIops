"""
Grafana Dashboard Generator - Grafana 仪表盘配置自动生成

功能：
1. 自动生成 Grafana Dashboard JSON 配置
2. 预置多种专业仪表盘模板（系统监控、应用性能、根因分析等）
3. 支持 Prometheus/Tempo/Loki 数据源面板
4. 动态变量与交互式过滤
5. 通过 Grafana API 自动导入/更新仪表盘
6. 告警规则可视化配置
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import uuid

import httpx
from pydantic import BaseModel, Field

from .config import (
    ObservabilityConfig,
    get_observability_config,
    GrafanaConfig,
)

logger = logging.getLogger(__name__)


class PanelType(str, Enum):
    """面板类型"""
    TIMESERIES = "timeseries"
    STAT = "stat"
    TABLE = "table"
    HEATMAP = "heatmap"
    BARGAUGE = "bargauge"
    GRAPH = "graph"  # 旧版图表
    TRACE_VIEWER = "traceViewer"
    LOGS = "logs"
    PIE_CHART = "piechart"
    STATE_TIMELINE = "stateTimeline"


class DashboardTemplate(str, Enum):
    """预置仪表盘模板"""
    SYSTEM_OVERVIEW = "system_overview"
    APPLICATION_PERFORMANCE = "application_performance"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    SERVICE_MESH = "service_mesh"
    CUSTOM = "custom"


@dataclass
class PanelConfig:
    """面板配置"""
    title: str
    panel_type: PanelType
    grid_pos: Dict[str, int]  # {x, y, w, h}
    datasource: str = "${datasource}"
    queries: List[Dict[str, Any]] = field(default_factory=list)
    description: Optional[str] = None
    alert_config: Optional[Dict[str, Any]] = None
    options: Dict[str, Any] = field(default_factory=dict)
    thresholds: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class VariableConfig:
    """变量配置"""
    name: str
    label: str
    type: str  # query, custom, interval, etc.
    query: str
    datasource: Optional[str] = None
    default: Optional[str] = None
    multi: bool = False
    include_all: bool = False


class GrafanaDashboardGenerator:
    """
    Grafana 仪表盘生成器
    
    提供：
    - 多种预置模板
    - 自定义面板组合
    - 自动化部署到 Grafana
    - 告警规则集成
    """
    
    def __init__(
        self,
        config: Optional[ObservabilityConfig] = None,
        grafana_config: Optional[GrafanaConfig] = None,
    ):
        """
        初始化仪表盘生成器
        
        Args:
            config: 可观测性总配置
            grafana_config: 单独的 Grafana 配置
        """
        self.config = config or get_observability_config()
        self.grafana_config = grafana_config or self.config.grafana
        
        self.base_url = self.grafana_config.url.rstrip("/")
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """建立连接"""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            
            if self.grafana_config.api_key:
                headers["Authorization"] = f"Bearer {self.grafana_config.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers=headers,
            )
        logger.info(f"Connected to Grafana at {self.base_url}")
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            raise RuntimeError("Grafana client not connected. Call connect() first.")
        return self._client
    
    def generate_dashboard(
        self,
        template: DashboardTemplate = DashboardTemplate.SYSTEM_OVERVIEW,
        title: Optional[str] = None,
        variables: Optional[List[VariableConfig]] = None,
        custom_panels: Optional[List[PanelConfig]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        生成完整的 Dashboard JSON 配置
        
        Args:
            template: 仪表盘模板类型
            title: 仪表盘标题
            variables: 变量列表
            custom_panels: 自定义面板列表
            **kwargs: 其他自定义参数
            
        Returns:
            Grafana Dashboard JSON 字典
        """
        dashboard_uid = kwargs.get("dashboard_uid", str(uuid.uuid4())[:8])
        title = title or f"AIOps - {template.value.replace('_', ' ').title()}"
        
        if template == DashboardTemplate.CUSTOM and custom_panels:
            panels = [self._build_panel(p) for p in custom_panels]
        else:
            panels = self._generate_template_panels(template, **kwargs)
        
        variables_list = self._build_variables(variables) if variables else self._default_variables(template)
        
        dashboard = {
            "uid": dashboard_uid,
            "title": title,
            "tags": ["aiops", "observability", "auto-generated"],
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 1,
            "refresh": "30s",
            "time": {
                "from": "now-1h",
                "to": "now",
            },
            "timepicker": {},
            "annotations": {
                "list": [
                    {
                        "builtIn": 1,
                        "datasource": {
                            "type": "grafana",
                            "uid": "-- Grafana --",
                        },
                        "enable": True,
                        "hide": True,
                        "iconColor": "rgba(0, 211, 255, 1)",
                        "name": "Annotations & Alerts",
                        "type": "dashboard",
                    },
                    {
                        "datasource": {
                            "type": "prometheus",
                            "uid": "${datasource}",
                        },
                        "enable": True,
                        "hide": False,
                        "iconColor": "yellow",
                        "name": "Prometheus Alerts",
                        "type": "alerts",
                    },
                ],
            },
            "templating": {
                "list": variables_list,
            },
            "panels": panels,
            "links": [],
        }
        
        logger.info(f"Generated dashboard: {title} with {len(panels)} panels")
        return dashboard
    
    def _default_variables(self, template: DashboardTemplate) -> List[Dict[str, Any]]:
        """获取默认变量配置"""
        return [
            {
                "current": {
                    "selected": False,
                    "text": "Prometheus",
                    "value": self.grafana_config.datasource_name_prometheus,
                },
                "hide": 0,
                "includeAll": False,
                "label": "Datasource",
                "multi": False,
                "name": "datasource",
                "options": [],
                "query": self.grafana_config.datasource_name_prometheus,
                "queryValue": "",
                "refresh": 1,
                "regex": "",
                "skipUrlSync": False,
                "type": "datasource",
            },
            {
                "current": {
                    "selected": True,
                    "text": "All",
                    "value": "$__all",
                },
                "datasource": {
                    "type": "prometheus",
                    "uid": "${datasource}",
                },
                "definition": 'label_values(job)',
                "hide": 0,
                "includeAll": True,
                "label": "Instance",
                "multi": True,
                "name": "instance",
                "options": [],
                "query": {
                    "query": 'label_values(job)',
                    "refId": "StandardVariableQuery",
                },
                "refresh": 2,
                "regex": "",
                "skipUrlSync": False,
                "sort": 1,
                "type": "query",
            },
            {
                "current": {
                    "selected": False,
                    "text": "5m",
                    "value": "5m",
                },
                "hide": 0,
                "label": "Interval",
                "name": "interval",
                "options": [
                    {"selected": True, "text": "5m", "value": "5m"},
                    {"selected": False, "text": "15m", "value": "15m"},
                    {"selected": False, "text": "30m", "value": "30m"},
                    {"selected": False, "text": "1h", "value": "1h"},
                ],
                "query": "5m,15m,30m,1h",
                "queryValue": "5m",
                "refresh": 2,
                "skipUrlSync": False,
                "type": "interval",
            },
        ]
    
    def _build_variables(self, variables: List[VariableConfig]) -> List[Dict[str, Any]]:
        """构建变量配置列表"""
        result = []
        for var in variables:
            var_dict = {
                "current": {
                    "selected": True,
                    "text": var.default or var.label,
                    "value": var.default or var.label,
                },
                "hide": 0,
                "label": var.label,
                "multi": var.multi,
                "name": var.name,
                "options": [],
                "query": var.query,
                "refresh": 2,
                "skipUrlSync": False,
                "type": var.type,
            }
            
            if var.datasource:
                var_dict["datasource"] = {
                    "type": "prometheus",
                    "uid": var.datasource,
                }
                var_dict["definition"] = var.query
            
            result.append(var_dict)
        
        return result
    
    def _generate_template_panels(
        self,
        template: DashboardTemplate,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """根据模板生成面板列表"""
        
        if template == DashboardTemplate.SYSTEM_OVERVIEW:
            return self._create_system_overview_panels(**kwargs)
        
        elif template == DashboardTemplate.APPLICATION_PERFORMANCE:
            return self._create_apm_panels(**kwargs)
        
        elif template == DashboardTemplate.ROOT_CAUSE_ANALYSIS:
            return self._create_rca_panels(**kwargs)
        
        elif template == DashboardTemplate.SERVICE_MESH:
            return self._create_service_mesh_panels(**kwargs)
        
        else:
            return []
    
    def _create_system_overview_panels(self, **kwargs) -> List[Dict[str, Any]]:
        """创建系统概览面板"""
        ds = "${datasource}"
        instance_filter = '${instance}'
        
        panels = []
        
        # Row Header - 系统资源使用率
        panels.append({
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0},
            "id": None,
            "panels": [],
            "title": "📊 System Resource Usage",
            "type": "row",
        })
        
        # CPU 使用率统计
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 70},
                            {"color": "red", "value": 90},
                        ],
                    },
                    "unit": "percent",
                },
            },
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 1},
            "id": None,
            "options": {
                "orientation": "auto",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
                "colorMode": "value",
                "graphMode": "area",
            },
            "panelId": None,
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{mode="idle", job=~"{instance_filter}"}}[${{interval}}])) * 100)',
                "legendFormat": "{{instance}}",
                "range": True,
                "refId": "A",
            }],
            "title": "CPU Usage %",
            "type": PanelType.STAT.value,
        })
        
        # 内存使用率
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "percent",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 80},
                            {"color": "red", "value": 95},
                        ],
                    },
                },
            },
            "gridPos": {"h": 8, "w": 6, "x": 6, "y": 1},
            "id": None,
            "options": {
                "orientation": "auto",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
                "colorMode": "value",
                "graphMode": "area",
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'(1 - (node_memory_MemAvailable_bytes{{job=~"{instance_filter}"}} / node_memory_MemTotal_bytes{{job=~"{instance_filter}"}})) * 100',
                "legendFormat": "{{instance}}",
                "range": True,
                "refId": "A",
            }],
            "title": "Memory Usage %",
            "type": PanelType.STAT.value,
        })
        
        # 磁盘使用率
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "percent",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 80},
                            {"color": "red", "value": 95},
                        ],
                    },
                },
            },
            "gridPos": {"h": 8, "w": 6, "x": 12, "y": 1},
            "id": None,
            "options": {
                "orientation": "auto",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
                "colorMode": "value",
                "graphMode": "area",
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'(1 - (node_filesystem_avail_bytes{{job=~"{instance_filter}", fstype!~"tmpfs|overlay"}} / node_filesystem_size_bytes{{job=~"{instance_filter}", fstype!~"tmpfs|overlay"}})) * 100',
                "legendFormat": "{{instance}}: {{mountpoint}}",
                "range": True,
                "refId": "A",
            }],
            "title": "Disk Usage %",
            "type": PanelType.STAT.value,
        })
        
        # 网络流量
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisCenteredZero": False,
                        "axisColorMode": "text",
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "off"},
                    },
                    "mappings": [],
                    "thresholds": {"mode": "absolute", "steps": [{"color": "green"}]},
                    "unit": "Bps",
                },
            },
            "gridPos": {"h": 8, "w": 6, "x": 18, "y": 1},
            "id": None,
            "options": {
                "legend": {"calcs": ["mean", "max"], "displayMode": "table", "placement": "bottom", "showLegend": True},
                "tooltip": {"mode": "single", "sort": "none"},
            },
            "targets": [
                {
                    "datasource": ds,
                    "editorMode": "code",
                    "expr": f'sum by(instance) (irate(node_network_receive_bytes_total{{job=~"{instance_filter}", device!="lo"}}[${{interval}}]))',
                    "legendFormat": "RX - {{instance}}",
                    "range": True,
                    "refId": "A",
                },
                {
                    "datasource": ds,
                    "editorMode": "code",
                    "expr": f'sum by(instance) (irate(node_network_transmit_bytes_total{{job=~"{instance_filter}", device!="lo"}}[${{interval}}))',
                    "legendFormat": "TX - {{instance}}",
                    "range": True,
                    "refId": "B",
                },
            ],
            "title": "Network I/O",
            "type": PanelType.TIMESERIES.value,
        })
        
        # CPU 时间序列图
        panels.append({
            "datasource": ds,
            "description": "CPU usage over time per instance",
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisCenteredZero": False,
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 20,
                        "gradientMode": "opacity",
                        "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                        "lineInterpolation": "smooth",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "none"},
                        "thresholdsStyle": {"mode": "line+area"},
                    },
                    "unit": "percent",
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 9},
            "id": None,
            "options": {
                "legend": {"calcs": ["last", "mean", "max"], "displayMode": "table", "placement": "right", "showLegend": True},
                "tooltip": {"mode": "multi", "sort": "desc"},
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'100 - (avg by(instance) (irate(node_cpu_seconds_total{{mode="idle", job=~"{instance_filter}"}}[${{interval}}])) * 100)',
                "legendFormat": "{{instance}}",
                "range": True,
                "refId": "A",
            }],
            "title": "📈 CPU Usage Timeline",
            "type": PanelType.TIMESERIES.value,
        })
        
        # 内存时间序列图
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisPlacement": "auto",
                        "drawStyle": "line",
                        "fillOpacity": 20,
                        "gradientMode": "opacity",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"mode": "none"},
                        "thresholdsStyle": {"mode": "line+area"},
                    },
                    "unit": "percent",
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 9},
            "id": None,
            "options": {
                "legend": {"calcs": ["last", "mean", "max"], "displayMode": "table", "placement": "right"},
                "tooltip": {"mode": "multi", "sort": "desc"},
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'(1 - (node_memory_MemAvailable_bytes{{job=~"{instance_filter}"}} / node_memory_MemTotal_bytes{{job=~"{instance_filter}"}})) * 100',
                "legendFormat": "{{instance}}",
                "range": True,
                "refId": "A",
            }],
            "title": "💾 Memory Usage Timeline",
            "type": PanelType.TIMESERIES.value,
        })
        
        return panels
    
    def _create_apm_panels(self, **kwargs) -> List[Dict[str, Any]]:
        """创建 APM 应用性能监控面板"""
        service_name = kwargs.get("service_name", "${service}")
        ds = "${datasource}"
        
        panels = []
        
        # Header Row
        panels.append({
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0},
            "panels": [],
            "title": "⚡ Application Performance Monitoring",
            "type": "row",
        })
        
        # Request Rate
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green"}, {"color": "yellow", "value": 100}, {"color": "red", "value": 500}],
                    },
                    "unit": "reqps",
                },
            },
            "gridPos": {"h": 7, "w": 6, "x": 0, "y": 1},
            "id": None,
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "orientation": "horizontal",
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'sum(rate(http_requests_total{{service="{service_name}"}}[${{interval}}]))',
                "legendFormat": "Requests/sec",
                "refId": "A",
            }],
            "title": "Request Rate",
            "type": PanelType.STAT.value,
        })
        
        # Error Rate
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "percent",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green"}, {"color": "yellow", "value": 1}, {"color": "red", "value": 5}],
                    },
                },
            },
            "gridPos": {"h": 7, "w": 6, "x": 6, "y": 1},
            "id": None,
            "options": {
                "colorMode": "background",
                "graphMode": "area",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "orientation": "horizontal",
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'(sum(rate(http_requests_total{{service="{service_name}", status=~"5.."}}[${{interval}}])) / sum(rate(http_requests_total{{service="{service_name}"}}[${{interval}}]))) * 100',
                "legendFormat": "Error %",
                "refId": "A",
            }],
            "title": "Error Rate",
            "type": PanelType.STAT.value,
        })
        
        # P50 Latency
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "ms",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green"}, {"color": "yellow", "value": 200}, {"color": "red", "value": 500}],
                    },
                },
            },
            "gridPos": {"h": 7, "w": 6, "x": 12, "y": 1},
            "id": None,
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "orientation": "horizontal",
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[${{interval}})) by (le)) * 1000',
                "legendFormat": "P50",
                "refId": "A",
            }],
            "title": "Latency P50",
            "type": PanelType.STAT.value,
        })
        
        # P99 Latency
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "ms",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green"}, {"color": "yellow", "value": 500}, {"color": "red", "value": 1000}],
                    },
                },
            },
            "gridPos": {"h": 7, "w": 6, "x": 18, "y": 1},
            "id": None,
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "orientation": "horizontal",
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[${{interval}})) by (le)) * 1000',
                "legendFormat": "P99",
                "refId": "A",
            }],
            "title": "Latency P99",
            "type": PanelType.STAT.value,
        })
        
        # Latency Distribution Heatmap
        panels.append({
            "datasource": ds,
            "description": "Request latency distribution over time",
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-spectral"},
                    "custom": {
                        "axisCenteredZero": False,
                        "axisColorMode": "text",
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "bars",
                        "fillOpacity": 80,
                        "gradientMode": "scheme",
                        "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "scaleDistribution": {"type": "linear"},
                        "showPoints": "never",
                        "spanNulls": False,
                        "stacking": {"group": "A", "mode": "normal"},
                        "thresholdsStyle": {"mode": "off"},
                    },
                    "unit": "ms",
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
            "id": None,
            "options": {
                "calculate": False,
                "cellGap": 2,
                "color": {"mode": "scheme"},
                "columns": [[{"id": "le"}]],
                "exemplars": {"color": "rgba(255,0,255,0.7)"},
                "filterable": False,
                "rows": [[{"id": "time"}]],
                "showFrame": True,
                "showValue": "never",
                "tooltip": {"mode": "single", "sort": "none"},
                "yAxis": {"format": "ms"},
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": f'sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[${{interval}})) by (le)',
                "format": "heatmap",
                "legendFormat": "{{le}}",
                "refId": "A",
            }],
            "title": "📊 Latency Distribution (Heatmap)",
            "type": PanelType.HEATMAP.value,
        })
        
        # Trace Viewer Panel
        panels.append({
            "datasource": {
                "type": "tempo",
                "uid": "${tempo_datasource}",
            },
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
            "id": None,
            "options": {
                "searchBy": "traceID",
                "tags": [{"key": "service.name", "operator": "=", "value": service_name}],
            },
            "title": "🔍 Trace Explorer",
            "type": PanelType.TRACE_VIEWER.value,
        })
        
        return panels
    
    def _create_rca_panels(self, **kwargs) -> List[Dict[str, Any]]:
        """创建根因分析专用面板"""
        ds = "${datasource}"
        
        panels = []
        
        # Header
        panels.append({
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0},
            "panels": [],
            "title": "🔬 Root Cause Analysis Dashboard",
            "type": "row",
        })
        
        # Alert Overview Table
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {
                        "align": "auto",
                        "cellOptions": {"type": "auto"},
                        "inspect": False,
                    },
                    "mappings": [],
                    "thresholds": {"mode": "absolute", "steps": [{"color": "green"}]},
                },
            },
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 1},
            "id": None,
            "options": {
                "cellHeight": "sm",
                "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False},
                "showHeader": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "exemplar": False,
                "expr": 'ALERTS{alertstate="firing"}',
                "format": "table",
                "instant": True,
                "legendFormat": "__auto",
                "range": False,
                "refId": "Alerts",
            }],
            "title": "🚨 Active Alerts",
            "type": PanelType.TABLE.value,
        })
        
        # Correlation Matrix placeholder
        panels.append({
            "datasource": ds,
            "description": "Metric correlation analysis for root cause identification",
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {
                        "axisCenteredZero": True,
                        "axisPlacement": "auto",
                        "drawStyle": "bars",
                        "fillOpacity": 80,
                        "gradientMode": "opacity",
                        "lineWidth": 1,
                        "pointSize": 5,
                        "showPoints": "never",
                        "spanNulls": False,
                    },
                    "unit": "short",
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 9},
            "id": None,
            "options": {
                "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                "tooltip": {"mode": "single"},
            },
            "targets": [
                {
                    "datasource": ds,
                    "editorMode": "code",
                    "expr": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
                    "legendFormat": "Memory Usage",
                    "refId": "mem",
                },
                {
                    "datasource": ds,
                    "editorMode": "code",
                    "expr": '100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[${interval}])) * 100)',
                    "legendFormat": "CPU Usage",
                    "refId": "cpu",
                },
                {
                    "datasource": ds,
                    "editorMode": "code",
                    "expr": '(sum(rate(http_requests_total{status=~"5.."}[${interval}])) / sum(rate(http_requests_total[${interval}]))) * 100',
                    "legendFormat": "Error Rate",
                    "refId": "error",
                },
            ],
            "title": "📈 Key Metrics Correlation",
            "type": PanelType.TIMESERIES.value,
        })
        
        # Service Dependency Graph (placeholder - would need plugin)
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "short",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "blue"},
                            {"color": "yellow", "value": 500},
                            {"color": "red", "value": 2000},
                        ],
                    },
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 9},
            "id": None,
            "options": {
                "displayMode": "gradient",
                "minVizHeight": 10,
                "minVizWidth": 0,
                "orientation": "horizontal",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showUnfilled": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": 'sum by(service) (http_request_duration_seconds_sum) / sum by(service) (http_request_duration_seconds_count) * 1000',
                "legendFormat": "{{service}}",
                "refId": "A",
            }],
            "title": "⏱️ Avg Latency by Service",
            "type": PanelType.BARGAUGE.value,
        })
        
        return panels
    
    def _create_service_mesh_panels(self, **kwargs) -> List[Dict[str, Any]]:
        """创建服务网格监控面板"""
        ds = "${datasource}"
        
        panels = []
        
        panels.append({
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": 0},
            "panels": [],
            "title": "🌐 Service Mesh Overview",
            "type": "row",
        })
        
        # Inter-service traffic
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "palette-classic"},
                    "custom": {
                        "axisPlacement": "auto",
                        "drawStyle": "line",
                        "fillOpacity": 20,
                        "lineWidth": 2,
                        "pointSize": 5,
                        "showPoints": "never",
                        "spanNulls": False,
                    },
                    "unit": "Bps",
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 1},
            "id": None,
            "options": {
                "legend": {"calcs": ["mean", "max"], "displayMode": "table"},
                "tooltip": {"mode": "multi"},
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": 'sum by(source_service, target_service) (istio_requests_total{}) * 100',
                "legendFormat": "{{source_service}} → {{target_service}}",
                "refId": "A",
            }],
            "title": "Service-to-Service Traffic",
            "type": PanelType.TIMESERIES.value,
        })
        
        # Error rates by service
        panels.append({
            "datasource": ds,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "unit": "percent",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "green"}, {"color": "red", "value": 1}],
                    },
                },
            },
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 1},
            "id": None,
            "options": {
                "displayMode": "gradient",
                "orientation": "horizontal",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                "showUnfilled": True,
            },
            "targets": [{
                "datasource": ds,
                "editorMode": "code",
                "expr": '(sum by(destination_service) (istio_requests_total{response_code=~"5.."}) / sum by(destination_service) (istio_requests_total{})) * 100',
                "legendFormat": "{{destination_service}}",
                "refId": "A",
            }],
            "title": "Error Rate by Service",
            "type": PanelType.BARGAUGE.value,
        })
        
        return panels
    
    def _build_panel(self, panel_config: PanelConfig) -> Dict[str, Any]:
        """根据 PanelConfig 构建 Grafana 面板字典"""
        panel = {
            "datasource": panel_config.datasource,
            "description": panel_config.description,
            "gridPos": panel_config.grid_pos,
            "id": None,
            "options": panel_config.options,
            "targets": panel_config.queries,
            "title": panel_config.title,
            "type": panel_config.panel_type.value,
        }
        
        if panel_config.thresholds:
            panel["fieldConfig"] = {
                "defaults": {
                    "thresholds": {
                        "mode": "absolute",
                        "steps": panel_config.thresholds,
                    },
                }
            }
        
        if panel_config.alert_config:
            panel["alert"] = panel_config.alert_config
        
        return panel
    
    async def deploy_to_grafana(
        self,
        dashboard: Dict[str, Any],
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """
        将仪表盘部署到 Grafana
        
        Args:
            dashboard: 生成的仪表盘配置
            overwrite: 是否覆盖已存在的仪表盘
            
        Returns:
            部署结果
        """
        client = self._get_client()
        
        payload = {
            "dashboard": dashboard,
            "overwrite": overwrite,
            "message": f"Updated by AIOps Observability Platform - {datetime.now().isoformat()}",
        }
        
        try:
            response = await client.post("/api/dashboards/db", json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Dashboard deployed successfully: {result.get('slug')}")
            
            return {
                "success": True,
                "dashboard_id": result.get("id"),
                "dashboard_uid": result.get("uid"),
                "url": f"{self.base_url}/d/{result.get('uid')}/{dashboard.get('title', '')}",
                "status": result.get("status"),
            }
            
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(f"Failed to deploy dashboard: {error_detail}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {error_detail}",
            }
        except Exception as e:
            logger.error(f"Error deploying dashboard: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def list_dashboards(self, folder_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出已有仪表盘"""
        client = self._get_client()
        
        params = {}
        if folder_name:
            params["folderIds"] = await self._get_folder_id(folder_name)
        
        try:
            response = await client.get("/api/search", params=params)
            response.raise_for_status()
            
            dashboards = response.json()
            return [{
                "id": d.get("id"),
                "uid": d.get("uid"),
                "title": d.get("title"),
                "url": d.get("url"),
                "type": d.get("type"),
            } for d in dashboards]
            
        except Exception as e:
            logger.error(f"Error listing dashboards: {e}")
            return []
    
    async def delete_dashboard(self, dashboard_uid: str) -> bool:
        """删除仪表盘"""
        client = self._get_client()
        
        try:
            response = await client.delete(f"/api/dashboards/uid/{dashboard_uid}")
            response.raise_for_status()
            logger.info(f"Dashboard {dashboard_uid} deleted")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting dashboard {dashboard_uid}: {e}")
            return False
    
    async def _get_folder_id(self, folder_name: str) -> Optional[int]:
        """获取文件夹 ID"""
        client = self._get_client()
        
        try:
            response = await client.get("/api/folders")
            response.raise_for_status()
            
            folders = response.json()
            for folder in folders:
                if folder.get("title") == folder_name:
                    return folder.get("id")
            
            create_response = await client.post("/api/folders", json={"title": folder_name})
            create_response.raise_for_status()
            
            return create_response.json().get("id")
            
        except Exception as e:
            logger.error(f"Error getting/creating folder {folder_name}: {e}")
            return None


async def create_dashboard_generator(
    config: Optional[ObservabilityConfig] = None,
) -> GrafanaDashboardGenerator:
    """
    工厂函数：创建仪表盘生成器实例
    
    Args:
        config: 可观测性配置
        
    Returns:
        已连接的仪表盘生成器
    """
    generator = GrafanaDashboardGenerator(config=config)
    await generator.connect()
    return generator
