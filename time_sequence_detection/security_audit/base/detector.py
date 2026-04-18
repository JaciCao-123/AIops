import os
import json
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import joblib

try:
    from prophet import Prophet
except ImportError:
    Prophet = None

from base.config import config
from base.logger import get_logger


class DetectorError(Exception):
    pass


class DataValidationError(DetectorError):
    pass


class ModelError(DetectorError):
    pass


class ConfigurationError(DetectorError):
    pass


class BaseDetector(ABC):
    name: str = "base"
    
    def __init__(self, base_dir: Optional[str] = None):
        self.logger = get_logger(f"{self.__class__.__name__}")
        
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = Path(base_dir)
        
        self.raw_data_dir = self.base_dir / config.paths.get("raw_data_dir", "data/raw")
        self.cleaned_data_dir = self.base_dir / config.paths.get("cleaned_data_dir", "data/cleaned")
        self.model_dir = self.base_dir / config.paths.get("model_dir", "models")
        self.events_dir = self.base_dir.parent / "correlation_engine" / "events"
        
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.cleaned_data_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
    
    def run_pipeline(self) -> bool:
        try:
            self.logger.info(f"开始执行 {self.name} 检测器管道")
            
            self.logger.info("步骤 1/4: 生成数据")
            if not self.generate_data():
                self.logger.error("数据生成失败")
                return False
            
            self.logger.info("步骤 2/4: 清洗数据")
            if not self.clean_data():
                self.logger.error("数据清洗失败")
                return False
            
            self.logger.info("步骤 3/4: 训练模型")
            if not self.train_model():
                self.logger.error("模型训练失败")
                return False
            
            self.logger.info("步骤 4/4: 预测与告警")
            if not self.predict_and_alert():
                self.logger.error("预测告警失败")
                return False
            
            self.logger.info(f"{self.name} 检测器管道执行完成")
            return True
            
        except Exception as e:
            self.logger.exception(f"管道执行异常: {e}")
            return False
    
    @abstractmethod
    def generate_data(self) -> bool:
        pass
    
    @abstractmethod
    def clean_data(self) -> bool:
        pass
    
    @abstractmethod
    def train_model(self) -> bool:
        pass
    
    @abstractmethod
    def predict_and_alert(self) -> bool:
        pass
    
    def _load_raw_data(self, filename: str, required_columns: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
        filepath = self.raw_data_dir / filename
        if not filepath.exists():
            self.logger.error(f"原始数据文件不存在: {filepath}")
            return None
        try:
            df = pd.read_csv(filepath)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            if required_columns and not self._validate_dataframe(df, required_columns):
                return None
            
            return df
        except pd.errors.EmptyDataError:
            self.logger.error(f"数据文件为空: {filepath}")
            return None
        except pd.errors.ParserError as e:
            self.logger.error(f"数据解析错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"加载数据失败: {e}")
            return None
    
    def _load_cleaned_data(self, filename: str, required_columns: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
        filepath = self.cleaned_data_dir / filename
        if not filepath.exists():
            self.logger.error(f"清洗数据文件不存在: {filepath}")
            return None
        try:
            df = pd.read_csv(filepath)
            if 'ds' in df.columns:
                df['ds'] = pd.to_datetime(df['ds'])
            
            default_required = ['ds', 'y']
            cols_to_check = required_columns or default_required
            if not self._validate_dataframe(df, cols_to_check):
                return None
            
            return df
        except pd.errors.EmptyDataError:
            self.logger.error(f"数据文件为空: {filepath}")
            return None
        except pd.errors.ParserError as e:
            self.logger.error(f"数据解析错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"加载数据失败: {e}")
            return None
    
    def _validate_dataframe(self, df: pd.DataFrame, required_columns: List[str], min_rows: int = 1) -> bool:
        if df is None:
            self.logger.error("DataFrame 为 None")
            raise DataValidationError("DataFrame 为 None")
        
        if df.empty:
            self.logger.error("DataFrame 为空")
            raise DataValidationError("DataFrame 为空")
        
        if len(df) < min_rows:
            self.logger.error(f"数据行数不足: {len(df)} < {min_rows}")
            raise DataValidationError(f"数据行数不足: {len(df)} < {min_rows}")
        
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            self.logger.error(f"缺少必需列: {missing_columns}")
            raise DataValidationError(f"缺少必需列: {missing_columns}")
        
        return True
    
    def _save_model(self, model: Any, filename: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        filepath = self.model_dir / filename
        try:
            model_data = {
                "model": model,
                "version": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "detector_name": self.name,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            joblib.dump(model_data, filepath)
            self.logger.info(f"模型已保存: {filepath} (版本: {model_data['version']})")
            return True
        except (IOError, OSError) as e:
            self.logger.error(f"保存模型失败 (IO错误): {e}")
            raise ModelError(f"保存模型失败: {e}")
        except Exception as e:
            self.logger.error(f"保存模型失败: {e}")
            raise ModelError(f"保存模型失败: {e}")
    
    def _load_model(self, filename: str, load_metadata: bool = False) -> Optional[Any]:
        filepath = self.model_dir / filename
        if not filepath.exists():
            self.logger.error(f"模型文件不存在: {filepath}")
            return None
        try:
            model_data = joblib.load(filepath)
            
            if isinstance(model_data, dict) and "model" in model_data:
                model = model_data["model"]
                version = model_data.get("version", "unknown")
                self.logger.info(f"模型已加载: {filepath} (版本: {version})")
                
                if load_metadata:
                    return model_data
                return model
            else:
                self.logger.info(f"模型已加载: {filepath} (旧格式，无版本信息)")
                return model_data
                
        except (IOError, OSError) as e:
            self.logger.error(f"加载模型失败 (IO错误): {e}")
            raise ModelError(f"加载模型失败: {e}")
        except Exception as e:
            self.logger.error(f"加载模型失败: {e}")
            raise ModelError(f"加载模型失败: {e}")
    
    def _save_alert(self, alert: Dict[str, Any], timestamp: datetime) -> Optional[str]:
        try:
            filename = f"{self.name}_alert_{timestamp.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.json"
            filepath = self.events_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(alert, f, indent=4, ensure_ascii=False, default=str)
            
            self.logger.info(f"告警已保存: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"保存告警失败: {e}")
            return None
    
    def _create_prophet_model(self, changepoint_prior_scale: float = 0.05) -> Any:
        if Prophet is None:
            raise ConfigurationError("Prophet 库未安装，请运行: pip install prophet")
        
        return Prophet(
            daily_seasonality=config.model.get("daily_seasonality", True),
            weekly_seasonality=config.model.get("weekly_seasonality", True),
            changepoint_prior_scale=changepoint_prior_scale
        )
    
    def _aggregate_by_time(self, df: pd.DataFrame, freq: str = 'T') -> pd.DataFrame:
        if 'timestamp' not in df.columns:
            raise DataValidationError("DataFrame 必须包含 'timestamp' 列")
        
        aggregated = df.groupby(pd.Grouper(key='timestamp', freq=freq)).size().reset_index(name='y')
        aggregated.columns = ['ds', 'y']
        return aggregated
