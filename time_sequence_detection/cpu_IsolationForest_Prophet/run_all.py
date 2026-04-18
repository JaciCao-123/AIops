#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU 使用率异常检测 - 完整流程

运行方式：
    python run_all.py

流程：
    1. 生成模拟数据
    2. 数据清洗
    3. 模型训练
    4. 数据可视化
    5. 实时检测
"""

import os
import sys
import subprocess
from datetime import datetime


def run_step(step_name, script_path):
    """
    运行单个步骤
    
    Args:
        step_name: 步骤名称
        script_path: 脚本路径
        
    Returns:
        是否成功
    """
    print("\n" + "=" * 80)
    print(f"🚀 {step_name}")
    print("=" * 80)
    
    start_time = datetime.now()
    
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.path.dirname(script_path)
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if result.returncode == 0:
        print(f"\n✅ {step_name} 完成 (耗时: {elapsed:.2f}秒)")
        return True
    else:
        print(f"\n❌ {step_name} 失败")
        return False


def main():
    """主函数"""
    print("=" * 80)
    print("CPU 使用率异常检测系统")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    base_dir = os.path.dirname(__file__)
    
    steps = [
        ("Step 1: 生成模拟数据", os.path.join(base_dir, "step1_generate_data.py")),
        ("Step 2: 数据清洗", os.path.join(base_dir, "step2_clean_data.py")),
        ("Step 3: 模型训练", os.path.join(base_dir, "step3_train_model.py")),
        ("Step 4: 数据可视化", os.path.join(base_dir, "step4_visualize.py")),
        ("Step 5: 实时检测", os.path.join(base_dir, "step5_predict.py")),
    ]
    
    results = []
    total_start = datetime.now()
    
    for step_name, script_path in steps:
        success = run_step(step_name, script_path)
        results.append((step_name, success))
        
        if not success:
            print(f"\n⚠️ 流程中断: {step_name} 失败")
            break
    
    total_elapsed = (datetime.now() - total_start).total_seconds()
    
    print("\n" + "=" * 80)
    print("📋 执行摘要")
    print("=" * 80)
    
    for step_name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {step_name}: {status}")
    
    print(f"\n总耗时: {total_elapsed:.2f}秒")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_success = all(success for _, success in results)
    if all_success:
        print("\n🎉 所有步骤执行成功！")
    else:
        print("\n⚠️ 部分步骤执行失败，请检查日志")


if __name__ == "__main__":
    main()
