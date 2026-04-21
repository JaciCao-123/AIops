#!/usr/bin/env python3
"""
AlertClusterSkill 配置模块
包含所有超参数、权重、停用词表和模型路径配置
"""
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

IT_STOPWORDS: List[str] = [
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "log", "logs", "info", "warn", "error", "debug", "trace", "level",
    "thread", "threads", "class", "method", "line", "file", "null",
    "true", "false", "none", "nullpointerexception", "exception", "throwable",
]

MIN_WORD_LENGTH: int = 2

class Word2VecConfig:
    vector_size: int = 100
    window: int = 5
    min_count: int = 5
    workers: int = 4
    epochs: int = 20
    sg: int = 0

class DistanceWeights:
    W_TIME: float = 0.05
    W_SEM: float = 1.0
    W_TOPO: float = 0.2

class DBSCANConfig:
    eps: float = 0.5
    min_samples: int = 2
    metric: str = "precomputed"

class DrainConfig:
    depth: int = 4
    sim_th: float = 0.4

DEFAULT_W2V_MODEL_PATH = MODELS_DIR / "it_word2vec.model"
DEFAULT_DRAIN_MODEL_PATH = MODELS_DIR / "drain_model.bin"
DEFAULT_TFIDF_MODEL_PATH = MODELS_DIR / "tfidf_vectorizer.pkl"

RAW_LOGS_PATH = DATA_DIR / "raw_logs.txt"
TRAINING_CORPUS_PATH = DATA_DIR / "training_corpus.txt"
