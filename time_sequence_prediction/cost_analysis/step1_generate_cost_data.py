
import pandas as pd
import numpy as np
import os

def generate_cost_data(days=90, anomaly_day=80, output_dir="data/raw"):
    """
    生成模拟的云成本数据。

    参数:
    - days (int): 生成数据的总天数。
    - anomaly_day (int): 注入异常的日期。
    - output_dir (str): 原始数据输出目录。
    """
    print(f"--- 步骤 1: 开始生成模拟成本数据 ({days}天) ---")
    
    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "cost_raw.csv")

    # 时间序列
    rng = pd.date_range('2023-01-01', periods=days * 24, freq='H')
    
    # 定义成本构成
    services = ['EC2', 'S3', 'RDS']
    regions = ['us-east-1', 'eu-west-1']
    projects = ['project_a', 'project_b', 'project_c']
    
    data = []

    for ts in rng:
        for service in services:
            for region in regions:
                for project in projects:
                    # 基础成本 + 周期性 + 趋势 + 噪声
                    base_cost = 0.1
                    daily_cycle = 0.05 * np.sin(2 * np.pi * ts.hour / 24)
                    weekly_cycle = 0.08 * np.sin(2 * np.pi * ts.dayofweek / 7)
                    trend = ts.dayofyear * 0.001
                    noise = np.random.normal(0, 0.02)
                    
                    cost = base_cost + daily_cycle + weekly_cycle + trend + noise
                    
                    # 注入异常
                    is_anomaly_project = (service == 'EC2' and project == 'project_a')
                    if ts.dayofyear == anomaly_day and ts.hour >= 10 and ts.hour <= 14 and is_anomaly_project:
                        cost *= 5  # 成本激增5倍

                    data.append([ts, service, region, project, max(0, cost)])

    df = pd.DataFrame(data, columns=['timestamp', 'service', 'region', 'project_tag', 'cost'])
    df.to_csv(output_path, index=False)
    
    print(f"✅ 数据生成完毕，已保存至: {output_path}")
    print(f"💡 其中在第 {anomaly_day} 天为项目 'project_a' 的 'EC2' 服务注入了成本异常。")
    print("-" * 20)

if __name__ == "__main__":
    generate_cost_data()
