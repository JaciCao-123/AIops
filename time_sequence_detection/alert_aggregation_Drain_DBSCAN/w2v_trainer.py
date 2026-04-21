#!/usr/bin/env python3
"""
Word2Vec 训练模块
从历史IT日志/告警中生成高质量语料库，训练专用的Word2Vec模型
"""
import logging
from pathlib import Path
from typing import List, Optional

from gensim.models import Word2Vec
from gensim.models.word2vec import LineSentence

from config import Word2VecConfig, DEFAULT_W2V_MODEL_PATH, TRAINING_CORPUS_PATH
from text_preprocessor import tokenize_it_text

logger = logging.getLogger(__name__)


class Word2VecTrainer:
    """
    Word2Vec训练器
    
    负责从原始日志文件构建语料库并训练Word2Vec模型
    """
    
    def __init__(
        self,
        vector_size: int = Word2VecConfig.vector_size,
        window: int = Word2VecConfig.window,
        min_count: int = Word2VecConfig.min_count,
        workers: int = Word2VecConfig.workers,
        epochs: int = Word2VecConfig.epochs,
        sg: int = Word2VecConfig.sg,
    ):
        self.vector_size = vector_size
        self.window = window
        self.min_count = min_count
        self.workers = workers
        self.epochs = epochs
        self.sg = sg
        self._model: Optional[Word2Vec] = None
    
    def build_corpus_from_file(
        self,
        raw_log_file_path: str,
        output_corpus_path: Optional[str] = None,
    ) -> int:
        """
        从原始日志文件构建分词语料库
        
        Args:
            raw_log_file_path: 原始日志文件路径
            output_corpus_path: 语料库输出路径（可选）
        
        Returns:
            处理的日志行数
        """
        raw_path = Path(raw_log_file_path)
        if not raw_path.exists():
            raise FileNotFoundError(f"原始日志文件不存在: {raw_log_file_path}")
        
        corpus_path = Path(output_corpus_path) if output_corpus_path else TRAINING_CORPUS_PATH
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        
        line_count = 0
        with open(raw_path, 'r', encoding='utf-8', errors='ignore') as f_in, \
             open(corpus_path, 'w', encoding='utf-8') as f_out:
            
            for line in f_in:
                line = line.strip()
                if not line:
                    continue
                
                tokens = tokenize_it_text(line)
                if tokens:
                    f_out.write(' '.join(tokens) + '\n')
                    line_count += 1
        
        logger.info(f"语料库构建完成: {line_count} 行 -> {corpus_path}")
        return line_count
    
    def build_corpus_from_texts(
        self,
        texts: List[str],
        output_corpus_path: Optional[str] = None,
    ) -> int:
        """
        从文本列表构建分词语料库
        
        Args:
            texts: 文本列表
            output_corpus_path: 语料库输出路径（可选）
        
        Returns:
            处理的文本数量
        """
        corpus_path = Path(output_corpus_path) if output_corpus_path else TRAINING_CORPUS_PATH
        corpus_path.parent.mkdir(parents=True, exist_ok=True)
        
        line_count = 0
        with open(corpus_path, 'w', encoding='utf-8') as f_out:
            for text in texts:
                tokens = tokenize_it_text(text)
                if tokens:
                    f_out.write(' '.join(tokens) + '\n')
                    line_count += 1
        
        logger.info(f"语料库构建完成: {line_count} 行 -> {corpus_path}")
        return line_count
    
    def train_from_corpus(
        self,
        corpus_path: str,
        output_model_path: Optional[str] = None,
    ) -> Word2Vec:
        """
        从语料库文件训练Word2Vec模型
        
        Args:
            corpus_path: 语料库文件路径
            output_model_path: 模型输出路径（可选）
        
        Returns:
            训练好的Word2Vec模型
        """
        corpus_path = Path(corpus_path)
        if not corpus_path.exists():
            raise FileNotFoundError(f"语料库文件不存在: {corpus_path}")
        
        logger.info(f"开始训练Word2Vec模型...")
        logger.info(f"  vector_size={self.vector_size}, window={self.window}")
        logger.info(f"  min_count={self.min_count}, epochs={self.epochs}")
        
        sentences = LineSentence(str(corpus_path))
        
        self._model = Word2Vec(
            sentences=sentences,
            vector_size=self.vector_size,
            window=self.window,
            min_count=self.min_count,
            workers=self.workers,
            epochs=self.epochs,
            sg=self.sg,
        )
        
        vocab_size = len(self._model.wv)
        logger.info(f"训练完成，词表大小: {vocab_size}")
        
        if output_model_path:
            self.save_model(output_model_path)
        
        return self._model
    
    def train_from_texts(
        self,
        texts: List[str],
        output_model_path: Optional[str] = None,
    ) -> Word2Vec:
        """
        从文本列表直接训练Word2Vec模型（不保存中间语料库）
        
        Args:
            texts: 文本列表
            output_model_path: 模型输出路径（可选）
        
        Returns:
            训练好的Word2Vec模型
        """
        logger.info(f"开始训练Word2Vec模型...")
        logger.info(f"  文本数量: {len(texts)}")
        
        sentences = [tokenize_it_text(text) for text in texts]
        sentences = [s for s in sentences if s]
        
        self._model = Word2Vec(
            sentences=sentences,
            vector_size=self.vector_size,
            window=self.window,
            min_count=self.min_count,
            workers=self.workers,
            epochs=self.epochs,
            sg=self.sg,
        )
        
        vocab_size = len(self._model.wv)
        logger.info(f"训练完成，词表大小: {vocab_size}")
        
        if output_model_path:
            self.save_model(output_model_path)
        
        return self._model
    
    def save_model(self, model_path: str) -> None:
        """
        保存训练好的模型
        """
        if self._model is None:
            raise ValueError("模型未训练，无法保存")
        
        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        logger.info(f"模型已保存: {path}")
    
    @staticmethod
    def load_model(model_path: str) -> Word2Vec:
        """
        加载已训练的模型
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        model = Word2Vec.load(str(path))
        logger.info(f"模型已加载: {path}, 词表大小: {len(model.wv)}")
        return model


def train_and_save_model(
    raw_log_file_path: str,
    output_model_path: str,
    vector_size: int = Word2VecConfig.vector_size,
    window: int = Word2VecConfig.window,
    min_count: int = Word2VecConfig.min_count,
    workers: int = Word2VecConfig.workers,
    epochs: int = Word2VecConfig.epochs,
) -> Word2Vec:
    """
    便捷函数：从原始日志文件训练并保存Word2Vec模型
    
    Args:
        raw_log_file_path: 原始日志文件路径
        output_model_path: 输出模型路径
        vector_size: 词向量维度
        window: 上下文窗口大小
        min_count: 最小词频阈值
        workers: 并行工作进程数
        epochs: 训练轮数
    
    Returns:
        训练好的Word2Vec模型
    """
    trainer = Word2VecTrainer(
        vector_size=vector_size,
        window=window,
        min_count=min_count,
        workers=workers,
        epochs=epochs,
    )
    
    corpus_path = str(Path(output_model_path).with_suffix('.corpus'))
    trainer.build_corpus_from_file(raw_log_file_path, corpus_path)
    model = trainer.train_from_corpus(corpus_path, output_model_path)
    
    return model
