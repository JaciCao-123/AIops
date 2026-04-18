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


class SSHDetector(BaseDetector):
    name = "ssh"
    
    def __init__(self, base_dir: Optional[str] = None):
        super().__init__(base_dir)
        self.ssh_config = config.ssh
        self.logger = get_logger("SSHDetector")
    
    def generate_data(self) -> bool:
        try:
            days = self.ssh_config.get("training_days", 30)
            anomaly_day = self.ssh_config.get("anomaly_day", 25)
            start_date = config.get("detection.start_date", "2023-03-01")
            
            self.logger.info(f"生成SSH登录失败日志数据 ({days}天, 起始日期: {start_date})")
            
            rng = pd.date_range(start_date, periods=days * 24 * 60, freq='T')
            data = []
            
            normal_failures = self.ssh_config.get("normal_failures_per_day", 50)
            normal_failure_times = np.random.choice(rng, size=days * normal_failures, replace=False)
            
            normal_users = [f"user{np.random.randint(1, 10)}" for _ in range(20)]
            normal_ips = [f"10.0.{np.random.randint(1, 5)}.{np.random.randint(1, 255)}" for _ in range(30)]
            hosts = [f"prod-server-{i:02d}" for i in range(1, 6)]
            
            for ts in normal_failure_times:
                data.append([
                    ts, 
                    np.random.choice(normal_users), 
                    f"203.0.113.{np.random.randint(1, 255)}", 
                    np.random.choice(hosts),
                    np.random.choice(["Failed", "Failed", "Failed", "Invalid"], p=[0.7, 0.1, 0.1, 0.1]),
                    np.random.randint(1, 5)
                ])
            
            attack_ip = self.ssh_config.get("attack_ip", "198.51.100.123")
            attack_user = self.ssh_config.get("attack_user", "root")
            attack_host = self.ssh_config.get("attack_host", "prod-server-01")
            attack_attempts = self.ssh_config.get("attack_attempts", 300)
            
            start_dt = pd.to_datetime(start_date)
            attack_start_time = start_dt + timedelta(days=anomaly_day-1, hours=14, minutes=0)
            self.logger.info(f"注入SSH暴力破解攻击: {attack_start_time}, IP: {attack_ip}, 目标: {attack_host}")
            
            for i in range(attack_attempts):
                ts = attack_start_time + timedelta(seconds=np.random.randint(1, 300))
                data.append([
                    ts, 
                    attack_user, 
                    attack_ip, 
                    attack_host,
                    "Failed",
                    np.random.randint(1, 3)
                ])
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'username', 'source_ip', 'hostname', 'status', 'attempts'
            ])
            df.sort_values('timestamp', inplace=True)
            
            output_path = self.raw_data_dir / "ssh_failures.csv"
            df.to_csv(output_path, index=False)
            
            self.logger.info(f"SSH日志数据已保存: {output_path}, 共 {len(df)} 条记录")
            return True
            
        except Exception as e:
            self.logger.exception(f"生成数据失败: {e}")
            return False
    
    def clean_data(self) -> bool:
        try:
            self.logger.info("清洗SSH日志数据")
            
            df = self._load_raw_data("ssh_failures.csv")
            if df is None:
                return False
            
            df_aggregated = self._aggregate_by_time(df, freq='T')
            
            output_path = self.cleaned_data_dir / "ssh_failures_minutely.csv"
            df_aggregated.to_csv(output_path, index=False)
            
            self.logger.info(f"SSH数据已聚合保存: {output_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"清洗数据失败: {e}")
            return False
    
    def train_model(self) -> bool:
        try:
            self.logger.info("训练SSH异常检测模型")
            
            df = self._load_cleaned_data("ssh_failures_minutely.csv")
            if df is None:
                return False
            
            anomaly_day = self.ssh_config.get("anomaly_day", 25)
            anomaly_day_end = self.ssh_config.get("anomaly_day_end", anomaly_day)
            min_training_samples = self.ssh_config.get("min_training_samples", 500)
            
            train_df = df[~df['ds'].dt.day.between(anomaly_day, anomaly_day_end)]
            self.logger.info(f"排除异常日 {anomaly_day}-{anomaly_day_end} 的数据用于训练，训练集大小: {len(train_df)}")
            
            if len(train_df) < min_training_samples:
                self.logger.warning(f"训练数据不足: {len(train_df)} 条 (最小要求: {min_training_samples})，可能影响模型质量")
            
            changepoint_scale = config.model.get("ssh_changepoint_prior_scale", 0.05)
            model = self._create_prophet_model(changepoint_prior_scale=changepoint_scale)
            
            self.logger.info("开始训练 Prophet 模型...")
            model.fit(train_df)
            
            metadata = {
                "training_samples": len(train_df),
                "anomaly_days_excluded": f"{anomaly_day}-{anomaly_day_end}",
                "changepoint_prior_scale": changepoint_scale
            }
            return self._save_model(model, "prophet_ssh_model.pkl", metadata)
            
        except Exception as e:
            self.logger.exception(f"训练模型失败: {e}")
            return False
    
    def predict_and_alert(self) -> bool:
        try:
            self.logger.info("预测SSH异常并生成告警")
            
            model = self._load_model("prophet_ssh_model.pkl")
            if model is None:
                return False
            
            df_raw = self._load_raw_data("ssh_failures.csv")
            if df_raw is None:
                return False
            
            df_total = self._aggregate_by_time(df_raw, freq='T')
            
            forecast = model.predict(df_total[['ds']])
            result = pd.concat([df_total.set_index('ds'), forecast.set_index('ds')], axis=1)
            
            min_threshold = self.ssh_config.get("min_failure_threshold", 5)
            result['anomaly'] = result.apply(
                lambda row: row['y'] > row['yhat_upper'] and row['y'] > min_threshold, 
                axis=1
            )
            anomalies = result[result['anomaly'] == True]
            
            if anomalies.empty:
                self.logger.info("未检测到SSH暴力破解攻击")
                return True
            
            self.logger.warning(f"检测到 {len(anomalies)} 个SSH异常点")
            
            for ts, row in anomalies.iterrows():
                self._process_anomaly(ts, row, df_raw)
            
            return True
            
        except Exception as e:
            self.logger.exception(f"预测告警失败: {e}")
            return False
    
    def _process_anomaly(self, ts, row, df_raw: pd.DataFrame) -> None:
        try:
            self.logger.warning(
                f"[SSH告警] 时间: {ts}, 失败次数: {int(row['y'])}, 阈值: {row['yhat_upper']:.2f}"
            )
            
            detail = df_raw[
                (df_raw['timestamp'] >= ts) & 
                (df_raw['timestamp'] < ts + pd.Timedelta(minutes=1))
            ]
            
            if detail.empty:
                return
            
            top_source_ip = detail['source_ip'].mode()[0]
            top_username = detail['username'].mode()[0]
            target_host = detail['hostname'].mode()[0]
            unique_users = detail['username'].nunique()
            total_attempts = detail['attempts'].sum()
            
            is_root_attack = 'root' in detail['username'].values
            
            self.logger.info(
                f"根因定位: 攻击源IP '{top_source_ip}' -> 主机 '{target_host}' -> "
                f"用户 '{top_username}', 尝试用户数 {unique_users}"
            )
            
            alert = {
                "alert_type": "SSH_BruteForce_Detected",
                "timestamp": ts.isoformat(),
                "severity": "CRITICAL" if is_root_attack else "HIGH",
                "description": f"SSH failure rate {int(row['y'])}/min exceeds threshold {row['yhat_upper']:.2f}/min",
                "entities": {
                    "source_ip": top_source_ip,
                    "target_user": top_username,
                    "target_host": target_host,
                    "unique_users_tried": unique_users,
                    "total_attempts": int(total_attempts)
                },
                "source_system": "ssh_detector",
                "indicators": {
                    "is_root_attack": is_root_attack,
                    "is_distributed_attack": unique_users > 10,
                    "is_single_target": len(detail['hostname'].unique()) == 1
                }
            }
            
            self._save_alert(alert, ts)
            
        except Exception as e:
            self.logger.error(f"处理异常失败: {e}")


if __name__ == "__main__":
    detector = SSHDetector()
    success = detector.run_pipeline()
    sys.exit(0 if success else 1)
