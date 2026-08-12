
import pandas as pd
import pickle
import os
import json
import numpy as np

def predict_cost_anomaly(raw_data_dir="data/raw", input_dir="data/cleaned",
                         model_dir="models", margin=0.10):
    """
    加载模型对测试集进行预测、评估，并对异常进行根因分析。

    参数:
    - raw_data_dir (str): 包含明细数据的原始数据目录。
    - input_dir (str): 清洗后的聚合数据目录（cost_total_hourly.csv）。
    - model_dir (str): 模型与划分信息目录。
    - margin (float): 异常判定超出置信上限的最小幅度比例（0.10=超10%），
      用于过滤噪声误报。
    """
    print("--- 步骤 4: 开始预测与根因分析 ---")

    model_path = os.path.join(model_dir, "prophet_cost_model.pkl")
    split_path = os.path.join(model_dir, "split_info.json")
    raw_data_path = os.path.join(raw_data_dir, "cost_raw.csv")
    cleaned_path = os.path.join(input_dir, "cost_total_hourly.csv")

    if not os.path.exists(model_path):
        print(f"❌ 错误: 模型文件不存在: {model_path}")
        print("请先运行 step3_train_cost_model.py")
        return
    if not os.path.exists(split_path):
        print(f"❌ 错误: 划分信息文件不存在: {split_path}")
        return
    if not os.path.exists(cleaned_path):
        print(f"❌ 错误: 聚合数据文件不存在: {cleaned_path}")
        return

    # 加载模型和划分信息
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    with open(split_path, 'r', encoding='utf-8') as f:
        split_info = json.load(f)
    print("✅ 模型与划分信息加载成功。")

    # 加载聚合数据，仅取测试集区间
    df_total = pd.read_csv(cleaned_path)
    df_total['ds'] = pd.to_datetime(df_total['ds'])
    df_total = df_total.sort_values('ds').reset_index(drop=True)

    test_start = pd.to_datetime(split_info['test_start'])
    test_end = pd.to_datetime(split_info['test_end'])
    test_df = df_total[(df_total['ds'] >= test_start) & (df_total['ds'] <= test_end)]
    print(f"📊 测试集区间: {test_start} ~ {test_end} (共 {len(test_df)} 条)")

    # 对测试集进行预测
    print("开始对测试集进行预测...")
    forecast = model.predict(test_df[['ds']])

    # 合并实际值和预测值
    result = pd.concat([test_df.set_index('ds'), forecast.set_index('ds')], axis=1)
    result = result[~result['yhat_upper'].isna()]

    # 回归评估指标（排除已知异常点，评估正常模式拟合能力）
    eval_df = result.copy()
    anomaly_dates = set(pd.Timestamp(d).date() for d in split_info.get('excluded_anomaly_dates', []))
    if anomaly_dates:
        eval_df = eval_df[~pd.Index(eval_df.index.date).isin(anomaly_dates)]

    if len(eval_df) > 0:
        mae = (eval_df['y'] - eval_df['yhat']).abs().mean()
        rmse = np.sqrt(((eval_df['y'] - eval_df['yhat']) ** 2).mean())
        # WAPE: 加权绝对百分比误差，对近零成本值更稳健（MAPE 在 y 接近 0 时失真）
        wape = (eval_df['y'] - eval_df['yhat']).abs().sum() / eval_df['y'].sum() * 100
        print(f"📈 测试集回归评估 (剔除已知异常日, 共 {len(eval_df)} 条):")
        print(f"   MAE  = {mae:.4f}")
        print(f"   RMSE = {rmse:.4f}")
        print(f"   WAPE = {wape:.2f}%")

    # 异常检测逻辑（超出置信上限且超过 margin 幅度才告警，过滤噪声）
    result['anomaly'] = result.apply(
        lambda row: row['y'] > row['yhat_upper'] * (1 + margin), axis=1
    )
    anomalies = result[result['anomaly'] == True]

    if anomalies.empty:
        print("🟢 在测试集中未检测到成本异常。")
    else:
        print(f"🔴 检测到 {len(anomalies)} 个成本异常点！")

        # 根因分析
        for ts, row in anomalies.iterrows():
            print(f"\n[告警] 时间: {ts}, 实际成本: {row['y']:.2f}, 预期上限: {row['yhat_upper']:.2f}")

            # 下钻分析（明细数据）
            print("  -> 开始下钻分析...")
            if os.path.exists(raw_data_path):
                df_raw = pd.read_csv(raw_data_path)
                df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
                detail_at_anomaly = df_raw[df_raw['timestamp'] == ts]

                if not detail_at_anomaly.empty:
                    root_cause = detail_at_anomaly.sort_values('cost', ascending=False).iloc[0]
                    total_at_ts = detail_at_anomaly['cost'].sum()
                    share = root_cause['cost'] / total_at_ts * 100 if total_at_ts else 0
                    print(f"  -> 根因定位: 项目 '{root_cause['project_tag']}' 的 "
                          f"'{root_cause['service']}' 服务成本最高，达到 {root_cause['cost']:.2f} "
                          f"(占该时刻总成本 {share:.1f}%)。")
                else:
                    print("  -> 该时间点无明细数据。")
            else:
                print(f"  -> 原始明细数据不存在: {raw_data_path}")

    print("-" * 20)

if __name__ == "__main__":
    predict_cost_anomaly()
