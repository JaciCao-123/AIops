"""
Root Cause Analyzer - 多维根因分析引擎

功能：
1. 整合 Prometheus 指标、Tempo 链路、日志数据进行综合分析
2. 时间序列异常检测与关联分析
3. 服务调用链分析与瓶颈识别
4. 基于图神经网络的根因推理（可选）
5. 多维度证据收集与置信度评分
6. 自动生成根因分析报告
7. 支持与 LLM 集成进行智能分析增强

架构设计：
- 数据层：从 Prometheus/Tempo/Loki 采集数据
- 分析层：多算法融合的根因推理
- 推理层：基于规则的专家系统 + LLM 增强
- 输出层：结构化分析报告与可视化数据
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

import numpy as np
from pydantic import BaseModel, Field

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

logger = logging.getLogger(__name__)


class AnalysisSeverity(str, Enum):
    """分析严重级别"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceType(str, Enum):
    """证据类型"""
    METRIC_ANOMALY = "metric_anomaly"  # 指标异常
    TRACE_ERROR = "trace_error"  # 链路错误
    CORRELATION = "correlation"  # 时间相关性
    DEPENDENCY = "dependency"  # 依赖关系
    THRESHOLD_BREACH = "threshold_breach"  # 阈值突破
    LOG_PATTERN = "log_pattern"  # 日志模式


@dataclass
class Evidence:
    """
    证据项
    
    表示支持某个根因假设的证据
    """
    evidence_id: str
    evidence_type: EvidenceType
    source: str  # 数据来源 (prometheus/tempo/logs)
    description: str
    confidence: float  # 该证据的可信度 [0-1]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "type": self.evidence_type.value,
            "source": self.source,
            "description": self.description,
            "confidence": round(self.confidence, 3),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class RootCauseHypothesis:
    """
    根因假设
    
    表示一个可能的根本原因及其支持证据
    """
    hypothesis_id: str
    title: str
    description: str
    affected_component: str  # 受影响组件/服务
    severity: AnalysisSeverity
    confidence_score: float  # 综合置信度 [0-1]
    evidences: List[Evidence] = field(default_factory=list)
    related_metrics: List[str] = field(default_factory=list)
    related_traces: List[str] = field(default_factory=list)
    remediation_steps: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def evidence_count(self) -> int:
        return len(self.evidences)
    
    @property
    def avg_evidence_confidence(self) -> float:
        if not self.evidences:
            return 0.0
        return np.mean([e.confidence for e in self.evidences])
    
    def add_evidence(self, evidence: Evidence):
        """添加证据"""
        self.evidences.append(evidence)
        self._recalculate_confidence()
    
    def _recalculate_confidence(self):
        """重新计算综合置信度"""
        if not self.evidences:
            return
        
        evidence_weights = {
            EvidenceType.METRIC_ANOMALY: 0.25,
            EvidenceType.TRACE_ERROR: 0.30,
            EvidenceType.CORRELATION: 0.20,
            EvidenceType.DEPENDENCY: 0.15,
            EvidenceType.THRESHOLD_BREACH: 0.10,
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for ev in self.evidences:
            weight = evidence_weights.get(ev.evidence_type, 0.1)
            weighted_sum += ev.confidence * weight
            total_weight += weight
        
        self.confidence_score = weighted_sum / total_weight if total_weight > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "description": self.description,
            "affected_component": self.affected_component,
            "severity": self.severity.value,
            "confidence_score": round(self.confidence_score, 3),
            "evidence_count": self.evidence_count,
            "avg_evidence_confidence": round(self.avg_evidence_confidence, 3),
            "evidences": [ev.to_dict() for ev in self.evidences],
            "related_metrics": self.related_metrics,
            "related_traces": self.related_traces,
            "remediation_steps": self.remediation_steps,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class RootCauseAnalysisReport:
    """
    根因分析报告
    
    完整的分析结果，包含所有假设和证据
    """
    analysis_id: str
    incident_time: datetime
    incident_description: str
    analysis_time: datetime
    analysis_duration_seconds: float
    
    overall_severity: AnalysisSeverity
    root_confidence: float
    
    hypotheses: List[RootCauseHypothesis] = field(default_factory=list)
    
    data_sources_used: List[str] = field(default_factory=list)
    metrics_analyzed: int = 0
    traces_analyzed: int = 0
    
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def top_hypothesis(self) -> Optional[RootCauseHypothesis]:
        """获取最高置信度的假设"""
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.confidence_score)
    
    @property
    def critical_hypotheses(self) -> List[RootCauseHypothesis]:
        """获取高严重级别的假设"""
        return [h for h in self.hypotheses if h.severity == AnalysisSeverity.CRITICAL]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "incident_time": self.incident_time.isoformat(),
            "incident_description": self.incident_description,
            "analysis_time": self.analysis_time.isoformat(),
            "analysis_duration_seconds": round(self.analysis_duration_seconds, 2),
            "overall_severity": self.overall_severity.value,
            "root_confidence": round(self.root_confidence, 3),
            "hypotheses": [h.to_dict() for h in sorted(
                self.hypotheses, 
                key=lambda x: x.confidence_score, 
                reverse=True
            )],
            "top_hypothesis": self.top_hypothesis.to_dict() if self.top_hypothesis else None,
            "data_sources_used": self.data_sources_used,
            "metrics_analyzed": self.metrics_analyzed,
            "traces_analyzed": self.traces_analyzed,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


