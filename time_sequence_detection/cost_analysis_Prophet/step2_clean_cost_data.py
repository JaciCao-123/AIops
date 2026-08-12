
import pandas as pd
import os

def clean_cost_data(input_dir="data/raw", output_dir="data/cleaned"):
    """
    清洗和聚合原始成本数据，为训练做准备。

    参数:
    - input_dir (str): 原始数据输入目录。
    - output_dir (str): 清洗后数据输出目录。
    """
    print("--- 步骤 2: 开始清洗和聚合数据 ---")

    os.makedirs(output_dir, exist_ok=True)
    input_path = os.path.join(input_dir, "cost_raw.csv")
    output_path = os.path.join(output_dir, "cost_total_hourly.csv")

    if not os.path.exists(input_path):
        print(f"❌ 错误: 原始数据文件不存在: {input_path}")
        print("请先运行 step1_generate_cost_data.py")
        return

    df = pd.read_csv(input_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # 按小时聚合总成本
    df_total = df.groupby('timestamp')['cost'].sum().reset_index()
    df_total.columns = ['ds', 'y']  # 重命名以符合Prophet的要求

    df_total.to_csv(output_path, index=False)

    print(f"✅ 数据清洗和聚合完毕，已保存至: {output_path}")
    print(f"  共 {len(df_total)} 条小时级记录 ({df_total['ds'].min()} ~ {df_total['ds'].max()})")
    print("-" * 20)

if __name__ == "__main__":
    clean_cost_data()
