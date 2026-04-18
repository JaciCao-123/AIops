#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: 模型训练

功能：
1. 使用 Prophet 训练时序预测模型（处理周期性）
2. 使用 Isolation Forest 训练异常检测模型
3. 集成两种模型进行综合检测
4. 模型验证和评估
"""

import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

try:
    from prophet import Prophet
    USE_PROPHET = True
    print("✅ 使用 Prophet 进行时序预测")
except ImportError:
    from statsmodels.tsa.seasonal import STL
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    USE_PROPHET = False
    print("⚠️ Prophet 未安装，降级使用 statsmodels")

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error


class CPUModelTrainer:
    """
    CPU 使用率模型训练器
    集成 Prophet 和 Isolation Forest
    """
    
    def __init__(self, data_dir, model_dir):
        """
        初始化训练器
        
        Args:
            data_dir: 数据目录
            model_dir: 模型保存目录
        """
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.prophet_models = {}
        self.if_models = {}
        self.scalers = {}
        self.train_report = {}
    
    def load_data(self):
        """加载清洗后的数据"""
        print(f"📂 加载清洗数据: {self.data_dir}")
        
        combined_path = os.path.join(self.data_dir, 'cpu_usage_cleaned.csv')
        df = pd.read_csv(combined_path)
        df['ds'] = pd.to_datetime(df['ds'])
        
        print(f"   - 总记录数: {len(df)}")
        print(f"   - 机器数: {df['machine_id'].nunique()}")
        print(f"   - 时间范围: {df['ds'].min()} ~ {df['ds'].max()}")
        
        return df
    
    def train_prophet(self, df, machine_id):
        """
        训练 Prophet 模型
        
        Args:
            df: 单台机器的数据
            machine_id: 机器 ID
            
        Returns:
            训练好的 Prophet 模型
        """
        print(f"\n🚀 训练 Prophet 模型: {machine_id}")
        
        start_time = datetime.now()
        
        model = Prophet(
            growth='linear',
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,
            interval_width=0.95,
            changepoint_prior_scale=0.01
        )
        
        model.fit(df[['ds', 'y']])
        
        train_time = (datetime.now() - start_time).total_seconds()
        print(f"   ✅ Prophet 训练完成 (耗时: {train_time:.2f}秒)")
        
        return model, train_time
    
    def train_isolation_forest(self, df, machine_id):
        """
        训练 Isolation Forest 模型
        
        Args:
            df: 单台机器的数据
            machine_id: 机器 ID
            
        Returns:
            训练好的 Isolation Forest 模型和标准化器
        """
        print(f"🌲 训练 Isolation Forest 模型: {machine_id}")
        
        start_time = datetime.now()
        
        df['hour'] = df['ds'].dt.hour
        df['minute'] = df['ds'].dt.minute
        df['weekday'] = df['ds'].dt.weekday
        
        features = ['y', 'hour', 'minute', 'weekday']
        X = df[features].values
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_scaled)
        
        train_time = (datetime.now() - start_time).total_seconds()
        print(f"   ✅ Isolation Forest 训练完成 (耗时: {train_time:.2f}秒)")
        
        return model, scaler, train_time
    
    def validate(self, df, machine_id, prophet_model, if_model, scaler):
        """
        验证模型效果
        
        Args:
            df: 数据
            machine_id: 机器 ID
            prophet_model: Prophet 模型
            if_model: Isolation Forest 模型
            scaler: 标准化器
            
        Returns:
            验证指标
        """
        print(f"📈 验证模型: {machine_id}")
        
        train_size = int(len(df) * 0.8)
        train_df = df.iloc[:train_size]
        test_df = df.iloc[train_size:]
        
        print(f"   - 训练集: {len(train_df)} 条")
        print(f"   - 测试集: {len(test_df)} 条")
        
        forecast = prophet_model.predict(test_df[['ds']])
        
        y_true = test_df['y'].values
        y_pred = forecast['yhat'].values
        
        mae = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        
        mape = np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + 1e-8))) * 100
        
        test_features = test_df.copy()
        test_features['hour'] = test_features['ds'].dt.hour
        test_features['minute'] = test_features['ds'].dt.minute
        test_features['weekday'] = test_features['ds'].dt.weekday
        
        X_test = test_features[['y', 'hour', 'minute', 'weekday']].values
        X_test_scaled = scaler.transform(X_test)
        
        if_scores = if_model.decision_function(X_test_scaled)
        if_predictions = if_model.predict(X_test_scaled)
        
        if_anomaly_rate = (if_predictions == -1).sum() / len(if_predictions) * 100
        
        print(f"   - MAE: {mae:.4f}")
        print(f"   - RMSE: {rmse:.4f}")
        print(f"   - MAPE: {mape:.2f}%")
        print(f"   - IF 异常率: {if_anomaly_rate:.2f}%")
        
        return {
            'mae': mae,
            'rmse': rmse,
            'mape': mape,
            'if_anomaly_rate': if_anomaly_rate
        }
    
    def save_models(self, machine_id, prophet_model, if_model, scaler):
        """
        保存模型
        
        Args:
            machine_id: 机器 ID
            prophet_model: Prophet 模型
            if_model: Isolation Forest 模型
            scaler: 标准化器
        """
        os.makedirs(self.model_dir, exist_ok=True)
        
        model_data = {
            'prophet': prophet_model,
            'isolation_forest': if_model,
            'scaler': scaler,
            'machine_id': machine_id,
            'train_time': datetime.now().isoformat()
        }
        
        model_path = os.path.join(self.model_dir, f'{machine_id}_model.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"   ✅ 模型已保存: {model_path}")
    
    def train_all(self, df):
        """
        训练所有机器的模型
        
        Args:
            df: 完整数据
        """
        print("\n" + "=" * 60)
        print("🚀 开始训练所有机器的模型")
        print("=" * 60)
        
        machines = df['machine_id'].unique()
        all_metrics = {}
        
        for machine_id in machines:
            print(f"\n{'='*60}")
            print(f"📊 处理机器: {machine_id}")
            print("=" * 60)
            
            machine_df = df[df['machine_id'] == machine_id].copy()
            machine_df = machine_df.sort_values('ds')
            
            prophet_model, prophet_time = self.train_prophet(machine_df, machine_id)
            if_model, scaler, if_time = self.train_isolation_forest(machine_df, machine_id)
            
            metrics = self.validate(machine_df, machine_id, prophet_model, if_model, scaler)
            metrics['prophet_train_time'] = prophet_time
            metrics['if_train_time'] = if_time
            
            self.save_models(machine_id, prophet_model, if_model, scaler)
            
            self.prophet_models[machine_id] = prophet_model
            self.if_models[machine_id] = if_model
            self.scalers[machine_id] = scaler
            all_metrics[machine_id] = metrics
        
        self.train_report['machines'] = len(machines)
        self.train_report['metrics'] = all_metrics
        
        return all_metrics
    
    def print_report(self):
        """打印训练报告"""
        print("\n" + "=" * 60)
        print("📋 模型训练报告")
        print("=" * 60)
        print(f"训练机器数: {self.train_report['machines']}")
        
        print("\n各机器验证指标:")
        print("-" * 60)
        print(f"{'机器':<15} {'MAE':>8} {'RMSE':>8} {'MAPE':>10} {'IF异常率':>10}")
        print("-" * 60)
        
        for machine_id, metrics in self.train_report['metrics'].items():
            print(f"{machine_id:<15} "
                  f"{metrics['mae']:>8.2f} "
                  f"{metrics['rmse']:>8.2f} "
                  f"{metrics['mape']:>9.2f}% "
                  f"{metrics['if_anomaly_rate']:>9.2f}%")


def main():
    """主函数"""
    print("=" * 60)
    print("Step 3: 模型训练")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, 'data', 'cleaned')
    model_dir = os.path.join(base_dir, 'models')
    
    trainer = CPUModelTrainer(data_dir, model_dir)
    
    df = trainer.load_data()
    trainer.train_all(df)
    trainer.print_report()
    
    return trainer


if __name__ == "__main__":
    main()
