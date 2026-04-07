import os
import threading
import yaml
from typing import Any, Dict, Optional


class Config:
    _instance: Optional['Config'] = None
    _lock = threading.Lock()
    _config: Dict[str, Any] = {}
    
    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._load_config(config_path)
        return cls._instance
    
    def _load_config(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "detection": {
                "auth": {"anomaly_day": 25, "training_days": 30, "min_failure_threshold": 10},
                "cloud": {"anomaly_day": 25, "training_days": 30, "min_api_calls_threshold": 100},
                "app_server": {"anomaly_day": 25, "training_days": 30, "min_error_threshold": 50},
                "ssh": {"anomaly_day": 25, "training_days": 30, "min_failure_threshold": 5}
            },
            "correlation": {
                "time_window_minutes": 15,
                "severity_threshold": "HIGH"
            },
            "model": {
                "prophet": {
                    "daily_seasonality": True,
                    "weekly_seasonality": True
                }
            },
            "paths": {
                "raw_data_dir": "data/raw",
                "cleaned_data_dir": "data/cleaned",
                "model_dir": "models",
                "events_dir": "../correlation_engine/events"
            }
        }
    
    @property
    def auth(self) -> Dict[str, Any]:
        return self._config.get("detection", {}).get("auth", {})
    
    @property
    def cloud(self) -> Dict[str, Any]:
        return self._config.get("detection", {}).get("cloud", {})
    
    @property
    def app_server(self) -> Dict[str, Any]:
        return self._config.get("detection", {}).get("app_server", {})
    
    @property
    def ssh(self) -> Dict[str, Any]:
        return self._config.get("detection", {}).get("ssh", {})
    
    @property
    def correlation(self) -> Dict[str, Any]:
        return self._config.get("correlation", {})
    
    @property
    def model(self) -> Dict[str, Any]:
        return self._config.get("model", {}).get("prophet", {})
    
    @property
    def paths(self) -> Dict[str, Any]:
        return self._config.get("paths", {})
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        return self._config.get("logging", {})
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value


config = Config()
