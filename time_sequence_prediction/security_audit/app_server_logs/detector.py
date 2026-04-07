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


class AppServerDetector(BaseDetector):
    name = "app_server"
    
    def __init__(self, base_dir: Optional[str] = None):
        super().__init__(base_dir)
        self.app_config = config.app_server
        self.logger = get_logger("AppServerDetector")
    
    def generate_data(self) -> bool:
        try:
            days = self.app_config.get("training_days", 30)
            anomaly_day = self.app_config.get("anomaly_day", 25)
            start_date = config.get("detection.start_date", "2023-03-01")
            
            self.logger.info(f"生成应用/服务器错误日志数据 ({days}天, 起始日期: {start_date})")
            
            rng = pd.date_range(start_date, periods=days * 24 * 60, freq='T')
            data = []
            
            normal_errors = self.app_config.get("normal_errors_per_day", 200)
            normal_error_times = np.random.choice(rng, size=days * normal_errors, replace=False)
            
            services = [
                "order-service", "payment-service", "user-service", 
                "inventory-service", "notification-service", "api-gateway"
            ]
            
            error_codes = self.app_config.get("error_types", ["500", "502", "503", "504"])
            error_messages = {
                "500": "Internal Server Error",
                "502": "Bad Gateway",
                "503": "Service Unavailable",
                "504": "Gateway Timeout"
            }
            
            for ts in normal_error_times:
                service = np.random.choice(services, p=[0.25, 0.2, 0.15, 0.15, 0.1, 0.15])
                error_code = np.random.choice(error_codes, p=[0.4, 0.2, 0.25, 0.15])
                data.append([
                    ts,
                    service,
                    error_code,
                    error_messages[error_code],
                    f"/api/v1/{np.random.choice(['orders', 'payments', 'users', 'inventory'])}/{np.random.randint(1, 1000)}",
                    np.random.randint(100, 5000)
                ])
            
            attack_service = self.app_config.get("attack_service", "payment-service")
            start_dt = pd.to_datetime(start_date)
            attack_start_time = start_dt + timedelta(days=anomaly_day-1, hours=14, minutes=15)
            
            self.logger.info(f"注入应用错误激增: {attack_start_time}, 服务: {attack_service}")
            
            for i in range(300):
                ts = attack_start_time + timedelta(seconds=np.random.randint(1, 180))
                error_code = np.random.choice(error_codes, p=[0.5, 0.3, 0.15, 0.05])
                data.append([
                    ts,
                    attack_service,
                    error_code,
                    error_messages[error_code],
                    f"/api/v1/payments/{np.random.randint(1, 1000)}",
                    np.random.randint(5000, 30000)
                ])
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'service', 'error_code', 'error_message', 'endpoint', 'response_time_ms'
            ])
            df.sort_values('timestamp', inplace=True)
            
            output_path = self.raw_data_dir / "app_server_errors.csv"
            df.to_csv(output_path, index=False)
            
            self.logger.info(f"应用/服务器错误日志已保存: {output_path}, 共 {len(df)} 条记录")
            return True
            
        except Exception as e:
            self.logger.exception(f"生成数据失败: {e}")
            return False
    
    def clean_data(self) -> bool:
        try:
            self.logger.info("清洗应用/服务器错误日志数据")
            
            df = self._load_raw_data("app_server_errors.csv")
            if df is None:
                return False
            
            df_aggregated = self._aggregate_by_time(df, freq='T')
            
            output_path = self.cleaned_data_dir / "app_server_errors_minutely.csv"
            df_aggregated.to_csv(output_path, index=False)
            
            self.logger.info(f"应用/服务器错误数据已聚合保存: {output_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"清洗数据失败: {e}")
            return False
    
    def train_model(self) -> bool:
        try:
            self.logger.info("训练应用/服务器异常检测模型")
            
            df = self._load_cleaned_data("app_server_errors_minutely.csv")
            if df is None:
                return False
            
            anomaly_day = self.app_config.get("anomaly_day", 25)
            anomaly_day_end = self.app_config.get("anomaly_day_end", anomaly_day)
            min_training_samples = self.app_config.get("min_training_samples", 1000)
            
            train_df = df[~df['ds'].dt.day.between(anomaly_day, anomaly_day_end)]
            self.logger.info(f"排除异常日 {anomaly_day}-{anomaly_day_end} 的数据用于训练，训练集大小: {len(train_df)}")
            
            if len(train_df) < min_training_samples:
                self.logger.warning(f"训练数据不足: {len(train_df)} 条 (最小要求: {min_training_samples})，可能影响模型质量")
            
            changepoint_scale = config.model.get("app_server_changepoint_prior_scale", 0.08)
            model = self._create_prophet_model(changepoint_prior_scale=changepoint_scale)
            
            self.logger.info("开始训练 Prophet 模型...")
            model.fit(train_df)
            
            metadata = {
                "training_samples": len(train_df),
                "anomaly_days_excluded": f"{anomaly_day}-{anomaly_day_end}",
                "changepoint_prior_scale": changepoint_scale
            }
            return self._save_model(model, "prophet_app_server_model.pkl", metadata)
            
        except Exception as e:
            self.logger.exception(f"训练模型失败: {e}")
            return False
    
    def predict_and_alert(self) -> bool:
        try:
            self.logger.info("预测应用/服务器异常并生成告警")
            
            model = self._load_model("prophet_app_server_model.pkl")
            if model is None:
                return False
            
            df_raw = self._load_raw_data("app_server_errors.csv")
            if df_raw is None:
                return False
            
            df_total = self._aggregate_by_time(df_raw, freq='T')
            
            forecast = model.predict(df_total[['ds']])
            result = pd.concat([df_total.set_index('ds'), forecast.set_index('ds')], axis=1)
            
            min_threshold = self.app_config.get("min_error_threshold", 50)
            result['anomaly'] = result.apply(
                lambda row: row['y'] > row['yhat_upper'] and row['y'] > min_threshold, 
                axis=1
            )
            anomalies = result[result['anomaly'] == True]
            
            if anomalies.empty:
                self.logger.info("未检测到应用/服务器异常")
                return True
            
            self.logger.warning(f"检测到 {len(anomalies)} 个应用/服务器异常点")
            
            for ts, row in anomalies.iterrows():
                self._process_anomaly(ts, row, df_raw)
            
            return True
            
        except Exception as e:
            self.logger.exception(f"预测告警失败: {e}")
            return False
    
    def _process_anomaly(self, ts, row, df_raw: pd.DataFrame) -> None:
        try:
            self.logger.warning(
                f"[AppServer告警] 时间: {ts}, 错误次数: {int(row['y'])}, 阈值: {row['yhat_upper']:.2f}"
            )
            
            detail = df_raw[
                (df_raw['timestamp'] >= ts) & 
                (df_raw['timestamp'] < ts + pd.Timedelta(minutes=1))
            ]
            
            if detail.empty:
                return
            
            top_service = detail['service'].mode()[0]
            top_error_code = detail['error_code'].mode()[0]
            unique_endpoints = detail['endpoint'].nunique()
            avg_response_time = detail['response_time_ms'].mean()
            max_response_time = detail['response_time_ms'].max()
            
            error_500_count = len(detail[detail['error_code'] == '500'])
            error_502_504_count = len(detail[detail['error_code'].isin(['502', '504'])])
            
            self.logger.info(
                f"根因定位: 服务 '{top_service}', 主要错误码 '{top_error_code}', "
                f"受影响端点数 {unique_endpoints}, 平均响应时间 {avg_response_time:.0f}ms"
            )
            
            alert = {
                "alert_type": "AppServer_ErrorSpike_Detected",
                "timestamp": ts.isoformat(),
                "severity": "HIGH" if int(row['y']) > 100 else "MEDIUM",
                "description": f"Application error rate {int(row['y'])}/min exceeds threshold {row['yhat_upper']:.2f}/min",
                "entities": {
                    "service": top_service,
                    "error_code": top_error_code,
                    "affected_endpoints": unique_endpoints,
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "max_response_time_ms": max_response_time
                },
                "source_system": "app_server_detector",
                "indicators": {
                    "is_service_degradation": error_502_504_count > 10,
                    "is_internal_error": error_500_count > 20,
                    "is_latency_issue": avg_response_time > 5000,
                    "potential_cascade_failure": unique_endpoints > 20 and error_502_504_count > 15
                }
            }
            
            self._save_alert(alert, ts)
            
        except Exception as e:
            self.logger.error(f"处理异常失败: {e}")


if __name__ == "__main__":
    detector = AppServerDetector()
    success = detector.run_pipeline()
    sys.exit(0 if success else 1)
