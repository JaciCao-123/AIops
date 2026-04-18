#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 数据可视化

功能：
1. CPU 使用率趋势图
2. 多机器对比图
3. 异常点标注
4. 预测结果可视化
"""

import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False


class CPUVisualizer:
    """
    CPU 使用率可视化器
    """
    
    def __init__(self, data_dir, model_dir, report_dir):
        """
        初始化可视化器
        
        Args:
            data_dir: 数据目录
            model_dir: 模型目录
            report_dir: 报告目录
        """
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.report_dir = report_dir
        self.models = {}
    
    def load_models(self):
        """加载所有模型"""
        print(f"📂 加载模型: {self.model_dir}")
        
        for filename in os.listdir(self.model_dir):
            if filename.endswith('_model.pkl'):
                machine_id = filename.replace('_model.pkl', '')
                model_path = os.path.join(self.model_dir, filename)
                
                with open(model_path, 'rb') as f:
                    self.models[machine_id] = pickle.load(f)
                
                print(f"   ✅ {machine_id}")
    
    def plot_cpu_trend(self, df, machine_id, save=True):
        """
        绘制 CPU 使用率趋势图
        
        Args:
            df: 数据
            machine_id: 机器 ID
            save: 是否保存
        """
        print(f"📊 绘制 CPU 趋势图: {machine_id}")
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(df['ds'], df['y'], 'b-', linewidth=0.8, label='CPU 使用率')
        
        if 'is_fault' in df.columns:
            fault_df = df[df['is_fault'] == True]
            if len(fault_df) > 0:
                ax.scatter(fault_df['ds'], fault_df['y'], 
                          c='red', s=20, label='故障点', zorder=5)
        
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('CPU 使用率 (%)', fontsize=12)
        ax.set_title(f'{machine_id} CPU 使用率趋势', fontsize=14)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        plt.xticks(rotation=45)
        
        ax.set_ylim(0, 105)
        
        plt.tight_layout()
        
        if save:
            os.makedirs(self.report_dir, exist_ok=True)
            save_path = os.path.join(self.report_dir, f'{machine_id}_cpu_trend.png')
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"   ✅ 已保存: {save_path}")
        
        plt.close()
    
    def plot_prediction(self, df, machine_id, model_data, save=True):
        """
        绘制预测结果图
        
        Args:
            df: 数据
            machine_id: 机器 ID
            model_data: 模型数据
            save: 是否保存
        """
        print(f"📊 绘制预测图: {machine_id}")
        
        prophet_model = model_data['prophet']
        
        forecast = prophet_model.predict(df[['ds']])
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.plot(df['ds'], df['y'], 'b-', linewidth=0.8, label='实际值', alpha=0.7)
        ax.plot(df['ds'], forecast['yhat'], 'r-', linewidth=1, label='预测值')
        ax.fill_between(df['ds'], forecast['yhat_lower'], forecast['yhat_upper'],
                       color='red', alpha=0.2, label='置信区间')
        
        residual = np.abs(df['y'].values - forecast['yhat'].values)
        threshold = np.percentile(residual, 95)
        anomaly_mask = residual > threshold
        
        ax.scatter(df['ds'][anomaly_mask], df['y'][anomaly_mask],
                  c='orange', s=30, label=f'异常点 (残差>{threshold:.1f})', zorder=5)
        
        if 'is_fault' in df.columns:
            fault_df = df[df['is_fault'] == True]
            if len(fault_df) > 0:
                ax.scatter(fault_df['ds'], fault_df['y'],
                          c='red', s=50, marker='x', label='故障点', zorder=6)
        
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('CPU 使用率 (%)', fontsize=12)
        ax.set_title(f'{machine_id} CPU 使用率预测', fontsize=14)
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        plt.xticks(rotation=45)
        
        ax.set_ylim(0, 105)
        
        plt.tight_layout()
        
        if save:
            os.makedirs(self.report_dir, exist_ok=True)
            save_path = os.path.join(self.report_dir, f'{machine_id}_prediction.png')
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"   ✅ 已保存: {save_path}")
        
        plt.close()
    
    def plot_multi_machine_comparison(self, df, save=True):
        """
        绘制多机器对比图
        
        Args:
            df: 完整数据
            save: 是否保存
        """
        print("📊 绘制多机器对比图...")
        
        machines = df['machine_id'].unique()
        n_machines = len(machines)
        
        fig, axes = plt.subplots(n_machines, 1, figsize=(14, 4 * n_machines))
        
        if n_machines == 1:
            axes = [axes]
        
        for idx, machine_id in enumerate(machines):
            machine_df = df[df['machine_id'] == machine_id]
            
            axes[idx].plot(machine_df['ds'], machine_df['y'], 
                          linewidth=0.8, label=machine_id)
            
            if 'is_fault' in machine_df.columns:
                fault_df = machine_df[machine_df['is_fault'] == True]
                if len(fault_df) > 0:
                    axes[idx].scatter(fault_df['ds'], fault_df['y'],
                                     c='red', s=20, label='故障点')
            
            axes[idx].set_ylabel('CPU (%)', fontsize=10)
            axes[idx].set_title(f'{machine_id}', fontsize=12)
            axes[idx].legend(loc='upper right')
            axes[idx].grid(True, alpha=0.3)
            axes[idx].set_ylim(0, 105)
            
            axes[idx].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            axes[idx].xaxis.set_major_locator(mdates.DayLocator())
        
        axes[-1].set_xlabel('时间', fontsize=12)
        
        plt.suptitle('多机器 CPU 使用率对比', fontsize=14, y=1.02)
        plt.tight_layout()
        
        if save:
            os.makedirs(self.report_dir, exist_ok=True)
            save_path = os.path.join(self.report_dir, 'multi_machine_comparison.png')
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"   ✅ 已保存: {save_path}")
        
        plt.close()
    
    def visualize_all(self):
        """生成所有可视化"""
        print("\n" + "=" * 60)
        print("📊 开始生成可视化")
        print("=" * 60)
        
        combined_path = os.path.join(self.data_dir, 'cpu_usage_cleaned.csv')
        df = pd.read_csv(combined_path)
        df['ds'] = pd.to_datetime(df['ds'])
        
        self.plot_multi_machine_comparison(df)
        
        for machine_id in df['machine_id'].unique():
            machine_df = df[df['machine_id'] == machine_id].copy()
            
            self.plot_cpu_trend(machine_df, machine_id)
            
            if machine_id in self.models:
                self.plot_prediction(machine_df, machine_id, self.models[machine_id])
        
        print("\n✅ 所有可视化已完成")


def main():
    """主函数"""
    print("=" * 60)
    print("Step 4: 数据可视化")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    data_dir = os.path.join(base_dir, 'data', 'cleaned')
    model_dir = os.path.join(base_dir, 'models')
    report_dir = os.path.join(base_dir, 'reports')
    
    visualizer = CPUVisualizer(data_dir, model_dir, report_dir)
    visualizer.load_models()
    visualizer.visualize_all()
    
    return visualizer


if __name__ == "__main__":
    main()
