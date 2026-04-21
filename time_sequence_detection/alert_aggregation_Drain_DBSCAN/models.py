#!/usr/bin/env python3
"""
AlertClusterSkill 数据模型定义
使用 Pydantic 定义输入输出的数据结构
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AlertInput(BaseModel):
    time: str = Field(..., description="告警时间，格式: YYYY-MM-DD HH:MM:SS")
    node_id: str = Field(..., description="告警来源节点ID")
    raw_msg: str = Field(..., description="原始告警消息")

    def get_datetime(self) -> datetime:
        return datetime.strptime(self.time, "%Y-%m-%d %H:%M:%S")


class ClusterInfo(BaseModel):
    cluster_id: int = Field(..., description="聚类ID")
    alert_count: int = Field(..., description="该聚类包含的告警数量")
    representative_alert: str = Field(..., description="代表性告警消息")
    affected_nodes: List[str] = Field(..., description="受影响的节点列表")
    alerts: Optional[List[AlertInput]] = Field(default=None, description="聚类中的所有告警")


class AggregationResult(BaseModel):
    total_input: int = Field(..., description="输入告警总数")
    noise_count: int = Field(..., description="噪声告警数量")
    clusters: List[ClusterInfo] = Field(..., description="聚类结果列表")

    class Config:
        json_schema_extra = {
            "example": {
                "total_input": 2,
                "noise_count": 0,
                "clusters": [
                    {
                        "cluster_id": 0,
                        "alert_count": 2,
                        "representative_alert": "Connection to Redis 10.0.0.1 timeout",
                        "affected_nodes": ["node-1"]
                    }
                ]
            }
        }


class ParsedAlert(BaseModel):
    original: AlertInput
    template: str = Field(..., description="Drain提取的模板字符串")
    tokens: List[str] = Field(..., description="分词后的词列表")
    vector: Optional[List[float]] = Field(default=None, description="TF-IDF加权Word2Vec向量")


class TrainingConfig(BaseModel):
    raw_log_file_path: str = Field(..., description="原始日志文件路径")
    output_model_path: str = Field(..., description="输出模型路径")
    vector_size: int = Field(default=100, description="词向量维度")
    window: int = Field(default=5, description="上下文窗口大小")
    min_count: int = Field(default=5, description="最小词频阈值")
    workers: int = Field(default=4, description="并行工作进程数")
    epochs: int = Field(default=20, description="训练轮数")
