"""
Grafana 统一查询客户端

通过 Grafana Data Source Proxy API 统一查询 Prometheus 指标、Loki 日志、
仪表盘和告警，不直接暴露后端数据源端口。
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from ..observability.config import get_observability_config
from ..agents.grafana_log_client import GrafanaLogClient
from ..utils.logger import get_logger

logger = get_logger("mcp.grafana_client")


class GrafanaUnifiedClient:
    """
    Grafana 统一查询客户端

    通过 Grafana API 代理查询所有可观测数据，包括：
    - Prometheus 指标 (通过 Grafana Datasource Proxy)
    - Loki 日志 (通过 GrafanaLogClient)
    - 仪表盘列表和详情
    - 告警列表

    认证方式：Bearer Token (API Key)
    """

    def __init__(self):
        config = get_observability_config()
        self.grafana_config = config.grafana
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            # 优先使用 API Key
            if self.grafana_config.api_key:
                headers["Authorization"] = f"Bearer {self.grafana_config.api_key}"
            else:
                # fallback 到 Basic Auth
                import base64
                auth_str = f"{self.grafana_config.username}:{self.grafana_config.password}"
                encoded = base64.b64encode(auth_str.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

            self._client = httpx.AsyncClient(
                base_url=self.grafana_config.url.rstrip("/"),
                headers=headers,
                timeout=30,
            )
        return self._client

    # ─── Prometheus 指标查询 ────────────────────────────

    async def _find_prometheus_datasource_uid(self) -> str:
        """
        查找 Prometheus 数据源的 UID
        通过 Grafana API GET /api/datasources 获取
        """
        client = await self._get_client()
        ds_name = self.grafana_config.datasource_name_prometheus

        response = await client.get("/api/datasources")
        response.raise_for_status()
        datasources = response.json()

        # 先按名称精确匹配
        for ds in datasources:
            if ds.get("type") == "prometheus" and (
                ds.get("name") == ds_name or ds.get("type") == "prometheus"
            ):
                uid = ds.get("uid")
                logger.info(f"Found Prometheus datasource: {ds.get('name')} (uid={uid})")
                return uid

        # fallback: 返回第一个 Prometheus 数据源
        for ds in datasources:
            if ds.get("type") == "prometheus":
                uid = ds.get("uid")
                logger.info(f"Fallback to Prometheus datasource: {ds.get('name')} (uid={uid})")
                return uid

        raise ValueError(f"No Prometheus datasource found in Grafana")

    async def query_metrics(
        self, query: str, time: str = ""
    ) -> Dict[str, Any]:
        """
        通过 Grafana 代理执行 PromQL 即时查询

        使用 Grafana 的统一查询接口 POST /api/ds/query
        """
        if not query:
            return {"success": False, "error": "PromQL query is required"}

        try:
            ds_uid = await self._find_prometheus_datasource_uid()
            client = await self._get_client()

            payload = {
                "queries": [
                    {
                        "refId": "A",
                        "datasource": {"type": "prometheus", "uid": ds_uid},
                        "expr": query,
                        "instant": True,
                        "format": "table",
                    }
                ],
                "from": time or "now-1h",
                "to": "now",
            }

            logger.info(f"Querying Prometheus via Grafana: {query}")
            response = await client.post("/api/ds/query", json=payload)
            response.raise_for_status()
            data = response.json()

            # 解析 Grafana 统一查询响应
            results = []
            for ref_id, frame in data.get("results", {}).items():
                for series in frame.get("frames", []):
                    schema = series.get("schema", {})
                    fields = schema.get("fields", [])
                    data_rows = series.get("data", {}).get("values", [])

                    # 提取字段名
                    field_names = [f.get("name", f"col{i}") for i, f in enumerate(fields)]

                    for row in data_rows:
                        row_data = dict(zip(field_names, row))
                        results.append(row_data)

            return {
                "success": True,
                "datasource": self.grafana_config.datasource_name_prometheus,
                "query": query,
                "result_type": "vector",
                "result_count": len(results),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }

    async def query_metrics_range(
        self,
        query: str,
        start: str = "",
        end: str = "",
        step: str = "",
    ) -> Dict[str, Any]:
        """
        通过 Grafana 代理执行 PromQL 范围查询
        """
        if not query:
            return {"success": False, "error": "PromQL query is required"}

        try:
            ds_uid = await self._find_prometheus_datasource_uid()
            client = await self._get_client()

            payload = {
                "queries": [
                    {
                        "refId": "A",
                        "datasource": {"type": "prometheus", "uid": ds_uid},
                        "expr": query,
                        "instant": False,
                        "range": True,
                        "format": "table",
                        "intervalMs": self._parse_step_ms(step),
                    }
                ],
                "from": start or "now-1h",
                "to": end or "now",
            }

            logger.info(f"Querying Prometheus range via Grafana: {query}")
            response = await client.post("/api/ds/query", json=payload)
            response.raise_for_status()
            data = response.json()

            # 解析结果
            results = []
            for ref_id, frame in data.get("results", {}).items():
                for series in frame.get("frames", []):
                    schema = series.get("schema", {})
                    fields = schema.get("fields", [])
                    data_rows = series.get("data", {}).get("values", [])

                    field_names = [f.get("name", f"col{i}") for i, f in enumerate(fields)]

                    for row in data_rows:
                        row_data = dict(zip(field_names, row))
                        results.append(row_data)

            return {
                "success": True,
                "datasource": self.grafana_config.datasource_name_prometheus,
                "query": query,
                "result_type": "matrix",
                "result_count": len(results),
                "time_range": f"{start} → {end}",
                "results": results,
            }

        except Exception as e:
            logger.error(f"Prometheus range query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query,
            }

    def _parse_step_ms(self, step: str) -> int:
        """将步长字符串转为毫秒"""
        if not step:
            return 60000  # 默认 1 分钟
        step = step.lower()
        if step.endswith("s"):
            return int(step[:-1]) * 1000
        if step.endswith("m"):
            return int(step[:-1]) * 60000
        if step.endswith("h"):
            return int(step[:-1]) * 3600000
        return 60000

    # ─── Loki 日志查询 ──────────────────────────────────

    async def query_logs(
        self,
        query: str,
        start: str = "",
        end: str = "",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        通过 Grafana 代理查询 Loki 日志
        复用已有的 GrafanaLogClient
        """
        async with GrafanaLogClient() as log_client:
            return await log_client.query_logs(
                query=query,
                start=start,
                end=end,
                limit=limit,
            )

    # ─── 仪表盘管理 ──────────────────────────────────────

    async def list_dashboards(self, query: str = "") -> Dict[str, Any]:
        """
        列出 Grafana 仪表盘
        GET /api/search
        """
        try:
            client = await self._get_client()
            params = {"type": "dash-db"}
            if query:
                params["query"] = query

            response = await client.get("/api/search", params=params)
            response.raise_for_status()
            dashboards = response.json()

            results = []
            for db in dashboards:
                results.append({
                    "uid": db.get("uid"),
                    "title": db.get("title"),
                    "url": db.get("url"),
                    "folder_title": db.get("folderTitle", ""),
                    "tags": db.get("tags", []),
                })

            return {
                "success": True,
                "result_count": len(results),
                "results": results,
            }

        except Exception as e:
            logger.error(f"List dashboards failed: {e}")
            return {"success": False, "error": str(e)}

    async def get_dashboard(self, uid: str) -> Dict[str, Any]:
        """
        获取 Grafana 仪表盘详情
        GET /api/dashboards/uid/{uid}
        """
        if not uid:
            return {"success": False, "error": "Dashboard UID is required"}

        try:
            client = await self._get_client()
            response = await client.get(f"/api/dashboards/uid/{uid}")
            response.raise_for_status()
            data = response.json()

            dashboard = data.get("dashboard", {})
            return {
                "success": True,
                "uid": uid,
                "title": dashboard.get("title"),
                "panels": len(dashboard.get("panels", [])),
                "templating": dashboard.get("templating", {}),
                "dashboard": dashboard,
            }

        except Exception as e:
            logger.error(f"Get dashboard failed: {e}")
            return {"success": False, "error": str(e), "uid": uid}

    # ─── 告警查询 ────────────────────────────────────────

    async def list_alerts(self, state: str = "") -> Dict[str, Any]:
        """
        列出 Grafana 告警
        GET /api/v1/provisioning/alert-rules
        """
        try:
            client = await self._get_client()

            if state:
                response = await client.get(
                    "/api/v1/provisioning/alert-rules",
                    params={"state": state},
                )
            else:
                response = await client.get("/api/v1/provisioning/alert-rules")

            response.raise_for_status()
            rules = response.json()

            results = []
            for rule in rules if isinstance(rules, list) else []:
                results.append({
                    "uid": rule.get("uid"),
                    "title": rule.get("title"),
                    "condition": rule.get("condition", ""),
                    "for_duration": rule.get("for", ""),
                    "updated": rule.get("updated", ""),
                })

            return {
                "success": True,
                "result_count": len(results),
                "state_filter": state or "all",
                "results": results,
            }

        except Exception as e:
            logger.error(f"List alerts failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── 生命周期管理 ────────────────────────────────────

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
