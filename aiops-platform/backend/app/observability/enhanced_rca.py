"""
Enhanced Root Cause Analyzer - 增强型根因分析引擎

整合 Observability 平台与 time_sequence_detection 算法库：
1. GNN_RCA - 图神经网络根因分析（微服务拓扑）
2. IsolationForest + Prophet - CPU/内存异常检测
3. Drain + DBSCAN - 智能告警聚合
4. LSTM 日志异常检测（可选）

架构设计：
┌─────────────────────────────────────────────────────────────┐
│                  Enhanced RCA Engine                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Prometheus│  │  Tempo   │  │   Loki   │  │  Alerts  │   │
│  │ Metrics  │  │  Traces  │  │   Logs   │  │ Events   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│       ▼             ▼             ▼             ▼          │
│  ┌─────────────────────────────────────────────────┐      │
│  │           Data Bridge Layer (数据桥接层)         │      │
│  │  Prometheus → TimeSeries | Traces → Graph      │      │
│  └─────────────────────┬───────────────────────────┘      │
│                        │                                   │
│  ┌─────────────────────▼───────────────────────────┐      │
│  │        Algorithm Integration Layer               │      │
│  │  ┌─────────────┐ ┌────────────┐ ┌────────────┐  │      │
│  │  │ GNN_RCA     │ │ IsoForest  │ │ Drain+DB   │  │      │
│  │  │ (图神经网络) │ │ + Prophet  │ │ SCAN 聚合  │  │      │
│  │  └─────────────┘ └────────────┘ └────────────┘  │      │
│  └─────────────────────┬───────────────────────────┘      │
│                        │                                   │
│  ┌─────────────────────▼───────────────────────────┐      │
│  │        Result Fusion & Ranking Engine            │      │
│  │    多源证据融合 | 置信度加权 | 根因排序           │      │
│  └─────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

# 添加 time_sequence_detection 到路径
TIME_SEQ_DIR = str(Path(__file__).parent.parent.parent.parent / "time_sequence_detection")
if TIME_SEQ_DIR not in sys.path:
    sys.path.insert(0, TIME_SEQ_DIR)

from .config import (
    ObservabilityConfig,
    get_observability_config,
)
from .prometheus_client import (
    PrometheusClient,
    AlertEvent,
)
from .tempo_query import (
    TempoQueryClient,
    Trace,
)
from .root_cause_analyzer import (
    RootCauseAnalyzer,
    RootCauseAnalysisReport,
    RootCauseHypothesis,
    Evidence,
    EvidenceType,
    AnalysisSeverity,
)

logger = logging.getLogger(__name__)


class AlgorithmType(str, Enum):
    """算法类型枚举"""
    GNN_RCA = "gnn_rca"
    ISOLATION_FOREST = "isolation_forest"
    DRAIN_DBSCAN = "drain_dbscan"
    PROPHET_FORECAST = "prophet_forecast"
    STATISTICAL = "statistical"
    LLM_ENHANCED = "llm_enhanced"


class FusionStrategy(str, Enum):
    """融合策略"""
    WEIGHTED_AVERAGE = "weighted_average"  # 加权平均
    MAX_CONFIDENCE = "max_confidence"  # 取最大置信度
    VOTING = "voting"  # 投票机制
    STACKING = "stacking"  # 堆叠融合


@dataclass
class AlgorithmResult:
    """单个算法的分析结果"""
    algorithm_type: AlgorithmType
    algorithm_name: str
    success: bool
    confidence_score: float
    root_cause_candidates: List[Dict[str, Any]] = field(default_factory=list)
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "algorithm": self.algorithm_name,
            "type": self.algorithm_type.value,
            "success": self.success,
            "confidence": round(self.confidence_score, 3),
            "candidates": self.root_cause_candidates[:5],
            "execution_time_ms": round(self.execution_time_ms, 2),
            "metadata": self.metadata,
        }


@dataclass
class FusedAnalysisReport:
    """融合后的增强分析报告"""
    base_report: RootCauseAnalysisReport
    algorithm_results: List[AlgorithmResult] = field(default_factory=list)
    fusion_strategy: FusionStrategy = FusionStrategy.WEIGHTED_AVERAGE
    
    @property
    def algorithms_used(self) -> List[str]:
        return [r.algorithm_name for r in self.algorithm_results if r.success]
    
    @property
    def total_execution_time_ms(self) -> float:
        return sum(r.execution_time_ms for r in self.algorithm_results)
    
    def to_dict(self) -> Dict[str, Any]:
        base = self.base_report.to_dict()
        
        return {
            **base,
            "enhanced_analysis": {
                "algorithms_executed": len(self.algorithm_results),
                "algorithms_successful": len([r for r in self.algorithm_results if r.success]),
                "algorithms_used": self.algorithms_used,
                "fusion_strategy": self.fusion_strategy.value,
                "total_algorithm_time_ms": round(self.total_execution_time_ms, 2),
                "algorithm_details": [r.to_dict() for r in self.algorithm_results],
            },
        }


class TimeSeriesDataBridge:
    """
    数据桥接层
    
    将 Prometheus/Tempo 的数据转换为时间序列算法需要的格式
    """
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    async def prometheus_to_timeseries(
        self,
        prometheus: PrometheusClient,
        queries: List[str],
        duration_minutes: int = 60,
        step: str = "1m",
    ) -> Dict[str, pd.DataFrame]:
        """
        将 Prometheus 查询结果转换为 Pandas DataFrame
        
        Args:
            prometheus: Prometheus 客户端
            queries: PromQL 查询列表
            duration_minutes: 回溯时间
            step: 采样间隔
            
        Returns:
            {metric_name: DataFrame} 字典
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=duration_minutes)
        
        result_dataframes = {}
        
        for query in queries:
            try:
                query_result = await prometheus.range_query(
                    query=query,
                    start=start_time,
                    end=end_time,
                    step=step,
                )
                
                if query_result.status == "success" and query_result.data:
                    dfs = []
                    
                    for item in query_result.data:
                        metric_labels = item.get("metric", {})
                        values = item.get("values", [])
                        
                        if not values:
                            continue
                        
                        timestamps = []
                        measurements = []
                        
                        for ts, val in values:
                            if ts is not None and val is not None:
                                timestamps.append(ts)
                                measurements.append(val)
                        
                        if timestamps:
                            instance_id = metric_labels.get("instance", "unknown")
                            service = metric_labels.get("service", "unknown")
                            
                            df = pd.DataFrame({
                                "timestamp": timestamps,
                                "value": measurements,
                                "instance": instance_id,
                                "service": service,
                            })
                            
                            label_str = "_".join(f"{k}={v}" for k, v in metric_labels.items() 
                                               if k not in ["__name__"])
                            key = f"{query[:30]}_{label_str}" if label_str else query[:30]
                            
                            dfs.append(df)
                    
                    if dfs:
                        combined_df = pd.concat(dfs, ignore_index=True)
                        combined_df["timestamp"] = pd.to_datetime(combined_df["timestamp"])
                        combined_df = combined_df.sort_values("timestamp")
                        
                        metric_key = self._extract_metric_name(query)
                        result_dataframes[metric_key] = combined_df
                        
            except Exception as e:
                logger.error(f"Error converting query to timeseries: {query[:50]}... Error: {e}")
                continue
        
        return result_dataframes
    
    def _extract_metric_name(self, query: str) -> str:
        """从 PromQL 提取指标名称"""
        if "cpu" in query.lower():
            return "cpu_usage"
        elif "memory" in query.lower():
            return "memory_usage"
        elif "disk" in query.lower():
            return "disk_usage"
        elif "error" in query.lower():
            return "error_rate"
        elif "latency" in query.lower() or "duration" in query.lower():
            return "latency"
        elif "request" in query.lower():
            return "request_rate"
        else:
            return f"metric_{hash(query) % 10000}"
    
    async def tempo_to_graph_data(
        self,
        tempo: TempoQueryClient,
        lookback_minutes: int = 30,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        将 Tempo Trace 数据转换为图结构数据（用于 GNN）
        
        Returns:
            {
                "nodes": [{"id", "service", "metrics"}],
                "edges": [{"source", "target", "count", "avg_duration"}],
                "node_features": np.ndarray,
                "edge_index": np.ndarray,
            }
        """
        search_result = await tempo.search_traces(
            lookback=f"{lookback_minutes}m",
            limit=limit,
        )
        
        nodes = {}  # service -> node data
        edges = []  # (source, target) list
        
        for trace_info in search_result.traces:
            trace_id = trace_info.get("traceID", "")
            
            try:
                trace = await tempo.query_trace_by_id(trace_id)
                if not trace:
                    continue
                
                span_pairs = []
                
                for span in trace.spans:
                    service = span.service_name or "unknown"
                    
                    if service not in nodes:
                        nodes[service] = {
                            "id": service,
                            "service": service,
                            "span_count": 0,
                            "total_duration": 0.0,
                            "error_count": 0,
                            "request_count": 0,
                        }
                    
                    nodes[service]["span_count"] += 1
                    nodes[service]["request_count"] += 1
                    
                    if span.duration_ms:
                        nodes[service]["total_duration"] += span.duration_ms
                    
                    if span.is_error:
                        nodes[service]["error_count"] += 1
                    
                    if span.parent_span_id:
                        parent_span = next(
                            (s for s in trace.spans if s.span_id == span.parent_span_id),
                            None,
                        )
                        if parent_span:
                            span_pairs.append((parent_span.service_name or "unknown", service))
                
                for source, target in span_pairs:
                    edges.append((source, target))
                
            except Exception as e:
                logger.debug(f"Error processing trace {trace_id}: {e}")
                continue
        
        edge_counts = {}
        edge_durations = {}
        
        for src, tgt in edges:
            key = (src, tgt)
            edge_counts[key] = edge_counts.get(key, 0) + 1
        
        unique_edges = [
            {"source": src, "target": tgt, "count": cnt}
            for (src, tgt), cnt in edge_counts.items()
        ]
        
        node_list = list(nodes.values())
        
        node_features_list = []
        for node in node_list:
            avg_dur = node["total_duration"] / max(node["span_count"], 1)
            err_rate = node["error_count"] / max(node["request_count"], 1)
            
            features = [
                node["span_count"],
                avg_dur,
                err_rate * 100,
                node["request_count"],
            ]
            
            features_normalized = [f / 1000 if i == 0 else f for i, f in enumerate(features)]
            node_features_list.append(features_normalized)
        
        node_array = np.array(node_features_list) if node_features_list else np.array([])
        
        service_to_idx = {node["id"]: idx for idx, node in enumerate(node_list)}
        
        edge_indices = []
        for edge in unique_edges:
            src_idx = service_to_idx.get(edge["source"], -1)
            tgt_idx = service_to_idx.get(edge["target"], -1)
            if src_idx >= 0 and tgt_idx >= 0:
                edge_indices.append([src_idx, tgt_idx])
        
        edge_index = np.array(edge_indices).T if edge_indices else np.array([]).reshape(2, 0)
        
        graph_data = {
            "nodes": node_list,
            "edges": unique_edges,
            "node_features": node_array,
            "edge_index": edge_index,
            "num_nodes": len(node_list),
            "num_edges": len(unique_edges),
            "traces_analyzed": len(search_result.traces),
        }
        
        return graph_data


class IsolationForestDetector:
    """
    Isolation Forest 异常检测集成
    
    用于 CPU、内存等指标的异常检测
    """
    
    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        
        self.model: Optional[Any] = None
        self.scaler = Optional[Any] = None
        self.is_fitted = False
    
    def fit(self, X: np.ndarray) -> "IsolationForestDetector":
        """训练模型"""
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X.reshape(-1, 1) if X.ndim == 1 else X)
        
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        
        self.model.fit(X_scaled)
        self.is_fitted = True
        
        return self
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测异常
        
        Returns:
            (labels, anomaly_scores)
            labels: 1=normal, -1=anomaly
            scores: 异常分数（越低越异常）
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        
        X_scaled = self.scaler.transform(X.reshape(-1, 1) if X.ndim == 1 else X)
        
        labels = self.model.predict(X_scaled)
        scores = self.model.decision_function(X_scaled)
        
        return labels, scores
    
    def detect_from_dataframe(
        self,
        df: pd.DataFrame,
        value_column: str = "value",
    ) -> Dict[str, Any]:
        """
        从 DataFrame 检测异常
        
        Returns:
            异常检测结果字典
        """
        values = df[value_column].values.reshape(-1, 1)
        
        start_time = datetime.now()
        
        labels, scores = self.predict(values)
        
        anomaly_indices = np.where(labels == -1)[0]
        
        anomalies = []
        for idx in anomaly_indices:
            row = df.iloc[idx]
            anomalies.append({
                "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
                "value": float(row[value_column]),
                "anomaly_score": float(scores[idx]),
                "instance": row.get("instance", "unknown"),
            })
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "algorithm": "IsolationForest",
            "total_points": len(values),
            "anomaly_count": len(anomalies),
            "anomaly_ratio": len(anomalies) / len(values) if len(values) > 0 else 0,
            "anomalies": sorted(anomalies, key=lambda x: x["anomaly_score"])[:20],
            "statistics": {
                "mean_score": float(np.mean(scores)),
                "min_score": float(np.min(scores)),
                "std_score": float(np.std(scores)),
            },
            "execution_time_ms": execution_time,
        }


class ProphetForecaster:
    """
    Prophet 时序预测集成
    
    用于预测正常趋势并检测偏差
    """
    
    def __init__(
        self,
        growth: str = "linear",
        changepoint_prior_scale: float = 0.05,
        seasonality_mode: str = "multiplicative",
    ):
        self.growth = growth
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_mode = seasonality_mode
        self.model = None
        self.is_fitted = False
    
    def fit(self, df: pd.DataFrame, value_col: str = "value") -> "ProphetForecaster":
        """训练 Prophet 模型"""
        try:
            from prophet import Prophet
            
            train_df = df[["timestamp", value_col]].copy()
            train_df.columns = ["ds", "y"]
            
            self.model = Prophet(
                growth=self.growth,
                changepoint_prior_scale=self.changepoint_prior_scale,
                seasonality_mode=self.seasonality_mode,
                daily_seasonality=True,
                weekly_seasonality=True,
            )
            
            self.model.fit(train_df)
            self.is_fitted = True
            
        except ImportError:
            logger.warning("Prophet not installed, using fallback method")
            self._fit_fallback(df, value_col)
        
        return self
    
    def _fit_fallback(self, df: pd.DataFrame, value_col: str):
        """降级方案：使用移动平均"""
        self.fallback_mean = df[value_col].mean()
        self.fallback_std = df[value_col].std()
        self.is_fitted = True
    
    def detect_anomalies(
        self,
        df: pd.DataFrame,
        value_col: str = "value",
        threshold_sigma: float = 2.5,
    ) -> Dict[str, Any]:
        """
        检测与预测值偏差过大的异常点
        """
        start_time = datetime.now()
        
        if self.model is not None and self.is_fitted:
            future = self.model.make_future_dataframe(periods=0)
            forecast = self.model.predict(future)
            
            merged = df.copy()
            merged = merged.merge(forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]],
                                 left_on="timestamp", right_on="ds", how="left")
            
            residuals = merged[value_col] - merged["yhat"]
            std_residual = (residuals - residuals.mean()) / (residuals.std() + 1e-8)
            
            anomaly_mask = std_residual.abs() > threshold_sigma
            
            anomalies = []
            for idx in merged[anomaly_mask].index.tolist()[:20]:
                row = merged.loc[idx]
                anomalies.append({
                    "timestamp": row["timestamp"].isoformat(),
                    "actual_value": float(row[value_col]),
                    "predicted_value": float(row["yhat"]),
                    "residual": float(residuals.loc[idx]),
                    "z_score": float(std_residual.loc[idx]),
                    "instance": row.get("instance", "unknown"),
                })
        else:
            mean = getattr(self, 'fallback_mean', df[value_col].mean())
            std = getattr(self, 'fallback_std', df[value_col].std())
            
            z_scores = ((df[value_col] - mean) / (std + 1e-8)).abs()
            anomaly_mask = z_scores > threshold_sigma
            
            anomalies = []
            for idx in df[anomaly_mask].index.tolist()[:20]:
                row = df.loc[idx]
                anomalies.append({
                    "timestamp": row["timestamp"].isoformat(),
                    "actual_value": float(row[value_col]),
                    "predicted_value": float(mean),
                    "residual": float(row[value_col] - mean),
                    "z_score": float(z_scores.loc[idx]),
                    "instance": row.get("instance", "unknown"),
                })
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "algorithm": "Prophet",
            "total_points": len(df),
            "anomaly_count": len(anomalies),
            "anomaly_ratio": len(anomalies) / len(df) if len(df) > 0 else 0,
            "threshold_sigma": threshold_sigma,
            "anomalies": anomalies,
            "execution_time_ms": execution_time,
        }


class GNRootCauseEngine:
    """
    GNN 根因分析引擎集成
    
    整合 microservice_rca 和 GNN_RCA 的模型能力
    """
    
    def __init__(
        self,
        model_type: str = "gat",
        hidden_dim: int = 64,
        num_layers: int = 3,
    ):
        self.model_type = model_type
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        self.model = None
        self.device = None
        self.is_loaded = False
    
    def load_pretrained_model(self, model_path: Optional[str] = None) -> bool:
        """
        加载预训练模型
        
        Args:
            model_path: 模型文件路径（可选，使用默认路径）
            
        Returns:
            是否加载成功
        """
        try:
            import torch
            
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            
            gnn_rca_dir = os.path.join(TIME_SEQ_DIR, "microservice_rca")
            sys.path.insert(0, gnn_rca_dir)
            
            from model import GATRootCauseModel, GCNRootCauseModel
            
            num_features = 4  # [span_count, avg_duration, error_rate, request_count]
            
            if self.model_type == "gat":
                self.model = GATRootCauseModel(
                    num_features=num_features,
                    hidden_dim=self.hidden_dim,
                    num_layers=self.num_layers,
                )
            else:
                self.model = GCNRootCauseModel(
                    num_features=num_features,
                    hidden_dim=self.hidden_dim,
                    num_layers=self.num_layers,
                )
            
            if model_path and os.path.exists(model_path):
                state_dict = torch.load(model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                logger.info(f"Loaded GNN model from {model_path}")
            else:
                default_model_path = os.path.join(gnn_rca_dir, "models", "best_model.pt")
                if os.path.exists(default_model_path):
                    state_dict = torch.load(default_model_path, map_location=self.device)
                    self.model.load_state_dict(state_dict)
                    logger.info(f"Loaded default GNN model")
            
            self.model = self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to load GNN model: {e}")
            logger.info("Will use rule-based fallback for root cause analysis")
            return False
    
    def predict_root_causes(
        self,
        graph_data: Dict[str, Any],
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """
        使用 GNN 预测根因节点
        
        Args:
            graph_data: 图数据（来自 DataBridge）
            top_k: 返回 Top-K 个候选根因
            
        Returns:
            根因预测结果
        """
        start_time = datetime.now()
        
        if not self.is_loaded or self.model is None:
            return self._rule_based_root_cause(graph_data, top_k)
        
        try:
            import torch
            
            node_features = torch.FloatTensor(graph_data["node_features"]).to(self.device)
            edge_index = torch.LongTensor(graph_data["edge_index"]).to(self.device)
            
            with torch.no_grad():
                scores = self.model(node_features, edge_index)
                probabilities = torch.sigmoid(scores).cpu().numpy()
            
            top_indices = np.argsort(probabilities)[::-1][:top_k]
            
            candidates = []
            for rank, idx in enumerate(top_indices, 1):
                if idx < len(graph_data["nodes"]):
                    node = graph_data["nodes"][idx]
                    candidates.append({
                        "rank": rank,
                        "service": node["id"],
                        "score": float(probabilities[idx]),
                        "metrics": {
                            "span_count": node.get("span_count", 0),
                            "error_count": node.get("error_count", 0),
                            "avg_duration": node.get("total_duration", 0) / max(node.get("span_count", 1), 1),
                        },
                    })
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "algorithm": f"GNN ({self.model_type.upper()})",
                "success": True,
                "top_candidates": candidates,
                "all_scores": probabilities.tolist(),
                "graph_stats": {
                    "nodes": graph_data["num_nodes"],
                    "edges": graph_data["num_edges"],
                },
                "execution_time_ms": execution_time,
            }
            
        except Exception as e:
            logger.error(f"GNN prediction failed: {e}, falling back to rule-based")
            return self._rule_based_root_cause(graph_data, top_k)
    
    def _rule_based_root_cause(
        self,
        graph_data: Dict[str, Any],
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """
        规则-based 根因推理（当 GNN 模型不可用时的降级方案）
        """
        nodes = graph_data.get("nodes", [])
        
        scored_nodes = []
        
        for node in nodes:
            error_count = node.get("error_count", 0)
            request_count = node.get("request_count", 1)
            total_duration = node.get("total_duration", 0)
            span_count = node.get("span_count", 1)
            
            error_rate = error_count / max(request_count, 1)
            avg_duration = total_duration / max(span_count, 1)
            
            score = (
                error_rate * 0.4 +
                min(avg_duration / 5000, 1.0) * 0.3 +
                min(error_count / 10, 1.0) * 0.3
            )
            
            scored_nodes.append({
                "service": node["id"],
                "score": score,
                "metrics": {
                    "error_rate": error_rate,
                    "avg_duration": avg_duration,
                    "error_count": error_count,
                },
            })
        
        scored_nodes.sort(key=lambda x: x["score"], reverse=True)
        
        candidates = [
            {**node, "rank": rank + 1}
            for rank, node in enumerate(scored_nodes[:top_k])
        ]
        
        return {
            "algorithm": "Rule-Based (GNN Fallback)",
            "success": True,
            "top_candidates": candidates,
            "graph_stats": {
                "nodes": graph_data["num_nodes"],
                "edges": graph_data["num_edges"],
            },
            "execution_time_ms": 0,
        }


class EnhancedRootCauseAnalyzer:
    """
    增强型根因分析器
    
    整合所有算法和可观测性数据源
    """
    
    def __init__(
        self,
        config: Optional[ObservabilityConfig] = None,
        enable_gnn: bool = True,
        enable_isolation_forest: bool = True,
        enable_prophet: bool = True,
        fusion_strategy: FusionStrategy = FusionStrategy.WEIGHTED_AVERAGE,
    ):
        self.config = config or get_observability_config()
        
        self.enable_gnn = enable_gnn
        self.enable_isolation_forest = enable_isolation_forest
        self.enable_prophet = enable_prophet
        self.fusion_strategy = fusion_strategy
        
        self.base_analyzer: Optional[RootCauseAnalyzer] = None
        self.prometheus: Optional[PrometheusClient] = None
        self.tempo: Optional[TempoQueryClient] = None
        
        self.data_bridge = TimeSeriesDataBridge()
        
        self.gnn_engine: Optional[GNRootCauseEngine] = None
        self.if_detector: Optional[IsolationForestDetector] = None
        self.prophet_forecaster: Optional[ProphetForecaster] = None
        
        self.algorithm_results: List[AlgorithmResult] = []
    
    async def __aenter__(self):
        await self._initialize_clients()
        self._initialize_algorithms()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def _initialize_clients(self):
        """初始化数据源客户端"""
        if self.config.prometheus.enabled:
            self.prometheus = PrometheusClient(config=self.config)
            await self.prometheus.connect()
        
        if self.config.tempo.enabled:
            self.tempo = TempoQueryClient(config=self.config)
            await self.tempo.connect()
        
        self.base_analyzer = RootCauseAnalyzer(
            config=self.config,
            prometheus_client=self.prometheus,
            tempo_client=self.tempo,
        )
    
    def _initialize_algorithms(self):
        """初始化算法引擎"""
        if self.enable_gnn:
            self.gnn_engine = GNRootCauseEngine(model_type="gat")
            self.gnn_engine.load_pretrained_model()
        
        if self.enable_isolation_forest:
            self.if_detector = IsolationForestDetector(contamination=0.05)
        
        if self.enable_prophet:
            self.prophet_forecaster = ProphetForecaster()
    
    async def analyze_enhanced(
        self,
        service_name: Optional[str] = None,
        time_window_minutes: int = 30,
        alert_events: Optional[List[AlertEvent]] = None,
        custom_queries: Optional[List[str]] = None,
    ) -> FusedAnalysisReport:
        """
        执行增强型根因分析
        
        整合多个算法进行综合分析
        """
        overall_start = datetime.now()
        
        logger.info("="*60)
        logger.info("🚀 Starting Enhanced Root Cause Analysis")
        logger.info("="*60)
        
        self.algorithm_results = []
        
        # Step 1: 基础分析（原有的 observability 分析）
        logger.info("\n📍 Step 1: Base Observability Analysis...")
        base_report = await self.base_analyzer.analyze_incident(
            alert_events=alert_events,
            service_name=service_name,
            time_window_minutes=time_window_minutes,
            custom_queries=custom_queries,
        )
        
        # Step 2: Isolation Forest 异常检测
        if self.enable_isolation_forest and self.prometheus:
            logger.info("\n📍 Step 2: Isolation Forest Anomaly Detection...")
            if_result = await self._run_isolation_forest_analysis(
                service_name=service_name,
                time_window_minutes=time_window_minutes,
            )
            self.algorithm_results.append(if_result)
        
        # Step 3: Prophet 时序预测异常检测
        if self.enable_prophet and self.prometheus:
            logger.info("\n📍 Step 3: Prophet Forecast Anomaly Detection...")
            prophet_result = await self._run_prophet_analysis(
                service_name=service_name,
                time_window_minutes=time_window_minutes,
            )
            self.algorithm_results.append(prophet_result)
        
        # Step 4: GNN 根因分析
        if self.enable_gnn and self.tempo:
            logger.info("\n📍 Step 4: GNN Root Cause Analysis...")
            gnn_result = await self._run_gnn_analysis(
                service_name=service_name,
                time_window_minutes=time_window_minutes,
            )
            self.algorithm_results.append(gnn_result)
        
        # Step 5: Trace 错误链路分析
        if self.tempo:
            logger.info("\n📍 Step 5: Trace Error Propagation Analysis...")
            trace_error_result = await self._run_trace_error_analysis(
                service_name=service_name,
                time_window_minutes=time_window_minutes,
            )
            self.algorithm_results.append(trace_error_result)
        
        # Step 6: 慢请求链路分析
        if self.tempo:
            logger.info("\n📍 Step 6: Slow Trace Performance Analysis...")
            slow_trace_result = await self._run_slow_trace_analysis(
                service_name=service_name,
                time_window_minutes=time_window_minutes,
                threshold_ms=1000,
            )
            self.algorithm_results.append(slow_trace_result)
        
        # Step 7: 结果融合
        logger.info("\n📍 Step 7: Multi-Algorithm Fusion...")
        fused_report = self._fuse_results(base_report)
        
        overall_duration = (datetime.now() - overall_start).total_seconds()
        
        logger.info(f"\n✅ Enhanced Analysis Complete!")
        logger.info(f"   Total Duration: {overall_duration:.2f}s")
        logger.info(f"   Algorithms Used: {fused_report.algorithms_used}")
        
        return fused_report
    
    async def _run_isolation_forest_analysis(
        self,
        service_name: Optional[str],
        time_window_minutes: int,
    ) -> AlgorithmResult:
        """运行 Isolation Forest 异常检测"""
        start_time = datetime.now()
        
        try:
            queries = [
                '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
                '100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            ]
            
            ts_data = await self.data_bridge.prometheus_to_timeseries(
                prometheus=self.prometheus,
                queries=queries,
                duration_minutes=time_window_minutes,
                step="1m",
            )
            
            all_anomalies = []
            all_metrics = {}
            
            for metric_name, df in ts_data.items():
                if len(df) > 10:
                    detector = IsolationForestDetector(contamination=0.03)
                    detector.fit(df["value"].values)
                    result = detector.detect_from_dataframe(df)
                    
                    all_anomalies.extend(result.get("anomalies", []))
                    all_metrics[metric_name] = {
                        "total_points": result["total_points"],
                        "anomaly_count": result["anomaly_count"],
                    }
            
            confidence = min(0.95, len(all_anomalies) / 10) if all_anomalies else 0.1
            
            candidates = []
            if all_anomalies:
                worst_anomaly = max(all_anomalies, key=lambda x: abs(x.get("anomaly_score", 0)))
                candidates.append({
                    "component": worst_anomaly.get("instance", "unknown"),
                    "type": "metric_anomaly",
                    "description": f"检测到显著异常点: value={worst_anomaly['value']:.2f}",
                    "score": confidence,
                })
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AlgorithmResult(
                algorithm_type=AlgorithmType.ISOLATION_FOREST,
                algorithm_name="Isolation Forest Anomaly Detection",
                success=True,
                confidence_score=confidence,
                root_cause_candidates=candidates,
                execution_time_ms=execution_time,
                metadata={
                    "anomalies_found": len(all_anomalies),
                    "metrics_analyzed": list(all_metrics.keys()),
                    **all_metrics,
                },
            )
            
        except Exception as e:
            return AlgorithmResult(
                algorithm_type=AlgorithmType.ISOLATION_FOREST,
                algorithm_name="Isolation Forest",
                success=False,
                confidence_score=0.0,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=str(e),
            )
    
    async def _run_prophet_analysis(
        self,
        service_name: Optional[str],
        time_window_minutes: int,
    ) -> AlgorithmResult:
        """运行 Prophet 时序预测分析"""
        start_time = datetime.now()
        
        try:
            queries = [
                'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100',
            ]
            
            if service_name:
                queries.append(
                    f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))'
                )
            
            ts_data = await self.data_bridge.prometheus_to_timeseries(
                prometheus=self.prometheus,
                queries=queries,
                duration_minutes=min(time_window_minutes * 2, 120),
                step="5m",
            )
            
            all_anomalies = []
            
            for metric_name, df in ts_data.items():
                if len(df) > 20:
                    forecaster = ProphetForecaster()
                    forecaster.fit(df)
                    result = forecaster.detect_anomalies(df, threshold_sigma=2.5)
                    
                    all_anomalies.extend(result.get("anomalies", []))
            
            confidence = min(0.9, len(all_anomalies) / 5) if all_anomalies else 0.1
            
            candidates = []
            if all_anomalies:
                top_anomaly = max(all_anomalies, key=lambda x: abs(x.get("z_score", 0)))
                candidates.append({
                    "component": top_anomaly.get("instance", "unknown"),
                    "type": "trend_deviation",
                    "description": f"时序偏离预期: z-score={top_anomaly['z_score']:.2f}",
                    "score": confidence,
                })
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AlgorithmResult(
                algorithm_type=AlgorithmType.PROPHET_FORECAST,
                algorithm_name="Prophet Trend Anomaly Detection",
                success=True,
                confidence_score=confidence,
                root_cause_candidates=candidates,
                execution_time_ms=execution_time,
                metadata={
                    "anomalies_found": len(all_anomalies),
                },
            )
            
        except Exception as e:
            return AlgorithmResult(
                algorithm_type=AlgorithmType.PROPHET_FORECAST,
                algorithm_name="Prophet",
                success=False,
                confidence_score=0.0,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=str(e),
            )
    
    async def _run_gnn_analysis(
        self,
        service_name: Optional[str],
        time_window_minutes: int,
    ) -> AlgorithmResult:
        """运行 GNN 根因分析"""
        start_time = datetime.now()
        
        try:
            graph_data = await self.data_bridge.tempo_to_graph_data(
                tempo=self.tempo,
                lookback_minutes=time_window_minutes,
                limit=150,
            )
            
            if graph_data["num_nodes"] < 2:
                return AlgorithmResult(
                    algorithm_type=AlgorithmType.GNN_RCA,
                    algorithm_name="GNN Root Cause Analysis",
                    success=False,
                    confidence_score=0.0,
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    error_message=f"Insufficient nodes in graph ({graph_data['num_nodes']} found)",
                )
            
            prediction = self.gnn_engine.predict_root_causes(
                graph_data=graph_data,
                top_k=3,
            )
            
            candidates = [
                {
                    "component": cand["service"],
                    "type": "service_dependency",
                    "description": f"GNN 评分最高的服务节点 (rank={cand['rank']})",
                    "score": cand["score"],
                    "details": cand.get("metrics", {}),
                }
                for cand in prediction.get("top_candidates", [])
            ]
            
            top_score = candidates[0]["score"] if candidates else 0.0
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AlgorithmResult(
                algorithm_type=AlgorithmType.GNN_RCA,
                algorithm_name=prediction.get("algorithm", "GNN Root Cause"),
                success=prediction.get("success", False),
                confidence_score=top_score,
                root_cause_candidates=candidates,
                execution_time_ms=execution_time,
                metadata=prediction,
            )
            
        except Exception as e:
            return AlgorithmResult(
                algorithm_type=AlgorithmType.GNN_RCA,
                algorithm_name="GNN Root Cause",
                success=False,
                confidence_score=0.0,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=str(e),
            )
    
    async def _run_trace_error_analysis(
        self,
        service_name: Optional[str],
        time_window_minutes: int,
    ) -> AlgorithmResult:
        """
        运行 Trace 错误链路分析
        
        从 Tempo 查询错误链路，分析错误传播路径
        """
        start_time = datetime.now()
        
        try:
            if not self.tempo:
                return AlgorithmResult(
                    algorithm_type=AlgorithmType.STATISTICAL,
                    algorithm_name="Trace Error Analysis",
                    success=False,
                    confidence_score=0.0,
                    execution_time_ms=0,
                    error_message="Tempo client not initialized",
                )
            
            lookback = f"{time_window_minutes}m"
            
            error_traces = await self.tempo.search_error_traces(
                service_name=service_name,
                lookback=lookback,
                limit=50,
            )
            
            if not error_traces.traces:
                return AlgorithmResult(
                    algorithm_type=AlgorithmType.STATISTICAL,
                    algorithm_name="Trace Error Analysis",
                    success=True,
                    confidence_score=0.1,
                    root_cause_candidates=[],
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    metadata={"message": "No error traces found"},
                )
            
            error_services = {}
            error_propagation_paths = []
            
            for trace_data in error_traces.traces[:20]:
                trace_id = trace_data.get("traceID")
                if not trace_id:
                    continue
                
                trace = await self.tempo.query_trace_by_id(trace_id)
                if not trace:
                    continue
                
                for span in trace.error_spans:
                    svc = span.service_name
                    if svc not in error_services:
                        error_services[svc] = {
                            "error_count": 0,
                            "error_types": [],
                            "affected_operations": [],
                        }
                    
                    error_services[svc]["error_count"] += 1
                    
                    if span.operation_name not in error_services[svc]["affected_operations"]:
                        error_services[svc]["affected_operations"].append(span.operation_name)
                    
                    for event in span.events:
                        if "exception" in event.name.lower():
                            exc_type = event.attributes.get("exception.type", "Unknown")
                            if exc_type not in error_services[svc]["error_types"]:
                                error_services[svc]["error_types"].append(exc_type)
                
                propagation_path = self._extract_error_propagation_path(trace)
                if propagation_path:
                    error_propagation_paths.append(propagation_path)
            
            candidates = []
            for svc, data in sorted(error_services.items(), key=lambda x: x[1]["error_count"], reverse=True):
                confidence = min(0.95, data["error_count"] / 10 + 0.3)
                candidates.append({
                    "component": svc,
                    "type": "trace_error",
                    "description": f"服务 {svc} 检测到 {data['error_count']} 次错误，涉及操作: {', '.join(data['affected_operations'][:3])}",
                    "score": confidence,
                    "error_types": data["error_types"],
                    "affected_operations": data["affected_operations"],
                })
            
            if error_propagation_paths:
                most_common_path = max(set(tuple(p) for p in error_propagation_paths), 
                                       key=lambda x: error_propagation_paths.count(list(x)))
                candidates.append({
                    "component": most_common_path[0] if most_common_path else "unknown",
                    "type": "error_propagation",
                    "description": f"检测到常见错误传播路径: {' → '.join(most_common_path)}",
                    "score": 0.7,
                    "propagation_path": list(most_common_path),
                })
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AlgorithmResult(
                algorithm_type=AlgorithmType.STATISTICAL,
                algorithm_name="Trace Error Propagation Analysis",
                success=True,
                confidence_score=candidates[0]["score"] if candidates else 0.1,
                root_cause_candidates=candidates,
                execution_time_ms=execution_time,
                metadata={
                    "total_error_traces": len(error_traces.traces),
                    "services_with_errors": len(error_services),
                    "error_services": error_services,
                },
            )
            
        except Exception as e:
            return AlgorithmResult(
                algorithm_type=AlgorithmType.STATISTICAL,
                algorithm_name="Trace Error Analysis",
                success=False,
                confidence_score=0.0,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=str(e),
            )
    
    async def _run_slow_trace_analysis(
        self,
        service_name: Optional[str],
        time_window_minutes: int,
        threshold_ms: int = 1000,
    ) -> AlgorithmResult:
        """
        运行慢请求链路分析
        
        从 Tempo 查询慢请求链路，识别性能瓶颈
        """
        start_time = datetime.now()
        
        try:
            if not self.tempo:
                return AlgorithmResult(
                    algorithm_type=AlgorithmType.STATISTICAL,
                    algorithm_name="Slow Trace Analysis",
                    success=False,
                    confidence_score=0.0,
                    execution_time_ms=0,
                    error_message="Tempo client not initialized",
                )
            
            lookback = f"{time_window_minutes}m"
            
            slow_traces = await self.tempo.search_slow_traces(
                min_duration=f"{threshold_ms}ms",
                service_name=service_name,
                lookback=lookback,
                limit=30,
            )
            
            if not slow_traces.traces:
                return AlgorithmResult(
                    algorithm_type=AlgorithmType.STATISTICAL,
                    algorithm_name="Slow Trace Analysis",
                    success=True,
                    confidence_score=0.1,
                    root_cause_candidates=[],
                    execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                    metadata={"message": f"No slow traces found (threshold: {threshold_ms}ms)"},
                )
            
            slow_spans_by_service = {}
            slowest_operations = []
            
            for trace_data in slow_traces.traces[:15]:
                trace_id = trace_data.get("traceID")
                if not trace_id:
                    continue
                
                trace = await self.tempo.query_trace_by_id(trace_id)
                if not trace:
                    continue
                
                for span in trace.spans:
                    if span.duration_ms and span.duration_ms > threshold_ms:
                        svc = span.service_name
                        if svc not in slow_spans_by_service:
                            slow_spans_by_service[svc] = {
                                "total_slow_spans": 0,
                                "total_duration_ms": 0,
                                "operations": {},
                            }
                        
                        slow_spans_by_service[svc]["total_slow_spans"] += 1
                        slow_spans_by_service[svc]["total_duration_ms"] += span.duration_ms
                        
                        op = span.operation_name
                        if op not in slow_spans_by_service[svc]["operations"]:
                            slow_spans_by_service[svc]["operations"][op] = {
                                "count": 0,
                                "avg_duration_ms": 0,
                                "max_duration_ms": 0,
                            }
                        
                        slow_spans_by_service[svc]["operations"][op]["count"] += 1
                        slow_spans_by_service[svc]["operations"][op]["avg_duration_ms"] = (
                            slow_spans_by_service[svc]["operations"][op]["avg_duration_ms"] * 
                            (slow_spans_by_service[svc]["operations"][op]["count"] - 1) + 
                            span.duration_ms
                        ) / slow_spans_by_service[svc]["operations"][op]["count"]
                        slow_spans_by_service[svc]["operations"][op]["max_duration_ms"] = max(
                            slow_spans_by_service[svc]["operations"][op]["max_duration_ms"],
                            span.duration_ms
                        )
                        
                        slowest_operations.append({
                            "service": svc,
                            "operation": op,
                            "duration_ms": span.duration_ms,
                        })
            
            candidates = []
            for svc, data in sorted(slow_spans_by_service.items(), 
                                    key=lambda x: x[1]["total_duration_ms"], reverse=True):
                avg_duration = data["total_duration_ms"] / data["total_slow_spans"]
                confidence = min(0.95, avg_duration / 1000 + 0.2)
                
                top_operations = sorted(
                    data["operations"].items(),
                    key=lambda x: x[1]["avg_duration_ms"],
                    reverse=True
                )[:3]
                
                candidates.append({
                    "component": svc,
                    "type": "performance_bottleneck",
                    "description": f"服务 {svc} 存在性能瓶颈，平均延迟 {avg_duration:.1f}ms，慢操作: {', '.join([op for op, _ in top_operations])}",
                    "score": confidence,
                    "avg_duration_ms": avg_duration,
                    "slow_span_count": data["total_slow_spans"],
                    "top_operations": [{"operation": op, **stats} for op, stats in top_operations],
                })
            
            slowest_operations.sort(key=lambda x: x["duration_ms"], reverse=True)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return AlgorithmResult(
                algorithm_type=AlgorithmType.STATISTICAL,
                algorithm_name="Slow Trace Performance Analysis",
                success=True,
                confidence_score=candidates[0]["score"] if candidates else 0.1,
                root_cause_candidates=candidates,
                execution_time_ms=execution_time,
                metadata={
                    "total_slow_traces": len(slow_traces.traces),
                    "threshold_ms": threshold_ms,
                    "slowest_operations": slowest_operations[:10],
                },
            )
            
        except Exception as e:
            return AlgorithmResult(
                algorithm_type=AlgorithmType.STATISTICAL,
                algorithm_name="Slow Trace Analysis",
                success=False,
                confidence_score=0.0,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                error_message=str(e),
            )
    
    def _extract_error_propagation_path(self, trace) -> List[str]:
        """
        从 Trace 中提取错误传播路径
        
        Args:
            trace: Trace 对象
            
        Returns:
            错误传播路径（服务列表）
        """
        if not trace.error_spans:
            return []
        
        error_span_ids = {s.span_id for s in trace.error_spans}
        
        def find_root_error_span(span):
            if span.span_id in error_span_ids:
                if not span.parent_span_id:
                    return span
                parent = next((s for s in trace.spans if s.span_id == span.parent_span_id), None)
                if parent and parent.span_id in error_span_ids:
                    return find_root_error_span(parent)
            return span
        
        root_error_spans = [find_root_error_span(s) for s in trace.error_spans]
        
        if root_error_spans:
            root = root_error_spans[0]
            path = [root.service_name]
            
            def add_children(span, current_path):
                children = [s for s in trace.spans if s.parent_span_id == span.span_id]
                for child in children:
                    if child.span_id in error_span_ids:
                        new_path = current_path + [child.service_name]
                        add_children(child, new_path)
                if len(current_path) > len(path):
                    path.extend(current_path[len(path):])
            
            add_children(root, path)
            return path
        
        return []
    
    def _fuse_results(self, base_report: RootCauseAnalysisReport) -> FusedAnalysisReport:
        """
        融合多算法结果到基础报告
        """
        if not self.algorithm_results:
            return FusedAnalysisReport(
                base_report=base_report,
                fusion_strategy=self.fusion_strategy,
            )
        
        successful_results = [r for r in self.algorithm_results if r.success]
        
        for algo_result in successful_results:
            for candidate in algo_result.root_cause_candidates:
                evidence = Evidence(
                    evidence_id=f"algo_{algo_result.algorithm_type.value}_{candidate.get('component', 'unknown')}",
                    evidence_type=EvidenceType.CORRELATION,
                    source=algo_result.algorithm_name,
                    description=candidate.get("description", ""),
                    confidence=candidate.get("score", 0.5),
                    timestamp=datetime.now(),
                    metadata={
                        "algorithm": algo_result.algorithm_type.value,
                        "component": candidate.get("component"),
                        "type": candidate.get("type"),
                    },
                )
                
                existing_hyp = next(
                    (h for h in base_report.hypotheses 
                     if h.affected_component == candidate.get("component")),
                    None,
                )
                
                if existing_hyp:
                    existing_hyp.add_evidence(evidence)
                else:
                    new_hyp = RootCauseHypothesis(
                        hypothesis_id=f"fused_{len(base_report.hypotheses)}",
                        title=f"[{algo_result.algorithm_name}] {candidate.get('component', 'Unknown')} 异常",
                        description=candidate.get("description", ""),
                        affected_component=candidate.get("component", "unknown"),
                        severity=AnalysisSeverity.HIGH if candidate.get("score", 0) > 0.7 else AnalysisSeverity.MEDIUM,
                        confidence_score=candidate.get("score", 0.5),
                    )
                    new_hyp.add_evidence(evidence)
                    base_report.hypotheses.append(new_hyp)
        
        base_report.hypotheses.sort(key=lambda h: h.confidence_score, reverse=True)
        
        if base_report.hypotheses:
            base_report.root_confidence = base_report.hypotheses[0].confidence_score
        
        return FusedAnalysisReport(
            base_report=base_report,
            algorithm_results=self.algorithm_results,
            fusion_strategy=self.fusion_strategy,
        )


async def create_enhanced_analyzer(
    config: Optional[ObservabilityConfig] = None,
    enable_all_algorithms: bool = True,
) -> EnhancedRootCauseAnalyzer:
    """
    工厂函数：创建增强型根因分析器
    
    Args:
        config: 可观测性配置
        enable_all_algorithms: 是否启用所有算法
        
    Returns:
        已初始化的增强型分析器
    """
    analyzer = EnhancedRootCauseAnalyzer(
        config=config,
        enable_gnn=enable_all_algorithms,
        enable_isolation_forest=enable_all_algorithms,
        enable_prophet=enable_all_algorithms,
    )
    return analyzer
