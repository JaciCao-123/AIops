"""
Observability Platform - 可观测性平台包

集成 Prometheus、Grafana、OpenTelemetry、Tempo 进行根因分析
联合 time_sequence_detection 算法库进行增强型根因推理

模块说明:
- config: 可观测平台配置管理
- prometheus_client: Prometheus 指标查询与采集
- opentelemetry_tracer: OpenTelemetry 分布式追踪
- tempo_query: Tempo 链路追踪查询与分析
- grafana_dashboard: Grafana 仪表盘自动生成
- root_cause_analyzer: 多维根因分析引擎（基础版）
- enhanced_rca: 增强型根因分析引擎（集成 GNN/IF/Prophet）
- metrics_collector: 统一指标采集器
- observability_api: REST API 接口
- schemas: 数据模型定义

集成算法 (time_sequence_detection):
- GNN_RCA: 图神经网络微服务根因定位
- IsolationForest + Prophet: 时序异常检测与趋势预测
- Drain + DBSCAN: 智能告警聚合
"""

from .config import ObservabilityConfig, get_observability_config
from .prometheus_client import PrometheusClient, create_prometheus_client

# OpenTelemetry 为可选依赖，若未安装则降级
try:
    from .opentelemetry_tracer import (
        OpenTelemetryTracer,
        get_tracer,
        initialize_observability,
    )
    _OPENTELEMETRY_AVAILABLE = True
except ImportError:
    import logging
    logging.getLogger("observability").warning(
        "OpenTelemetry packages not installed. Tracing disabled. "
        "Install: pip install opentelemetry-api opentelemetry-sdk "
        "opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi "
        "opentelemetry-instrumentation-httpx"
    )
    OpenTelemetryTracer = None  # type: ignore
    _OPENTELEMETRY_AVAILABLE = False

    def get_tracer():
        return None

    def initialize_observability(**kwargs):
        pass

from .tempo_query import TempoQueryClient, create_tempo_client
from .root_cause_analyzer import RootCauseAnalyzer, create_root_cause_analyzer
from .grafana_dashboard import GrafanaDashboardGenerator, DashboardTemplate

# 增强型模块 (联合 time_sequence_detection)
from .enhanced_rca import (
    EnhancedRootCauseAnalyzer,
    create_enhanced_analyzer,
    TimeSeriesDataBridge,
    IsolationForestDetector,
    ProphetForecaster,
    GNRootCauseEngine,
    AlgorithmType,
    FusionStrategy,
)

__all__ = [
    # 基础模块
    "ObservabilityConfig",
    "get_observability_config",
    "PrometheusClient",
    "create_prometheus_client",
    "OpenTelemetryTracer",
    "get_tracer",
    "initialize_observability",
    "TempoQueryClient",
    "create_tempo_client",
    "RootCauseAnalyzer",
    "create_root_cause_analyzer",
    "GrafanaDashboardGenerator",
    "DashboardTemplate",
    
    # 增强型模块 (联合算法)
    "EnhancedRootCauseAnalyzer",
    "create_enhanced_analyzer",
    "TimeSeriesDataBridge",
    "IsolationForestDetector",
    "ProphetForecaster",
    "GNRootCauseEngine",
    "AlgorithmType",
    "FusionStrategy",
]
