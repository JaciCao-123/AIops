import logging
import sys
from typing import Dict, Optional

from base.config import config

_loggers: Dict[str, logging.Logger] = {}


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(name)
    
    if logger.handlers:
        _loggers[name] = logger
        return logger
    
    log_level = level or config.logging_config.get("level", "INFO")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    log_format = config.logging_config.get(
        "format", 
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    formatter = logging.Formatter(log_format)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.propagate = False
    
    _loggers[name] = logger
    return logger


def get_logger(name: str) -> logging.Logger:
    return setup_logger(name)
