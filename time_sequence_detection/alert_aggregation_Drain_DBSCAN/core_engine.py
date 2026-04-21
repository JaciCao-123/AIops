#!/usr/bin/env python3
"""
在线告警聚合引擎
实现 Drain + TF-IDF + Word2Vec + DBSCAN 的完整聚合流水线
"""
import logging
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from gensim.models import Word2Vec
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from config import (
    DistanceWeights, DBSCANConfig, DrainConfig,
    DEFAULT_W2V_MODEL_PATH, DEFAULT_DRAIN_MODEL_PATH, DEFAULT_TFIDF_MODEL_PATH,
    MODELS_DIR,
)
from models import AlertInput, AggregationResult, ClusterInfo, ParsedAlert
from text_preprocessor import tokenize_it_text, preprocess_for_drain

logger = logging.getLogger(__name__)

DRAIN_AVAILABLE = False
try:
    from logparser.Drain import LogParser
    DRAIN_AVAILABLE = True
except ImportError:
    logger.debug("logparser.Drain 不可用，使用简化模板提取")


class SimpleDrainParser:
    """
    简化的模板提取器
    当 logparser.Drain 不可用时使用
    """
    
    def __init__(self):
        self._templates = {}
    
    def parse(self, text: str) -> str:
        """
        提取日志模板
        将动态变量替换为占位符
        """
        template = preprocess_for_drain(text)
        return template


