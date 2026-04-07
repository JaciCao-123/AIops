#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 生成 CPU 使用率模拟数据

功能：
1. 模拟多台机器的 CPU 使用率数据
2. 包含日周期性（工作时间高、夜间低）
3. 包含周周期性（工作日高、周末低）
4. 注入突发高峰（定时任务）
5. 注入故障（持续高 CPU、CPU 突增、CPU 异常低）
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class CPUDataGenerator:
    """
    CPU 使用率数据生成器
    模拟真实服务器 CPU 使用率的各种模式
    """
    
    def __init__(self, machines, start_time, days=7, freq='1min'):
        """
        初始化数据生成器
        
        Args:
            machines: 机器列表
            start_time: 开始时间
            days: 生成数据的天数
            freq: 数据频率
        """
        self.machines = machines
        self.start_time = start_time
        self.days = days
        self.freq = freq
        
        self.fault_periods = []
        self.burst_periods = []
        
        self.generation_report = {}
    
    def _daily_pattern(self, hour, minute):
        """
        日周期模式
        工作时间（9:00-18:00）CPU 使用率较高
        
        Args:
            hour: 小时
            minute: 分钟
            
        Returns:
            CPU 使用率增量
        """
        if 9 <= hour <= 18:
            progress = (hour - 9 + minute / 60) / 9
            return 25 + 15 * np.sin(2 * np.pi * progress)
        else:
            if hour < 9:
                base = 10
                progress = (hour + minute / 60) / 9
            else:
                base = 10
                progress = (hour - 18 + minute / 60) / 6
            return base + 5 * np.sin(2 * np.pi * progress / 2)
    
    def _weekly_pattern(self, weekday):
        """
        周周期模式
        工作日 CPU 使用率较高，周末较低
        
        Args:
            weekday: 星期几（0=周一，6=周日）
            
        Returns:
            系数
        """
        if weekday < 5:
            return 1.0
        else:
            return 0.6
    
    def _generate_burst(self, ts, machine_idx):
        """
        生成突发高峰（定时任务、批处理）
        
        Args:
            ts: 时间戳
            machine_idx: 机器索引
            
        Returns:
            突发增量
        """
        hour = ts.hour
        minute = ts.minute
        
        burst_value = 0
        
        if hour == 2 and 0 <= minute < 30:
            burst_value = 30 + np.random.uniform(0, 10)
        
        if hour == 14 and 30 <= minute < 45:
            if machine_idx % 2 == 0:
                burst_value = 20 + np.random.uniform(0, 5)
        
        return burst_value
    
    def _is_in_fault_period(self, ts, machine_idx):
        """
        判断是否在故障期间
        
        Args:
            ts: 时间戳
            machine_idx: 机器索引
            
        Returns:
            (is_fault, fault_type, multiplier)
        """
        for fault in self.fault_periods:
            if fault['machine_idx'] == machine_idx:
                if fault['start'] <= ts <= fault['end']:
                    return True, fault['type'], fault['multiplier']
        return False, None, 1.0
    
    def add_fault(self, machine_idx, fault_type, start_time, duration_minutes):
        """
        添加故障注入
        
        Args:
            machine_idx: 机器索引
            fault_type: 故障类型 ('high_cpu', 'cpu_spike', 'low_cpu')
            start_time: 故障开始时间
            duration_minutes: 故障持续时间（分钟）
        """
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        if fault_type == 'high_cpu':
            multiplier = 2.5
        elif fault_type == 'cpu_spike':
            multiplier = 3.0
        elif fault_type == 'low_cpu':
            multiplier = 0.1
        else:
            multiplier = 1.0
        
        self.fault_periods.append({
            'machine_idx': machine_idx,
            'type': fault_type,
            'start': start_time,
            'end': end_time,
            'multiplier': multiplier
        })
    
    def generate(self):
        """
        生成完整的 CPU 使用率数据
        
        Returns:
            DataFrame: 包含 timestamp, machine_id, cpu_usage, is_fault, fault_type 列
        """
        print(f"📊 开始生成 {len(self.machines)} 台机器 {self.days} 天的 CPU 数据...")
        
        timestamps = pd.date_range(
            start=self.start_time,
            periods=self.days * 24 * 60,
            freq=self.freq
        )
        
        data = []
        total_fault_points = 0
        
        for machine_idx, machine_id in enumerate(self.machines):
            base_cpu = 20 + np.random.uniform(-5, 5)
            
            for ts in timestamps:
                hour = ts.hour
                minute = ts.minute
                weekday = ts.weekday()
                
                daily = self._daily_pattern(hour, minute)
                weekly = self._weekly_pattern(weekday)
                burst = self._generate_burst(ts, machine_idx)
                noise = np.random.uniform(-3, 3)
                
                cpu_usage = base_cpu + daily * weekly + burst + noise
                
                is_fault, fault_type, multiplier = self._is_in_fault_period(ts, machine_idx)
                
                if is_fault:
                    if fault_type == 'high_cpu':
                        cpu_usage = min(95, cpu_usage * multiplier)
                    elif fault_type == 'cpu_spike':
                        cpu_usage = min(100, cpu_usage + 60 * multiplier)
                    elif fault_type == 'low_cpu':
                        cpu_usage = max(1, cpu_usage * multiplier)
                    total_fault_points += 1
                
                cpu_usage = max(0, min(100, cpu_usage))
                
                data.append({
                    'timestamp': ts,
                    'machine_id': machine_id,
                    'cpu_usage': round(cpu_usage, 2),
                    'is_fault': is_fault,
                    'fault_type': fault_type if is_fault else None
                })
        
        df = pd.DataFrame(data)
        
        self.generation_report = {
            'total_records': len(df),
            'machines': len(self.machines),
            'days': self.days,
            'fault_periods': len(self.fault_periods),
            'fault_points': total_fault_points,
            'time_range': f"{timestamps[0]} ~ {timestamps[-1]}"
        }
        
        print(f"✅ 数据生成完成: {len(df)} 条记录")
        print(f"   - 机器数量: {len(self.machines)}")
        print(f"   - 故障注入点: {total_fault_points} 个")
        
        return df
    
    def save(self, df, output_path):
        """
        保存数据到 CSV
        
        Args:
            df: 数据 DataFrame
            output_path: 输出路径
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"✅ 数据已保存: {output_path}")
    
    def print_report(self):
        """打印生成报告"""
        print("\n" + "=" * 60)
        print("📋 数据生成报告")
        print("=" * 60)
        print(f"总记录数: {self.generation_report['total_records']}")
        print(f"机器数量: {self.generation_report['machines']}")
        print(f"数据天数: {self.generation_report['days']}")
        print(f"时间范围: {self.generation_report['time_range']}")
        print(f"故障期间数: {self.generation_report['fault_periods']}")
        print(f"故障注入点: {self.generation_report['fault_points']}")


def main():
    """主函数"""
    print("=" * 60)
    print("Step 1: 生成 CPU 使用率模拟数据")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    output_path = os.path.join(base_dir, 'data', 'raw', 'cpu_usage_raw.csv')
    
    machines = ['server-1', 'server-2', 'server-3']
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    
    generator = CPUDataGenerator(
        machines=machines,
        start_time=start_time,
        days=7,
        freq='1min'
    )
    
    generator.add_fault(
        machine_idx=0,
        fault_type='high_cpu',
        start_time=datetime(2024, 1, 3, 10, 0, 0),
        duration_minutes=30
    )
    
    generator.add_fault(
        machine_idx=1,
        fault_type='cpu_spike',
        start_time=datetime(2024, 1, 4, 14, 0, 0),
        duration_minutes=15
    )
    
    generator.add_fault(
        machine_idx=2,
        fault_type='low_cpu',
        start_time=datetime(2024, 1, 5, 8, 0, 0),
        duration_minutes=20
    )
    
    df = generator.generate()
    generator.save(df, output_path)
    generator.print_report()
    
    return df


if __name__ == "__main__":
    main()
