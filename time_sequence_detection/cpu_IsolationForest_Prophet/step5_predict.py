#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5: 实时异常检测

功能：
1. 加载训练好的模型
2. 实时预测 CPU 使用率
3. 双重检测机制：Prophet 残差 + Isolation Forest
4. 分位数阈值检测
5. 告警降噪
"""

import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import deque


class CPUAnomalyDetector:
    """
    CPU 异常检测器
    集成 Prophet 和 Isolation Forest 双重检测
    """
    
    def __init__(self, model_path, window_size=30, percentile=95, 
                 residual_threshold=15, if_threshold=-0.3):
        """
        初始化检测器
        
        Args:
            model_path: 模型文件路径
            window_size: 滑动窗口大小
            percentile: 分位数阈值
            residual_threshold: 残差阈值（绝对值）
            if_threshold: Isolation Forest 分数阈值
        """
        self.model_path = model_path
        self.window_size = window_size
        self.percentile = percentile
        self.residual_threshold = residual_threshold
        self.if_threshold = if_threshold
        
        self.residual_window = deque(maxlen=window_size)
        
        self.prophet_model = None
        self.if_model = None
        self.scaler = None
        self.machine_id = None
        
        self._load_model()
    
    def _load_model(self):
        """加载模型"""
        print(f"📂 加载模型: {self.model_path}")
        
        with open(self.model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.prophet_model = model_data['prophet']
        self.if_model = model_data['isolation_forest']
        self.scaler = model_data['scaler']
        self.machine_id = model_data['machine_id']
        
        print(f"   - 机器: {self.machine_id}")
        print(f"   - Prophet 模型: ✅")
        print(f"   - Isolation Forest: ✅")
    
    def predict(self, timestamp):
        """
        预测单个时间点的 CPU 使用率
        
        Args:
            timestamp: 时间戳
            
        Returns:
            预测结果字典
        """
        future = pd.DataFrame({'ds': [timestamp]})
        forecast = self.prophet_model.predict(future)
        
        return {
            'yhat': forecast['yhat'].values[0],
            'yhat_lower': forecast['yhat_lower'].values[0],
            'yhat_upper': forecast['yhat_upper'].values[0]
        }
    
    def _calculate_if_score(self, timestamp, cpu_usage):
        """
        计算 Isolation Forest 异常分数
        
        Args:
            timestamp: 时间戳
            cpu_usage: CPU 使用率
            
        Returns:
            异常分数
        """
        features = np.array([[
            cpu_usage,
            timestamp.hour,
            timestamp.minute,
            timestamp.weekday()
        ]])
        
        features_scaled = self.scaler.transform(features)
        
        score = self.if_model.decision_function(features_scaled)[0]
        
        return score
    
    def detect(self, timestamp, cpu_usage):
        """
        检测异常
        双重检测机制：Prophet 残差 + Isolation Forest
        
        Args:
            timestamp: 时间戳
            cpu_usage: 实际 CPU 使用率
            
        Returns:
            检测结果字典
        """
        pred = self.predict(timestamp)
        yhat = pred['yhat']
        
        residual = abs(cpu_usage - yhat)
        
        self.residual_window.append(residual)
        
        if len(self.residual_window) >= 10:
            residual_threshold = np.percentile(list(self.residual_window), self.percentile)
            residual_threshold = max(residual_threshold, self.residual_threshold)
        else:
            residual_threshold = self.residual_threshold
        
        prophet_anomaly = residual > residual_threshold
        
        if_score = self._calculate_if_score(timestamp, cpu_usage)
        if_anomaly = if_score < self.if_threshold
        
        is_anomaly = prophet_anomaly or if_anomaly
        
        if prophet_anomaly and if_anomaly:
            severity = 'high'
        elif prophet_anomaly or if_anomaly:
            severity = 'medium'
        else:
            severity = 'none'
        
        return {
            'timestamp': timestamp,
            'machine_id': self.machine_id,
            'actual': cpu_usage,
            'predicted': yhat,
            'yhat_lower': pred['yhat_lower'],
            'yhat_upper': pred['yhat_upper'],
            'residual': residual,
            'residual_threshold': residual_threshold,
            'if_score': if_score,
            'if_threshold': self.if_threshold,
            'prophet_anomaly': prophet_anomaly,
            'if_anomaly': if_anomaly,
            'is_anomaly': is_anomaly,
            'severity': severity
        }


class AlertManager:
    """
    告警管理器
    实现告警降噪和状态管理
    """
    
    def __init__(self, consecutive_threshold=2, cooldown_minutes=5):
        """
        初始化告警管理器
        
        Args:
            consecutive_threshold: 连续异常次数阈值
            cooldown_minutes: 告警冷却时间（分钟）
        """
        self.consecutive_threshold = consecutive_threshold
        self.cooldown_minutes = cooldown_minutes
        
        self.consecutive_count = 0
        self.alert_status = False
        self.last_alert_time = None
        self.alert_history = []
    
    def update(self, is_anomaly, severity, timestamp):
        """
        更新告警状态
        
        Args:
            is_anomaly: 是否检测到异常
            severity: 严重程度
            timestamp: 时间戳
            
        Returns:
            是否触发告警
        """
        if is_anomaly:
            self.consecutive_count += 1
            
            if self.consecutive_count >= self.consecutive_threshold:
                if self.last_alert_time is None or \
                   (timestamp - self.last_alert_time).total_seconds() >= self.cooldown_minutes * 60:
                    
                    if not self.alert_status:
                        self.alert_status = True
                        self.last_alert_time = timestamp
                        
                        self.alert_history.append({
                            'timestamp': timestamp,
                            'severity': severity,
                            'consecutive_count': self.consecutive_count
                        })
                        
                        return True
        else:
            self.consecutive_count = 0
            self.alert_status = False
        
        return False
    
    def get_alert_summary(self):
        """获取告警摘要"""
        return {
            'total_alerts': len(self.alert_history),
            'high_severity': sum(1 for a in self.alert_history if a['severity'] == 'high'),
            'medium_severity': sum(1 for a in self.alert_history if a['severity'] == 'medium')
        }


class CPUPredictor:
    """
    CPU 预测器
    整合检测和告警功能
    """
    
    def __init__(self, model_dir, window_size=30, percentile=95,
                 residual_threshold=15, if_threshold=-0.3, consecutive_threshold=2):
        """
        初始化预测器
        
        Args:
            model_dir: 模型目录
            window_size: 滑动窗口大小
            percentile: 分位数阈值
            residual_threshold: 残差阈值
            if_threshold: IF 分数阈值
            consecutive_threshold: 连续异常阈值
        """
        self.model_dir = model_dir
        self.detectors = {}
        self.alert_managers = {}
        
        self._load_all_models(window_size, percentile, residual_threshold, if_threshold)
        
        for machine_id in self.detectors:
            self.alert_managers[machine_id] = AlertManager(consecutive_threshold)
        
        self.results = []
    
    def _load_all_models(self, window_size, percentile, residual_threshold, if_threshold):
        """加载所有机器的模型"""
        print(f"📂 加载所有模型: {self.model_dir}")
        
        for filename in os.listdir(self.model_dir):
            if filename.endswith('_model.pkl'):
                model_path = os.path.join(self.model_dir, filename)
                
                detector = CPUAnomalyDetector(
                    model_path=model_path,
                    window_size=window_size,
                    percentile=percentile,
                    residual_threshold=residual_threshold,
                    if_threshold=if_threshold
                )
                
                self.detectors[detector.machine_id] = detector
    
    def process_single(self, machine_id, timestamp, cpu_usage):
        """
        处理单个数据点
        
        Args:
            machine_id: 机器 ID
            timestamp: 时间戳
            cpu_usage: CPU 使用率
            
        Returns:
            处理结果
        """
        if machine_id not in self.detectors:
            return None
        
        detector = self.detectors[machine_id]
        alert_manager = self.alert_managers[machine_id]
        
        result = detector.detect(timestamp, cpu_usage)
        
        is_alert = alert_manager.update(
            result['is_anomaly'],
            result['severity'],
            timestamp
        )
        
        result['is_alert'] = is_alert
        
        self.results.append(result)
        
        return result
    
    def process_batch(self, df):
        """
        批量处理数据
        
        Args:
            df: 数据 DataFrame
            
        Returns:
            处理结果列表
        """
        print(f"\n🔄 批量处理 {len(df)} 个数据点...")
        
        for _, row in df.iterrows():
            self.process_single(
                row['machine_id'],
                row['ds'] if 'ds' in row else row['timestamp'],
                row['y'] if 'y' in row else row['cpu_usage']
            )
        
        return self.results
    
    def print_summary(self):
        """打印处理摘要"""
        total = len(self.results)
        anomalies = sum(1 for r in self.results if r['is_anomaly'])
        high_severity = sum(1 for r in self.results if r['severity'] == 'high')
        medium_severity = sum(1 for r in self.results if r['severity'] == 'medium')
        
        print("\n" + "=" * 60)
        print("📋 预测结果摘要")
        print("=" * 60)
        print(f"处理数据点: {total}")
        print(f"检测异常点: {anomalies} ({anomalies/total*100:.1f}%)")
        print(f"高严重度: {high_severity}")
        print(f"中严重度: {medium_severity}")
        
        print("\n各机器告警统计:")
        for machine_id, alert_manager in self.alert_managers.items():
            summary = alert_manager.get_alert_summary()
            print(f"   {machine_id}: {summary['total_alerts']} 次告警 "
                  f"(高: {summary['high_severity']}, 中: {summary['medium_severity']})")


def generate_test_data(start_time, periods=100, freq='1min', inject_anomaly=True):
    """
    生成测试数据
    
    Args:
        start_time: 开始时间
        periods: 数据点数量
        freq: 时间频率
        inject_anomaly: 是否注入异常
        
    Returns:
        DataFrame
    """
    timestamps = pd.date_range(start=start_time, periods=periods, freq=freq)
    
    data = []
    
    for i, ts in enumerate(timestamps):
        hour = ts.hour
        minute = ts.minute
        weekday = ts.weekday()
        
        if 9 <= hour <= 18:
            daily = 30 + 20 * np.sin(2 * np.pi * (hour - 9 + minute/60) / 9)
        else:
            daily = 15 + 5 * np.sin(2 * np.pi * hour / 24)
        
        weekly = 1.0 if weekday < 5 else 0.6
        
        cpu_usage = 20 + daily * weekly + np.random.uniform(-3, 3)
        
        if inject_anomaly and 50 <= i < 60:
            cpu_usage = min(95, cpu_usage + 40)
        
        cpu_usage = max(0, min(100, cpu_usage))
        
        data.append({
            'ds': ts,
            'y': round(cpu_usage, 2)
        })
    
    return pd.DataFrame(data)


def main():
    """主函数"""
    print("=" * 60)
    print("Step 5: 实时异常检测")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    model_dir = os.path.join(base_dir, 'models')
    
    predictor = CPUPredictor(
        model_dir=model_dir,
        window_size=30,
        percentile=95,
        residual_threshold=15,
        if_threshold=-0.3,
        consecutive_threshold=2
    )
    
    start_time = datetime(2024, 1, 6, 10, 0, 0)
    test_df = generate_test_data(start_time, periods=100, inject_anomaly=True)
    test_df['machine_id'] = 'server-1'
    
    print("\n📊 实时检测结果:")
    print("-" * 120)
    print(f"{'时间戳':<20} {'机器':<12} {'实际值':>8} {'预测值':>8} {'残差':>8} "
          f"{'IF分数':>8} {'Prophet':>8} {'IF':>8} {'严重度':<8} {'状态':<10}")
    print("-" * 120)
    
    for _, row in test_df.iterrows():
        result = predictor.process_single(
            row['machine_id'],
            row['ds'],
            row['y']
        )
        
        if result:
            if result['is_alert']:
                status = "🔴 告警"
            elif result['is_anomaly']:
                status = "🟡 异常"
            else:
                status = "🟢 正常"
            
            print(f"{result['timestamp'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{result['machine_id']:<12} "
                  f"{result['actual']:>8.1f} "
                  f"{result['predicted']:>8.1f} "
                  f"{result['residual']:>8.1f} "
                  f"{result['if_score']:>8.3f} "
                  f"{'⚠️' if result['prophet_anomaly'] else '✅':>8} "
                  f"{'⚠️' if result['if_anomaly'] else '✅':>8} "
                  f"{result['severity']:<8} "
                  f"{status:<10}")
    
    predictor.print_summary()
    
    return predictor


if __name__ == "__main__":
    main()
