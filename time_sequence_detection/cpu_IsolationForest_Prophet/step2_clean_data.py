#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 2: 数据清洗

功能：
1. 处理缺失值
2. 处理超出范围的值（0-100%）
3. 去除重复记录
4. 转换为 Prophet 格式
5. 按机器分组保存
"""

import os
import numpy as np
import pandas as pd


class CPUDataCleaner:
    """
    CPU 使用率数据清洗器
    """
    
    def __init__(self, input_path, output_dir):
        """
        初始化清洗器
        
        Args:
            input_path: 输入文件路径
            output_dir: 输出目录
        """
        self.input_path = input_path
        self.output_dir = output_dir
        self.clean_report = {}
    
    def load(self):
        """加载原始数据"""
        print(f"📂 加载原始数据: {self.input_path}")
        df = pd.read_csv(self.input_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        print(f"   - 记录数: {len(df)}")
        print(f"   - 机器数: {df['machine_id'].nunique()}")
        print(f"   - 时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
        
        return df
    
    def clean(self, df):
        """
        清洗数据
        
        Args:
            df: 原始数据
            
        Returns:
            清洗后的数据字典（按机器分组）
        """
        print("\n🔄 开始数据清洗...")
        
        original_count = len(df)
        
        missing_count = df['cpu_usage'].isnull().sum()
        self.clean_report['missing_values'] = missing_count
        print(f"   [1/5] 缺失值检测: 发现 {missing_count} 个缺失值")
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        before_dedup = len(df)
        df = df.drop_duplicates(subset=['timestamp', 'machine_id'])
        after_dedup = len(df)
        duplicates_removed = before_dedup - after_dedup
        self.clean_report['duplicates_removed'] = duplicates_removed
        print(f"   [2/5] 去重处理: 移除 {duplicates_removed} 条重复记录")
        
        out_of_range_high = (df['cpu_usage'] > 100).sum()
        out_of_range_low = (df['cpu_usage'] < 0).sum()
        self.clean_report['out_of_range_high'] = out_of_range_high
        self.clean_report['out_of_range_low'] = out_of_range_low
        print(f"   [3/5] 范围检测: >100% 有 {out_of_range_high} 个, <0% 有 {out_of_range_low} 个")
        
        df['cpu_usage'] = df['cpu_usage'].clip(0, 100)
        
        machines_data = {}
        for machine_id in df['machine_id'].unique():
            machine_df = df[df['machine_id'] == machine_id].copy()
            
            prophet_df = machine_df[['timestamp', 'cpu_usage']].copy()
            prophet_df.columns = ['ds', 'y']
            
            machines_data[machine_id] = {
                'prophet': prophet_df,
                'full': machine_df
            }
        
        print(f"   [4/5] 格式转换: Prophet 格式 (ds, y)")
        print(f"   [5/5] 按机器分组: {len(machines_data)} 台机器")
        
        self.clean_report['original_count'] = original_count
        self.clean_report['cleaned_count'] = len(df)
        self.clean_report['retention_rate'] = len(df) / original_count * 100
        self.clean_report['machines'] = len(machines_data)
        
        return machines_data
    
    def save(self, machines_data):
        """
        保存清洗后的数据
        
        Args:
            machines_data: 按机器分组的数据
        """
        os.makedirs(self.output_dir, exist_ok=True)
        
        all_prophet_data = []
        
        for machine_id, data in machines_data.items():
            prophet_df = data['prophet']
            prophet_df['machine_id'] = machine_id
            all_prophet_data.append(prophet_df)
            
            machine_path = os.path.join(self.output_dir, f'{machine_id}_cleaned.csv')
            prophet_df[['ds', 'y']].to_csv(machine_path, index=False)
            print(f"   ✅ {machine_id}: {len(prophet_df)} 条记录")
        
        combined_df = pd.concat(all_prophet_data, ignore_index=True)
        combined_path = os.path.join(self.output_dir, 'cpu_usage_cleaned.csv')
        combined_df.to_csv(combined_path, index=False)
        print(f"\n✅ 合并数据已保存: {combined_path}")
    
    def print_report(self):
        """打印清洗报告"""
        print("\n" + "=" * 60)
        print("📋 数据清洗报告")
        print("=" * 60)
        print(f"原始记录数: {self.clean_report['original_count']}")
        print(f"清洗后记录数: {self.clean_report['cleaned_count']}")
        print(f"数据保留率: {self.clean_report['retention_rate']:.2f}%")
        print(f"缺失值: {self.clean_report['missing_values']}")
        print(f"重复记录: {self.clean_report['duplicates_removed']}")
        print(f"超出范围(>100%): {self.clean_report['out_of_range_high']}")
        print(f"超出范围(<0%): {self.clean_report['out_of_range_low']}")
        print(f"机器数量: {self.clean_report['machines']}")


def main():
    """主函数"""
    print("=" * 60)
    print("Step 2: 数据清洗")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    input_path = os.path.join(base_dir, 'data', 'raw', 'cpu_usage_raw.csv')
    output_dir = os.path.join(base_dir, 'data', 'cleaned')
    
    cleaner = CPUDataCleaner(input_path, output_dir)
    
    df = cleaner.load()
    machines_data = cleaner.clean(df)
    cleaner.save(machines_data)
    cleaner.print_report()
    
    return machines_data


if __name__ == "__main__":
    main()
