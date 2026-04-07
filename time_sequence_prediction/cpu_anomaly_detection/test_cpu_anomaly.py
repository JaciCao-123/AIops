#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU 异常检测测试脚本
生成测试数据并使用已有模型进行异常检测
"""

import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from collections import deque


def generate_cpu_data(start_time, periods=100, inject_anomaly=True, anomaly_start=50, anomaly_end=60):
    """
    生成 CPU 测试数据
    
    Args:
        start_time: 开始时间
        periods: 数据点数量
        inject_anomaly: 是否注入异常
        anomaly_start: 异常开始索引
        anomaly_end: 异常结束索引
        
    Returns:
        DataFrame
    """
    np.random.seed(42)
    timestamps = pd.date_range(start=start_time, periods=periods, freq='1min')
    
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
        
        is_injected_anomaly = False
        if inject_anomaly and anomaly_start <= i < anomaly_end:
            cpu_usage = min(95, cpu_usage + 40)
            is_injected_anomaly = True
        
        cpu_usage = max(0, min(100, cpu_usage))
        
        data.append({
            'index': i,
            'timestamp': ts,
            'cpu_usage': round(cpu_usage, 2),
            'injected_anomaly': is_injected_anomaly
        })
    
    return pd.DataFrame(data)


def detect_anomalies(df, model_path, residual_threshold=15, if_threshold=-0.3, use_dynamic_threshold=True):
    """
    使用模型检测异常
    
    Args:
        df: 测试数据 DataFrame
        model_path: 模型路径
        residual_threshold: 残差阈值（固定值）
        if_threshold: Isolation Forest 分数阈值
        use_dynamic_threshold: 是否使用动态阈值
        
    Returns:
        检测结果 DataFrame
    """
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    prophet_model = model_data['prophet']
    if_model = model_data['isolation_forest']
    scaler = model_data['scaler']
    machine_id = model_data['machine_id']
    
    results = []
    residual_window = deque(maxlen=30)
    
    for _, row in df.iterrows():
        ts = row['timestamp']
        cpu = row['cpu_usage']
        
        future = pd.DataFrame({'ds': [ts]})
        forecast = prophet_model.predict(future)
        yhat = forecast['yhat'].values[0]
        yhat_lower = forecast['yhat_lower'].values[0]
        yhat_upper = forecast['yhat_upper'].values[0]
        
        residual = abs(cpu - yhat)
        residual_window.append(residual)
        
        if use_dynamic_threshold and len(residual_window) >= 10:
            current_threshold = max(np.percentile(list(residual_window), 95), residual_threshold)
        else:
            current_threshold = residual_threshold
        
        features = np.array([[cpu, ts.hour, ts.minute, ts.weekday()]])
        features_scaled = scaler.transform(features)
        if_score = if_model.decision_function(features_scaled)[0]
        
        prophet_anomaly = residual > current_threshold
        if_anomaly = if_score < if_threshold
        is_anomaly = prophet_anomaly or if_anomaly
        
        if prophet_anomaly and if_anomaly:
            severity = 'high'
        elif prophet_anomaly or if_anomaly:
            severity = 'medium'
        else:
            severity = 'none'
        
        results.append({
            'index': row['index'],
            'timestamp': ts,
            'machine_id': machine_id,
            'actual': cpu,
            'predicted': yhat,
            'yhat_lower': yhat_lower,
            'yhat_upper': yhat_upper,
            'residual': residual,
            'residual_threshold': current_threshold,
            'if_score': if_score,
            'prophet_anomaly': prophet_anomaly,
            'if_anomaly': if_anomaly,
            'is_anomaly': is_anomaly,
            'severity': severity,
            'injected_anomaly': row['injected_anomaly']
        })
    
    return pd.DataFrame(results)


def main():
    print("=" * 80)
    print("CPU 异常检测测试 - 参数调优")
    print("=" * 80)
    
    base_dir = os.path.dirname(__file__)
    model_dir = os.path.join(base_dir, 'models')
    model_path = os.path.join(model_dir, 'server-1_model.pkl')
    
    start_time = datetime(2024, 1, 6, 10, 0, 0)
    print(f"\n📊 生成测试数据...")
    print(f"   - 开始时间: {start_time}")
    print(f"   - 数据点数: 100")
    print(f"   - 异常注入: 索引 50-59 (CPU 飙升 40%)")
    
    test_df = generate_cpu_data(start_time, periods=100, inject_anomaly=True)
    
    print("\n⚠️  注入异常的数据点:")
    print("-" * 60)
    for _, row in test_df[test_df['injected_anomaly']].iterrows():
        print(f"   [{row['index']:3d}] {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} - CPU: {row['cpu_usage']:.1f}%")
    
    print("\n" + "=" * 80)
    print("测试不同参数组合")
    print("=" * 80)
    
    configs = [
        {'name': '默认参数 (动态阈值)', 'residual_threshold': 15, 'if_threshold': -0.3, 'use_dynamic_threshold': True},
        {'name': '固定残差阈值 15', 'residual_threshold': 15, 'if_threshold': -0.3, 'use_dynamic_threshold': False},
        {'name': '固定残差阈值 10', 'residual_threshold': 10, 'if_threshold': -0.3, 'use_dynamic_threshold': False},
        {'name': '固定残差阈值 8', 'residual_threshold': 8, 'if_threshold': -0.3, 'use_dynamic_threshold': False},
        {'name': '降低 IF 阈值 -0.1', 'residual_threshold': 15, 'if_threshold': -0.1, 'use_dynamic_threshold': False},
        {'name': '组合: 残差10 + IF-0.1', 'residual_threshold': 10, 'if_threshold': -0.1, 'use_dynamic_threshold': False},
    ]
    
    print(f"\n{'配置名称':<25} {'召回率':>10} {'精确率':>10} {'TP':>5} {'FP':>5} {'FN':>5}")
    print("-" * 80)
    
    best_config = None
    best_f1 = 0
    
    for config in configs:
        results_df = detect_anomalies(
            test_df, model_path,
            residual_threshold=config['residual_threshold'],
            if_threshold=config['if_threshold'],
            use_dynamic_threshold=config['use_dynamic_threshold']
        )
        
        injected_count = results_df['injected_anomaly'].sum()
        detected_count = results_df['is_anomaly'].sum()
        tp = ((results_df['injected_anomaly']) & (results_df['is_anomaly'])).sum()
        fp = ((~results_df['injected_anomaly']) & (results_df['is_anomaly'])).sum()
        fn = ((results_df['injected_anomaly']) & (~results_df['is_anomaly'])).sum()
        
        recall = tp / injected_count * 100 if injected_count > 0 else 0
        precision = tp / detected_count * 100 if detected_count > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        print(f"{config['name']:<25} {recall:>9.1f}% {precision:>9.1f}% {tp:>5} {fp:>5} {fn:>5}")
        
        if f1 > best_f1:
            best_f1 = f1
            best_config = config
    
    print("\n" + "=" * 80)
    print(f"推荐配置: {best_config['name']}")
    print("=" * 80)
    
    results_df = detect_anomalies(
        test_df, model_path,
        residual_threshold=best_config['residual_threshold'],
        if_threshold=best_config['if_threshold'],
        use_dynamic_threshold=best_config['use_dynamic_threshold']
    )
    
    print("\n检测详情 (推荐配置):")
    print("-" * 100)
    print(f"{'索引':>5} {'时间':<20} {'实际CPU':>8} {'预测CPU':>8} {'残差':>8} {'阈值':>8} {'IF分数':>8} {'状态':<10}")
    print("-" * 100)
    
    for _, row in results_df.iterrows():
        if row['injected_anomaly'] or row['is_anomaly']:
            status = '🔴 异常' if row['is_anomaly'] else '🟢 正常'
            injected = '(注入)' if row['injected_anomaly'] else ''
            
            print(f"{row['index']:>5} "
                  f"{row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{row['actual']:>8.1f} "
                  f"{row['predicted']:>8.1f} "
                  f"{row['residual']:>8.1f} "
                  f"{row['residual_threshold']:>8.1f} "
                  f"{row['if_score']:>8.3f} "
                  f"{status:<10} {injected}")
    
    print("\n" + "=" * 80)
    print("提高召回率的方法总结")
    print("=" * 80)
    print("""
1. 使用固定阈值代替动态阈值
   - 动态阈值会被异常数据拉高，导致后续异常漏检
   - 固定阈值更稳定，但可能增加误报

2. 降低残差阈值
   - 当前默认: 15
   - 推荐值: 8-12
   - 越低越敏感，召回率越高，但精确率可能下降

3. 调整 Isolation Forest 阈值
   - 当前默认: -0.3
   - 推荐值: -0.1 到 0
   - 越高越敏感（更接近0）

4. 组合策略
   - 同时调整残差阈值和IF阈值
   - 使用 OR 逻辑（任一触发即报警）
""")
    
    return results_df


if __name__ == "__main__":
    main()