class RootCauseAnalyzer:
    """
    根因分析引擎
    
    整合多个数据源，使用多种分析方法进行根因推理
    
    核心能力：
    - 时间序列异常检测与关联
    - 调用链错误传播分析
    - 服务依赖关系推理
    - 多维证据融合
    - LLM 增强分析（可选）
    """
    
    def __init__(
        self,
        config: Optional[ObservabilityConfig] = None,
        prometheus_client: Optional[PrometheusClient] = None,
        tempo_client: Optional[TempoQueryClient] = None,
    ):
        """
        初始化根因分析器
        
        Args:
            config: 可观测性配置
            prometheus_client: Prometheus 客户端（可选，会自动创建）
            tempo_client: Tempo 客户端（可选，会自动创建）
        """
        self.config = config or get_observability_config()
        
        self.prometheus = prometheus_client
        self.tempo = tempo_client
        
        self.rca_config = self.config.root_c_analysis
        
        self._hypothesis_counter = 0
        self._evidence_counter = 0
    
    async def __aenter__(self):
        await self._ensure_clients()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def _ensure_clients(self):
        """确保客户端已初始化"""
        if not self.prometheus and self.config.prometheus.enabled:
            self.prometheus = PrometheusClient(config=self.config)
            await self.prometheus.connect()
        
        if not self.tempo and self.config.tempo.enabled:
            self.tempo = TempoQueryClient(config=self.config)
            await self.tempo.connect()
    
    def _generate_id(self, prefix: str = "") -> str:
        """生成唯一 ID"""
        if prefix == "h":
            self._hypothesis_counter += 1
            return f"hyp_{self._hypothesis_counter:04d}"
        elif prefix == "e":
            self._evidence_counter += 1
            return f"ev_{self._evidence_counter:04d}"
        else:
            return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{np.random.randint(10000)}"
    
    async def analyze_incident(
        self,
        alert_events: Optional[List[AlertEvent]] = None,
        service_name: Optional[str] = None,
        time_window_minutes: int = 15,
        custom_queries: Optional[List[str]] = None,
    ) -> RootCauseAnalysisReport:
        """
        执行完整的根因分析
        
        Args:
            alert_events: 触发分析的告警事件列表
            service_name: 目标服务名称
            time_window_minutes: 分析时间窗口
            custom_queries: 自定义 PromQL 查询
            
        Returns:
            完整的根因分析报告
        """
        start_time = datetime.now()
        analysis_id = self._generate_id("rca")
        
        logger.info(f"[{analysis_id}] Starting root cause analysis")
        
        await self._ensure_clients()
        
        hypotheses: List[RootCauseHypothesis] = []
        data_sources = []
        metrics_count = 0
        traces_count = 0
        
        incident_desc = service_name or "System-wide issue"
        incident_time = datetime.now() - timedelta(minutes=time_window_minutes)
        
        # Step 1: 收集告警事件
        if not alert_events and self.prometheus:
            logger.info(f"[{analysis_id}] Collecting alerts from Prometheus...")
            alert_events = await self.prometheus.check_alert_rules()
        
        if alert_events:
            data_sources.append("prometheus_alerts")
            logger.info(f"[{analysis_id}] Found {len(alert_events)} active alerts")
        
        # Step 2: 指标异常检测与分析
        if self.prometheus:
            logger.info(f"[{analysis_id}] Analyzing metrics anomalies...")
            metric_hypotheses, m_count = await self._analyze_metrics(
                service_name=service_name,
                time_window_minutes=time_window_minutes,
                custom_queries=custom_queries,
                alert_events=alert_events,
            )
            hypotheses.extend(metric_hypotheses)
            metrics_count = m_count
            data_sources.append("prometheus_metrics")
        
        # Step 3: 链路追踪分析
        if self.tempo:
            logger.info(f"[{analysis_id}] Analyzing trace data...")
            trace_hypotheses, t_count = await self._analyze_traces(
                service_name=service_name,
                alert_events=alert_events,
                time_window_minutes=time_window_minutes,
            )
            hypotheses.extend(trace_hypotheses)
            traces_count = t_count
            data_sources.append("tempo_traces")
        
        # Step 4: 关联分析与证据融合
        logger.info(f"[{analysis_id}] Performing correlation analysis...")
        await self._perform_correlation_analysis(
            hypotheses=hypotheses,
            time_window_minutes=time_window_minutes,
        )
        
        # Step 5: 排序和筛选
        hypotheses = sorted(hypotheses, key=lambda h: h.confidence_score, reverse=True)
        
        # 过滤低置信度假设
        threshold = self.rca_config.get("confidence_threshold", 0.7)
        filtered_hypotheses = [h for h in hypotheses if h.confidence_score >= threshold]
        
        if not filtered_hypotheses:
            filtered_hypotheses = hypotheses[:5]  # 至少保留前5个
        
        # Step 6: 生成总结和建议
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        report = RootCauseAnalysisReport(
            analysis_id=analysis_id,
            incident_time=incident_time,
            incident_description=incident_desc,
            analysis_time=end_time,
            analysis_duration_seconds=duration,
            overall_severity=self._determine_overall_severity(filtered_hypotheses),
            root_confidence=filtered_hypotheses[0].confidence_score if filtered_hypotheses else 0,
            hypotheses=filtered_hypotheses,
            data_sources_used=data_sources,
            metrics_analyzed=metrics_count,
            traces_analyzed=traces_count,
            summary=self._generate_summary(filtered_hypotheses),
            recommendations=self._generate_recommendations(filtered_hypotheses),
        )
        
        logger.info(f"[{analysis_id}] Analysis complete. Duration: {duration:.2f}s, Hypotheses: {len(filtered_hypotheses)}")
        
        return report
    
    async def _analyze_metrics(
        self,
        service_name: Optional[str],
        time_window_minutes: int,
        custom_queries: Optional[List[str]],
        alert_events: List[AlertEvent],
    ) -> Tuple[List[RootCauseHypothesis], int]:
        """
        指标分析阶段
        
        检测指标异常并生成初步假设
        """
        hypotheses = []
        queries_to_analyze = []
        
        default_queries = [
            'cpu_usage',
            'memory_usage',
            'disk_usage',
            'error_rate',
            'latency_p99',
        ]
        
        if custom_queries:
            queries_to_analyze.extend(custom_queries)
        else:
            prometheus_queries = self.config.prometheus.default_queries
            for q_key in default_queries:
                if q_key in prometheus_queries:
                    queries_to_analyze.append(prometheus_queries[q_key])
            
            if service_name:
                queries_to_analyze.append(
                    f'sum(rate(http_requests_total{{service="{service_name}"}}[5m]))'
                )
                queries_to_analyze.append(
                    f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m])) by (le))'
                )
        
        analyzed_count = len(queries_to_analyze)
        
        for query in queries_to_analyze:
            try:
                anomaly_result = await self.prometheus.detect_anomalies(
                    query=query,
                    lookback_hours=time_window_minutes / 60,
                    zscore_threshold=2.5,
                )
                
                if anomaly_result.get("anomalies"):
                    hypothesis = self._create_metric_hypothesis(
                        query=query,
                        anomaly_data=anomaly_result,
                    )
                    if hypothesis:
                        hypotheses.append(hypothesis)
                        
            except Exception as e:
                logger.error(f"Error analyzing query {query[:50]}...: {e}")
                continue
        
        # 为告警事件创建假设
        for alert in (alert_events or []):
            hypothesis = self._create_alert_hypothesis(alert)
            if hypothesis:
                hypotheses.append(hypothesis)
        
        return hypotheses, analyzed_count
    
    def _create_metric_hypothesis(
        self,
        query: str,
        anomaly_data: Dict[str, Any],
    ) -> Optional[RootCauseHypothesis]:
        """根据指标异常创建假设"""
        anomalies = anomaly_data.get("anomalies", [])
        if not anomalies:
            return None
        
        latest_anomaly = anomalies[-1]
        value = latest_anomaly.get("value", 0)
        z_score = latest_anomaly.get("z_score", 0)
        
        component = self._infer_component_from_query(query)
        severity = self._determine_severity_from_zscore(z_score)
        
        hypothesis = RootCauseHypothesis(
            hypothesis_id=self._generate_id("h"),
            title=f"{component} 异常检测",
            description=f"检测到 {component} 存在显著异常，当前值 {value:.2f}，Z-Score: {z_score:.2f}",
            affected_component=component,
            severity=severity,
            confidence_score=min(0.9, abs(z_score) / 4),
            related_metrics=[query],
        )
        
        evidence = Evidence(
            evidence_id=self._generate_id("e"),
            evidence_type=EvidenceType.METRIC_ANOMALY,
            source="prometheus",
            description=f"指标异常: Z-Score={z_score:.2f}, Value={value:.2f}",
            confidence=min(1.0, abs(z_score) / 3),
            timestamp=datetime.now(),
            metadata={
                "query": query,
                "z_score": z_score,
                "value": value,
                "anomaly_count": len(anomalies),
            },
        )
        
        hypothesis.add_evidence(evidence)
        hypothesis.remediation_steps = self._get_remediation_for_component(component)
        
        return hypothesis
    
    def _create_alert_hypothesis(self, alert: AlertEvent) -> Optional[RootCauseHypothesis]:
        """根据告警事件创建假设"""
        component = alert.labels.get("component", alert.metric_name)
        
        hypothesis = RootCauseHypothesis(
            hypothesis_id=self._generate_id("h"),
            title=f"告警触发: {alert.rule_name}",
            description=alert.message,
            affected_component=component,
            severity=self._map_alert_severity(alert.severity),
            confidence_score=0.8,
            related_metrics=[alert.metric_name],
        )
        
        evidence = Evidence(
            evidence_id=self._generate_id("e"),
            evidence_type=EvidenceType.THRESHOLD_BREACH,
            source="prometheus_alerts",
            description=f"阈值突破: {alert.metric_name}={alert.current_value:.2f} > {alert.threshold:.2f}",
            confidence=0.85,
            timestamp=alert.timestamp,
            metadata={
                "rule_name": alert.rule_name,
                "current_value": alert.current_value,
                "threshold": alert.threshold,
            },
        )
        
        hypothesis.add_evidence(evidence)
        hypothesis.remediation_steps = self._get_remediation_for_component(component)
        
        return hypothesis
    
    async def _analyze_traces(
        self,
        service_name: Optional[str],
        alert_events: List[AlertEvent],
        time_window_minutes: int,
    ) -> Tuple[List[RootCauseHypothesis], int]:
        """
        链路追踪分析阶段
        
        分析错误调用链和性能问题
        """
        hypotheses = []
        traces_analyzed = 0
        
        try:
            error_search = await self.tempo.search_error_traces(
                service_name=service_name,
                lookback=f"{time_window_minutes}m",
                limit=20,
            )
            
            traces_analyzed += len(error_search.traces)
            
            for trace_info in error_search.traces[:10]:  # 限制分析数量
                try:
                    trace_id = trace_info.get("traceID", "")
                    if not trace_id:
                        continue
                    
                    error_analysis = await self.tempo.analyze_error_propagation(trace_id)
                    
                    if error_analysis.get("potential_root_causes"):
                        rc_spans = error_analysis["potential_root_causes"]
                        
                        for rc_span in rc_spans:
                            hypothesis = RootCauseHypothesis(
                                hypothesis_id=self._generate_id("h"),
                                title=f"链路错误: {rc_span['operation_name']}",
                                description=f"在服务 {rc_span['service_name']} 中检测到根本性错误",
                                affected_component=rc_span["service_name"],
                                severity=AnalysisSeverity.HIGH,
                                confidence_score=0.75,
                                related_traces=[trace_id],
                            )
                            
                            evidence = Evidence(
                                evidence_id=self._generate_id("e"),
                                evidence_type=EvidenceType.TRACE_ERROR,
                                source="tempo",
                                description=f"错误传播起点: {rc_span['operation_name']} in {rc_span['service_name']}",
                                confidence=0.80,
                                timestamp=datetime.now(),
                                metadata={
                                    "trace_id": trace_id,
                                    "span_id": rc_span["span_id"],
                                    "operation": rc_span["operation_name"],
                                    "error_message": rc_span.get("error_message", ""),
                                },
                            )
                            
                            hypothesis.add_evidence(evidence)
                            hypotheses.append(hypothesis)
                            
                except Exception as e:
                    logger.debug(f"Error analyzing trace {trace_id}: {e}")
                    continue
            
            # 慢请求分析
            slow_search = await self.tempo.search_slow_traces(
                min_duration="3s",
                service_name=service_name,
                lookback=f"{time_window_minutes}m",
                limit=10,
            )
            
            traces_analyzed += len(slow_search.traces)
            
            for trace_info in slow_search.traces[:5]:
                try:
                    trace_id = trace_info.get("traceID", "")
                    perf_analysis = await self.tempo.analyze_trace_performance(trace_id)
                    
                    bottlenecks = perf_analysis.get("bottleneck_analysis", [])
                    if bottlenecks:
                        top_bottleneck = bottlenecks[0]
                        
                        hypothesis = RootCauseHypothesis(
                            hypothesis_id=self._generate_id("h"),
                            title=f"性能瓶颈: {top_bottleneck['operation_name']}",
                            description=f"检测到显著性能瓶颈在 {top_bottleneck['service_name']} 的 {top_bottleneck['operation_name']}",
                            affected_component=top_bottleneck["service_name"],
                            severity=AnalysisSeverity.MEDIUM,
                            confidence_score=0.65,
                            related_traces=[trace_id],
                        )
                        
                        evidence = Evidence(
                            evidence_id=self._generate_id("e"),
                            evidence_type=EvidenceType.CORRELATION,
                            source="tempo",
                            description=f"慢操作: {top_bottleneck['duration_ms']:.0f}ms ({top_bottleneck['severity']})",
                            confidence=0.70,
                            timestamp=datetime.now(),
                            metadata=top_bottleneck,
                        )
                        
                        hypothesis.add_evidence(evidence)
                        hypotheses.append(hypothesis)
                        
                except Exception as e:
                    logger.debug(f"Error analyzing slow trace {trace_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in trace analysis: {e}")
        
        return hypotheses, traces_analyzed
    
    async def _perform_correlation_analysis(
        self,
        hypotheses: List[RootCauseHypothesis],
        time_window_minutes: int,
    ):
        """
        关联分析阶段
        
        在不同假设之间寻找时间相关性和依赖关系
        """
        if len(hypotheses) < 2 or not self.prometheus:
            return
        
        components = list(set(h.affected_component for h in hypotheses))
        
        if len(components) < 2:
            return
        
        queries = []
        for comp in components[:5]:  # 限制查询数量
            if comp.lower() in ["cpu", "memory", "disk"]:
                query_key = f"{comp}_usage"
                if query_key in self.config.prometheus.default_queries:
                    queries.append(self.config.prometheus.default_queries[query_key])
        
        if len(queries) < 2:
            return
        
        try:
            correlation_result = await self.prometheus.correlate_metrics(
                queries=queries,
                time_window_minutes=time_window_minutes,
            )
            
            strong_correlations = correlation_result.get("strong_correlations", [])
            
            for corr in strong_correlations:
                coef = corr["correlation_coefficient"]
                
                for hyp in hypotheses:
                    if any(c in hyp.affected_component.lower() for c in ["metric_0", "metric_1"]):
                        evidence = Evidence(
                            evidence_id=self._generate_id("e"),
                            evidence_type=EvidenceType.CORRELATION,
                            source="prometheus_correlation",
                            description=f"与其他指标强相关 (r={coef:.3f})",
                            confidence=min(0.9, abs(coef)),
                            timestamp=datetime.now(),
                            metadata=corr,
                        )
                        hyp.add_evidence(evidence)
                        
        except Exception as e:
            logger.error(f"Error in correlation analysis: {e}")
    
    def _infer_component_from_query(self, query: str) -> str:
        """从 PromQL 推断组件类型"""
        query_lower = query.lower()
        
        if "cpu" in query_lower:
            return "CPU"
        elif "memory" in query_lower or "mem" in query_lower:
            return "Memory"
        elif "disk" in query_lower or "filesystem" in query_lower:
            return "Disk"
        elif "network" in query_lower:
            return "Network"
        elif "http_request" in query_lower or "latency" in query_lower:
            return "Application Latency"
        elif "error" in query_lower:
            return "Error Rate"
        else:
            return "Unknown Component"
    
    def _determine_severity_from_zscore(self, z_score: float) -> AnalysisSeverity:
        """根据 Z-Score 确定严重级别"""
        abs_z = abs(z_score)
        
        if abs_z >= 4:
            return AnalysisSeverity.CRITICAL
        elif abs_z >= 3:
            return AnalysisSeverity.HIGH
        elif abs_z >= 2:
            return AnalysisSeverity.MEDIUM
        else:
            return AnalysisSeverity.LOW
    
    def _map_alert_severity(self, alert_severity) -> AnalysisSeverity:
        """映射告警严重级别"""
        mapping = {
            "emergency": AnalysisSeverity.CRITICAL,
            "critical": AnalysisSeverity.CRITICAL,
            "warning": AnalysisSeverity.MEDIUM,
            "info": AnalysisSeverity.LOW,
        }
        severity_str = alert_severity.value if hasattr(alert_severity, 'value') else str(alert_severity)
        return mapping.get(severity_str.lower(), AnalysisSeverity.LOW)
    
    def _get_remediation_for_component(self, component: str) -> List[str]:
        """获取组件修复建议"""
        remediations = {
            "CPU": [
                "检查是否有 CPU 密集型进程",
                "考虑优化算法或增加计算资源",
                "查看是否存在死循环或无限递归",
            ],
            "Memory": [
                "检查内存泄漏情况",
                "审查大对象分配和缓存策略",
                "考虑增加内存或优化内存使用",
            ],
            "Disk": [
                "清理不必要的文件和日志",
                "检查磁盘 I/O 瓶颈",
                "扩展存储容量",
            ],
            "Application Latency": [
                "分析慢 SQL 查询",
                "检查外部 API 调用延迟",
                "审查代码中的阻塞操作",
            ],
            "Error Rate": [
                "检查最近部署变更",
                "审查应用日志获取详细错误信息",
                "验证外部依赖可用性",
            ],
        }
        
        return remediations.get(component, ["需要进一步人工调查"])
    
    def _determine_overall_severity(
        self, 
        hypotheses: List[RootCauseHypothesis]
    ) -> AnalysisSeverity:
        """确定整体严重级别"""
        if not hypotheses:
            return AnalysisSeverity.INFO
        
        severities = [h.severity for h in hypotheses]
        
        if AnalysisSeverity.CRITICAL in severities:
            return AnalysisSeverity.CRITICAL
        elif AnalysisSeverity.HIGH in severities:
            return AnalysisSeverity.HIGH
        elif AnalysisSeverity.MEDIUM in severities:
            return AnalysisSeverity.MEDIUM
        else:
            return AnalysisSeverity.LOW
    
    def _generate_summary(
        self, 
        hypotheses: List[RootCauseHypothesis]
    ) -> str:
        """生成分析摘要"""
        if not hypotheses:
            return "未发现明确的根因假设，建议进一步监控和调查。"
        
        top = hypotheses[0]
        
        parts = [
            f"分析发现 {len(hypotheses)} 个潜在根因假设。",
            f"最可能的原因是: {top.title} (置信度: {top.confidence_score*100:.1f}%)。",
            f"受影响的组件: {top.affected_component}。",
        ]
        
        critical_count = sum(1 for h in hypotheses if h.severity == AnalysisSeverity.CRITICAL)
        if critical_count > 0:
            parts.append(f"其中包含 {critical_count} 个严重级别的问题。")
        
        return " ".join(parts)
    
    def _generate_recommendations(
        self, 
        hypotheses: List[RootCauseHypothesis]
    ) -> List[str]:
        """生成总体建议"""
        if not hypotheses:
            return ["继续监控系统指标，等待更多数据"]
        
        recommendations = []
        seen_components = set()
        
        for hyp in hypotheses[:3]:
            if hyp.affected_component not in seen_components:
                seen_components.add(hyp.affected_component)
                recommendations.extend(hyp.remediation_steps[:2])
        
        recommendations.extend([
            "查看详细的根因分析报告以获取更多信息",
            "如果问题持续存在，建议联系相关团队进行深入调查",
        ])
        
        return recommendations[:8]


async def create_root_cause_analyzer(
    config: Optional[ObservabilityConfig] = None,
) -> RootCauseAnalyzer:
    """
    工厂函数：创建根因分析器实例
    
    Args:
        config: 可观测性配置
        
    Returns:
        已配置的根因分析器
    """
    analyzer = RootCauseAnalyzer(config=config)
    return analyzer
