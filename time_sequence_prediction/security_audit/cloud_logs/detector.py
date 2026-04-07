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


class CloudDetector(BaseDetector):
    name = "cloud"
    
    def __init__(self, base_dir: Optional[str] = None):
        super().__init__(base_dir)
        self.cloud_config = config.cloud
        self.logger = get_logger("CloudDetector")
    
    def generate_data(self) -> bool:
        try:
            days = self.cloud_config.get("training_days", 30)
            anomaly_day = self.cloud_config.get("anomaly_day", 25)
            start_date = config.get("detection.start_date", "2023-03-01")
            
            self.logger.info(f"生成云平台API调用日志数据 ({days}天, 起始日期: {start_date})")
            
            rng = pd.date_range(start_date, periods=days * 24 * 60, freq='T')
            data = []
            
            normal_calls = self.cloud_config.get("normal_api_calls_per_day", 5000)
            normal_call_times = np.random.choice(rng, size=min(days * normal_calls, len(rng)), replace=False)
            
            api_actions = [
                "ecs:DescribeInstances", "ecs:RunInstances", "ecs:StopInstances",
                "rds:DescribeDBInstances", "rds:CreateDatabase", "rds:DeleteDatabase",
                "oss:PutObject", "oss:GetObject", "oss:DeleteObject",
                "vpc:DescribeVpcs", "vpc:CreateVpc", "vpc:DeleteVpc",
                "ram:CreateUser", "ram:DeleteUser", "ram:AttachPolicyToUser"
            ]
            
            normal_users = [f"admin{i}@example.com" for i in range(1, 10)]
            normal_ips = [f"10.0.{np.random.randint(1, 10)}.{np.random.randint(1, 255)}" for _ in range(50)]
            
            for ts in normal_call_times:
                action = np.random.choice(api_actions, p=[0.3, 0.1, 0.05, 0.15, 0.05, 0.02, 0.1, 0.1, 0.03, 0.05, 0.02, 0.01, 0.01, 0.005, 0.005])
                data.append([
                    ts,
                    np.random.choice(normal_users),
                    action,
                    np.random.choice(normal_ips),
                    np.random.choice(["Success", "Success", "Success", "Throttled", "Denied"], p=[0.85, 0.1, 0.03, 0.015, 0.005]),
                    np.random.randint(100, 500)
                ])
            
            attack_ip = self.cloud_config.get("attack_ip", "103.24.77.55")
            attack_attempts = self.cloud_config.get("attack_attempts", 500)
            start_dt = pd.to_datetime(start_date)
            attack_start_time = start_dt + timedelta(days=anomaly_day-1, hours=14, minutes=5)
            
            self.logger.info(f"注入云平台异常访问: {attack_start_time}, IP: {attack_ip}")
            
            suspicious_actions = [
                "ram:CreateUser", "ram:AttachPolicyToUser", "ram:DeleteUser",
                "rds:DeleteDatabase", "vpc:DeleteVpc", "ecs:StopInstances"
            ]
            
            for i in range(attack_attempts):
                ts = attack_start_time + timedelta(seconds=np.random.randint(1, 300))
                data.append([
                    ts,
                    f"compromised_user@example.com",
                    np.random.choice(suspicious_actions),
                    attack_ip,
                    np.random.choice(["Success", "Denied"], p=[0.3, 0.7]),
                    np.random.randint(50, 200)
                ])
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'user', 'action', 'source_ip', 'status', 'response_time_ms'
            ])
            df.sort_values('timestamp', inplace=True)
            
            output_path = self.raw_data_dir / "cloud_api_calls.csv"
            df.to_csv(output_path, index=False)
            
            self.logger.info(f"云平台API调用日志已保存: {output_path}, 共 {len(df)} 条记录")
            return True
            
        except Exception as e:
            self.logger.exception(f"生成数据失败: {e}")
            return False
    
    def clean_data(self) -> bool:
        try:
            self.logger.info("清洗云平台API调用日志数据")
            
            df = self._load_raw_data("cloud_api_calls.csv")
            if df is None:
                return False
            
            df_aggregated = self._aggregate_by_time(df, freq='T')
            
            output_path = self.cleaned_data_dir / "cloud_api_calls_minutely.csv"
            df_aggregated.to_csv(output_path, index=False)
            
            self.logger.info(f"云平台API调用数据已聚合保存: {output_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"清洗数据失败: {e}")
            return False
    
    def train_model(self) -> bool:
        try:
            self.logger.info("训练云平台异常检测模型")
            
            df = self._load_cleaned_data("cloud_api_calls_minutely.csv")
            if df is None:
                return False
            
            anomaly_day = self.cloud_config.get("anomaly_day", 25)
            anomaly_day_end = self.cloud_config.get("anomaly_day_end", anomaly_day)
            min_training_samples = self.cloud_config.get("min_training_samples", 1000)
            
            train_df = df[~df['ds'].dt.day.between(anomaly_day, anomaly_day_end)]
            self.logger.info(f"排除异常日 {anomaly_day}-{anomaly_day_end} 的数据用于训练，训练集大小: {len(train_df)}")
            
            if len(train_df) < min_training_samples:
                self.logger.warning(f"训练数据不足: {len(train_df)} 条 (最小要求: {min_training_samples})，可能影响模型质量")
            
            changepoint_scale = config.model.get("cloud_changepoint_prior_scale", 0.05)
            model = self._create_prophet_model(changepoint_prior_scale=changepoint_scale)
            
            self.logger.info("开始训练 Prophet 模型...")
            model.fit(train_df)
            
            metadata = {
                "training_samples": len(train_df),
                "anomaly_days_excluded": f"{anomaly_day}-{anomaly_day_end}",
                "changepoint_prior_scale": changepoint_scale
            }
            return self._save_model(model, "prophet_cloud_model.pkl", metadata)
            
        except Exception as e:
            self.logger.exception(f"训练模型失败: {e}")
            return False
    
    def predict_and_alert(self) -> bool:
        try:
            self.logger.info("预测云平台异常并生成告警")
            
            model = self._load_model("prophet_cloud_model.pkl")
            if model is None:
                return False
            
            df_raw = self._load_raw_data("cloud_api_calls.csv")
            if df_raw is None:
                return False
            
            df_total = self._aggregate_by_time(df_raw, freq='T')
            
            forecast = model.predict(df_total[['ds']])
            result = pd.concat([df_total.set_index('ds'), forecast.set_index('ds')], axis=1)
            
            min_threshold = self.cloud_config.get("min_api_calls_threshold", 100)
            result['anomaly'] = result.apply(
                lambda row: row['y'] > row['yhat_upper'] and row['y'] > min_threshold, 
                axis=1
            )
            anomalies = result[result['anomaly'] == True]
            
            if anomalies.empty:
                self.logger.info("未检测到云平台异常访问")
                return True
            
            self.logger.warning(f"检测到 {len(anomalies)} 个云平台异常点")
            
            for ts, row in anomalies.iterrows():
                self._process_anomaly(ts, row, df_raw)
            
            return True
            
        except Exception as e:
            self.logger.exception(f"预测告警失败: {e}")
            return False
    
    def _process_anomaly(self, ts, row, df_raw: pd.DataFrame) -> None:
        try:
            self.logger.warning(
                f"[Cloud告警] 时间: {ts}, API调用次数: {int(row['y'])}, 阈值: {row['yhat_upper']:.2f}"
            )
            
            detail = df_raw[
                (df_raw['timestamp'] >= ts) & 
                (df_raw['timestamp'] < ts + pd.Timedelta(minutes=1))
            ]
            
            if detail.empty:
                return
            
            top_source_ip = detail['source_ip'].mode()[0]
            top_user = detail['user'].mode()[0]
            unique_actions = detail['action'].nunique()
            denied_count = len(detail[detail['status'] == 'Denied'])
            
            dangerous_actions = detail[detail['action'].str.contains('Delete|Stop|Attach', case=False, na=False)]
            has_dangerous_ops = len(dangerous_actions) > 0
            
            self.logger.info(
                f"根因定位: 主要来源IP '{top_source_ip}', 用户 '{top_user}', "
                f"操作类型数 {unique_actions}, 拒绝次数 {denied_count}, "
                f"包含危险操作: {has_dangerous_ops}"
            )
            
            alert = {
                "alert_type": "Cloud_Anomaly_Detected",
                "timestamp": ts.isoformat(),
                "severity": "HIGH" if has_dangerous_ops else "MEDIUM",
                "description": f"Cloud API call rate {int(row['y'])}/min exceeds threshold {row['yhat_upper']:.2f}/min",
                "entities": {
                    "source_ip": top_source_ip,
                    "user": top_user,
                    "unique_actions": unique_actions,
                    "denied_count": denied_count
                },
                "source_system": "cloud_detector",
                "indicators": {
                    "has_dangerous_operations": has_dangerous_ops,
                    "high_denial_rate": denied_count > int(row['y']) * 0.5,
                    "potential_compromise": has_dangerous_ops and denied_count > 10
                }
            }
            
            self._save_alert(alert, ts)
            
        except Exception as e:
            self.logger.error(f"处理异常失败: {e}")


if __name__ == "__main__":
    detector = CloudDetector()
    success = detector.run_pipeline()
    sys.exit(0 if success else 1)
