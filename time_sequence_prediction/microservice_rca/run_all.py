#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微服务根因定位 - 完整流程运行脚本

执行步骤：
1. 生成模拟数据
2. 数据清理和对齐
3. 模型训练
4. 预测和根因分析
"""

import os
import sys
import subprocess
import argparse
from datetime import datetime


def run_step(step_name: str, script_path: str) -> bool:
    """
    运行单个步骤
    
    Args:
        step_name: 步骤名称
        script_path: 脚本路径
        
    Returns:
        是否成功
    """
    print("\n" + "=" * 60)
    print(f"执行: {step_name}")
    print("=" * 60)
    
    start_time = datetime.now()
    
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.path.dirname(__file__)
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    if result.returncode == 0:
        print(f"\n✅ {step_name} 完成 (耗时: {elapsed:.1f}秒)")
        return True
    else:
        print(f"\n❌ {step_name} 失败 (退出码: {result.returncode})")
        return False


def main():
    parser = argparse.ArgumentParser(description='微服务根因定位完整流程')
    parser.add_argument('--skip-data', action='store_true', help='跳过数据生成')
    parser.add_argument('--skip-clean', action='store_true', help='跳过数据清理')
    parser.add_argument('--skip-train', action='store_true', help='跳过模型训练')
    parser.add_argument('--model', type=str, default='gat', 
                        choices=['gcn', 'gat', 'sage'],
                        help='使用的模型类型')
    parser.add_argument('--epochs', type=int, default=30, help='训练轮数')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("微服务根因定位 - 完整流程")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    base_dir = os.path.dirname(__file__)
    
    steps = []
    
    if not args.skip_data:
        steps.append(("Step 1: 生成模拟数据", 
                     os.path.join(base_dir, "step1_generate_data.py")))
    
    if not args.skip_clean:
        steps.append(("Step 2: 数据清理和对齐",
                     os.path.join(base_dir, "step2_clean_data.py")))
    
    if not args.skip_train:
        steps.append(("Step 3: 模型训练",
                     os.path.join(base_dir, "step3_train_model.py")))
    
    steps.append(("Step 4: 预测和根因分析",
                 os.path.join(base_dir, "step4_predict.py")))
    
    success_count = 0
    for step_name, script_path in steps:
        if run_step(step_name, script_path):
            success_count += 1
        else:
            print(f"\n⚠️ 流程中断于: {step_name}")
            break
    
    print("\n" + "=" * 60)
    print("执行结果汇总")
    print("=" * 60)
    print(f"完成步骤: {success_count}/{len(steps)}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_count == len(steps):
        print("\n🎉 所有步骤执行完成!")
        
        models_dir = os.path.join(base_dir, "models")
        if os.path.exists(models_dir):
            print("\n📁 生成的模型文件:")
            for f in os.listdir(models_dir):
                if f.endswith('.pt'):
                    filepath = os.path.join(models_dir, f)
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    print(f"   - {f} ({size_mb:.2f} MB)")
        
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
