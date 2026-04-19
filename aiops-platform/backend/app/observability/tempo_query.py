"""
Tempo Query Client - Tempo 分布式追踪查询与分析

功能：
1. 通过 Trace ID 查询完整调用链
2. 基于标签的 Trace 搜索
3. Span 分析与性能瓶颈识别
4. 错误链路与异常传播分析
5. 服务依赖关系图构建
6. 与 Prometheus 指标关联进行根因分析
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
from pydantic import BaseModel, Field

from .config import (
    ObservabilityConfig,
    get_observability_config,
    TempoConfig,
)

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """Span 类型"""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"
    DATABASE = "DATABASE"
    MESSAGE_QUEUE = "MESSAGE_QUEUE"


class StatusCode(str, Enum):
    """状态码"""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


@dataclass
class SpanAttribute:
    """Span 属性"""
    key: str
    value: Any


@dataclass
class SpanEvent:
    """Span 事件"""
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanLink:
    """Span 链接"""
    trace_id: str
    span_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """
    Span 数据结构
    
    表示分布式追踪中的一个操作单元
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    
    operation_name: str
    kind: SpanKind
    
    start_time: datetime
    end_time: Optional[datetime]
    
    status_code: StatusCode = StatusCode.UNSET
    status_message: str = ""
    
    service_name: str = ""
    resource_attributes: Dict[str, Any] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanLink] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """获取持续时间（毫秒）"""
        if self.start_time and self.end_time:
            delta = (self.end_time - self.start_time).total_seconds() * 1000
            return delta
        return None
    
    @property
    def is_error(self) -> bool:
        """是否包含错误"""
        return self.status_code == StatusCode.ERROR
    
    @property
    def has_exceptions(self) -> bool:
        """是否有异常事件"""
        return any("exception" in event.name.lower() for event in self.events)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code.value,
            "status_message": self.status_message,
            "service_name": self.service_name,
            "attributes": self.attributes,
            "is_error": self.is_error,
            "has_exceptions": self.has_exceptions,
        }


