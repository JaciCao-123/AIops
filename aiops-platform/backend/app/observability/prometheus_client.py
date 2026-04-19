"""
Prometheus Client - Prometheus 指标查询与采集客户端

功能：
1. PromQL 查询执行与结果解析
2. 多维度指标采集（CPU、内存、磁盘、网络、应用指标）
3. 异常检测与阈值告警
4. 时间序列数据分析
5. 支持根因分析的指标关联
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

import httpx
import numpy as np
from pydantic import BaseModel, Field

from .config import ObservabilityConfig, get_observability_config, PrometheusConfig

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """指标类型枚举"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(str, Enum):
    """告警严重级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MetricPoint:
    """单个指标数据点"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class TimeSeries:
    """时间序列数据"""
    metric_name: str
    labels: Dict[str, str]
    points: List[MetricPoint] = field(default_factory=list)
    
    @property
    def latest_value(self) -> Optional[float]:
        """获取最新值"""
        return self.points[-1].value if self.points else None
    
    @property
    def values(self) -> List[float]:
        """获取所有值列表"""
        return [p.value for p in self.points]
    
    def get_statistics(self) -> Dict[str, float]:
        """计算统计信息"""
        if not self.values:
            return {}
        values_array = np.array(self.values)
        return {
            "mean": float(np.mean(values_array)),
            "std": float(np.std(values_array)),
            "min": float(np.min(values_array)),
            "max": float(np.max(values_array)),
            "p50": float(np.percentile(values_array, 50)),
            "p95": float(np.percentile(values_array, 95)),
            "p99": float(np.percentile(values_array, 99)),
            "current": self.latest_value or 0,
        }


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    query: str
    severity: AlertSeverity
    threshold: float
    condition: str  # "gt", "lt", "eq", "ne"
    duration: int = 300  # 持续时间（秒）
    message: str = ""
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class AlertEvent:
    """告警事件"""
    rule_name: str
    severity: AlertSeverity
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime
    message: str
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "labels": self.labels,
        }