class AlertClusterEngine:
    """
    告警聚合引擎
    
    实现完整的在线聚合流程：
    1. Drain模板提取
    2. TF-IDF加权的Word2Vec向量化
    3. 多维异构距离矩阵计算
    4. DBSCAN聚类
    """
    
    def __init__(
        self,
        w2v_model_path: Optional[str] = None,
        drain_model_dir: Optional[str] = None,
        w_time: float = DistanceWeights.W_TIME,
        w_sem: float = DistanceWeights.W_SEM,
        w_topo: float = DistanceWeights.W_TOPO,
        eps: float = DBSCANConfig.eps,
        min_samples: int = DBSCANConfig.min_samples,
    ):
        self.w2v_model_path = w2v_model_path or str(DEFAULT_W2V_MODEL_PATH)
        self.drain_model_dir = drain_model_dir or str(MODELS_DIR / "drain")
        self.w_time = w_time
        self.w_sem = w_sem
        self.w_topo = w_topo
        self.eps = eps
        self.min_samples = min_samples
        
        self._w2v_model: Optional[Word2Vec] = None
        self._drain_parser: Optional[LogParser] = None
        self._tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self._vector_size: int = 100
    
    def load_models(self) -> None:
        """
        加载所有必要的模型
        """
        self._load_w2v_model()
        self._init_drain_parser()
        logger.info("所有模型加载完成")
    
    def _load_w2v_model(self) -> None:
        """
        加载Word2Vec模型
        """
        path = Path(self.w2v_model_path)
        if not path.exists():
            raise FileNotFoundError(f"Word2Vec模型不存在: {self.w2v_model_path}")
        
        self._w2v_model = Word2Vec.load(str(path))
        self._vector_size = self._w2v_model.wv.vector_size
        logger.info(f"Word2Vec模型已加载，词表大小: {len(self._w2v_model.wv)}")
    
    def _init_drain_parser(self) -> None:
        """
        初始化Drain解析器
        """
        if DRAIN_AVAILABLE:
            try:
                drain_dir = Path(self.drain_model_dir)
                drain_dir.mkdir(parents=True, exist_ok=True)
                
                self._drain_parser = LogParser(
                    log_format="",
                    indir=str(drain_dir),
                    outdir=str(drain_dir),
                    depth=DrainConfig.depth,
                    st=DrainConfig.sim_th,
                )
                logger.info("Drain解析器初始化完成")
                return
            except Exception as e:
                logger.warning(f"Drain解析器初始化失败: {e}，使用简化模板提取")
        
        self._drain_parser = SimpleDrainParser()
        logger.info("使用简化模板提取器")
    
    def _parse_with_drain(self, text: str) -> str:
        """
        使用Drain提取模板
        """
        preprocessed = preprocess_for_drain(text)
        
        if self._drain_parser is None:
            return preprocessed
        
        try:
            if isinstance(self._drain_parser, SimpleDrainParser):
                return self._drain_parser.parse(text)
            
            log_entry = {'LineId': 1, 'Content': preprocessed}
            result = self._drain_parser.parse([log_entry])
            if result is not None and len(result) > 0:
                return result[0].get('EventTemplate', preprocessed)
        except Exception as e:
            logger.debug(f"模板解析失败: {e}")
        
        return preprocessed
    
    def _compute_tfidf_weighted_vector(
        self,
        tokens: List[str],
        tfidf_weights: Optional[dict] = None,
    ) -> np.ndarray:
        """
        计算TF-IDF加权的Word2Vec向量
        
        公式：V_alert = Σ (TF-IDF权重 * Word2Vec词向量)，最后L2归一化
        """
        if not tokens or self._w2v_model is None:
            return np.zeros(self._vector_size)
        
        vector = np.zeros(self._vector_size)
        total_weight = 0.0
        
        for token in tokens:
            if token in self._w2v_model.wv:
                weight = 1.0
                if tfidf_weights and token in tfidf_weights:
                    weight = tfidf_weights[token]
                
                vector += weight * self._w2v_model.wv[token]
                total_weight += weight
        
        if total_weight > 0:
            vector = vector / total_weight
        
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    def _compute_simple_vector(self, tokens: List[str]) -> np.ndarray:
        """
        计算简单平均向量（无TF-IDF加权）
        """
        if not tokens or self._w2v_model is None:
            return np.zeros(self._vector_size)
        
        vectors = []
        for token in tokens:
            if token in self._w2v_model.wv:
                vectors.append(self._w2v_model.wv[token])
        
        if not vectors:
            return np.zeros(self._vector_size)
        
        vector = np.mean(vectors, axis=0)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    def _compute_distance_matrix(
        self,
        parsed_alerts: List[ParsedAlert],
    ) -> np.ndarray:
        """
        计算多维异构距离矩阵
        
        公式：Distance(i, j) = W_TIME * D_time + W_SEM * D_sem + W_TOPO * D_topo
        """
        n = len(parsed_alerts)
        if n == 0:
            return np.array([])
        
        times = np.array([a.original.get_datetime().timestamp() for a in parsed_alerts])
        nodes = [a.original.node_id for a in parsed_alerts]
        vectors = np.array([a.vector for a in parsed_alerts])
        
        time_diff = np.abs(times[:, np.newaxis] - times[np.newaxis, :])
        d_time = time_diff / (time_diff.max() + 1e-10)
        
        norm_vectors = normalize(vectors, norm='l2', axis=1)
        cosine_sim = np.dot(norm_vectors, norm_vectors.T)
        d_sem = 1 - cosine_sim
        d_sem = np.clip(d_sem, 0, 2)
        
        d_topo = np.array([[0.0 if nodes[i] == nodes[j] else 1.0 for j in range(n)] for i in range(n)])
        
        distance_matrix = (
            self.w_time * d_time +
            self.w_sem * d_sem +
            self.w_topo * d_topo
        )
        
        distance_matrix = np.maximum(distance_matrix, 0)
        
        return distance_matrix
    
    def _dbscan_cluster(
        self,
        distance_matrix: np.ndarray,
    ) -> np.ndarray:
        """
        使用预计算距离矩阵进行DBSCAN聚类
        """
        if distance_matrix.size == 0:
            return np.array([])
        
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric='precomputed',
        )
        
        labels = clustering.fit_predict(distance_matrix)
        return labels
    
    def parse_alerts(self, alerts: List[AlertInput]) -> List[ParsedAlert]:
        """
        解析告警列表，提取模板和向量
        """
        parsed_alerts = []
        
        for alert in alerts:
            template = self._parse_with_drain(alert.raw_msg)
            tokens = tokenize_it_text(template)
            vector = self._compute_simple_vector(tokens)
            
            parsed = ParsedAlert(
                original=alert,
                template=template,
                tokens=tokens,
                vector=vector.tolist() if isinstance(vector, np.ndarray) else vector,
            )
            parsed_alerts.append(parsed)
        
        return parsed_alerts
    
    def cluster_alerts(
        self,
        alerts: List[AlertInput],
    ) -> AggregationResult:
        """
        对告警列表进行聚类聚合
        
        Args:
            alerts: 告警输入列表
        
        Returns:
            聚合结果
        """
        if not alerts:
            return AggregationResult(total_input=0, noise_count=0, clusters=[])
        
        parsed_alerts = self.parse_alerts(alerts)
        
        distance_matrix = self._compute_distance_matrix(parsed_alerts)
        
        labels = self._dbscan_cluster(distance_matrix)
        
        noise_count = int(np.sum(labels == -1))
        
        unique_labels = set(labels) - {-1}
        clusters = []
        
        for label in sorted(unique_labels):
            indices = np.where(labels == label)[0]
            cluster_alerts = [alerts[i] for i in indices]
            cluster_parsed = [parsed_alerts[i] for i in indices]
            
            vectors = np.array([np.array(p.vector) for p in cluster_parsed])
            norms = np.linalg.norm(vectors, axis=1)
            center_idx = np.argmin(np.sum(distance_matrix[np.ix_(indices, indices)], axis=1))
            
            representative = cluster_alerts[center_idx].raw_msg
            affected_nodes = list(set(a.node_id for a in cluster_alerts))
            
            cluster_info = ClusterInfo(
                cluster_id=int(label),
                alert_count=len(cluster_alerts),
                representative_alert=representative,
                affected_nodes=affected_nodes,
                alerts=cluster_alerts,
            )
            clusters.append(cluster_info)
        
        clusters.sort(key=lambda x: x.alert_count, reverse=True)
        
        return AggregationResult(
            total_input=len(alerts),
            noise_count=noise_count,
            clusters=clusters,
        )


def create_engine(
    w2v_model_path: Optional[str] = None,
    **kwargs,
) -> AlertClusterEngine:
    """
    工厂函数：创建并初始化告警聚合引擎
    """
    engine = AlertClusterEngine(w2v_model_path=w2v_model_path, **kwargs)
    engine.load_models()
    return engine
