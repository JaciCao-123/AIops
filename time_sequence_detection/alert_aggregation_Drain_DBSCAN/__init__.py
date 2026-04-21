#!/usr/bin/env python3
"""
AlertClusterSkill - 告警聚合技能模块

基于 Drain + TF-IDF + Word2Vec + DBSCAN 的智能告警聚合系统

使用示例:
    from alert_aggregation_Drain_DBSCAN import AlertClusterSkill
    
    # 离线训练
    skill = AlertClusterSkill()
    await skill.train_from_texts(logs, "model.word2vec")
    
    # 在线聚合
    result = await skill.execute(alerts)
"""
from .config import (
    IT_STOPWORDS,
    MIN_WORD_LENGTH,
    Word2VecConfig,
    DistanceWeights,
    DBSCANConfig,
    DrainConfig,
    DEFAULT_W2V_MODEL_PATH,
)
from .models import (
    AlertInput,
    ClusterInfo,
    AggregationResult,
    ParsedAlert,
    TrainingConfig,
)
from .text_preprocessor import (
    tokenize_it_text,
    preprocess_for_drain,
    batch_tokenize,
)
from .w2v_trainer import (
    Word2VecTrainer,
    train_and_save_model,
)
from .core_engine import (
    AlertClusterEngine,
    create_engine,
)
from .skill import (
    AlertClusterSkill,
    create_skill,
)

__all__ = [
    "IT_STOPWORDS",
    "MIN_WORD_LENGTH",
    "Word2VecConfig",
    "DistanceWeights",
    "DBSCANConfig",
    "DrainConfig",
    "DEFAULT_W2V_MODEL_PATH",
    "AlertInput",
    "ClusterInfo",
    "AggregationResult",
    "ParsedAlert",
    "TrainingConfig",
    "tokenize_it_text",
    "preprocess_for_drain",
    "batch_tokenize",
    "Word2VecTrainer",
    "train_and_save_model",
    "AlertClusterEngine",
    "create_engine",
    "AlertClusterSkill",
    "create_skill",
]

__version__ = "1.0.0"
