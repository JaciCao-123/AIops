
import pandas as pd
import numpy as np
import os

# 中国主要法定节假日（按年份组织，简化：忽略调休补班，仅假期日期）
HOLIDAYS = {
    2023: {
        "元旦": ("2023-01-01", "2023-01-02"),
        "春节": ("2023-01-21", "2023-01-27"),
        "清明节": ("2023-04-05", "2023-04-05"),
        "劳动节": ("2023-04-29", "2023-05-03"),
        "端午节": ("2023-06-22", "2023-06-24"),
        "中秋国庆": ("2023-09-29", "2023-10-06"),
    },
    2024: {
        "元旦": ("2024-01-01", "2024-01-01"),
        "春节": ("2024-02-10", "2024-02-17"),
        "清明节": ("2024-04-04", "2024-04-06"),
        "劳动节": ("2024-05-01", "2024-05-05"),
        "端午节": ("2024-06-08", "2024-06-10"),
        "中秋节": ("2024-09-15", "2024-09-17"),
        "国庆节": ("2024-10-01", "2024-10-07"),
    },
}

# 节假日成本波动系数：假期业务量下降，成本按此比例缩减
HOLIDAY_FACTOR = 0.7

# 异常注入日期（2024 年，应落在测试集区间）
ANOMALY_DATES = ("2024-12-27",)


def _holiday_factor(ts: pd.Timestamp) -> float:
    """返回指定时间所属节假日的成本系数，非节假日为 1.0。"""
    year_holidays = HOLIDAYS.get(ts.year, {})
    for _name, (start, end) in year_holidays.items():
        if pd.Timestamp(start) <= ts.normalize() <= pd.Timestamp(end):
            return HOLIDAY_FACTOR
    return 1.0


def generate_cost_data(start="2023-01-01", days=730, output_dir="data/raw"):
    """
    生成模拟的云成本数据（两年，含节假日波动与异常）。

    参数:
    - start (str): 起始日期，默认 2023-01-01。
    - days (int): 生成数据的总天数，默认 730（两年，覆盖完整年周期，
      保证 Prophet 年季节性可稳定学习）。
    - output_dir (str): 原始数据输出目录。
    """
    print(f"--- 步骤 1: 开始生成模拟成本数据 ({start} 起, {days}天, 含节假日波动) ---")

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "cost_raw.csv")
    holiday_path = os.path.join(output_dir, "holidays.csv")

    # 固定随机种子，保证可复现
    rng_noise = np.random.default_rng(7)

    rng = pd.date_range(start, periods=days * 24, freq='h')

    services = ['EC2', 'S3', 'RDS']
    regions = ['us-east-1', 'eu-west-1']
    projects = ['project_a', 'project_b', 'project_c']

    anomaly_dates = set(pd.Timestamp(d) for d in ANOMALY_DATES)
    data = []

    for ts in rng:
        holiday_factor = _holiday_factor(ts)
        for service in services:
            for region in regions:
                for project in projects:
                    # 基础成本 + 日周期 + 周周期 + 年周期 + 趋势 + 噪声
                    base_cost = 0.1
                    daily_cycle = 0.05 * np.sin(2 * np.pi * ts.hour / 24)
                    weekly_cycle = 0.08 * np.sin(2 * np.pi * ts.dayofweek / 7)
                    yearly_cycle = 0.15 * np.sin(2 * np.pi * ts.dayofyear / 365)
                    trend = ts.dayofyear * 0.001
                    noise = rng_noise.normal(0, 0.02)

                    cost = base_cost + daily_cycle + weekly_cycle + yearly_cycle + trend + noise
                    # 节假日成本下调（业务降载）
                    cost *= holiday_factor

                    # 注入异常：指定日期(2024-12-27)的指定项目+服务成本激增 10 倍
                    is_anomaly = (ts.normalize() in anomaly_dates
                                  and service == 'EC2' and project == 'project_a')
                    if is_anomaly and 10 <= ts.hour <= 14:
                        cost *= 10

                    data.append([ts, service, region, project, max(0, cost)])

    df = pd.DataFrame(data, columns=['timestamp', 'service', 'region', 'project_tag', 'cost'])
    df.to_csv(output_path, index=False)

    # 输出节假日表（供 Prophet holidays 参数使用）
    holiday_rows = []
    for year, holidays in HOLIDAYS.items():
        for name, (start_d, end_d) in holidays.items():
            for d in pd.date_range(start_d, end_d):
                holiday_rows.append({"ds": d.strftime("%Y-%m-%d"), "holiday": name})
    pd.DataFrame(holiday_rows).to_csv(holiday_path, index=False)

    print(f"✅ 数据生成完毕，已保存至: {output_path}")
    print(f"✅ 节假日表已保存至: {holiday_path} ({len(holiday_rows)} 天)")
    print(f"💡 节假日成本按 {HOLIDAY_FACTOR} 倍下调，共 {sum(len(v) for v in HOLIDAYS.values())} 个节日")
    print(f"💡 异常注入: {ANOMALY_DATES} (项目 'project_a' 的 'EC2' 服务, 10-14时, 成本×10)")
    print("-" * 20)


if __name__ == "__main__":
    generate_cost_data()
