
import pandas as pd
import pickle
import os
import json

# 尝试导入Prophet，如果失败则给出提示
try:
    from prophet import Prophet
except ImportError:
    print("❌ 错误: Prophet库未安装。")
    print("请运行: pip install prophet")
    exit()

def train_cost_model(input_dir="data/cleaned", raw_dir="data/raw", model_dir="models",
                     train_ratio=0.8, anomaly_dates=("2024-12-27",)):
    """
    使用清洗后的数据训练Prophet模型，并按时间划分训练集/测试集。

    参数:
    - input_dir (str): 清洗后数据输入目录。
    - raw_dir (str): 原始数据目录（读取节假日表 holidays.csv）。
    - model_dir (str): 模型保存目录。
    - train_ratio (float): 训练集占比（按时间顺序，默认 0.8）。
    - anomaly_dates (tuple): 需要从训练集中排除的异常日期（YYYY-MM-DD）。
    """
    print("--- 步骤 3: 开始训练成本预测模型 (含训练/测试集划分) ---")

    os.makedirs(model_dir, exist_ok=True)
    input_path = os.path.join(input_dir, "cost_total_hourly.csv")
    holiday_path = os.path.join(raw_dir, "holidays.csv")
    model_path = os.path.join(model_dir, "prophet_cost_model.pkl")
    split_path = os.path.join(model_dir, "split_info.json")

    if not os.path.exists(input_path):
        print(f"❌ 错误: 清洗后的数据文件不存在: {input_path}")
        print("请先运行 step2_clean_cost_data.py")
        return

    df = pd.read_csv(input_path)
    df['ds'] = pd.to_datetime(df['ds'])
    df = df.sort_values('ds').reset_index(drop=True)

    # 按时间顺序划分训练集 / 测试集
    split_idx = int(len(df) * train_ratio)
    split_date = df.loc[split_idx, 'ds']
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    print(f"📊 数据划分: 共 {len(df)} 条 | 训练集 {len(train_df)} 条 | 测试集 {len(test_df)} 条")
    print(f"   训练截止: {train_df['ds'].max()} | 测试开始: {test_df['ds'].min()}")

    # 从训练数据中排除已知的异常日，防止模型学到异常模式
    anomaly_dates = set(pd.Timestamp(d).date() for d in anomaly_dates)
    before = len(train_df)
    train_df = train_df[~train_df['ds'].dt.date.isin(anomaly_dates)]
    excluded = before - len(train_df)
    if excluded:
        print(f"💡 已从训练数据中排除异常日: {sorted(str(d) for d in anomaly_dates)} (共 {excluded} 条)")

    # 构建节假日回归器（Prophet holidays）
    holidays = None
    if os.path.exists(holiday_path):
        h = pd.read_csv(holiday_path)
        h['ds'] = pd.to_datetime(h['ds'])
        holidays = h[['ds', 'holiday']].rename(columns={"holiday": "holiday"})
        holidays['lower_window'] = 0
        holidays['upper_window'] = 0
        print(f"📅 已加载 {len(holidays)} 个节假日用于模型训练")
    else:
        print("⚠️ 未找到节假日表 holidays.csv，跳过节假日建模")

    # 初始化并训练模型（传入节假日回归器）
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=True,   # 数据覆盖全年，开启年季节性
        changepoint_prior_scale=0.05,
        seasonality_mode='additive',
        interval_width=0.68,       # 1σ 置信区间，提高异常检测灵敏度
        holidays=holidays          # 自定义节假日表优先于内置国家节假日
    )

    print("模型开始训练...")
    model.fit(train_df)
    print("模型训练完毕。")

    # 保存模型和划分信息
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    split_info = {
        "train_ratio": train_ratio,
        "split_date": split_date.strftime("%Y-%m-%d %H:%M:%S"),
        "train_start": train_df['ds'].min().strftime("%Y-%m-%d %H:%M:%S"),
        "train_end": train_df['ds'].max().strftime("%Y-%m-%d %H:%M:%S"),
        "test_start": test_df['ds'].min().strftime("%Y-%m-%d %H:%M:%S"),
        "test_end": test_df['ds'].max().strftime("%Y-%m-%d %H:%M:%S"),
        "train_size": len(train_df),
        "test_size": len(test_df),
        "excluded_anomaly_dates": sorted(str(d) for d in anomaly_dates),
        "holidays_used": list(holidays['holiday'].unique()) if holidays is not None else []
    }
    with open(split_path, 'w', encoding='utf-8') as f:
        json.dump(split_info, f, ensure_ascii=False, indent=2)

    print(f"✅ 模型已保存至: {model_path}")
    print(f"✅ 划分信息已保存至: {split_path}")
    print("-" * 20)

if __name__ == "__main__":
    train_cost_model()
