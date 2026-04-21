#!/usr/bin/env python3
"""
LogAnalysisSkill - 日志分析技能封装

基于已有的 DeepLog 模型进行日志异常检测（仅推理，不训练）

使用方式：
    from skill import LogAnalysisSkill
    
    skill = LogAnalysisSkill()
    
    # 方式1: 检测已解析的结构化日志
    result = await skill.detect_from_file()
    
    # 方式2: 实时检测原始日志
    result = await skill.detect_logs(raw_logs)
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import deque
from dataclasses import dataclass, field

import torch
import torch.nn.functional as F
import pandas as pd

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()
MODEL_PATH = BASE_DIR / "models" / "deeplog_model.pth"
STRUCTURED_LOGS_PATH = BASE_DIR / "data" / "cleaned" / "logs_structured.csv"


@dataclass
class AnomalyResult:
    timestamp: str
    expected_events: List[str]
    expected_probs: List[float]
    actual_event: str
    actual_template: str
    window: List[str]


@dataclass
class DetectionResult:
    total_logs: int = 0
    total_predictions: int = 0
    anomalies_detected: int = 0
    anomaly_rate: float = 0.0
    anomalies: List[AnomalyResult] = field(default_factory=list)
    anomaly_event_stats: Dict[str, int] = field(default_factory=dict)


class DeepLog(torch.nn.Module):
    """DeepLog 模型定义"""
    
    def __init__(self, num_events, embedding_dim=128, hidden_dim=128, num_layers=2, dropout=0.3):
        super(DeepLog, self).__init__()
        self.num_events = num_events
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        self.embedding = torch.nn.Embedding(num_events, embedding_dim)
        self.lstm = torch.nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        self.fc = torch.nn.Linear(hidden_dim, num_events)
        self.dropout = torch.nn.Dropout(dropout)
    
    def forward(self, x):
        x = self.embedding(x)
        lstm_out, _ = self.lstm(x)
        lstm_out = lstm_out[:, -1, :]
        lstm_out = self.dropout(lstm_out)
        output = self.fc(lstm_out)
        return output


class LogAnalysisSkill:
    """
    日志分析技能
    
    基于 DeepLog 模型进行日志序列异常检测（仅推理）
    
    使用前提：
    1. 已运行 1_generate_data.py 生成训练数据
    2. 已运行 2_parse_logs.py 解析日志
    3. 已运行 3_train_model.py 训练模型
    
    使用示例：
        skill = LogAnalysisSkill()
        
        # 检测已解析的日志文件
        result = await skill.detect_from_file()
        
        # 实时检测原始日志
        logs = ["[2024-01-01 10:00:00.000] [INFO] [order-service] Receive Request", ...]
        result = await skill.detect_logs(logs)
    """
    
    def __init__(
        self,
        model_path: str = None,
        top_k: int = 3,
        auto_load: bool = True,
    ):
        self.model_path = Path(model_path) if model_path else MODEL_PATH
        self.top_k = top_k
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.model = None
        self.event2idx = None
        self.idx2event = None
        self.num_events = None
        self.window_size = None
        
        self._is_loaded = False
        
        if auto_load and self.model_path.exists():
            self.load_model()
    
    def load_model(self) -> bool:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"模型文件不存在: {self.model_path}\n"
                f"请先运行训练脚本: python 3_train_model.py"
            )
        
        logger.info(f"加载模型: {self.model_path}")
        
        checkpoint = torch.load(self.model_path, map_location=self.device)
        
        self.event2idx = checkpoint['event2idx']
        self.idx2event = checkpoint['idx2event']
        self.num_events = checkpoint['num_events']
        self.window_size = checkpoint['window_size']
        
        self.model = DeepLog(
            num_events=self.num_events,
            embedding_dim=128,
            hidden_dim=128,
            num_layers=2,
            dropout=0.3,
        ).to(self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        self._is_loaded = True
        
        logger.info(f"模型加载成功: 事件类型={self.num_events}, 窗口大小={self.window_size}")
        return True
    
    def _ensure_model_loaded(self):
        if not self._is_loaded:
            self.load_model()
    
    def _extract_template(self, message: str) -> str:
        template = message
        template = re.sub(r'\b\d+\.\d+\.\d+\.\d+\b', '<IP>', template)
        template = re.sub(r'\b\d+ms\b', '<TIME>', template)
        template = re.sub(r'\b\d+s\b', '<TIME>', template)
        template = re.sub(r'\b\d+ms\.\d+\b', '<TIME>', template)
        template = re.sub(r'\b\d+\b', '<NUM>', template)
        template = re.sub(r'\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b', '<ID>', template)
        return template
    
    def _parse_log_line(self, line: str) -> Optional[Dict[str, str]]:
        log_format = r'\[(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] \[(?P<level>\w+)\] \[(?P<service>[\w-]+)\] (?P<message>.+)'
        match = re.match(log_format, line.strip())
        if match:
            return {
                'timestamp': match.group('timestamp'),
                'level': match.group('level'),
                'service': match.group('service'),
                'message': match.group('message'),
            }
        return None
    
    def _get_event_id(self, template: str) -> str:
        if not hasattr(self, '_template_to_event'):
            self._template_to_event = {}
            for event_id, idx in self.event2idx.items():
                if event_id != 'UNK':
                    self._template_to_event[event_id] = event_id
        
        if template in self._template_to_event:
            return self._template_to_event[template]
        
        return 'UNK'
    
    def _predict_next_events(self, sequence: List[str]) -> tuple:
        sequence_indices = [self.event2idx.get(eid, 0) for eid in sequence]
        sequence_tensor = torch.LongTensor([sequence_indices]).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(sequence_tensor)
            probabilities = F.softmax(outputs, dim=1)
            top_k_probs, top_k_indices = torch.topk(probabilities, self.top_k, dim=1)
            top_k_events = [self.idx2event[idx.item()] for idx in top_k_indices[0]]
            top_k_probs = top_k_probs[0].cpu().numpy()
        
        return top_k_events, top_k_probs
    
    async def detect_from_file(
        self,
        data_path: str = None,
        test_ratio: float = 0.3,
    ) -> DetectionResult:
        """
        从已解析的结构化日志文件检测异常
        
        Args:
            data_path: 结构化日志文件路径
            test_ratio: 测试数据比例
            
        Returns:
            DetectionResult: 检测结果
        """
        self._ensure_model_loaded()
        
        data_path = Path(data_path) if data_path else STRUCTURED_LOGS_PATH
        
        if not data_path.exists():
            raise FileNotFoundError(
                f"数据文件不存在: {data_path}\n"
                f"请先运行解析脚本: python 2_parse_logs.py"
            )
        
        logger.info(f"加载数据: {data_path}")
        
        df = pd.read_csv(data_path)
        split_idx = int(len(df) * (1 - test_ratio))
        df_test = df.iloc[split_idx:].reset_index(drop=True)
        
        return await self._detect_from_dataframe(df_test)
    
    async def detect_logs(
        self,
        logs: List[str],
    ) -> DetectionResult:
        """
        实时检测原始日志
        
        Args:
            logs: 原始日志行列表
            
        Returns:
            DetectionResult: 检测结果
        """
        self._ensure_model_loaded()
        
        parsed_logs = []
        templates = {}
        event_counter = 0
        
        for line in logs:
            parsed = self._parse_log_line(line)
            if parsed:
                template = self._extract_template(parsed['message'])
                
                if template not in templates:
                    event_id = f"E{len(templates) + 1}"
                    templates[template] = event_id
                
                parsed['event_id'] = templates[template]
                parsed['template'] = template
                parsed_logs.append(parsed)
        
        if not parsed_logs:
            logger.warning("没有有效的日志行被解析")
            return DetectionResult()
        
        df = pd.DataFrame(parsed_logs)
        df.rename(columns={
            'timestamp': 'Timestamp',
            'event_id': 'EventId',
            'template': 'EventTemplate',
        }, inplace=True)
        
        return await self._detect_from_dataframe(df)
    
    async def _detect_from_dataframe(self, df: pd.DataFrame) -> DetectionResult:
        """从 DataFrame 执行检测"""
        logger.info(f"开始检测 {len(df)} 条日志")
        
        result = DetectionResult()
        anomalies = []
        
        event_ids = df['EventId'].tolist()
        timestamps = df['Timestamp'].tolist()
        templates = df['EventTemplate'].tolist()
        
        window = deque(maxlen=self.window_size)
        
        for i in range(len(event_ids)):
            current_event = event_ids[i]
            current_timestamp = timestamps[i]
            current_template = templates[i]
            
            result.total_logs += 1
            
            if len(window) == self.window_size:
                predicted_events, predicted_probs = self._predict_next_events(list(window))
                result.total_predictions += 1
                
                if current_event not in predicted_events:
                    anomaly = AnomalyResult(
                        timestamp=current_timestamp,
                        expected_events=predicted_events,
                        expected_probs=predicted_probs.tolist(),
                        actual_event=current_event,
                        actual_template=current_template,
                        window=list(window),
                    )
                    anomalies.append(anomaly)
                    result.anomalies_detected += 1
                    
                    logger.info(
                        f"[ANOMALY] {current_timestamp}: "
                        f"expected={predicted_events}, actual={current_event}"
                    )
            
            window.append(current_event)
        
        result.anomalies = anomalies
        result.anomaly_rate = (
            result.anomalies_detected / max(result.total_predictions, 1) * 100
        )
        
        for a in anomalies:
            event = a.actual_event
            result.anomaly_event_stats[event] = result.anomaly_event_stats.get(event, 0) + 1
        
        logger.info(
            f"检测完成: {result.anomalies_detected} 个异常, "
            f"异常率 {result.anomaly_rate:.2f}%"
        )
        
        return result
    
    async def execute(
        self,
        logs: List[str] = None,
        data_path: str = None,
    ) -> DetectionResult:
        """
        执行入口（兼容 Multi-Agent 调用）
        
        Args:
            logs: 原始日志列表（优先）
            data_path: 结构化日志文件路径
            
        Returns:
            DetectionResult: 检测结果
        """
        if logs:
            return await self.detect_logs(logs)
        else:
            return await self.detect_from_file(data_path)
    
    def __repr__(self) -> str:
        status = "loaded" if self._is_loaded else "not_loaded"
        return f"LogAnalysisSkill(status={status}, model={self.model_path.name})"


async def create_skill(**kwargs) -> LogAnalysisSkill:
    """工厂函数：创建技能实例"""
    return LogAnalysisSkill(**kwargs)
