
import pandas as pd
import pickle
import os

# 尝试导入Prophet，如果失败则给出提示
try:
    from prophet import Prophet
except ImportError:
    print("❌ 错误: Prophet库未安装。")
    print("请运行: pip install prophet")
    exit()

def train_cost_model(input_dir="data/cleaned", model_dir="models", anomaly_day=80):
    """
    使用清洗后的数据训练Prophet模型。

    参数:
    - input_dir (str): 清洗后数据输入目录。
    - model_dir (str): 模型保存目录。
    - anomaly_day (int): 异常注入的日期，用于从训练数据中排除。
    """
    print("--- 步骤 3: 开始训练成本预测模型 ---")
    
    # 确保目录存在
    os.makedirs(model_dir, exist_ok=True)
    input_path = os.path.join(input_dir, "cost_total_hourly.csv")
    model_path = os.path.join(model_dir, "prophet_cost_model.pkl")

    if not os.path.exists(input_path):
        print(f"❌ 错误: 清洗后的数据文件不存在: {input_path}")
        print("请先运行 step2_clean_cost_data.py")
        return

    df = pd.read_csv(input_path)
    df['ds'] = pd.to_datetime(df['ds'])

    # 从训练数据中排除已知的异常日，防止模型学到异常模式
    train_df = df[df['ds'].dt.dayofyear != anomaly_day]
    print(f"💡 已从训练数据中排除第 {anomaly_day} 天的异常数据。")

    # 初始化并训练模型
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False, # 数据量不够一年，关闭年季节性
        changepoint_prior_scale=0.05
    )
    
    print("模型开始训练...")
    model.fit(train_df)
    print("模型训练完毕。")

    # 保存模型
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"✅ 模型已保存至: {model_path}")
    print("-" * 20)

if __name__ == "__main__":
    train_cost_model()
