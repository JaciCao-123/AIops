#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drain + DBSCAN 运维日志告警聚合系统 - 主流水线

完整流程：
Step 1: 原始日志流生成 → Step 2: Drain解析层 → Step 3: 特征构建层
→ Step 4: DBSCAN聚类层 → Step 5: 告警收敛层

使用方法:
    python run_pipeline.py [--logs 5000] [--eps 0.5] [--min-samples 5]
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    PIPELINE_CONFIG, LOG_GENERATOR_CONFIG, DRAIN_CONFIG,
    FEATURE_BUILDER_CONFIG, DBSCAN_CONFIG, ALERT_CONVERGENCE_CONFIG,
    DATA_DIRS, get_config_summary
)

from step1_log_generator import LogGenerator
from step2_drain_parser import DrainParser
from step3_feature_builder import FeatureBuilder
from step4_dbscan_clustering import DBClusterer
from step5_alert_convergence import AlertConvergence


class AlertAggregationPipeline:
    """告警聚合主流水线"""
    
    def __init__(self, args=None):
        self.args = args or {}
        
        self._apply_custom_config()
        
        self.log_df = None
        self.parsed_df = None
        self.feature_matrix = None
        self.feature_df = None
        self.clustered_df = None
        self.cluster_stats = None
        self.report = None
        
        self.execution_times = {}
    
    def _apply_custom_config(self):
        """应用命令行自定义配置"""
        if 'num_logs' in self.args:
            LOG_GENERATOR_CONFIG['num_logs'] = self.args['num_logs']
        
        if 'eps' in self.args:
            DBSCAN_CONFIG['eps'] = self.args['eps']
        
        if 'min_samples' in self.args:
            DBSCAN_CONFIG['min_samples'] = self.args['min_samples']
    
    def run(self):
        """执行完整的告警聚合流水线"""
        total_start_time = time.time()
        
        print("\n" + "=" * 70)
        print("🚀 Drain + DBSCAN 运维日志告警聚合系统")
        print("=" * 70)
        print(f"\n⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        summary = get_config_summary()
        print("\n📋 系统配置:")
        for key, value in summary.items():
            print(f"   • {key}: {value}")
        
        try:
            start_time = time.time()
            self.log_df = self._step1_generate_logs()
            self.execution_times['step1'] = time.time() - start_time
            
            start_time = time.time()
            self.parsed_df = self._step2_drain_parse()
            self.execution_times['step2'] = time.time() - start_time
            
            start_time = time.time()
            self.feature_matrix, self.feature_df = self._step3_build_features()
            self.execution_times['step3'] = time.time() - start_time
            
            start_time = time.time()
            self.clustered_df, self.cluster_stats = self._step4_dbscan_cluster()
            self.execution_times['step4'] = time.time() - start_time
            
            start_time = time.time()
            self.report = self._step5_alert_convergence()
            self.execution_times['step5'] = time.time() - start_time
            
            total_time = time.time() - total_start_time
            
            self._print_final_summary(total_time)
            
            return {
                'success': True,
                'log_count': len(self.log_df) if self.log_df is not None else 0,
                'template_count': self.parsed_df['template_id'].nunique() if self.parsed_df is not None else 0,
                'cluster_count': len(set(self.clustered_df['cluster_id'])) - (1 if -1 in set(self.clustered_df['cluster_id']) else 0),
                'execution_time_seconds': round(total_time, 2)
            }
            
        except Exception as e:
            print(f"\n❌ 流水线执行失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'execution_time_seconds': round(time.time() - total_start_time, 2)
            }
    
    def _step1_generate_logs(self) -> object:
        """Step 1: 生成原始日志流"""
        generator = LogGenerator(LOG_GENERATOR_CONFIG)
        return generator.generate_logs()
    
    def _step2_drain_parse(self) -> object:
        """Step 2: Drain日志解析"""
        parser = DrainParser(DRAIN_CONFIG)
        return parser.parse_logs(self.log_df)
    
    def _step3_build_features(self) -> tuple:
        """Step 3: 构建特征向量"""
        builder = FeatureBuilder(FEATURE_BUILDER_CONFIG)
        return builder.build_features(self.parsed_df)
    
    def _step4_dbscan_cluster(self) -> tuple:
        """Step 4: DBSCAN聚类"""
        clusterer = DBClusterer(DBSCAN_CONFIG)
        clustered_df = clusterer.cluster_alerts(self.feature_matrix, self.parsed_df)
        
        import json
        stats_file = DATA_DIRS["clusters"] / "cluster_statistics.json"
        with open(stats_file, 'r') as f:
            cluster_stats = json.load(f)
        
        return clustered_df, cluster_stats
    
    def _step5_alert_convergence(self) -> str:
        """Step 5: 告警收敛与报告生成"""
        converger = AlertConvergence(ALERT_CONVERGENCE_CONFIG)
        return converger.generate_convergence_report(
            self.clustered_df,
            self.cluster_stats
        )
    
    def _print_final_summary(self, total_time: float):
        """打印最终摘要"""
        print("\n" + "=" * 70)
        print("✅ 流水线执行完成!")
        print("=" * 70)
        
        print(f"\n⏱️  执行时间统计:")
        print("-" * 50)
        step_names = [
            ("Step 1: 日志生成", "step1"),
            ("Step 2: Drain解析", "step2"),
            ("Step 3: 特征构建", "step3"),
            ("Step 4: DBSCAN聚类", "step4"),
            ("Step 5: 告警收敛", "step5")
        ]
        
        for name, key in step_names:
            exec_time = self.execution_times.get(key, 0)
            bar_length = min(int(exec_time / 10), 30)
            bar = "█" * bar_length + "░" * (30 - bar_length)
            print(f"   {name:<20} | {bar} | {exec_time:>6.2f}s")
        
        print("   " + "-" * 50)
        print(f"   {'总耗时':<20} | {'':30s} | {total_time:>6.2f}s")
        
        print(f"\n📊 最终结果:")
        print(f"   • 输入日志数: {len(self.log_df):,}")
        print(f"   • 发现模板数: {self.parsed_df['template_id'].nunique()}")
        print(f"   • 特征维度: {self.feature_matrix.shape[1]}")
        print(f"   • 聚类数量: {len(set(self.clustered_df['cluster_id'])) - (1 if -1 in set(self.clustered_df['cluster_id']) else 0)}")
        noise_count = (self.clustered_df['cluster_id'] == -1).sum()
        print(f"   • 噪声点数: {noise_count:,}")
        
        print(f"\n💾 输出文件:")
        output_files = {
            "原始日志": DATA_DIRS["raw"] / "raw_logs.csv",
            "解析结果": DATA_DIRS["parsed"] / "parsed_logs.csv",
            "日志模板": DATA_DIRS["parsed"] / "log_templates.json",
            "特征数据": DATA_DIRS["features"] / "log_features.npz",
            "聚类结果": DATA_DIRS["clusters"] / "clustered_logs.csv",
            "收敛报告": DATA_DIRS["reports"] / "alert_convergence_report.md"
        }
        
        for desc, path in output_files.items():
            exists = "✅" if path.exists() else "❌"
            print(f"   {exists} {desc}: {path.name}")
        
        print(f"\n🎉 所有步骤完成! 报告已生成。")


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='Drain + DBSCAN 运维日志告警聚合系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_pipeline.py                          # 使用默认配置运行
  python run_pipeline.py --logs 10000             # 生成10000条日志
  python run_pipeline.py --eps 0.3 --min-samples 10  # 自定义DBSCAN参数
  python run_pipeline.py --quick                  # 快速模式（较少数据）
        """
    )
    
    parser.add_argument(
        '--logs', '-l',
        type=int,
        default=5000,
        help='生成的日志数量（默认: 5000）'
    )
    
    parser.add_argument(
        '--eps', '-e',
        type=float,
        default=0.5,
        help='DBSCAN的eps参数（邻域半径，默认: 0.5）'
    )
    
    parser.add_argument(
        '--min-samples', '-m',
        type=int,
        default=5,
        help='DBSCAN的min_samples参数（最小样本数，默认: 5）'
    )
    
    parser.add_argument(
        '--quick', '-q',
        action='store_true',
        help='快速测试模式（1000条日志，简化处理）'
    )
    
    return parser.parse_args()


def main():
    """主函数入口"""
    args = parse_arguments()
    
    if args.quick:
        args.logs = 1000
        print("\n⚡ 快速测试模式已启用（1000条日志）\n")
    
    pipeline = AlertAggregationPipeline(vars(args))
    result = pipeline.run()
    
    if result.get('success'):
        print(f"\n🎯 系统运行成功! 共处理 {result['log_count']:,} 条日志")
        sys.exit(0)
    else:
        print(f"\n💥 系统运行失败: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