@dataclass
class Trace:
    """
    Trace 数据结构
    
    表示一次完整的分布式请求调用链
    """
    trace_id: str
    root_spans: List[Span] = field(default_factory=list)
    spans: List[Span] = field(default_factory=list)
    
    @property
    def start_time(self) -> Optional[datetime]:
        """Trace 开始时间"""
        if not self.spans:
            return None
        return min(span.start_time for span in self.spans if span.start_time)
    
    @property
    def end_time(self) -> Optional[datetime]:
        """Trace 结束时间"""
        if not self.spans or not all(span.end_time for span in self.spans):
            return None
        return max(span.end_time for span in self.spans if span.end_time)
    
    @property
    def total_duration_ms(self) -> Optional[float]:
        """总持续时间"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    @property
    def span_count(self) -> int:
        """Span 数量"""
        return len(self.spans)
    
    @property
    def error_spans(self) -> List[Span]:
        """包含错误的 Span 列表"""
        return [s for s in self.spans if s.is_error]
    
    @property
    def services_involved(self) -> List[str]:
        """涉及的服务列表"""
        services = set(s.service_name for s in self.spans if s.service_name)
        return sorted(list(services))
    
    @property
    def has_errors(self) -> bool:
        """是否包含错误"""
        return any(s.is_error for s in self.spans)
    
    def get_service_spans(self, service_name: str) -> List[Span]:
        """获取特定服务的所有 Span"""
        return [s for s in self.spans if s.service_name == service_name]
    
    def get_span_tree(self) -> Dict[str, Any]:
        """
        构建 Span 树形结构
        
        Returns:
            树形结构的字典表示
        """
        span_map = {s.span_id: s for s in self.spans}
        
        def build_tree(span: Span) -> Dict[str, Any]:
            children = [build_tree(s) for s in self.spans if s.parent_span_id == span.span_id]
            
            return {
                "span_id": span.span_id,
                "operation_name": span.operation_name,
                "service_name": span.service_name,
                "kind": span.kind.value,
                "start_time": span.start_time.isoformat() if span.start_time else None,
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "duration_ms": span.duration_ms,
                "status": span.status_code.value,
                "is_error": span.is_error,
                "children": sorted(children, key=lambda x: x.get("start_time") or ""),
            }
        
        roots = [s for s in self.spans if not s.parent_span_id]
        trees = [build_tree(r) for r in roots]
        
        return {
            "trace_id": self.trace_id,
            "root_spans_count": len(roots),
            "total_spans": len(self.spans),
            "tree": sorted(trees, key=lambda x: x.get("start_time") or ""),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "span_count": self.span_count,
            "services_involved": self.services_involved,
            "has_errors": self.has_errors,
            "error_count": len(self.error_spans),
            "spans": [s.to_dict() for s in self.spans],
        }


@dataclass
class SearchResult:
    """搜索结果"""
    traces: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceDependency:
    """服务依赖关系"""
    source_service: str
    target_service: str
    call_count: int = 0
    avg_duration_ms: float = 0.0
    error_rate: float = 0.0


class TempoQueryClient:
    """
    Tempo 查询客户端
    
    提供：
    - Trace 查询与解析
    - 基于标签的搜索
    - 性能分析与瓶颈识别
    - 错误链路分析
    - 服务依赖图构建
    """
    
    def __init__(
        self,
        config: Optional[ObservabilityConfig] = None,
        tempo_config: Optional[TempoConfig] = None,
    ):
        """
        初始化 Tempo 客户端
        
        Args:
            config: 可观测性总配置
            tempo_config: 单独的 Tempo 配置
        """
        self.config = config or get_observability_config()
        self.tempo_config = tempo_config or self.config.tempo
        
        self.query_url = self.tempo_config.query_url.rstrip("/")
        self.default_lookback = self.tempo_config.default_lookback
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def connect(self):
        """建立连接"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.query_url,
                timeout=30.0,
                headers={"Accept": "application/json"},
            )
        logger.info(f"Connected to Tempo at {self.query_url}")
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            raise RuntimeError("Tempo client not connected. Call connect() first.")
        return self._client
    
    async def query_trace_by_id(
        self,
        trace_id: str,
    ) -> Optional[Trace]:
        """
        通过 Trace ID 查询完整的调用链
        
        Args:
            trace_id: Trace ID
            
        Returns:
            Trace 对象，如果未找到则返回 None
        """
        client = self._get_client()
        
        try:
            response = await client.get(f"/api/traces/{trace_id}")
            response.raise_for_status()
            
            data = response.json()
            return self._parse_trace_response(data)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Trace {trace_id} not found")
                return None
            logger.error(f"HTTP error querying trace: {e}")
            raise
        except Exception as e:
            logger.error(f"Error querying trace {trace_id}: {e}")
            raise
    
    async def search_traces(
        self,
        tags: Optional[Dict[str, str]] = None,
        service_name: Optional[str] = None,
        span_name: Optional[str] = None,
        min_duration: Optional[str] = None,
        max_duration: Optional[str] = None,
        lookback: Optional[str] = None,
        limit: int = 20,
    ) -> SearchResult:
        """
        搜索 Traces
        
        Args:
            tags: 标签过滤条件
            service_name: 服务名称
            span_name: Span 名称
            min_duration: 最小持续时间（如 "500ms", "1s"）
            max_duration: 最大持续时间
            lookback: 回溯时间范围（如 "1h", "30m"）
            limit: 返回结果数量限制
            
        Returns:
            搜索结果
        """
        client = self._get_client()
        lookback = lookback or self.default_lookback
        
        params: Dict[str, Any] = {
            "limit": limit,
            "start": f"-{lookback}",
        }
        
        if tags:
            for key, value in tags.items():
                params[f"tags"] = f"{key}={value}"
        
        if service_name:
            params["tags"] = params.get("tags", "") + f" service.name={service_name}"
        
        if span_name:
            params["spanNameFilter"] = span_name
        
        if min_duration:
            params["minDuration"] = min_duration
        
        if max_duration:
            params["maxDuration"] = max_duration
        
        try:
            response = await client.get("/api/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            traces = data.get("traces", [])
            
            result = SearchResult(
                traces=traces,
                total=data.get("metrics", {}).get("tracesFound", len(traces)),
                metrics=data.get("metrics", {}),
            )
            
            logger.info(f"Search returned {len(traces)} traces")
            return result
            
        except Exception as e:
            logger.error(f"Error searching traces: {e}")
            return SearchResult(traces=[], total=0, metrics={"error": str(e)})
    
    async def search_error_traces(
        self,
        service_name: Optional[str] = None,
        lookback: str = "1h",
        limit: int = 50,
    ) -> SearchResult:
        """
        搜索包含错误的 Traces
        
        Args:
            service_name: 服务名称（可选）
            lookback: 回溯时间
            limit: 结果限制
            
        Returns:
            包含错误的 Trace 列表
        """
        tags = {"error": "true"}
        if service_name:
            tags["service.name"] = service_name
        
        return await self.search_traces(
            tags=tags,
            lookback=lookback,
            limit=limit,
        )
    
    async def search_slow_traces(
        self,
        min_duration: str = "5s",
        service_name: Optional[str] = None,
        lookback: str = "1h",
        limit: int = 30,
    ) -> SearchResult:
        """
        搜索慢请求 Traces
        
        Args:
            min_duration: 最小持续时间阈值
            service_name: 服务名称
            lookback: 回溯时间
            limit: 结果限制
            
        Returns:
            慢请求 Trace 列表
        """
        return await self.search_traces(
            min_duration=min_duration,
            service_name=service_name,
            lookback=lookback,
            limit=limit,
        )
    
    def _parse_trace_response(self, data: Dict[str, Any]) -> Optional[Trace]:
        """
        解析 Tempo 返回的 Trace 数据
        
        Args:
            data: Tempo API 原始响应
            
        Returns:
            解析后的 Trace 对象
        """
        batches = data.get("batches", [])
        if not batches:
            return None
        
        all_spans = []
        trace_id = ""
        
        for batch in batches:
            resource_spans = batch.get("resourceSpans", [])
            
            for resource_span in resource_spans:
                resource = resource_span.get("resource", {})
                resource_attrs = {
                    attr["key"]: attr.get("value", {}).get("stringValue", "")
                    for attr in resource.get("attributes", [])
                }
                
                service_name = resource_attrs.get("service.name", "")
                
                scope_spans = resource_span.get("scopeSpans", [])
                
                for scope_span in scope_spans:
                    spans_data = scope_span.get("spans", [])
                    
                    for span_data in spans_data:
                        if not trace_id:
                            trace_id = span_data.get("traceId", "")
                        
                        span = self._parse_span(span_data, service_name, resource_attrs)
                        if span:
                            all_spans.append(span)
        
        if not all_spans:
            return None
        
        root_spans = [s for s in all_spans if not s.parent_span_id]
        
        return Trace(
            trace_id=trace_id,
            root_spans=root_spans,
            spans=all_spans,
        )
    
    def _parse_span(
        self,
        span_data: Dict[str, Any],
        service_name: str,
        resource_attrs: Dict[str, Any],
    ) -> Optional[Span]:
        """解析单个 Span 数据"""
        try:
            start_time_ns = span_data.get("startTimeUnixNano", "0")
            end_time_ns = span_data.get("endTimeUnixNano", "0")
            
            start_time = datetime.fromtimestamp(int(start_time_ns) / 1e9) if start_time_ns else None
            end_time = datetime.fromtimestamp(int(end_time_ns) / 1e9) if end_time_ns and int(end_time_ns) > 0 else None
            
            status = span_data.get("status", {})
            status_code_str = status.get("code", "STATUS_CODE_UNSET").replace("STATUS_CODE_", "")
            
            attributes = {}
            for attr in span_data.get("attributes", []):
                attr_value = attr.get("value", {})
                if "stringValue" in attr_value:
                    attributes[attr["key"]] = attr_value["stringValue"]
                elif "intValue" in attr_value:
                    attributes[attr["key"]] = attr_value.get("intValue", 0)
                elif "doubleValue" in attr_value:
                    attributes[attr["key"]] = attr_value.get("doubleValue", 0.0)
                elif "boolValue" in attr_value:
                    attributes[attr["key"]] = attr_value.get("boolValue", False)
            
            events = []
            for event in span_data.get("events", []):
                event_attrs = {}
                for attr in event.get("attributes", []):
                    attr_value = attr.get("value", {})
                    if "stringValue" in attr_value:
                        event_attrs[attr["key"]] = attr_value["stringValue"]
                
                event_time_unix_nano = event.get("timeUnixNano", "0")
                event_time = datetime.fromtimestamp(int(event_time_unix_nano) / 1e9) if event_time_unix_nano else None
                
                events.append(SpanEvent(
                    name=event.get("name", ""),
                    timestamp=event_time or datetime.now(),
                    attributes=event_attrs,
                ))
            
            kind_map = {
                "SPAN_KIND_INTERNAL": SpanKind.INTERNAL,
                "SPAN_KIND_SERVER": SpanKind.SERVER,
                "SPAN_KIND_CLIENT": SpanKind.CLIENT,
                "SPAN_KIND_PRODUCER": SpanKind.PRODUCER,
                "SPAN_KIND_CONSUMER": SpanKind.CONSUMER,
            }
            
            return Span(
                trace_id=span_data.get("traceId", ""),
                span_id=span_data.get("spanId", ""),
                parent_span_id=span_data.get("parentSpanId"),
                operation_name=span_data.get("name", "unknown"),
                kind=kind_map.get(span_data.get("kind", "SPAN_KIND_INTERNAL"), SpanKind.INTERNAL),
                start_time=start_time or datetime.now(),
                end_time=end_time,
                status_code=StatusCode(status_code_str) if status_code_str in StatusCode.__members__ else StatusCode.UNSET,
                status_message=status.get("message", ""),
                service_name=service_name,
                resource_attributes=resource_attrs,
                attributes=attributes,
                events=events,
            )
            
        except Exception as e:
            logger.error(f"Error parsing span: {e}")
            return None
    
    async def analyze_trace_performance(
        self,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        分析 Trace 性能特征
        
        Args:
            trace_id: Trace ID
            
        Returns:
            性能分析结果
        """
        trace = await self.query_trace_by_id(trace_id)
        if not trace:
            return {"error": "Trace not found"}
        
        spans_with_duration = [s for s in trace.spans if s.duration_ms is not None]
        
        if not spans_with_duration:
            return {"trace_id": trace_id, "message": "No duration data available"}
        
        durations = np.array([s.duration_ms for s in spans_with_duration])
        
        sorted_spans = sorted(spans_with_duration, key=lambda x: x.duration_ms or 0, reverse=True)
        top_5_slowest = sorted_spans[:5]
        
        error_spans = [s for s in trace.spans if s.is_error]
        
        service_stats = {}
        for service in trace.services_involved:
            service_spans = trace.get_service_spans(service)
            service_durations = [s.duration_ms for s in service_spans if s.duration_ms is not None]
            service_errors = sum(1 for s in service_spans if s.is_error)
            
            service_stats[service] = {
                "span_count": len(service_spans),
                "avg_duration_ms": float(np.mean(service_durations)) if service_durations else 0,
                "max_duration_ms": float(np.max(service_durations)) if service_durations else 0,
                "min_duration_ms": float(np.min(service_durations)) if service_durations else 0,
                "total_duration_ms": float(sum(service_durations)),
                "error_count": service_errors,
                "error_rate": service_errors / len(service_spans) if service_spans else 0,
            }
        
        return {
            "trace_id": trace.trace_id,
            "analysis_summary": {
                "total_spans": trace.span_count,
                "total_duration_ms": trace.total_duration_ms,
                "services_count": len(trace.services_involved),
                "services_involved": trace.services_involved,
                "has_errors": trace.has_errors,
                "error_count": len(error_spans),
            },
            "duration_statistics": {
                "mean_ms": float(np.mean(durations)),
                "std_ms": float(np.std(durations)),
                "min_ms": float(np.min(durations)),
                "max_ms": float(np.max(durations)),
                "p50_ms": float(np.percentile(durations, 50)),
                "p95_ms": float(np.percentile(durations, 95)),
                "p99_ms": float(np.percentile(durations, 99)),
            },
            "top_5_slowest_spans": [
                {
                    "span_id": s.span_id,
                    "operation_name": s.operation_name,
                    "service_name": s.service_name,
                    "duration_ms": s.duration_ms,
                    "is_error": s.is_error,
                } for s in top_5_slowest
            ],
            "error_spans": [
                {
                    "span_id": s.span_id,
                    "operation_name": s.operation_name,
                    "service_name": s.service_name,
                    "duration_ms": s.duration_ms,
                    "status_message": s.status_message,
                } for s in error_spans[:10]
            ],
            "service_breakdown": service_stats,
            "bottleneck_analysis": self._identify_bottlenecks(trace),
        }
    
    def _identify_bottlenecks(self, trace: Trace) -> List[Dict[str, Any]]:
        """
        识别性能瓶颈
        
        Args:
            trace: Trace 对象
            
        Returns:
            瓶颈列表
        """
        bottlenecks = []
        
        spans_with_duration = [(s, s.duration_ms) for s in trace.spans if s.duration_ms is not None]
        spans_with_duration.sort(key=lambda x: x[1] or 0, reverse=True)
        
        if not spans_with_duration:
            return bottlenecks
        
        avg_duration = np.mean([d for _, d in spans_with_duration])
        std_duration = np.std([d for _, d in spans_with_duration])
        threshold = avg_duration + (2 * std_duration)
        
        for span, duration in spans_with_duration:
            if duration > threshold:
                severity = "critical" if duration > avg_duration + (3 * std_duration) else "warning"
                bottlenecks.append({
                    "span_id": span.span_id,
                    "operation_name": span.operation_name,
                    "service_name": span.service_name,
                    "duration_ms": duration,
                    "severity": severity,
                    "deviation_from_mean": round((duration - avg_duration) / avg_duration * 100, 2) if avg_duration > 0 else 0,
                    "recommendation": self._generate_bottleneck_recommendation(span, duration, avg_duration),
                })
        
        return bottlenecks[:10]
    
    def _generate_bottleneck_recommendation(
        self,
        span: Span,
        duration: float,
        avg_duration: float,
    ) -> str:
        """生成瓶颈优化建议"""
        if "sql" in span.operation_name.lower() or "query" in span.operation_name.lower():
            return "Consider optimizing database query or adding indexes"
        elif "http" in span.operation_name.lower() or "request" in span.operation_name.lower():
            return "External API call is slow; consider caching or timeout optimization"
        elif span.kind == SpanKind.DATABASE:
            return "Database operation is a bottleneck; review query performance"
        elif span.kind == SpanKind.CLIENT:
            return "Downstream service call is slow; check dependency health"
        else:
            return f"This operation takes {round(duration/avg_duration, 2)}x longer than average"
    
    async def build_service_dependency_graph(
        self,
        time_window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        构建服务依赖关系图
        
        Args:
            time_window_minutes: 分析时间窗口
            
        Returns:
            服务依赖关系图
        """
        lookback = f"{time_window_minutes}m"
        search_result = await self.search_traces(lookback=lookback, limit=200)
        
        dependencies: Dict[Tuple[str, str], List[float]] = {}
        
        for trace_info in search_result.traces:
            trace_id = trace_info.get("traceID", "")
            if not trace_id:
                continue
            
            try:
                trace = await self.query_trace_by_id(trace_id)
                if not trace:
                    continue
                
                for span in trace.spans:
                    if span.parent_span_id and span.duration_ms:
                        parent_span = next(
                            (s for s in trace.spans if s.span_id == span.parent_span_id),
                            None,
                        )
                        
                        if parent_span and parent_span.service_name != span.service_name:
                            dep_key = (parent_span.service_name, span.service_name)
                            if dep_key not in dependencies:
                                dependencies[dep_key] = []
                            dependencies[dep_key].append(span.duration_ms or 0)
                            
            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                continue
        
        service_deps = []
        for (source, target), durations in dependencies.items():
            arr = np.array(durations) if durations else np.array([])
            service_deps.append(ServiceDependency(
                source_service=source,
                target_service=target,
                call_count=len(durations),
                avg_duration_ms=float(np.mean(arr)) if len(arr) > 0 else 0,
                error_rate=0.0,
            ))
        
        services = set()
        for dep in service_deps:
            services.add(dep.source_service)
            services.add(dep.target_service)
        
        return {
            "time_window_minutes": time_window_minutes,
            "traces_analyzed": len(search_result.traces),
            "services": sorted(list(services)),
            "dependencies": [
                {
                    "source": d.source_service,
                    "target": d.target_service,
                    "call_count": d.call_count,
                    "avg_duration_ms": round(d.avg_duration_ms, 2),
                } for d in sorted(service_deps, key=lambda x: x.call_count, reverse=True)
            ],
        }
    
    async def analyze_error_propagation(
        self,
        trace_id: str,
    ) -> Dict[str, Any]:
        """
        分析错误在调用链中的传播路径
        
        Args:
            trace_id: Trace ID
            
        Returns:
            错误传播分析结果
        """
        trace = await self.query_trace_by_id(trace_id)
        if not trace or not trace.has_errors:
            return {"message": "No errors found in this trace"}
        
        error_spans = trace.error_spans
        
        propagation_paths = []
        visited = set()
        
        for error_span in error_spans:
            path = self._find_error_path(error_span, trace, visited)
            if path:
                propagation_paths.append(path)
        
        root_causes = self._identify_root_cause_spans(error_spans, trace)
        
        return {
            "trace_id": trace_id,
            "total_errors": len(error_spans),
            "propagation_paths": propagation_paths,
            "potential_root_causes": [
                {
                    "span_id": rc.span_id,
                    "operation_name": rc.operation_name,
                    "service_name": rc.service_name,
                    "error_message": rc.status_message,
                    "first_in_chain": True,
                } for rc in root_causes
            ],
            "affected_services": list(set(
                s.service_name for s in error_spans if s.service_name
            )),
        }
    
    def _find_error_path(
        self,
        error_span: Span,
        trace: Trace,
        visited: set,
    ) -> Optional[List[Dict[str, Any]]]:
        """查找从根到错误 Span 的路径"""
        path = []
        current = error_span
        
        while current:
            span_id = current.span_id
            if span_id in visited:
                break
            visited.add(span_id)
            
            path.append({
                "span_id": current.span_id,
                "operation_name": current.operation_name,
                "service_name": current.service_name,
                "is_error": current.is_error,
                "duration_ms": current.duration_ms,
            })
            
            if current.parent_span_id:
                current = next(
                    (s for s in trace.spans if s.span_id == current.parent_span_id),
                    None,
                )
            else:
                break
        
        path.reverse()
        return path if len(path) > 1 else None
    
    def _identify_root_cause_spans(
        self,
        error_spans: List[Span],
        trace: Trace,
    ) -> List[Span]:
        """
        识别可能的根本原因 Span
        
        规则：
        1. 没有 parent 的错误 Span
        2. 在调用链最底层的错误 Span
        """
        error_span_ids = {s.span_id for s in error_spans}
        root_causes = []
        
        for error_span in error_spans:
            is_root = True
            
            child_errors = [
                s for s in error_spans 
                if s.parent_span_id == error_span.span_id
            ]
            
            if child_errors:
                is_root = False
            
            if is_root:
                root_causes.append(error_span)
        
        return root_causes
    
    async def health_check(self) -> Dict[str, Any]:
        """检查 Tempo 健康状态"""
        client = self._get_client()
        
        try:
            response = await client.get("/ready")
            is_ready = response.status_code == 204
            
            return {
                "status": "ready" if is_ready else "not_ready",
                "url": self.query_url,
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "url": self.query_url,
                "error": str(e),
            }


async def create_tempo_client(
    config: Optional[ObservabilityConfig] = None,
) -> TempoQueryClient:
    """
    工厂函数：创建 Tempo 客户端实例
    
    Args:
        config: 可观测性配置
        
    Returns:
        已连接的 Tempo 客户端
    """
    client = TempoQueryClient(config=config)
    await client.connect()
    return client
