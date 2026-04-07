
import pandas as pd
import pickle
import os

def predict_cost_anomaly(raw_data_dir="data/raw", model_path="models/prophet_cost_model.pkl", anomaly_day=80):
    """
    加载模型进行预测，并对异常进行根因分析。

    参数:
    - raw_data_dir (str): 包含明细数据的原始数据目录。
    - model_path (str): 训练好的模型路径。
    - anomaly_day (int): 我们期望发现异常的日期。
    """
    print("--- 步骤 4: 开始预测与根因分析 ---")

    # 检查模型和数据是否存在
    if not os.path.exists(model_path):
        print(f"❌ 错误: 模型文件不存在: {model_path}")
        print("请先运行 step3_train_cost_model.py")
        return
        
    raw_data_path = os.path.join(raw_data_dir, "cost_raw.csv")
    if not os.path.exists(raw_data_path):
        print(f"❌ 错误: 原始数据文件不存在: {raw_data_path}")
        return

    # 加载模型
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    print("✅ 模型加载成功。")

    # 加载用于模拟实时数据的全量数据
    df_raw = pd.read_csv(raw_data_path)
    df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
    
    # 聚合得到总成本，模拟监控系统的实时指标
    df_total = df_raw.groupby('timestamp')['cost'].sum().reset_index()
    df_total.columns = ['ds', 'y']

    # 使用模型进行预测
    print("开始对全量数据进行预测...")
    forecast = model.predict(df_total[['ds']])
    
    # 合并实际值和预测值
    result = pd.concat([df_total.set_index('ds'), forecast.set_index('ds')], axis=1)
    
    # 异常检测逻辑
    result['anomaly'] = result.apply(lambda row: row['y'] > row['yhat_upper'], axis=1)
    
    anomalies = result[result['anomaly'] == True]

    if anomalies.empty:
        print("🟢 在数据中未检测到成本异常。")
    else:
        print(f"🔴 检测到 {len(anomalies)} 个成本异常点！")
        
        # 根因分析
        for ts, row in anomalies.iterrows():
            print(f"\n[告警] 时间: {ts}, 实际成本: {row['y']:.2f}, 预期上限: {row['yhat_upper']:.2f}")
            
            # 下钻分析
            print("  -> 开始下钻分析...")
            detail_at_anomaly = df_raw[df_raw['timestamp'] == ts]
            
            # 按维度聚合，寻找贡献最大的部分
            # 这里使用一个简化的逻辑：找出花费最高的项目和服务组合
            root_cause = detail_at_anomaly.sort_values('cost', ascending=False).iloc[0]
            
            print(f"  -> 根因定位: 项目 '{root_cause['project_tag']}' 的 '{root_cause['service']}' 服务成本最高，达到 {root_cause['cost']:.2f}。")

    print("-" * 20)

if __name__ == "__main__":
    predict_cost_anomaly()
