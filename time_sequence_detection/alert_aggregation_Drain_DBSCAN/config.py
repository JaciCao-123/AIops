#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drain + DBSCAN 运维日志告警聚合系统 - 全局配置

基于 Drain 日志解析 + DBSCAN 密度聚类的智能告警收敛方案
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()

DATA_DIRS = {
    "raw": BASE_DIR / "data" / "raw",
    "parsed": BASE_DIR / "data" / "parsed",
    "features": BASE_DIR / "data" / "features",
    "clusters": BASE_DIR / "data" / "clusters",
    "reports": BASE_DIR / "data" / "reports"
}

for dir_path in DATA_DIRS.values():
    dir_path.mkdir(parents=True, exist_ok=True)

LOG_GENERATOR_CONFIG = {
    "num_logs": 5000,
    "time_range_hours": 2,
    
    "log_sources": {
        "application": {"weight": 0.40},
        "system": {"weight": 0.25},
        "middleware": {"weight": 0.20},
        "database": {"weight": 0.15}
    },
    
    "log_levels": {
        "ERROR": {"weight": 0.10, "color": "\033[91m"},
        "WARN": {"weight": 0.20, "color": "\033[93m"},
        "INFO": {"weight": 0.50, "color": "\033[92m"},
        "DEBUG": {"weight": 0.20, "color": "\033[94m"}
    },
    
    "services": [
        "order-service", "payment-service", "user-service",
        "inventory-service", "notification-service", "api-gateway",
        "mysql-master", "mysql-slave", "redis-cluster",
        "kafka-cluster", "elasticsearch-cluster"
    ],
    
    "anomaly_patterns": [
        "connection_timeout",
        "high_cpu_usage",
        "memory_leak",
        "disk_space_full",
        "database_connection_exhausted",
        "service_unavailable",
        "authentication_failure",
        "ssl_certificate_error"
    ],
    
    "anomaly_injection_rate": 0.15,
    
    "output_file": DATA_DIRS["raw"] / "raw_logs.csv"
}

DRAIN_CONFIG = {
    "depth": 4,
    "st": 0.5,
    "max_children": 100,
    "max_clusters": 50,
    
    "sim_threshold": 0.4,
    
    "regex": [
        r'(?P<ip>\d+\.\d+\.\d+\.\d+)',
        r'(?P<port>\d+)',
        r'(?P<id>[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})',
        r'(?P<user>\w+(?:@\w+)?)',
        r"(?P<path>\/[\w\/\.-]+)",
        r'(?P<number>\d+\.?\d*)',
        r'(?P<duration>\d+ms|\d+s|\d+m)',
        r'(?P<size>\d+[KBMG]?)',
        r"(?P<date>\d{4}[-/]\d{2}[-/]\d{2})",
        r'(?P<time>\d{2}:\d{2}:\d{2})',
        r'(?P<timestamp>\d{13})',
        r"(?P<url>https?://[\w\./:\?=&\-]+)"
    ]
}

FEATURE_BUILDER_CONFIG = {
    "feature_types": {
        "template_id_embedding": True,
        "log_level_encoding": True,
        "time_features": True,
        "statistical_features": True,
        "tfidf_vectorization": True
    },
    
    "tfidf_params": {
        "max_features": 1000,
        "min_df": 2,
        "max_df": 0.95,
        "ngram_range": (1, 2)
    },
    
    "time_window_seconds": 300,
    
    "normalization": "standard",
    
    "output_file": DATA_DIRS["features"] / "log_features.npz"
}

DBSCAN_CONFIG = {
    "eps": 0.5,
    "min_samples": 5,
    
    "metric": "euclidean",
    
    "algorithm": "auto",
    
    "n_jobs": -1,
    
    "noise_handling": "separate_cluster",
    
    "cluster_label_prefix": "CLUSTER_",
    
    "output_files": {
        "cluster_labels": DATA_DIRS["clusters"] / "cluster_labels.json",
        "cluster_centers": DATA_DIRS["clusters"] / "cluster_centers.json",
        "cluster_stats": DATA_DIRS["clusters"] / "cluster_statistics.json"
    }
}

ALERT_CONVERGENCE_CONFIG = {
    "severity_weights": {
        "ERROR": 1.0,
        "WARN": 0.6,
        "INFO": 0.2,
        "DEBUG": 0.1
    },
    
    "impact_factors": {
        "cluster_size_weight": 0.3,
        "error_rate_weight": 0.4,
        "frequency_weight": 0.3
    },
    
    "report_format": "markdown",
    
    "top_n_clusters": 10,
    
    "include_noise_analysis": True,
    
    "output_file": DATA_DIRS["reports"] / "alert_convergence_report.md"
}

PIPELINE_CONFIG = {
    "steps": ["generate_logs", "drain_parse", "build_features", "dbscan_cluster", "alert_convergence"],
    
    "save_intermediate_results": True,
    
    "random_seed": 42,
    
    "verbose": True,
    
    "parallel_processing": False
}


def get_config_summary():
    """获取配置摘要"""
    return {
        "base_dir": str(BASE_DIR),
        "log_count": LOG_GENERATOR_CONFIG["num_logs"],
        "drain_depth": DRAIN_CONFIG["depth"],
        "dbscan_eps": DBSCAN_CONFIG["eps"],
        "dbscan_min_samples": DBSCAN_CONFIG["min_samples"]
    }


if __name__ == "__main__":
    print("=" * 60)
    print("📋 Drain + DBSCAN 告警聚合系统配置")
    print("=" * 60)
    
    summary = get_config_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    print("\n📁 数据目录:")
    for name, path in DATA_DIRS.items():
        print(f"   {name}: {path}")
