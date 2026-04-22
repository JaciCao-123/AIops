"""
链路追踪 API 接口

提供 Trace 查询、服务依赖分析等接口
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import random
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/traces", tags=["tracing"])


class TraceSearchParams(BaseModel):
    """Trace 搜索参数"""
    service_name: Optional[str] = None
    error_only: bool = False
    slow_only: bool = False
    min_duration_ms: Optional[int] = None
    lookback: str = "1h"
    limit: int = 50


class TraceAnalysisParams(BaseModel):
    """Trace 分析参数"""
    trace_id: Optional[str] = None
    service_name: Optional[str] = None
    error_only: bool = False
    slow_only: bool = False
    min_duration_ms: Optional[int] = None
    lookback: str = "1h"


def parse_lookback(lookback: str) -> timedelta:
    """解析 lookback 时间字符串"""
    unit = lookback[-1]
    value = int(lookback[:-1])
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        return timedelta(hours=1)


def generate_mock_traces(
    service_name: Optional[str] = None,
    error_only: bool = False,
    slow_only: bool = False,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """生成模拟 Trace 数据"""
    services = ["api-gateway", "user-service", "order-service", "payment-service", "inventory-service", "notification-service"]
    operations = ["GET /api/users", "POST /api/orders", "GET /api/products", "POST /api/payments", "GET /api/inventory"]
    
    traces = []
    now = datetime.utcnow()
    
    for i in range(min(limit, 20)):
        trace_id = str(uuid.uuid4()).replace('-', '')[:32]
        root_service = service_name or random.choice(services)
        has_error = error_only or (random.random() < 0.2 if not error_only else True)
        duration = random.randint(500, 5000) if slow_only else random.randint(10, 2000)
        
        trace = {
            "traceID": trace_id,
            "rootServiceName": root_service,
            "rootTraceName": random.choice(operations),
            "startTime": (now - timedelta(minutes=random.randint(0, 60))).isoformat() + "Z",
            "durationMs": duration,
            "spanCount": random.randint(3, 15),
            "hasError": has_error,
            "services": random.sample(services, k=random.randint(2, 4))
        }
        traces.append(trace)
    
    return traces


def generate_mock_trace_detail(trace_id: str) -> Dict[str, Any]:
    """生成模拟 Trace 详情"""
    services = ["api-gateway", "user-service", "order-service", "payment-service"]
    operations = ["GET /api/users", "POST /api/orders", "validate_payment", "check_inventory"]
    
    spans = []
    base_time = datetime.utcnow() - timedelta(minutes=5)
    
    root_span_id = str(uuid.uuid4()).replace('-', '')[:16]
    spans.append({
        "spanID": root_span_id,
        "parentSpanID": None,
        "operationName": operations[0],
        "serviceName": services[0],
        "startTime": base_time.isoformat() + "Z",
        "durationMs": 1500,
        "tags": {"http.method": "GET", "http.status_code": 200},
        "hasError": False,
        "statusCode": "OK"
    })
    
    for i, (svc, op) in enumerate(zip(services[1:], operations[1:])):
        span_id = str(uuid.uuid4()).replace('-', '')[:16]
        has_error = i == 2
        spans.append({
            "spanID": span_id,
            "parentSpanID": root_span_id,
            "operationName": op,
            "serviceName": svc,
            "startTime": (base_time + timedelta(milliseconds=100 * (i + 1))).isoformat() + "Z",
            "durationMs": random.randint(50, 500),
            "tags": {"http.method": "POST", "http.status_code": 500 if has_error else 200},
            "hasError": has_error,
            "statusCode": "ERROR" if has_error else "OK"
        })
    
    error_spans = [s for s in spans if s["hasError"]]
    
    return {
        "traceID": trace_id,
        "spans": spans,
        "services": list(set(s["serviceName"] for s in spans)),
        "totalDurationMs": 1500,
        "hasError": len(error_spans) > 0,
        "errorSpans": error_spans
    }


def generate_mock_dependency(lookback: str) -> Dict[str, Any]:
    """生成模拟服务依赖关系"""
    services = [
        {"id": "api-gateway", "name": "api-gateway"},
        {"id": "user-service", "name": "user-service"},
        {"id": "order-service", "name": "order-service"},
        {"id": "payment-service", "name": "payment-service"},
        {"id": "inventory-service", "name": "inventory-service"},
        {"id": "notification-service", "name": "notification-service"},
        {"id": "mysql", "name": "mysql"},
        {"id": "redis", "name": "redis"},
    ]
    
    edges = [
        {"source": "api-gateway", "target": "user-service", "call_count": 15000, "error_count": 50, "error_rate": 0.33, "avg_latency_ms": 45, "p99_latency_ms": 120},
        {"source": "api-gateway", "target": "order-service", "call_count": 12000, "error_count": 120, "error_rate": 1.0, "avg_latency_ms": 85, "p99_latency_ms": 250},
        {"source": "order-service", "target": "payment-service", "call_count": 8000, "error_count": 30, "error_rate": 0.38, "avg_latency_ms": 120, "p99_latency_ms": 350},
        {"source": "order-service", "target": "inventory-service", "call_count": 8000, "error_count": 10, "error_rate": 0.13, "avg_latency_ms": 35, "p99_latency_ms": 80},
        {"source": "user-service", "target": "mysql", "call_count": 30000, "error_count": 5, "error_rate": 0.02, "avg_latency_ms": 15, "p99_latency_ms": 45},
        {"source": "user-service", "target": "redis", "call_count": 50000, "error_count": 0, "error_rate": 0.0, "avg_latency_ms": 2, "p99_latency_ms": 8},
        {"source": "payment-service", "target": "notification-service", "call_count": 5000, "error_count": 5, "error_rate": 0.1, "avg_latency_ms": 50, "p99_latency_ms": 150},
    ]
    
    return {
        "nodes": services,
        "edges": edges,
        "total_services": len(services),
        "total_edges": len(edges),
        "lookback": lookback
    }


@router.get("/search")
async def search_traces(
    service_name: Optional[str] = None,
    error_only: bool = False,
    slow_only: bool = False,
    lookback: str = "1h",
    limit: int = 50
):
    """
    搜索 Trace 列表
    
    Args:
        service_name: 服务名称过滤
        error_only: 仅显示错误链路
        slow_only: 仅显示慢请求
        lookback: 回溯时间
        limit: 返回数量限制
    """
    try:
        traces = generate_mock_traces(
            service_name=service_name,
            error_only=error_only,
            slow_only=slow_only,
            limit=limit
        )
        
        return {
            "total": len(traces),
            "traces": traces,
            "lookback": lookback
        }
    except Exception as e:
        logger.error(f"Failed to search traces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/dependency")
async def get_service_dependency(lookback: str = "24h"):
    """
    获取服务依赖关系图
    
    Args:
        lookback: 回溯时间
    """
    try:
        dependency = generate_mock_dependency(lookback)
        return dependency
    except Exception as e:
        logger.error(f"Failed to get service dependency: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{trace_id}")
async def get_trace_by_id(trace_id: str):
    """
    获取 Trace 详情
    
    Args:
        trace_id: Trace ID
    """
    try:
        trace = generate_mock_trace_detail(trace_id)
        return trace
    except Exception as e:
        logger.error(f"Failed to get trace detail: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Trace 不存在: {str(e)}")


@router.post("/analyze")
async def analyze_trace(params: TraceAnalysisParams):
    """
    分析 Trace
    
    Args:
        params: 分析参数
    """
    try:
        if params.trace_id:
            trace = generate_mock_trace_detail(params.trace_id)
            
            bottleneck_spans = sorted(trace["spans"], key=lambda x: x["durationMs"], reverse=True)[:3]
            
            return {
                "success": True,
                "trace_id": params.trace_id,
                "trace": trace,
                "performance_analysis": {
                    "bottleneck_spans": bottleneck_spans,
                    "slow_operations": [{"operation": s["operationName"], "avg_duration_ms": s["durationMs"]} for s in bottleneck_spans],
                    "latency_breakdown": {s["serviceName"]: s["durationMs"] for s in trace["spans"]}
                },
                "error_analysis": {
                    "error_spans": trace["errorSpans"],
                    "error_types": ["HTTP 500"] if trace["hasError"] else [],
                    "error_propagation_path": [s["serviceName"] for s in trace["errorSpans"]]
                } if trace["hasError"] else None,
                "services_involved": trace["services"],
                "error_count": len(trace["errorSpans"]),
                "total_duration_ms": trace["totalDurationMs"]
            }
        else:
            traces = generate_mock_traces(
                service_name=params.service_name,
                error_only=params.error_only,
                slow_only=params.slow_only,
                limit=20
            )
            
            return {
                "success": True,
                "total_traces": len(traces),
                "traces": traces,
                "lookback": params.lookback
            }
    except Exception as e:
        logger.error(f"Failed to analyze trace: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
