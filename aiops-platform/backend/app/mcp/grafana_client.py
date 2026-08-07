"""
Grafana 统一查询客户端

通过 Grafana Data Source Proxy API 统一查询 Prometheus 指标、Loki 日志、
仪表盘和告警，不直接暴露后端数据源端口。
"""

import asyncio
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

    # 查询结果中无需展示给 LLM 的冗余 label（UUID/驱动/网络标识等）
    NOISE_LABELS = {
        "__name__", "UUID", "pci_bus_id", "DCGM_FI_DRIVER_VERSION",
        "Hostname", "device", "instance", "job", "model_name",
    }

    @staticmethod
    def _rows_from_frame(series: dict) -> List[dict]:
        """
        将 Grafana /api/ds/query 返回的单个 frame 转为行字典列表。

        Grafana 返回 wide（列优先）格式：data.values 按列存储
        （第 0 列 Time，后续列为指标值），且每个 series 一个 frame，
        series 的 labels 位于 schema.fields[i].labels 中。
        """
        schema = series.get("schema", {})
        fields = schema.get("fields", [])
        values = series.get("data", {}).get("values", [])
        if not fields or not values:
            return []

        field_names = [f.get("name", f"col{i}") for i, f in enumerate(fields)]
        # 收集 series labels（来自各字段的 labels，Time 字段无 labels）
        series_labels: Dict[str, Any] = {}
        for f in fields:
            if f.get("name") != "Time" and f.get("labels"):
                series_labels.update(f["labels"])

        n = max(len(col) for col in values)
        rows = []
        for r in range(n):
            row = {
                fname: (col[r] if r < len(col) else None)
                for fname, col in zip(field_names, values)
            }
            for k, v in series_labels.items():
                row.setdefault(k, v)
            rows.append(row)
        return rows

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

            # 解析 Grafana 统一查询响应（wide 列优先格式，每 series 一个 frame）
            results = []
            for ref_id, frame in data.get("results", {}).items():
                for series in frame.get("frames", []):
                    results.extend(self._rows_from_frame(series))

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

            # 解析结果（wide 列优先格式，每 series 一个 frame）
            results = []
            for ref_id, frame in data.get("results", {}).items():
                for series in frame.get("frames", []):
                    results.extend(self._rows_from_frame(series))

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

    # ─── 聚合健康快照 ──────────────────────────────────
    #
    # get_rag_overview / get_gpu_overview 一次性返回 dashboard 关键指标，
    # 并基于通用运维阈值给出健康状态判断，供诊断 Agent 快速决策。

    @staticmethod
    def _extract_value(row: dict) -> Optional[float]:
        """从查询结果行中提取数值（跳过 Time 字段）"""
        for k, v in row.items():
            if k != "Time" and isinstance(v, (int, float)):
                return float(v)
        return None

    async def _query_snapshot(self, queries: Dict[str, str]) -> Dict[str, Any]:
        """
        并行执行一批 PromQL 即时查询，返回 {key: value} 快照。

        单结果指标返回 float；多结果指标返回 [{labels..., value}] 列表。
        查询失败或空结果返回 None。
        """
        results = await asyncio.gather(
            *(self.query_metrics(q) for q in queries.values()),
            return_exceptions=True,
        )
        snapshot: Dict[str, Any] = {}
        for key, result in zip(queries.keys(), results):
            if isinstance(result, Exception):
                logger.warning(f"snapshot query {key} failed: {result}")
                snapshot[key] = None
                continue
            if not result or not result.get("success"):
                snapshot[key] = None
                continue
            rows = result.get("results", [])
            if not rows:
                snapshot[key] = None
                continue
            if len(rows) == 1:
                snapshot[key] = self._extract_value(rows[0])
            else:
                multi = []
                for row in rows:
                    labels = {
                        k: v
                        for k, v in row.items()
                        if k != "Time" and k not in self.NOISE_LABELS
                        and not isinstance(v, (int, float))
                    }
                    labels["value"] = self._extract_value(row)
                    multi.append(labels)
                snapshot[key] = multi
        return snapshot

    @staticmethod
    def _pct(v: Optional[float]) -> Optional[float]:
        """百分比保留 1 位小数"""
        return round(v, 1) if v is not None else None

    async def get_rag_overview(self, lookback: str = "1h") -> Dict[str, Any]:
        """
        获取 RAG Operations Overview 健康快照。

        Args:
            lookback: 错误日志查询回看窗口，如 "1h"、"30m"

        Returns:
            结构化健康快照：status / summary / metrics / errors
        """
        queries = {
            "request_total": "sum(rag_requests_total)",
            "requests_by_intent": "rag_requests_total",
            "cache_hit_rate": (
                'rag_cache_requests_total{result="hit"} / '
                '(rag_cache_requests_total{result="hit"} + rag_cache_requests_total{result="miss"}) '
                "or on() vector(0)"
            ),
            "cache_hit": 'rag_cache_requests_total{result="hit"}',
            "cache_miss": 'rag_cache_requests_total{result="miss"}',
            "faithfulness": "rag_faithfulness_avg",
            "answer_relevancy": "rag_answer_relevancy_avg",
            "context_precision": "rag_context_precision_avg",
            "node_duration": "rag_node_duration_ms",
            "node_p95": 'rag_node_duration_histogram_ms{stat="p95"}',
            "rerank_filter_rate": "rag_rerank_filter_rate",
            "rerank_docs": "rag_rerank_docs_count",
            "rerank_scores_avg": 'rag_rerank_scores{stat="avg"}',
            "tokens_total": "sum(rag_llm_tokens_total)",
            "feedback_upvote": 'rag_feedback_total{type="upvote"}',
            "feedback_downvote": 'rag_feedback_total{type="downvote"}',
        }
        metrics = await self._query_snapshot(queries)

        # 并发获取最近错误日志
        try:
            logs = await self.query_logs(
                '{container_name="rag_backend"} | json | level = "ERROR"',
                start=f"{lookback} ago",
                limit=20,
            )
            errors = [
                e.get("message") or e.get("line") or str(e)
                for e in (logs.get("results", []) if logs.get("success") else [])
            ]
        except Exception as e:
            logger.warning(f"RAG error log query failed: {e}")
            errors = []

        # 健康状态判断（通用运维阈值）
        warnings: List[str] = []
        cache_hit_rate = metrics.get("cache_hit_rate")
        if cache_hit_rate is not None and cache_hit_rate < 0.3:
            warnings.append(f"缓存命中率过低: {self._pct(cache_hit_rate * 100)}%")
        p95_rows = metrics.get("node_p95")
        if isinstance(p95_rows, list):
            slow_nodes = [f"{r.get('node', '?')}={self._pct(r.get('value'))}ms" for r in p95_rows if (r.get("value") or 0) > 5000]
            if slow_nodes:
                warnings.append(f"节点 p95 耗时超阈值: {', '.join(slow_nodes)}")
        faithfulness = metrics.get("faithfulness")
        if faithfulness is not None and faithfulness < 0.5:
            warnings.append(f"Faithfulness 低于 0.5: {round(faithfulness, 2)}")
        if errors:
            warnings.append(f"检测到 {len(errors)} 条 ERROR 日志")

        if warnings:
            status = "WARNING"
        elif cache_hit_rate is not None and cache_hit_rate == 0 and (metrics.get("request_total") or 0) > 0:
            status = "WARNING"
        else:
            status = "HEALTHY"

        summary_parts = [f"总请求 {int(metrics.get('request_total') or 0)}"]
        if cache_hit_rate is not None:
            summary_parts.append(f"缓存命中率 {self._pct(cache_hit_rate * 100)}%")
        avg_duration = metrics.get("node_duration")
        if isinstance(avg_duration, list) and avg_duration:
            vals = [r.get("value") for r in avg_duration if r.get("value") is not None]
            if vals:
                summary_parts.append(f"节点平均耗时 {self._pct(sum(vals) / len(vals))}ms")
        if errors:
            summary_parts.append(f"ERROR 日志 {len(errors)} 条")
        summary = "RAG 服务运行" + ("异常" if warnings else "正常") + "；" + "，".join(summary_parts)

        return {
            "success": True,
            "source": "rag-ops-overview",
            "dashboard_url": (
                f"http://47.76.53.232:3000/d/rag-ops-overview/rag-operations-overview?orgId=1"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "summary": summary,
            "metrics": metrics,
            "errors": errors[:10],
            "warnings": warnings,
            "alerts": [],
        }

    async def get_gpu_overview(self, lookback: str = "1h") -> Dict[str, Any]:
        """
        获取 System & GPU Overview 健康快照。

        Args:
            lookback: 预留参数（当前为即时查询）

        Returns:
            结构化健康快照：status / summary / metrics
        """
        queries = {
            "cpu_usage_pct": '100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)',
            "memory_usage_pct": "(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100",
            "disk_usage_pct": (
                '(1 - node_filesystem_avail_bytes{mountpoint="/"} / '
                'node_filesystem_size_bytes{mountpoint="/"}) * 100'
            ),
            "load": "node_load1",
            "gpu_util": "DCGM_FI_DEV_GPU_UTIL",
            "gpu_mem_used": "DCGM_FI_DEV_FB_USED",
            "gpu_mem_total": "DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE",
            "gpu_temp": "DCGM_FI_DEV_GPU_TEMP",
            "gpu_power": "DCGM_FI_DEV_POWER_USAGE",
            "cpu_cores": 'count(node_cpu_seconds_total{mode="idle"})',
            "mem_total_bytes": "node_memory_MemTotal_bytes",
            "disk_total_bytes": 'node_filesystem_size_bytes{mountpoint="/"}',
            "disk_io_read": "rate(node_disk_read_bytes_total[1m])",
            "disk_io_write": "rate(node_disk_written_bytes_total[1m])",
            "network_rx": 'rate(node_network_receive_bytes_total{device!~"lo.*"}[1m])',
            "network_tx": 'rate(node_network_transmit_bytes_total{device!~"lo.*"}[1m])',
        }
        metrics = await self._query_snapshot(queries)

        # 健康状态判断
        warnings: List[str] = []
        for label, key in (("CPU", "cpu_usage_pct"), ("内存", "memory_usage_pct"), ("磁盘", "disk_usage_pct")):
            v = metrics.get(key)
            if v is not None:
                if v > 90:
                    warnings.append(f"{label}使用率过高: {self._pct(v)}%")
                elif v > 80:
                    warnings.append(f"{label}使用率偏高: {self._pct(v)}%")

        gpu_temps = metrics.get("gpu_temp")
        if isinstance(gpu_temps, list):
            hot = [f"GPU{r.get('gpu')}={self._pct(r.get('value'))}°C" for r in gpu_temps if (r.get("value") or 0) > 85]
            if hot:
                warnings.append("GPU 温度偏高: " + ", ".join(hot))

        status = "WARNING" if warnings else "HEALTHY"

        summary_parts = []
        for label, key in (("CPU", "cpu_usage_pct"), ("内存", "memory_usage_pct"), ("磁盘", "disk_usage_pct")):
            v = metrics.get(key)
            if v is not None:
                summary_parts.append(f"{label}使用率 {self._pct(v)}%")
        gpu_utils = metrics.get("gpu_util")
        if isinstance(gpu_utils, list) and gpu_utils:
            utils = [self._pct(r.get("value")) for r in gpu_utils if r.get("value") is not None]
            if utils:
                summary_parts.append(f"GPU利用率 {max(utils)}%")
        summary = "主机/GPU 资源" + ("存在告警" if warnings else "运行正常") + "；" + "，".join(summary_parts)

        return {
            "success": True,
            "source": "system-gpu-overview",
            "dashboard_url": (
                f"http://47.76.53.232:3000/d/system-gpu-overview/system-and-gpu-overview?orgId=1"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "summary": summary,
            "metrics": metrics,
            "warnings": warnings,
            "alerts": [],
        }

    async def get_vllm_overview(self, lookback: str = "1h") -> Dict[str, Any]:
        """
        获取 vLLM 推理引擎健康快照。

        采集指标（来自 Grafana 的 vLLM Inference Dashboard）:
        - 引擎状态、KV Cache 使用率、运行中/等待请求数
        - 请求吞吐 QPS、TTFT（p50/p95/p99）、Token 吞吐与累计量

        Args:
            lookback: 预留参数（当前为即时查询）

        Returns:
            结构化健康快照：status / summary / metrics / warnings
        """
        queries = {
            "engine_awake": 'sum(vllm:engine_sleep_state{sleep_state="awake"})',
            "kv_cache_usage_pct": 'vllm:kv_cache_usage_perc{engine="0"} * 100',
            "requests_running": "sum(vllm:num_requests_running)",
            "requests_waiting": "sum(vllm:num_requests_waiting)",
            "qps_1m": 'sum(rate(vllm:request_success_total{finished_reason="stop"}[1m]))',
            "qps_5m": 'sum(rate(vllm:request_success_total{finished_reason="stop"}[5m]))',
            "ttft_p50": 'histogram_quantile(0.50, rate(vllm:time_to_first_token_seconds_bucket[5m]))',
            "ttft_p95": 'histogram_quantile(0.95, rate(vllm:time_to_first_token_seconds_bucket[5m]))',
            "ttft_p99": 'histogram_quantile(0.99, rate(vllm:time_to_first_token_seconds_bucket[5m]))',
            "tokens_total": "sum(vllm:prompt_tokens_total + vllm:generation_tokens_total)",
            "tokens_per_sec": (
                "sum(rate(vllm:prompt_tokens_total[1m]) + "
                "rate(vllm:generation_tokens_total[1m]))"
            ),
        }
        metrics = await self._query_snapshot(queries)

        # 健康状态判断
        warnings: List[str] = []
        awake = metrics.get("engine_awake")
        if awake == 0:
            warnings.append("vLLM 引擎未激活（engine_sleep_state=0）")
        kv_cache = metrics.get("kv_cache_usage_pct")
        if kv_cache is not None and kv_cache > 90:
            warnings.append(f"KV Cache 使用率过高: {self._pct(kv_cache)}%")
        waiting = metrics.get("requests_waiting")
        if waiting is not None and waiting > 20:
            warnings.append(f"等待队列过长: {int(waiting)} 个请求")
        ttft_p95 = metrics.get("ttft_p95")
        if isinstance(ttft_p95, list):
            slow = [
                f"engine={r.get('engine', '?')}={self._pct(r.get('value'))}s"
                for r in ttft_p95 if (r.get("value") or 0) > 5
            ]
            if slow:
                warnings.append("TTFT p95 过高: " + ", ".join(slow))
        elif ttft_p95 is not None and ttft_p95 > 5:
            warnings.append(f"TTFT p95 过高: {self._pct(ttft_p95)}s")

        status = "WARNING" if warnings else "HEALTHY"

        summary_parts = []
        if awake == 1:
            summary_parts.append("引擎活跃")
        elif awake == 0:
            summary_parts.append("引擎休眠")
        if kv_cache is not None:
            summary_parts.append(f"KV Cache {self._pct(kv_cache)}%")
        summary_parts.append(
            f"运行/等待 {int(metrics.get('requests_running') or 0)}/"
            f"{int(metrics.get('requests_waiting') or 0)}"
        )
        summary_parts.append(f"QPS {self._pct(metrics.get('qps_1m'))}")
        summary_parts.append(f"累计Token {int(metrics.get('tokens_total') or 0)}")
        summary = "vLLM 推理引擎" + ("异常" if warnings else "运行正常") + "；" + "，".join(summary_parts)

        return {
            "success": True,
            "source": "vllm-inference-dashboard",
            "dashboard_url": (
                f"http://47.76.53.232:3000/d/dfohvuy2yx1j4e/vllm-inference-dashboard?orgId=1"
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "summary": summary,
            "metrics": metrics,
            "warnings": warnings,
            "alerts": [],
        }

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