class QueryResult(BaseModel):
    """查询结果模型"""
    status: str
    query: str
    result_type: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class PrometheusClient:
    """
    Prometheus 客户端
    
    提供完整的 Prometheus API 封装，支持：
    - 即时查询 (Instant Query)
    - 范围查询 (Range Query)
    - 元数据查询
    - 告警规则管理
    - 指标分析与异常检测
    """
    
    def __init__(
        self,
        config: Optional[ObservabilityConfig] = None,
        prometheus_config: Optional[PrometheusConfig] = None,
    ):
        """
        初始化 Prometheus 客户端
        
        Args:
            config: 可观测性总配置
            prometheus_config: 单独的 Prometheus 配置（优先使用）
        """
        self.config = config or get_observability_config()
        self.prometheus_config = prometheus_config or self.config.prometheus
        
        self.base_url = self.prometheus_config.url.rstrip("/")
        self.timeout = self.prometheus_config.timeout
        
        self._client: Optional[httpx.AsyncClient] = None
        self._alert_rules: List[AlertRule] = []
        
        self._initialize_default_alert_rules()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """建立连接"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        logger.info(f"Connected to Prometheus at {self.base_url}")
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            raise RuntimeError("Prometheus client not connected. Call connect() first.")
        return self._client
    
    def _initialize_default_alert_rules(self):
        """初始化默认告警规则"""
        thresholds = self.config.alerts.thresholds
        
        self._alert_rules = [
            AlertRule(
                name="HighCPUUsage",
                query=self.prometheus_config.default_queries["cpu_usage"],
                severity=AlertSeverity.WARNING,
                threshold=thresholds["cpu_usage_warning"],
                condition="gt",
                message="CPU 使用率超过 {threshold}%",
                labels={"component": "system"},
            ),
            AlertRule(
                name="CriticalCPUUsage",
                query=self.prometheus_config.default_queries["cpu_usage"],
                severity=AlertSeverity.CRITICAL,
                threshold=thresholds["cpu_usage_critical"],
                condition="gt",
                message="CPU 使用率超过 {threshold}%，系统可能过载",
                labels={"component": "system"},
            ),
            AlertRule(
                name="HighMemoryUsage",
                query=self.prometheus_config.default_queries["memory_usage"],
                severity=AlertSeverity.WARNING,
                threshold=thresholds["memory_usage_warning"],
                condition="gt",
                message="内存使用率超过 {threshold}%",
                labels={"component": "system"},
            ),
            AlertRule(
                name="CriticalMemoryUsage",
                query=self.prometheus_config.default_queries["memory_usage"],
                severity=AlertSeverity.CRITICAL,
                threshold=thresholds["memory_usage_critical"],
                condition="gt",
                message="内存使用率超过 {threshold}%，可能导致 OOM",
                labels={"component": "system"},
            ),
            AlertRule(
                name="HighDiskUsage",
                query=self.prometheus_config.default_queries["disk_usage"],
                severity=AlertSeverity.WARNING,
                threshold=thresholds["disk_usage_warning"],
                condition="gt",
                message="磁盘使用率超过 {threshold}%",
                labels={"component": "storage"},
            ),
            AlertRule(
                name="HighErrorRate",
                query=self.prometheus_config.default_queries["error_rate"],
                severity=AlertSeverity.WARNING,
                threshold=thresholds["error_rate_warning"],
                condition="gt",
                message="错误率超过 {threshold}%",
                labels={"component": "application"},
            ),
            AlertRule(
                name="HighLatencyP99",
                query=self.prometheus_config.default_queries["latency_p99"],
                severity=AlertSeverity.WARNING,
                threshold=thresholds["latency_p99_warning_ms"] / 1000,
                condition="gt",
                message="P99 延迟超过 {threshold}s",
                labels={"component": "application"},
            ),
        ]
    
    async def instant_query(
        self,
        query: str,
        time: Optional[datetime] = None,
    ) -> QueryResult:
        """
        执行即时查询
        
        Args:
            query: PromQL 查询语句
            time: 查询时间点（默认为当前时间）
            
        Returns:
            QueryResult: 查询结果
        """
        client = self._get_client()
        params: Dict[str, Any] = {"query": query}
        
        if time:
            params["time"] = time.timestamp()
        
        try:
            start_time = datetime.now()
            response = await client.get("/api/v1/query", params=params)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                result_data = data.get("data", {}).get("result", [])
                
                parsed_results = []
                for item in result_data:
                    parsed_item = {
                        "metric": item.get("metric", {}),
                        "value": self._parse_value(item.get("value")),
                    }
                    parsed_results.append(parsed_item)
                
                return QueryResult(
                    status="success",
                    query=query,
                    result_type=data.get("data", {}).get("resultType"),
                    data=parsed_results,
                    execution_time_ms=execution_time,
                )
            else:
                return QueryResult(
                    status="error",
                    query=query,
                    error=data.get("error", "Unknown error"),
                    execution_time_ms=execution_time,
                )
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying Prometheus: {e}")
            return QueryResult(
                status="error",
                query=query,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return QueryResult(
                status="error",
                query=query,
                error=str(e),
            )
    
    async def range_query(
        self,
        query: str,
        start: datetime,
        end: Optional[datetime] = None,
        step: str = "15s",
    ) -> QueryResult:
        """
        执行范围查询
        
        Args:
            query: PromQL 查询语句
            start: 开始时间
            end: 结束时间（默认为当前时间）
            step: 采样间隔
            
        Returns:
            QueryResult: 查询结果，包含时间序列数据
        """
        client = self._get_client()
        end = end or datetime.now()
        
        params = {
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step,
        }
        
        try:
            start_time = datetime.now()
            response = await client.get("/api/v1/query_range", params=params)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "success":
                result_data = data.get("data", {}).get("result", [])
                
                parsed_results = []
                for item in result_data:
                    parsed_item = {
                        "metric": item.get("metric", {}),
                        "values": [
                            self._parse_value(v) 
                            for v in item.get("values", [])
                        ],
                    }
                    parsed_results.append(parsed_item)
                
                return QueryResult(
                    status="success",
                    query=query,
                    result_type=data.get("data", {}).get("resultType"),
                    data=parsed_results,
                    execution_time_ms=execution_time,
                )
            else:
                return QueryResult(
                    status="error",
                    query=query,
                    error=data.get("error", "Unknown error"),
                    execution_time_ms=execution_time,
                )
                
        except Exception as e:
            logger.error(f"Error executing range query: {e}")
            return QueryResult(
                status="error",
                query=query,
                error=str(e),
            )
    
    def _parse_value(self, value: Optional[List]) -> Optional[Tuple[datetime, float]]:
        """解析 Prometheus 返回的值"""
        if not value or len(value) < 2:
            return None
        try:
            timestamp = datetime.fromtimestamp(value[0])
            metric_value = float(value[1])
            return (timestamp, metric_value)
        except (ValueError, TypeError):
            return None
    
    async def collect_system_metrics(
        self,
        instance: Optional[str] = None,
        duration_minutes: int = 5,
    ) -> Dict[str, Any]:
        """
        采集系统级指标
        
        Args:
            instance: 目标实例（可选）
            duration_minutes: 采集的时间范围（分钟）
            
        Returns:
            包含所有系统指标的字典
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration_minutes)
        
        instance_filter = f'{{instance="{instance}"}}' if instance else ""
        
        tasks = {}
        default_queries = self.prometheus_config.default_queries
        
        for metric_name, query_template in default_queries.items():
            if instance_filter and "{instance}" not in query_template:
                modified_query = query_template.replace(")", f"{instance_filter})")
            else:
                modified_query = query_template.format(instance=instance) if instance_filter else query_template
            
            tasks[metric_name] = self.range_query(
                query=modified_query,
                start=start_time,
                end=end_time,
                step="30s",
            )
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        metrics_data = {}
        for metric_name, result in zip(tasks.keys(), results):
            if isinstance(result, QueryResult) and result.status == "success":
                metrics_data[metric_name] = self._process_range_result(result)
            elif isinstance(result, Exception):
                logger.error(f"Failed to collect {metric_name}: {result}")
                metrics_data[metric_name] = {"error": str(result)}
        
        return {
            "collection_time": end_time.isoformat(),
            "duration_minutes": duration_minutes,
            "instance": instance,
            "metrics": metrics_data,
        }
    
    def _process_range_result(self, result: QueryResult) -> List[Dict[str, Any]]:
        """处理范围查询结果"""
        processed = []
        for item in result.data:
            metric_info = item.get("metric", {})
            values = item.get("values", [])
            
            time_series = TimeSeries(
                metric_name=metric_info.get("__name__", "unknown"),
                labels={k: v for k, v in metric_info.items() if k != "__name__"},
            )
            
            for ts, val in values:
                if ts is not None and val is not None:
                    time_series.points.append(MetricPoint(timestamp=ts, value=val))
            
            stats = time_series.get_statistics()
            processed.append({
                "labels": metric_info,
                "statistics": stats,
                "points_count": len(time_series.points),
                "latest_value": time_series.latest_value,
            })
        
        return processed
    
    async def collect_service_metrics(
        self,
        service_name: str,
        duration_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        采集服务级别指标
        
        Args:
            service_name: 服务名称
            duration_minutes: 采集时间范围
            
        Returns:
            服务指标数据
        """
        service_queries = {
            "request_total": f'sum(rate(http_requests_total{{service="{service_name}"}}[5m]))',
            "request_errors": f'sum(rate(http_requests_total{{service="{service_name}", status=~"5.."}}[5m]))',
            "latency_avg": f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))',
            "latency_p99": f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))',
            "throughput": f'sum(rate(http_requests_total{{service="{service_name}"}}[1m]))',
        }
        
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration_minutes)
        
        results = {}
        for metric_name, query in service_queries.items():
            result = await self.range_query(query, start_time, end_time, step="15s")
            if result.status == "success":
                results[metric_name] = self._process_range_result(result)
        
        return {
            "service": service_name,
            "collection_time": end_time.isoformat(),
            "metrics": results,
        }
    
    async def check_alert_rules(self) -> List[AlertEvent]:
        """
        检查所有告警规则并生成告警事件
        
        Returns:
            触发的告警事件列表
        """
        alert_events = []
        
        for rule in self._alert_rules:
            result = await self.instant_query(rule.query)
            
            if result.status != "success":
                continue
            
            for item in result.data:
                metric_labels = item.get("metric", {})
                _, current_value = item.get("value", (None, 0))
                
                if current_value is None:
                    continue
                
                triggered = False
                if rule.condition == "gt" and current_value > rule.threshold:
                    triggered = True
                elif rule.condition == "lt" and current_value < rule.threshold:
                    triggered = True
                elif rule.condition == "eq" and current_value == rule.threshold:
                    triggered = True
                
                if triggered:
                    event = AlertEvent(
                        rule_name=rule.name,
                        severity=rule.severity,
                        metric_name=metric_labels.get("__name__", rule.query[:50]),
                        current_value=current_value,
                        threshold=rule.threshold,
                        timestamp=datetime.now(),
                        message=rule.message.format(threshold=rule.threshold),
                        labels={**metric_labels, **rule.labels},
                    )
                    alert_events.append(event)
        
        alert_events.sort(key=lambda x: x.severity.value, reverse=True)
        return alert_events
    
    async def detect_anomalies(
        self,
        query: str,
        lookback_hours: int = 24,
        zscore_threshold: float = 3.0,
    ) -> Dict[str, Any]:
        """
        基于统计方法的异常检测
        
        Args:
            query: PromQL 查询
            lookback_hours: 回溯时间（小时）
            zscore_threshold: Z-Score 阈值
            
        Returns:
            异常检测结果
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=lookback_hours)
        
        result = await self.range_query(
            query=query,
            start=start_time,
            end=end_time,
            step="5m",
        )
        
        if result.status != "success" or not result.data:
            return {"anomalies": [], "message": "No data available"}
        
        anomalies = []
        for item in result.data:
            values = [v for _, v in item.get("values", []) if v is not None]
            
            if len(values) < 10:
                continue
            
            values_array = np.array(values)
            mean = np.mean(values_array)
            std = np.std(values_array)
            
            if std == 0:
                continue
            
            z_scores = np.abs((values_array - mean) / std)
            anomaly_indices = np.where(z_scores > zscore_threshold)[0]
            
            for idx in anomaly_indices:
                timestamps_values = item.get("values", [])
                if idx < len(timestamps_values):
                    ts, val = timestamps_values[idx]
                    anomalies.append({
                        "timestamp": ts.isoformat() if ts else None,
                        "value": val,
                        "z_score": float(z_scores[idx]),
                        "expected_range": [float(mean - 3 * std), float(mean + 3 * std)],
                        "labels": item.get("metric", {}),
                    })
        
        return {
            "query": query,
            "anomalies": anomalies,
            "total_anomalies": len(anomalies),
            "detection_method": "zscore",
            "threshold": zscore_threshold,
        }
    
    async def correlate_metrics(
        self,
        queries: List[str],
        time_window_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        指标相关性分析（用于根因分析）
        
        Args:
            queries: 要分析的 PromQL 查询列表
            time_window_minutes: 分析时间窗口
            
        Returns:
            相关性矩阵和分析结果
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=time_window_minutes)
        
        results = {}
        for i, query in enumerate(queries):
            result = await self.range_query(query, start_time, end_time, step="30s")
            if result.status == "success" and result.data:
                values = []
                for item in result.data:
                    for _, val in item.get("values", []):
                        if val is not None:
                            values.append(val)
                results[f"metric_{i}"] = np.array(values) if values else np.array([])
        
        correlation_matrix = {}
        metric_names = list(results.keys())
        
        for i, name_i in enumerate(metric_names):
            correlation_matrix[name_i] = {}
            for j, name_j in enumerate(metric_names):
                if i <= j:
                    arr_i = results[name_i]
                    arr_j = results[name_j]
                    
                    if len(arr_i) > 0 and len(arr_j) > 0:
                        min_len = min(len(arr_i), len(arr_j))
                        corr_coef = float(np.corrcoef(arr_i[:min_len], arr_j[:min_len])[0, 1])
                    else:
                        corr_coef = 0.0
                    
                    correlation_matrix[name_i][name_j] = corr_coef
                    if i != j:
                        correlation_matrix[name_j][name_i] = corr_coef
        
        return {
            "analysis_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_minutes": time_window_minutes,
            },
            "queries_analyzed": len(queries),
            "correlation_matrix": correlation_matrix,
            "strong_correlations": self._find_strong_correlations(correlation_matrix, threshold=0.7),
        }
    
    def _find_strong_correlations(
        self,
        matrix: Dict[str, Dict[str, float]],
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """找出强相关指标对"""
        strong_corrs = []
        seen = set()
        
        for m1, correlations in matrix.items():
            for m2, coef in correlations.items():
                if m1 != m2 and abs(coef) >= threshold:
                    pair = tuple(sorted([m1, m2]))
                    if pair not in seen:
                        seen.add(pair)
                        strong_corrs.append({
                            "metric_1": m1,
                            "metric_2": m2,
                            "correlation_coefficient": coef,
                            "strength": "strong" if abs(coef) > 0.9 else "moderate",
                        })
        
        strong_corrs.sort(key=lambda x: abs(x["correlation_coefficient"]), reverse=True)
        return strong_corrs
    
    async def get_metric_metadata(self, metric_name: str) -> Dict[str, Any]:
        """获取指标的元数据信息"""
        client = self._get_client()
        
        try:
            response = await client.get("/api/v1/metadata", params={"metric": metric_name})
            response.raise_for_status()
            data = response.json()
            return data.get("data", {})
        except Exception as e:
            logger.error(f"Error fetching metadata for {metric_name}: {e}")
            return {"error": str(e)}
    
    async def get_targets(self) -> List[Dict[str, Any]]:
        """获取 Prometheus targets 状态"""
        client = self._get_client()
        
        try:
            response = await client.get("/api/v1/targets")
            response.raise_for_status()
            data = response.json()
            
            targets = data.get("data", {}).get("activeTargets", [])
            return [{
                "labels": t.get("labels", {}),
                "health": t.get("health"),
                "last_scrape": t.get("lastScrape"),
                "scrape_duration": t.get("lastScrapeDuration"),
            } for t in targets]
        except Exception as e:
            logger.error(f"Error fetching targets: {e}")
            return []
    
    async def health_check(self) -> Dict[str, Any]:
        """检查 Prometheus 健康状态"""
        client = self._get_client()
        
        try:
            response = await client.get("/-/healthy")
            is_healthy = response.status_code == 200
            
            config_response = await client.get("/api/v1/status/config")
            config_data = config_response.json().get("data", {}) if config_response.status_code == 200 else {}
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "url": self.base_url,
                "version": config_data.get("versionInfo", {}).get("version", "unknown"),
                "uptime": self._estimate_uptime(config_data),
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "url": self.base_url,
                "error": str(e),
            }
    
    def _estimate_uptime(self, config_data: Dict[str, Any]) -> Optional[str]:
        """估算运行时间（简化版）"""
        return None


async def create_prometheus_client(
    config: Optional[ObservabilityConfig] = None,
) -> PrometheusClient:
    """
    工厂函数：创建 Prometheus 客户端实例
    
    Args:
        config: 可观测性配置
        
    Returns:
        已连接的 Prometheus 客户端
    """
    client = PrometheusClient(config=config)
    await client.connect()
    return client


# 便捷函数
async def query_prometheus(
    query: str,
    config: Optional[ObservabilityConfig] = None,
) -> QueryResult:
    """
    快捷查询函数
    
    Args:
        query: PromQL 查询
        config: 配置
        
    Returns:
        查询结果
    """
    async with create_prometheus_client(config) as client:
        return await client.instant_query(query)
