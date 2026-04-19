"""
OpenTelemetry Tracer - OpenTelemetry 分布式追踪集成

功能：
1. 自动配置 OpenTelemetry SDK
2. 支持 OTLP 导出器（发送至 Tempo/Jaeger）
3. 自动埋点与手动 Span 创建
4. 上下文传播（Context Propagation）
5. 自定义属性和事件记录
6. 与 FastAPI/asyncio 深度集成
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from opentelemetry import trace, context as otel_context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.semconv.trace import SpanAttributes

from .config import (
    ObservabilityConfig,
    get_observability_config,
    OpenTelemetryConfig,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SpanKind(str, Enum):
    """Span 类型"""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class TraceStatus(str, Enum):
    """Trace 状态"""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


@dataclass
class SpanContext:
    """Span 上下文信息"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: TraceStatus = TraceStatus.UNSET
    attributes: Dict[str, Any] = None
    events: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}
        if self.events is None:
            self.events = []


class OpenTelemetryTracer:
    """
    OpenTelemetry 追踪器
    
    提供：
    - SDK 初始化与配置
    - 自动仪器化（FastAPI、HTTP客户端等）
    - 手动 Span 管理
    - 上下文传播
    - 性能监控与错误追踪
    """
    
    def __init__(
        self,
        config: Optional[ObservabilityConfig] = None,
        otel_config: Optional[OpenTelemetryConfig] = None,
    ):
        """
        初始化 OpenTelemetry 追踪器
        
        Args:
            config: 可观测性总配置
            otel_config: 单独的 OTEL 配置
        """
        self.config = config or get_observability_config()
        self.otel_config = otel_config or self.config.opentelemetry
        
        self._tracer_provider: Optional[TracerProvider] = None
        self._tracer: Optional[trace.Tracer] = None
        self._is_initialized = False
        
        self._active_spans: Dict[str, Any] = {}
    
    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._is_initialized
    
    @property
    def tracer(self) -> trace.Tracer:
        """获取 tracer 实例"""
        if not self._is_initialized or self._tracer is None:
            raise RuntimeError("OpenTelemetry not initialized. Call initialize() first.")
        return self._tracer
    
    def initialize(self):
        """
        初始化 OpenTelemetry SDK
        
        配置导出器、采样率、资源属性等
        """
        if self._is_initialized:
            logger.warning("OpenTelemetry already initialized")
            return
        
        try:
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            
            resource = Resource.create(self.otel_config.resource_attributes)
            
            self._tracer_provider = TracerProvider(resource=resource)
            
            for exporter_name in self.otel_config.exporters:
                if exporter_name == "otlp":
                    otlp_exporter = OTLPSpanExporter(
                        endpoint=self.otel_config.endpoint,
                        insecure=True,
                    )
                    processor = BatchSpanProcessor(otlp_exporter)
                    self._tracer_provider.add_span_processor(processor)
                    logger.info(f"Configured OTLP exporter to {self.otel_config.endpoint}")
                
                elif exporter_name == "console":
                    console_exporter = ConsoleSpanExporter()
                    processor = BatchSpanProcessor(console_exporter)
                    self._tracer_provider.add_span_processor(processer)
                    logger.info("Configured console exporter")
            
            trace.set_tracer_provider(self._tracer_provider)
            
            self._tracer = self._tracer_provider.get_tracer(
                instrumenting_module="aiops-observability",
                schema_url="https://opentelemetry.io/schemas/1.21.0",
            )
            
            self._is_initialized = True
            logger.info(f"OpenTelemetry initialized successfully for service: {self.otel_config.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            raise
    
    def instrument_fastapi(self, app):
        """
        仪器化 FastAPI 应用
        
        Args:
            app: FastAPI 应用实例
        """
        if not self._is_initialized:
            self.initialize()
        
        FastAPIInstrumentor().instrument_app(app)
        logger.info("FastAPI instrumentation enabled")
    
    def instrument_httpx(self):
        """仪器化 HTTPX 客户端"""
        if not self._is_initialized:
            self.initialize()
        
        HTTPXInstrumentor().instrument()
        logger.info("HTTPX instrumentation enabled")
    
    def instrument_sqlalchemy(self, engine):
        """
        仪器化 SQLAlchemy 引擎
        
        Args:
            engine: SQLAlchemy engine 实例
        """
        if not self._is_initialized:
            self.initialize()
        
        SQLAlchemyInstrumentor().instrument(
            engine=engine,
        )
        logger.info("SQLAlchemy instrumentation enabled")
    
    def instrument_redis(self, redis_client):
        """
        仪器化 Redis 客户端
        
        Args:
            redis_client: Redis 客户端实例
        """
        if not self._is_initialized:
            self.initialize()
        
        RedisInstrumentor().instrument_client(redis_client)
        logger.info("Redis instrumentation enabled")
    
    def instrument_all(self, fastapi_app=None, sqlalchemy_engine=None, redis_client=None):
        """
        一键启用所有仪器化
        
        Args:
            fastapi_app: FastAPI 应用
            sqlalchemy_engine: SQLAlchemy 引擎
            redis_client: Redis 客户端
        """
        if not self._is_initialized:
            self.initialize()
        
        if fastapi_app:
            self.instrument_fastapi(fastapi_app)
        
        self.instrument_httpx()
        
        if sqlalchemy_engine:
            self.instrument_sqlalchemy(sqlalchemy_engine)
        
        if redis_client:
            self.instrument_redis(redis_client)
        
        logger.info("All instrumentations enabled")
    
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Any] = None,
    ) -> trace.Span:
        """
        开始一个新的 Span
        
        Args:
            name: 操作名称
            kind: Span 类型
            attributes: 属性字典
            parent: 父 Span 上下文
            
        Returns:
            新创建的 Span
        """
        if not self._is_initialized:
            raise RuntimeError("OpenTelemetry not initialized")
        
        ctx = parent if parent else otel_context.get_current()
        
        span = self.tracer.start_span(
            name=name,
            kind=trace.SpanKind[kind.value],
            attributes=attributes or {},
            context=ctx,
        )
        
        span_key = f"{span.context.trace_id}:{span.context.span_id}"
        self._active_spans[span_key] = {
            "span": span,
            "start_time": datetime.now(),
            "name": name,
        }
        
        return span
    
    def end_span(
        self,
        span: trace.Span,
        status: TraceStatus = TraceStatus.OK,
        error: Optional[Exception] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        结束 Span
        
        Args:
            span: 要结束的 Span
            status: 结束状态
            error: 异常对象（如果有）
            attributes: 额外属性
        """
        if error:
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            span.record_exception(error)
            span.set_attribute(SpanAttributes.EXCEPTION_TYPE, type(error).__name__)
            span.set_attribute(SpanAttributes.EXCEPTION_MESSAGE, str(error))
        else:
            if status == TraceStatus.OK:
                span.set_status(trace.Status(trace.StatusCode.OK))
            elif status == TraceStatus.ERROR:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
        
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        span.end()
        
        span_key = f"{span.context.trace_id}:{span.context.span_id}"
        if span_key in self._active_spans:
            del self._active_spans[span_key]
    
    @asynccontextmanager
    async def async_span_context(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        异步 Span 上下文管理器
        
        Usage:
            async with tracer.async_span_context("operation_name") as span:
                # 业务逻辑
                pass
        """
        span = self.start_span(name, kind=kind, attributes=attributes)
        try:
            yield span
        except Exception as e:
            self.end_span(span, status=TraceStatus.ERROR, error=e)
            raise
        else:
            self.end_span(span, status=TraceStatus.OK)
    
    @contextmanager
    def sync_span_context(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        同步 Span 上下文管理器
        
        Usage:
            with tracer.sync_span_context("operation_name") as span:
                # 业务逻辑
                pass
        """
        span = self.start_span(name, kind=kind, attributes=attributes)
        try:
            yield span
        except Exception as e:
            self.end_span(span, status=TraceStatus.ERROR, error=e)
            raise
        else:
            self.end_span(span, status=TraceStatus.OK)
    
    def trace_function(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Callable[[T], T]:
        """
        装饰器：自动追踪函数执行
        
        Usage:
            @tracer.trace_function()
            async def my_function():
                pass
            
            @tracer.trace_function(name="custom_operation", attributes={"key": "value"})
            def sync_function():
                pass
        """
        def decorator(func: T) -> T:
            func_name = name or f"{func.__module__}.{func.__qualname__}"
            
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    attr_dict = dict(attributes or {})
                    attr_dict["function.name"] = func.__name__
                    attr_dict["function.module"] = func.__module__
                    
                    async with self.async_span_context(func_name, kind=kind, attributes=attr_dict) as span:
                        result = await func(*args, **kwargs)
                        
                        if hasattr(result, '__dict__'):
                            span.set_attribute("result.type", type(result).__name__)
                        
                        return result
                
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    attr_dict = dict(attributes or {})
                    attr_dict["function.name"] = func.__name__
                    attr_dict["function.module"] = func.__module__
                    
                    with self.sync_span_context(func_name, kind=kind, attributes=attr_dict) as span:
                        start_time = time.time()
                        try:
                            result = func(*args, **kwargs)
                            
                            elapsed_ms = (time.time() - start_time) * 1000
                            span.set_attribute("execution.duration_ms", round(elapsed_ms, 2))
                            
                            return result
                        except Exception as e:
                            elapsed_ms = (time.time() - start_time) * 1000
                            span.set_attribute("execution.duration_ms", round(elapsed_ms, 2))
                            raise
                
                return sync_wrapper
            
        return decorator
    
    def trace_method(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> Callable:
        """
        装饰器：用于类方法的追踪（自动绑定 self）
        """
        def decorator(method: Callable) -> Callable:
            method_name = name or f"{method.__qualname__}"
            
            if asyncio.iscoroutinefunction(method):
                @wraps(method)
                async def async_method_wrapper(self_obj, *args, **kwargs):
                    attributes = {
                        "class.name": self_obj.__class__.__name__,
                        "method.name": method.__name__,
                    }
                    
                    async with self.async_span_context(method_name, kind=kind, attributes=attributes) as span:
                        return await method(self_obj, *args, **kwargs)
                
                return async_method_wrapper
            else:
                @wraps(method)
                def sync_method_wrapper(self_obj, *args, **kwargs):
                    attributes = {
                        "class.name": self_obj.__class__.__name__,
                        "method.name": method.__name__,
                    }
                    
                    with self.sync_span_context(method_name, kind=kind, attributes=attributes) as span:
                        return method(self_obj, *args, **kwargs)
                
                return sync_method_wrapper
            
        return decorator
    
    def add_event(
        self,
        span: trace.Span,
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        向 Span 添加事件
        
        Args:
            span: 目标 Span
            event_name: 事件名称
            attributes: 事件属性
        """
        span.add_event(event_name, attributes=attributes or {})
    
    def set_attribute(
        self,
        span: trace.Span,
        key: str,
        value: Any,
    ):
        """设置 Span 属性"""
        span.set_attribute(key, value)
    
    def record_exception(
        self,
        span: trace.Span,
        exception: Exception,
        escaped: bool = False,
    ):
        """
        记录异常到 Span
        
        Args:
            span: 目标 Span
            exception: 异常对象
            escaped: 是否未处理（未被捕获）
        """
        span.record_exception(exception, escaped=escaped)
    
    def get_current_span(self) -> Optional[trace.Span]:
        """获取当前活跃的 Span"""
        return trace.get_current_span()
    
    def get_trace_context(self) -> Dict[str, str]:
        """
        获取当前 Trace 上下文（用于跨服务传递）
        
        Returns:
            包含 trace_id 和 span_id 的字典
        """
        span = self.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            return {
                "trace_id": format(ctx.trace_id, '032x'),
                "span_id": format(ctx.span_id, '016x'),
                "trace_flags": format(ctx.trace_flags, '02x'),
            }
        return {}
    
    def shutdown(self):
        """关闭 OpenTelemetry SDK"""
        if self._tracer_provider:
            self._tracer_provider.shutdown()
            self._is_initialized = False
            logger.info("OpenTelemetry shutdown complete")


# 全局单例实例
_global_tracer: Optional[OpenTelemetryTracer] = None


def get_tracer() -> OpenTelemetryTracer:
    """
    获取全局 OpenTelemetry 追踪器实例
    
    Returns:
        全局追踪器实例
    """
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = OpenTelemetryTracer()
    return _global_tracer


def initialize_observability(config: Optional[ObservabilityConfig] = None) -> OpenTelemetryTracer:
    """
    初始化可观测性平台（便捷函数）
    
    Args:
        config: 可观测性配置
        
    Returns:
        已初始化的追踪器
    """
    global _global_tracer
    _global_tracer = OpenTelemetryTracer(config=config)
    _global_tracer.initialize()
    return _global_tracer


# 便捷装饰器
def trace_operation(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    便捷的追踪装饰器
    
    Usage:
        from aiops.app.observability.opentelemetry_tracer import trace_operation
        
        @trace_operation(name="my_api_endpoint")
        async def api_handler():
            pass
    """
    tracer = get_tracer()
    return tracer.trace_function(name=name, kind=kind, attributes=attributes)


# 数据类导入（如果需要）
try:
    from dataclasses import dataclass
except ImportError:
    dataclass = lambda x: x
