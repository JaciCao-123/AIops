import os
import sys
from typing import Dict, Any, Optional
from datetime import timedelta
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from base.detector import BaseDetector
from base.config import config
from base.logger import get_logger


class AuthDetector(BaseDetector):
    name = "auth"
    
    def __init__(self, base_dir: Optional[str] = None):
        super().__init__(base_dir)
        self.auth_config = config.auth
        self.logger = get_logger("AuthDetector")
    
    def generate_data(self) -> bool:
        try:
            days = self.auth_config.get("training_days", 30)
            anomaly_day = self.auth_config.get("anomaly_day", 25)
            start_date = config.get("detection.start_date", "2023-03-01")
            
            self.logger.info(f"生成身份认证日志数据 ({days}天, 起始日期: {start_date})")
            
            rng = pd.date_range(start_date, periods=days * 24 * 60, freq='T')
            data = []
            
            normal_failures = self.auth_config.get("normal_failures_per_day", 150)
            normal_failure_times = np.random.choice(rng, size=days * normal_failures, replace=False)
            for ts in normal_failure_times:
                data.append([
                    ts, 
                    f"user{np.random.randint(1, 50)}@example.com", 
                    f"app{np.random.randint(1, 3)}", 
                    f"5.188.21.{np.random.randint(1, 255)}",
                    np.random.choice(["invalid_password", "account_locked", "mfa_failed"], p=[0.6, 0.3, 0.1])
                ])
            
            leaked_user = self.auth_config.get("leaked_user", "leaked_user@example.com")
            target_app = self.auth_config.get("target_app", "app1")
            attack_attempts = self.auth_config.get("attack_attempts", 200)
            
            start_dt = pd.to_datetime(start_date)
            attack_start_time = start_dt + timedelta(days=anomaly_day-1, hours=14, minutes=10)
            self.logger.info(f"注入撞库攻击: {attack_start_time}, 用户: {leaked_user}")
            
            attack_ips = [f"104.28.2.{np.random.randint(1, 255)}" for _ in range(attack_attempts)]
            for i in range(attack_attempts):
                ts = attack_start_time + timedelta(seconds=np.random.randint(1, 120))
                data.append([ts, leaked_user, target_app, attack_ips[i], "invalid_password"])
            
            df = pd.DataFrame(data, columns=['timestamp', 'username', 'application', 'source_ip', 'failure_type'])
            df.sort_values('timestamp', inplace=True)
            
            output_path = self.raw_data_dir / "auth_failures.csv"
            df.to_csv(output_path, index=False)
            
            self.logger.info(f"身份认证日志数据已保存: {output_path}, 共 {len(df)} 条记录")
            return True
            
        except Exception as e:
            self.logger.exception(f"生成数据失败: {e}")
            return False
    
    def clean_data(self) -> bool:
        try:
            self.logger.info("清洗身份认证日志数据")
            
            df = self._load_raw_data("auth_failures.csv")
            if df is None:
                return False
            
            df_aggregated = self._aggregate_by_time(df, freq='T')
            
            output_path = self.cleaned_data_dir / "auth_failures_minutely.csv"
            df_aggregated.to_csv(output_path, index=False)
            
            self.logger.info(f"身份认证数据已聚合保存: {output_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"清洗数据失败: {e}")
            return False
    
    def train_model(self) -> bool:
        try:
            self.logger.info("训练身份认证异常检测模型")
            
            df = self._load_cleaned_data("auth_failures_minutely.csv")
            if df is None:
                return False
            
            anomaly_day = self.auth_config.get("anomaly_day", 25)
            anomaly_day_end = self.auth_config.get("anomaly_day_end", anomaly_day)
            min_training_samples = self.auth_config.get("min_training_samples", 1000)
            
            train_df = df[~df['ds'].dt.day.between(anomaly_day, anomaly_day_end)]
            self.logger.info(f"排除异常日 {anomaly_day}-{anomaly_day_end} 的数据用于训练，训练集大小: {len(train_df)}")
            
            if len(train_df) < min_training_samples:
                self.logger.warning(f"训练数据不足: {len(train_df)} 条 (最小要求: {min_training_samples})，可能影响模型质量")
            
            changepoint_scale = config.model.get("auth_changepoint_prior_scale", 0.1)
            model = self._create_prophet_model(changepoint_prior_scale=changepoint_scale)
            
            self.logger.info("开始训练 Prophet 模型...")
            model.fit(train_df)
            
            metadata = {
                "training_samples": len(train_df),
                "anomaly_days_excluded": f"{anomaly_day}-{anomaly_day_end}",
                "changepoint_prior_scale": changepoint_scale
            }
            return self._save_model(model, "prophet_auth_model.pkl", metadata)
            
        except Exception as e:
            self.logger.exception(f"训练模型失败: {e}")
            return False
    
    def predict_and_alert(self) -> bool:
        try:
            self.logger.info("预测身份认证异常并生成告警")
            
            model = self._load_model("prophet_auth_model.pkl")
            if model is None:
                return False
            
            df_raw = self._load_raw_data("auth_failures.csv")
            if df_raw is None:
                return False
            
            df_total = self._aggregate_by_time(df_raw, freq='T')
            
            forecast = model.predict(df_total[['ds']])
            result = pd.concat([df_total.set_index('ds'), forecast.set_index('ds')], axis=1)
            
            min_threshold = self.auth_config.get("min_failure_threshold", 10)
            result['anomaly'] = result.apply(
                lambda row: row['y'] > row['yhat_upper'] and row['y'] > min_threshold, 
                axis=1
            )
            anomalies = result[result['anomaly'] == True]
            
            if anomalies.empty:
                self.logger.info("未检测到身份认证撞库攻击")
                return True
            
            self.logger.warning(f"检测到 {len(anomalies)} 个身份认证异常点")
            
            for ts, row in anomalies.iterrows():
                self._process_anomaly(ts, row, df_raw)
            
            return True
            
        except Exception as e:
            self.logger.exception(f"预测告警失败: {e}")
            return False
    
    def _process_anomaly(self, ts, row, df_raw: pd.DataFrame) -> None:
        try:
            self.logger.warning(
                f"[Auth告警] 时间: {ts}, 失败次数: {int(row['y'])}, 阈值: {row['yhat_upper']:.2f}"
            )
            
            detail = df_raw[
                (df_raw['timestamp'] >= ts) & 
                (df_raw['timestamp'] < ts + pd.Timedelta(minutes=1))
            ]
            
            if detail.empty:
                return
            
            top_target_user = detail['username'].mode()[0]
            source_ip_count = detail['source_ip'].nunique()
            top_failure_type = detail['failure_type'].mode()[0]
            target_app = detail['application'].mode()[0]
            
            self.logger.info(
                f"根因定位: 来自 {source_ip_count} 个不同IP的攻击，"
                f"目标用户 '{top_target_user}'，应用 '{target_app}'，"
                f"主要失败类型 '{top_failure_type}'"
            )
            
            alert = {
                "alert_type": "Auth_CredentialStuffing_Detected",
                "timestamp": ts.isoformat(),
                "severity": "HIGH",
                "description": f"Authentication failure rate {int(row['y'])}/min exceeds threshold {row['yhat_upper']:.2f}/min",
                "entities": {
                    "target_user": top_target_user,
                    "target_app": target_app,
                    "source_ip_count": source_ip_count,
                    "failure_type": top_failure_type
                },
                "source_system": "auth_detector",
                "indicators": {
                    "is_credential_stuffing": source_ip_count > self.auth_config.get("credential_stuffing_ip_threshold", 50),
                    "is_targeted_attack": source_ip_count < self.auth_config.get("targeted_attack_ip_threshold", 10) and int(row['y']) > self.auth_config.get("targeted_attack_failure_threshold", 20)
                }
            }
            
            self._save_alert(alert, ts)
            
        except Exception as e:
            self.logger.error(f"处理异常失败: {e}")


if __name__ == "__main__":
    detector = AuthDetector()
    success = detector.run_pipeline()
    sys.exit(0 if success else 1)
