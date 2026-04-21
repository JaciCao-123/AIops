#!/usr/bin/env python3
"""
AlertClusterSkill 技能封装
提供对外的异步接口，可集成到 Multi-Agent 架构中
"""
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Union

from config import DEFAULT_W2V_MODEL_PATH
from core_engine import AlertClusterEngine, create_engine
from models import AlertInput, AggregationResult
from w2v_trainer import Word2VecTrainer, train_and_save_model

logger = logging.getLogger(__name__)


class AlertClusterSkill:
    """
    告警聚合技能
    
    提供两个核心能力：
    1. 离线训练：从历史日志训练Word2Vec模型
    2. 在线聚合：实时告警聚类压缩
    
    使用示例：
        # 离线训练
        skill = AlertClusterSkill()
        await skill.train_model("logs.txt", "model.word2vec")
        
        # 在线聚合
        skill = AlertClusterSkill(w2v_model_path="model.word2vec")
        result = await skill.execute(alerts)
    """
    
    def __init__(
        self,
        w2v_model_path: Optional[str] = None,
        auto_load: bool = True,
        **engine_kwargs,
    ):
        """
        初始化技能
        
        Args:
            w2v_model_path: Word2Vec模型路径
            auto_load: 是否自动加载模型
            **engine_kwargs: 传递给引擎的额外参数
        """
        self.w2v_model_path = w2v_model_path or str(DEFAULT_W2V_MODEL_PATH)
        self._engine: Optional[AlertClusterEngine] = None
        self._engine_kwargs = engine_kwargs
        self._is_trained = False
        
        if auto_load and Path(self.w2v_model_path).exists():
            self._load_engine()
    
    def _load_engine(self) -> None:
        """
        加载聚合引擎
        """
        if self._engine is None:
            self._engine = create_engine(
                w2v_model_path=self.w2v_model_path,
                **self._engine_kwargs,
            )
            self._is_trained = True
            logger.info("AlertClusterSkill 引擎加载完成")
    
    async def train_model(
        self,
        raw_log_file_path: str,
        output_model_path: Optional[str] = None,
        **training_kwargs,
    ) -> bool:
        """
        离线训练Word2Vec模型
        
        Args:
            raw_log_file_path: 原始日志文件路径
            output_model_path: 输出模型路径（默认使用初始化时的路径）
            **training_kwargs: 训练参数
        
        Returns:
            训练是否成功
        """
        try:
            model_path = output_model_path or self.w2v_model_path
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                train_and_save_model,
                raw_log_file_path,
                model_path,
            )
            
            self.w2v_model_path = model_path
            self._load_engine()
            
            logger.info(f"模型训练完成: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            return False
    
    async def train_from_texts(
        self,
        texts: List[str],
        output_model_path: Optional[str] = None,
        **training_kwargs,
    ) -> bool:
        """
        从文本列表训练Word2Vec模型
        
        Args:
            texts: 文本列表
            output_model_path: 输出模型路径
            **training_kwargs: 训练参数
        
        Returns:
            训练是否成功
        """
        try:
            model_path = output_model_path or self.w2v_model_path
            
            trainer = Word2VecTrainer(**training_kwargs)
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                trainer.train_from_texts,
                texts,
                model_path,
            )
            
            self.w2v_model_path = model_path
            self._load_engine()
            
            logger.info(f"模型训练完成: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"模型训练失败: {e}")
            return False
    
    async def execute(
        self,
        alerts: Union[List[AlertInput], List[dict]],
    ) -> AggregationResult:
        """
        执行告警聚合
        
        Args:
            alerts: 告警列表，可以是 AlertInput 对象或字典
        
        Returns:
            聚合结果
        """
        if not self._is_trained or self._engine is None:
            self._load_engine()
        
        normalized_alerts = []
        for alert in alerts:
            if isinstance(alert, AlertInput):
                normalized_alerts.append(alert)
            elif isinstance(alert, dict):
                normalized_alerts.append(AlertInput(**alert))
            else:
                logger.warning(f"忽略无效告警类型: {type(alert)}")
        
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            self._engine.cluster_alerts,
            normalized_alerts,
        )
        
        return result
    
    async def cluster(
        self,
        alerts: Union[List[AlertInput], List[dict]],
    ) -> dict:
        """
        执行告警聚合并返回字典格式结果
        
        Args:
            alerts: 告警列表
        
        Returns:
            聚合结果的字典表示
        """
        result = await self.execute(alerts)
        return result.model_dump()
    
    @property
    def is_ready(self) -> bool:
        """
        检查技能是否就绪
        """
        return self._is_trained and self._engine is not None
    
    def __repr__(self) -> str:
        status = "ready" if self.is_ready else "not_ready"
        return f"AlertClusterSkill(status={status}, model={self.w2v_model_path})"


async def create_skill(
    w2v_model_path: Optional[str] = None,
    **kwargs,
) -> AlertClusterSkill:
    """
    工厂函数：创建并初始化技能
    """
    skill = AlertClusterSkill(w2v_model_path=w2v_model_path, **kwargs)
    return skill
