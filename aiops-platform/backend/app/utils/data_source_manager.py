#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据源管理器

支持多种数据源类型：
- 本地文件系统 (filesystem)
- Prometheus 监控系统
- Elasticsearch 日志平台
- Grafana Loki 日志系统
- 阿里云云监控
- Jaeger 链路追踪
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from ..core.config import settings


class DataSourceManager:
    """
    数据源管理器
    
    统一管理多种数据源，提供统一的数据加载接口
    """
    
    def __init__(self):
        self.data_sources = settings.DATA_SOURCES
        self.default_source = settings.DEFAULT_DATA_SOURCE
    
    def list_available_sources(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的数据源
        """
        sources = []
        for name, config in self.data_sources.items():
            source_info = {
                "name": name,
                "type": config.get("type"),
                "description": config.get("description", ""),
                "available": self._check_source_available(name, config)
            }
            sources.append(source_info)
        return sources
    
    def _check_source_available(self, name: str, config: Dict) -> bool:
        """
        检查数据源是否可用
        """
        source_type = config.get("type")
        
        if source_type == "filesystem":
            base_path = config.get("base_path", "")
            return os.path.exists(base_path)
        
        elif source_type in ["monitoring", "logging", "tracing"]:
            url = config.get("url", "")
            if not url:
                return False
            try:
                if HAS_REQUESTS:
                    resp = requests.get(f"{url}/api/v1/status/config", timeout=2)
                    return resp.status_code == 200
            except:
                pass
            return False
        
        elif source_type == "cloud_monitoring":
            return config.get("enabled", False)
        
        return False
    
    async def load_data(
        self,
        source_name: str,
        data_type: str,
        time_range: Optional[tuple] = None,
        filters: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        从指定数据源加载数据
        
        Args:
            source_name: 数据源名称 (local, prometheus, elasticsearch, etc.)
            data_type: 数据类型 (logs, metrics, traces)
            time_range: 时间范围 (start_time, end_time)
            filters: 过滤条件
            
        Returns:
            加载的数据结果
        """
        if source_name not in self.data_sources:
            return {
                "success": False,
                "error": f"Unknown data source: {source_name}",
                "available_sources": list(self.data_sources.keys())
            }
        
        config = self.data_sources[source_name]
        source_type = config.get("type")
        
        if source_type == "filesystem":
            return await self._load_from_filesystem(config, data_type, time_range, filters, **kwargs)
        elif source_type == "monitoring":
            return await self._load_from_prometheus(config, data_type, time_range, filters, **kwargs)
        elif source_type == "logging":
            return await self._load_from_logging(config, data_type, time_range, filters, **kwargs)
        elif source_type == "tracing":
            return await self._load_from_tracing(config, data_type, time_range, filters, **kwargs)
        elif source_type == "cloud_monitoring":
            return await self._load_from_cloud_monitor(config, data_type, time_range, filters, **kwargs)
        else:
            return {
                "success": False,
                "error": f"Unsupported source type: {source_type}"
            }
    
    async def _load_from_filesystem(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从本地文件系统加载数据
        """
        base_path = config.get("base_path", "")
        
        if data_type == "logs":
            data_path = kwargs.get("data_path", base_path)
            return await self._load_parquet_logs(data_path, time_range, filters)
        
        elif data_type == "metrics":
            data_path = kwargs.get("data_path", base_path)
            return await self._load_parquet_metrics(data_path, time_range, filters)
        
        elif data_type == "traces":
            data_path = kwargs.get("data_path", base_path)
            return await self._load_parquet_traces(data_path, time_range, filters)
        
        return {
            "success": False,
            "error": f"Unsupported data type: {data_type}"
        }
    
    async def _load_parquet_logs(
        self,
        data_path: str,
        time_range: Optional[tuple],
        filters: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        加载 Parquet 格式的日志数据
        """
        if not HAS_PANDAS:
            return {
                "success": False,
                "error": "pandas is required for loading parquet files"
            }
        
        path = Path(data_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"Path not found: {data_path}"
            }
        
        logs = []
        log_path = path / "log-parquet"
        
        if not log_path.exists():
            return {
                "success": False,
                "error": f"Log path not found: {log_path}"
            }
        
        for parquet_file in log_path.glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet_file)
                for _, row in df.iterrows():
                    logs.append(row.to_dict())
            except Exception as e:
                print(f"Error loading {parquet_file}: {e}")
        
        error_logs = [l for l in logs if 'error' in str(l).lower() or 'exception' in str(l).lower()]
        
        return {
            "success": True,
            "source_type": "filesystem",
            "data_type": "logs",
            "total_logs": len(logs),
            "error_logs": len(error_logs),
            "sample_logs": logs[:5] if logs else [],
            "data_path": str(data_path)
        }
    
    async def _load_parquet_metrics(
        self,
        data_path: str,
        time_range: Optional[tuple],
        filters: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        加载 Parquet 格式的指标数据
        """
        if not HAS_PANDAS:
            return {
                "success": False,
                "error": "pandas is required for loading parquet files"
            }
        
        path = Path(data_path)
        metric_path = path / "metric-parquet"
        
        if not metric_path.exists():
            return {
                "success": False,
                "error": f"Metric path not found: {metric_path}"
            }
        
        metrics = {}
        
        service_path = metric_path / "apm" / "service"
        if service_path.exists():
            for parquet_file in service_path.glob("*.parquet"):
                try:
                    service_name = parquet_file.stem.replace("service_", "").replace("_2025-06-06", "")
                    df = pd.read_parquet(parquet_file)
                    metrics[service_name] = df.to_dict('records')
                except Exception as e:
                    print(f"Error loading {parquet_file}: {e}")
        
        return {
            "success": True,
            "source_type": "filesystem",
            "data_type": "metrics",
            "services": list(metrics.keys()),
            "metrics": metrics,
            "data_path": str(data_path)
        }
    
    async def _load_parquet_traces(
        self,
        data_path: str,
        time_range: Optional[tuple],
        filters: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        加载 Parquet 格式的链路追踪数据
        """
        if not HAS_PANDAS:
            return {
                "success": False,
                "error": "pandas is required for loading parquet files"
            }
        
        path = Path(data_path)
        trace_path = path / "trace-parquet"
        
        if not trace_path.exists():
            return {
                "success": False,
                "error": f"Trace path not found: {trace_path}"
            }
        
        traces = []
        for parquet_file in trace_path.glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet_file)
                for _, row in df.iterrows():
                    traces.append(row.to_dict())
            except Exception as e:
                print(f"Error loading {parquet_file}: {e}")
        
        return {
            "success": True,
            "source_type": "filesystem",
            "data_type": "traces",
            "total_traces": len(traces),
            "sample_traces": traces[:5] if traces else [],
            "data_path": str(data_path)
        }
    
    async def _load_from_prometheus(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从 Prometheus 加载指标数据
        """
        url = config.get("url", "http://localhost:9090")
        
        if not HAS_REQUESTS:
            return {
                "success": False,
                "error": "requests is required for Prometheus queries"
            }
        
        query = kwargs.get("query", "up")
        
        try:
            response = requests.get(
                f"{url}/api/v1/query",
                params={"query": query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "source_type": "prometheus",
                    "data_type": "metrics",
                    "query": query,
                    "result": data.get("data", {}).get("result", []),
                    "url": url
                }
            else:
                return {
                    "success": False,
                    "error": f"Prometheus query failed: {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_from_logging(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从日志平台（Elasticsearch/Loki）加载日志数据
        """
        source_name = config.get("name", "")
        url = config.get("url", "")
        
        if "elasticsearch" in source_name or "elasticsearch" in url or "9200" in url:
            return await self._load_from_elasticsearch(config, data_type, time_range, filters, **kwargs)
        elif "loki" in source_name or "loki" in url or "3100" in url:
            return await self._load_from_loki(config, data_type, time_range, filters, **kwargs)
        
        return {
            "success": False,
            "error": f"Unknown logging platform: {source_name}"
        }
    
    async def _load_from_elasticsearch(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从 Elasticsearch 加载日志
        """
        url = config.get("url", "http://localhost:9200")
        index = kwargs.get("index", config.get("index_pattern", "logstash-*"))
        query = kwargs.get("query", {"query": {"match_all": {}}})
        
        if not HAS_REQUESTS:
            return {
                "success": False,
                "error": "requests is required for Elasticsearch queries"
            }
        
        try:
            response = requests.post(
                f"{url}/{index}/_search",
                json=query,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                hits = data.get("hits", {}).get("hits", [])
                logs = [hit.get("_source", {}) for hit in hits]
                
                return {
                    "success": True,
                    "source_type": "elasticsearch",
                    "data_type": "logs",
                    "total_logs": len(logs),
                    "logs": logs,
                    "index": index
                }
            else:
                return {
                    "success": False,
                    "error": f"Elasticsearch query failed: {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_from_loki(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从 Grafana Loki 加载日志
        """
        url = config.get("url", "http://localhost:3100")
        query = kwargs.get("query", '{job="default"}')
        
        if not HAS_REQUESTS:
            return {
                "success": False,
                "error": "requests is required for Loki queries"
            }
        
        try:
            response = requests.get(
                f"{url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": time_range[0] if time_range else 0,
                    "end": time_range[1] if time_range else "now"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "source_type": "loki",
                    "data_type": "logs",
                    "result": data.get("data", {}).get("result", []),
                    "query": query
                }
            else:
                return {
                    "success": False,
                    "error": f"Loki query failed: {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_from_tracing(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从链路追踪系统（Jaeger）加载 trace 数据
        """
        url = config.get("url", "http://localhost:16686")
        service = kwargs.get("service", "")
        
        if not HAS_REQUESTS:
            return {
                "success": False,
                "error": "requests is required for Jaeger queries"
            }
        
        try:
            params = {"service": service} if service else {}
            response = requests.get(
                f"{url}/api/traces",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                traces = data.get("data", [])
                
                return {
                    "success": True,
                    "source_type": "jaeger",
                    "data_type": "traces",
                    "total_traces": len(traces),
                    "traces": traces,
                    "service": service
                }
            else:
                return {
                    "success": False,
                    "error": f"Jaeger query failed: {response.status_code}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_from_cloud_monitor(
        self,
        config: Dict,
        data_type: str,
        time_range: Optional[tuple],
        filters: Optional[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        从云监控平台加载指标数据
        """
        try:
            from .aliyun_monitor import AliyunMonitorClient
            
            client = AliyunMonitorClient()
            
            metric_name = kwargs.get("metric_name", "CPUUtilization")
            namespace = kwargs.get("namespace", "acs_ecs_dashboard")
            
            if time_range:
                start_time, end_time = time_range
            else:
                end_time = datetime.now()
                start_time = end_time - timedelta(hours=1)
            
            result = await client.get_metric_data(
                namespace=namespace,
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time
            )
            
            return {
                "success": True,
                "source_type": "aliyun_monitor",
                "data_type": "metrics",
                "metric_name": metric_name,
                "data": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


data_source_manager = DataSourceManager()
