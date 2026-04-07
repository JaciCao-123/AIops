import numpy as np
from sklearn.ensemble import IsolationForest
from typing import Tuple
import re

class AnomalyDetector:
    def __init__(self, contamination: float = 0.1):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.is_fitted = False
        self.error_patterns = [
            r'error',
            r'exception',
            r'failed',
            r'timeout',
            r'refused',
            r'oom',
            r'crash',
            r'fatal',
            r'critical'
        ]
    
    def _extract_features(self, log_content: str) -> np.ndarray:
        features = []
        
        features.append(len(log_content))
        
        features.append(sum(1 for c in log_content if c.isupper()))
        
        error_count = sum(1 for pattern in self.error_patterns 
                        if re.search(pattern, log_content.lower()))
        features.append(error_count)
        
        features.append(len(re.findall(r'\d+', log_content)))
        
        features.append(1 if 'ERROR' in log_content or 'error' in log_content else 0)
        features.append(1 if 'WARN' in log_content or 'warn' in log_content else 0)
        features.append(1 if 'timeout' in log_content.lower() else 0)
        features.append(1 if 'exception' in log_content.lower() else 0)
        
        return np.array(features).reshape(1, -1)
    
    def fit(self, logs: list):
        features = np.vstack([self._extract_features(log) for log in logs])
        self.model.fit(features)
        self.is_fitted = True
    
    def detect(self, log_content: str) -> Tuple[bool, float]:
        features = self._extract_features(log_content)
        
        if not self.is_fitted:
            is_anomaly = any(
                re.search(pattern, log_content.lower()) 
                for pattern in self.error_patterns
            )
            score = 0.8 if is_anomaly else 0.2
            return is_anomaly, score
        
        prediction = self.model.predict(features)[0]
        score = self.model.score_samples(features)[0]
        
        normalized_score = (score + 1) / 2
        normalized_score = max(0, min(1, normalized_score))
        
        is_anomaly = prediction == -1
        
        return is_anomaly, round(normalized_score, 3)
    
    def batch_detect(self, logs: list) -> list:
        return [self.detect(log) for log in logs]
