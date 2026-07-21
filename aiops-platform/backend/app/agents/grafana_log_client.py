"""
Grafana Loki 日志查询客户端

通过 Grafana Data Source Proxy API 查询 Loki 日志，
无需直接暴露 Loki 端口（3100），所有请求经过 Grafana 认证代理。
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import httpx

from ..observability.config import GrafanaConfig, get_observability_config
from ..utils.logger import get_logger

logger = get_logger("grafana_log_client")

# Grafana 数据源类型常量
DS_TYPE_LOKI = "loki"


class GrafanaLogClient:
    """
    Grafana Loki 日志查询客户端

    通过 Grafana API 代理查询 Loki 数据源，支持：
    - LogQL 查询语句
    - 时间范围（相对时间如 "1h ago" 或绝对时间戳）
    - 结果条数限制
    - 多数据源选择

    使用方式:
        client = GrafanaLogClient()
        result = await client.query_logs(
            query='{app="aiops-backend"} |= "error"',
            start="1h ago",
            end="now",
            limit=100
        )
    """

    def __init__(self, config: Optional[GrafanaConfig] = None):
        self.config = config or get_observability_config().grafana
        self._client: Optional[httpx.AsyncClient] = None
        self._loki_ds_uid: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            headers = {"Accept": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.config.url.rstrip("/"),
                headers=headers,
                timeout=30,
            )
        return self._client

    async def _get_loki_datasource_uid(self, datasource_name: str = "") -> str:
        """
        通过 Grafana API 查询 Loki 数据源的 UID

        GET /api/datasources
        返回所有数据源列表，从中找出 type=loki 的数据源
        """
        if self._loki_ds_uid:
            return self._loki_ds_uid

        client = await self._get_client()
        ds_name = datasource_name or self.config.datasource_name_loki

        try:
            response = await client.get("/api/datasources")
            response.raise_for_status()
            datasources = response.json()

            for ds in datasources:
                if ds.get("type") == DS_TYPE_LOKI:
                    if not datasource_name or ds.get("name") == ds_name:
                        self._loki_ds_uid = ds.get("uid", str(ds.get("id")))
                        logger.info(f"Found Loki datasource: {ds.get('name')} (uid={self._loki_ds_uid})")
                        return self._loki_ds_uid

            # 如果没找到按名称匹配的，返回第一个 Loki 数据源
            for ds in datasources:
                if ds.get("type") == DS_TYPE_LOKI:
                    self._loki_ds_uid = ds.get("uid", str(ds.get("id")))
                    logger.info(f"Fallback to Loki datasource: {ds.get('name')} (uid={self._loki_ds_uid})")
                    return self._loki_ds_uid

            raise ValueError(f"No Loki datasource found in Grafana (searched for: {ds_name})")

        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"Failed to list Grafana datasources: HTTP {e.response.status_code}. "
                f"Check Grafana URL ({self.config.url}) and API key."
            ) from e

    def _parse_time(self, time_str: str, default: datetime) -> datetime:
        """
        解析时间字符串

        支持格式:
        - "1h ago", "30m ago", "2d ago" (相对时间)
        - "2026-07-08T10:00:00Z" (ISO 格式)
        - "now" (当前时间)
        - "" (空字符串返回默认值)
        """
        if not time_str or time_str.lower() == "now":
            return default

        # 尝试解析相对时间: "N{h,m,d} ago"
        rel_match = re.match(r"^(\d+)\s*(h|m|d|s)\s*ago$", time_str.lower())
        if rel_match:
            value = int(rel_match.group(1))
            unit = rel_match.group(2)
            if unit == "s":
                delta = timedelta(seconds=value)
            elif unit == "m":
                delta = timedelta(minutes=value)
            elif unit == "h":
                delta = timedelta(hours=value)
            elif unit == "d":
                delta = timedelta(days=value)
            else:
                delta = timedelta(hours=value)
            return default - delta

        # 尝试解析 ISO 格式
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

        # 尝试解析 Unix 时间戳（秒）
        try:
            return datetime.fromtimestamp(float(time_str), tz=timezone.utc)
        except (ValueError, TypeError):
            pass

        logger.warning(f"Unable to parse time string: '{time_str}', using default")
        return default

    async def query_logs(
        self,
        query: str,
        start: str = "",
        end: str = "",
        limit: int = 100,
        datasource: str = "",
    ) -> Dict[str, Any]:
        """
        通过 Grafana Data Source Proxy 查询 Loki 日志

        Args:
            query: LogQL 查询语句，如 '{app="aiops-backend"} |= "error"'
            start: 开始时间（"1h ago" / ISO 格式 / 空=1小时前）
            end:   结束时间（"now" / ISO 格式 / 空=当前）
            limit: 最大返回日志条数（默认 100，最大 5000）
            datasource: Grafana 数据源名称（默认使用 Loki）

        Returns:
            结构化日志结果，包含：
            - success: 是否成功
            - result_count: 日志条数
            - results: 日志条目列表（timestamp, line, labels）
            - stats: 查询统计
            - error: 错误信息（失败时）
        """
        if not query:
            return {"success": False, "error": "LogQL query is required"}

        if not self.config.enabled:
            return {"success": False, "error": "Grafana is not enabled in config"}

        limit = min(max(limit, 1), 5000)
        now = datetime.now(timezone.utc)
        start_dt = self._parse_time(start, now - timedelta(hours=1))
        end_dt = self._parse_time(end, now)

        try:
            ds_uid = await self._get_loki_datasource_uid(datasource)
            client = await self._get_client()

            params = {
                "query": query,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "limit": str(limit),
                "direction": "backward",
            }

            proxy_url = f"/api/datasources/proxy/uid/{ds_uid}/loki/api/v1/query_range"
            logger.info(f"Querying Grafana Loki: {query} ({start} ~ {end})")

            t0 = datetime.now()
            response = await client.get(proxy_url, params=params)
            elapsed = (datetime.now() - t0).total_seconds() * 1000
            response.raise_for_status()
            data = response.json()

            # 解析 Loki 返回结果
            results = []
            result_type = data.get("data", {}).get("resultType", "")
            streams = data.get("data", {}).get("result", [])

            for stream in streams:
                stream_labels = stream.get("stream", {})
                values = stream.get("values", [])
                for ts_ns, line in values:
                    # Loki 时间戳是纳秒级
                    try:
                        ts_sec = int(ts_ns) / 1e9
                        ts_str = datetime.fromtimestamp(ts_sec, tz=timezone.utc).isoformat()
                    except (ValueError, TypeError):
                        ts_str = ts_ns

                    results.append({
                        "timestamp": ts_str,
                        "line": line,
                        "labels": stream_labels,
                    })

                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

            return {
                "success": True,
                "datasource": datasource or self.config.datasource_name_loki,
                "query": query,
                "time_range": f"{start_dt.isoformat()} → {end_dt.isoformat()}",
                "result_count": len(results),
                "results": results[:limit],
                "stats": {
                    "query_time_ms": round(elapsed, 1),
                },
            }

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            error_detail = f"Grafana API error (HTTP {status})"
            try:
                body = e.response.json()
                error_detail = body.get("message", body.get("error", error_detail))
            except (ValueError, AttributeError):
                error_detail = e.response.text[:500]
            logger.error(f"Grafana Loki query failed: {error_detail}")
            return {
                "success": False,
                "error": error_detail,
                "query": query,
                "status_code": status,
            }

        except httpx.RequestError as e:
            logger.error(f"Grafana connection failed: {e}")
            return {
                "success": False,
                "error": f"Cannot connect to Grafana at {self.config.url}: {e}",
                "query": query,
            }

        except Exception as e:
            logger.error(f"Unexpected error querying Grafana Loki: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }

    async def query_logs_stream(
        self,
        query: str,
        start: str = "",
        end: str = "",
        interval: str = "5m",
        datasource: str = "",
    ) -> Dict[str, Any]:
        """
        查询 Loki 日志指标（聚合查询）

        适用于 LogQL 聚合查询，如:
        sum(rate({app="aiops-backend"} |= "error" [5m]))

        Args:
            query: LogQL 聚合查询语句
            start: 开始时间
            end: 结束时间
            interval: 聚合间隔
            datasource: 数据源名称

        Returns:
            时序数据结果
        """
        if not query:
            return {"success": False, "error": "LogQL query is required"}

        if not self.config.enabled:
            return {"success": False, "error": "Grafana is not enabled in config"}

        now = datetime.now(timezone.utc)
        start_dt = self._parse_time(start, now - timedelta(hours=1))
        end_dt = self._parse_time(end, now)

        try:
            ds_uid = await self._get_loki_datasource_uid(datasource)
            client = await self._get_client()

            params = {
                "query": query,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "step": interval,
            }

            proxy_url = f"/api/datasources/proxy/uid/{ds_uid}/loki/api/v1/query_range"
            response = await client.get(proxy_url, params=params)
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "datasource": datasource or self.config.datasource_name_loki,
                "query": query,
                "result_type": data.get("data", {}).get("resultType", ""),
                "results": data.get("data", {}).get("result", []),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
