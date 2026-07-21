"""
Observability Platform Configuration - 可观测平台配置管理

支持 Prometheus、Grafana、OpenTelemetry、Tempo 的统一配置
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path


class PrometheusConfig(BaseModel):
    """Prometheus 配置"""
    enabled: bool = True
    url: str = "http://localhost:9090"
    timeout: int = 30
    query_timeout: str = "5m"
    
    default_queries: Dict[str, str] = {
        "cpu_usage": '100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
        "memory_usage": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
        "disk_usage": '(1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"})) * 100',
        "network_rx": 'irate(node_network_receive_bytes_total[5m])',
        "network_tx": 'irate(node_network_transmit_bytes_total[5m])',
        "request_rate": 'sum(rate(http_requests_total[5m])) by (service, method, status)',
        "error_rate": 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service) * 100',
        "latency_p50": 'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))',
        "latency_p99": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))',
        "active_connections": 'sum by (service) (nginx_connections{state="active"})',
    }


class GrafanaConfig(BaseModel):
    """Grafana 配置"""
    enabled: bool = True
    url: str = "http://localhost:3000"
    api_key: Optional[str] = None
    username: str = "admin"
    password: str = "admin"
    
    dashboard_folder: str = "AIOps Observability"
    datasource_name_prometheus: str = "Prometheus"
    datasource_name_tempo: str = "Tempo"
    datasource_name_loki: str = "Loki"


class OpenTelemetryConfig(BaseModel):
    """OpenTelemetry 配置"""
    enabled: bool = True
    service_name: str = "aiops-platform"
    endpoint: str = "http://localhost:4317"
    
    sampling_rate: float = 1.0  # 1.0 = 100% 采样
    
    resource_attributes: Dict[str, str] = {
        "service.name": "aiops-platform",
        "service.version": "1.0.0",
        "deployment.environment": "production",
    }
    
    exporters: List[str] = ["otlp", "console"]


class TempoConfig(BaseModel):
    """Tempo 分布式追踪配置"""
    enabled: bool = True
    url: str = "http://localhost:3200"
    query_url: str = "http://localhost:3200"
    
    default_lookback: str = "1h"
    max_spans_per_trace: int = 1000
    
    search_tags: List[str] = [
        "service.name",
        "error",
        "http.method",
        "http.status_code",
        "db.system",
        "rpc.system",
    ]


class LokiConfig(BaseModel):
    """Loki 日志系统配置（可选）"""
    enabled: bool = False
    url: str = "http://localhost:3100"
    org_id: str = "fake"
    
    default_labels: Dict[str, str] = {
        "job": "aiops-logs",
        "environment": "production",
    }


class AlertConfig(BaseModel):
    """告警规则配置"""
    enabled: bool = True
    
    thresholds: Dict[str, float] = {
        "cpu_usage_warning": 70.0,
        "cpu_usage_critical": 90.0,
        "memory_usage_warning": 80.0,
        "memory_usage_critical": 95.0,
        "disk_usage_warning": 80.0,
        "disk_usage_critical": 95.0,
        "error_rate_warning": 1.0,
        "error_rate_critical": 5.0,
        "latency_p99_warning_ms": 1000.0,
        "latency_p99_critical_ms": 3000.0,
    }
    
    alert_channels: List[str] = ["email", "webhook"]


class ObservabilityConfig(BaseModel):
    """
    可观测性平台总配置
    
    集成所有可观测组件的统一配置入口
    """
    prometheus: PrometheusConfig = Field(default_factory=PrometheusConfig)
    grafana: GrafanaConfig = Field(default_factory=GrafanaConfig)
    opentelemetry: OpenTelemetryConfig = Field(default_factory=OpenTelemetryConfig)
    tempo: TempoConfig = Field(default_factory=TempoConfig)
    loki: LokiConfig = Field(default_factory=LokiConfig)
    alerts: AlertConfig = Field(default_factory=AlertConfig)
    
    root_c_analysis: Dict[str, Any] = {
        "enabled": True,
        "max_depth": 5,
        "confidence_threshold": 0.7,
        "time_correlation_window_minutes": 10,
        "use_llm_enhancement": True,
    }
    
    class Config:
        env_prefix = "OBS_"

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """从环境变量加载配置"""
        return cls(
            prometheus=PrometheusConfig(
                url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
                enabled=os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
            ),
            grafana=GrafanaConfig(
                url=os.getenv("GRAFANA_URL", "http://localhost:3000"),
                api_key=os.getenv("GRAFANA_API_KEY"),
            ),
            tempo=TempoConfig(
                url=os.getenv("TEMPO_URL", "http://localhost:3200"),
            ),
            opentelemetry=OpenTelemetryConfig(
                endpoint=os.getenv("OTEL_ENDPOINT", "http://localhost:4317"),
                service_name=os.getenv("OTEL_SERVICE_NAME", "aiops-platform"),
            ),
        )


def get_observability_config() -> ObservabilityConfig:
    """获取可观测性配置单例"""
    return ObservabilityConfig.from_env()


config = get_observability_config()
