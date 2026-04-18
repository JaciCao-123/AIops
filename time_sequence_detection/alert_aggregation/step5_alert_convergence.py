#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5: 告警收敛层

功能：
1. 生成聚合报告
2. 提取每个簇的代表性告警
3. 计算告警严重程度和影响范围
4. 输出可操作的告警摘要
5. 生成Markdown格式的分析报告
"""

import json
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import ALERT_CONVERGENCE_CONFIG, DATA_DIRS


class AlertConvergence:
    """
    告警收敛器
    
    将DBSCAN聚类结果转化为可操作的告警收敛报告
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or ALERT_CONVERGENCE_CONFIG
        
        self.severity_weights = self.config["severity_weights"]
        
        self.impact_factors = self.config["impact_factors"]
    
    def generate_convergence_report(self, clustered_df: pd.DataFrame,
                                   cluster_stats: Dict) -> str:
        """生成告警收敛报告"""
        print("\n" + "=" * 60)
        print("📋 Step 5: 告警收敛与报告生成")
        print("=" * 60)
        
        convergence_analysis = self._analyze_convergence(clustered_df, cluster_stats)
        
        prioritized_clusters = self._prioritize_alerts(convergence_analysis)
        
        report = self._generate_markdown_report(
            clustered_df,
            cluster_stats,
            convergence_analysis,
            prioritized_clusters
        )
        
        output_file = self.config["output_file"]
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        self._print_summary(prioritized_clusters)
        
        return report
    
    def _analyze_convergence(self, clustered_df: pd.DataFrame,
                            cluster_stats: Dict) -> Dict:
        """分析每个聚类的收敛特征"""
        analysis = {
            'total_original_alerts': len(clustered_df),
            'total_unique_templates': clustered_df['template_id'].nunique(),
            'clusters_analyzed': [],
            'convergence_metrics': {}
        }
        
        clusters_data = cluster_stats.get('clusters', [])
        
        for cluster in clusters_data:
            cluster_id = cluster['cluster_id']
            
            severity_score = self._calculate_severity_score(cluster)
            
            impact_score = self._calculate_impact_score(cluster)
            
            convergence_ratio = self._calculate_convergence_ratio(cluster)
            
            urgency_level = self._determine_urgency(severity_score, impact_score)
            
            recommended_action = self._generate_recommendation(cluster, urgency_level)
            
            cluster_analysis = {
                'cluster_id': cluster_id,
                'cluster_label': cluster.get('cluster_label', str(cluster_id)),
                'original_alerts_count': cluster['size'],
                'severity_score': round(severity_score, 3),
                'impact_score': round(impact_score, 3),
                'urgency_level': urgency_level,
                'convergence_ratio': round(convergence_ratio, 3),
                'recommended_actions': recommended_action,
                'key_findings': self._extract_key_findings(cluster),
                'affected_services': list(cluster.get('top_services', {}).keys()),
                'time_span_minutes': round(
                    cluster['time_range'].get('duration_seconds', 0) / 60, 1
                ),
                'anomaly_concentration': cluster.get('anomaly_rate', 0)
            }
            
            analysis['clusters_analyzed'].append(cluster_analysis)
        
        total_converged = sum(1 for c in analysis['clusters_analyzed'] 
                            if c['convergence_ratio'] > 0.7)
        
        original_alerts = analysis['total_original_alerts']
        n_clusters = len(clusters_data)
        
        analysis['convergence_metrics'] = {
            'convergence_rate': round(total_converged / max(n_clusters, 1), 3),
            'compression_ratio': round(original_alerts / max(n_clusters, 1), 2),
            'avg_cluster_size': round(original_alerts / max(n_clusters, 1), 1),
            'high_urgency_count': sum(1 for c in analysis['clusters_analyzed'] 
                                     if c['urgency_level'] in ['CRITICAL', 'HIGH']),
            'medium_urgency_count': sum(1 for c in analysis['clusters_analyzed'] 
                                       if c['urgency_level'] == 'MEDIUM'),
            'low_urgency_count': sum(1 for c in analysis['clusters_analyzed'] 
                                    if c['urgency_level'] == 'LOW')
        }
        
        return analysis
    
    def _calculate_severity_score(self, cluster: Dict) -> float:
        """计算严重程度得分"""
        level_dist = cluster.get('level_distribution', {})
        
        weighted_severity = 0.0
        total_logs = sum(level_dist.values())
        
        if total_logs == 0:
            return 0.0
        
        for level, count in level_dist.items():
            weight = self.severity_weights.get(level, 0.0)
            weighted_severity += weight * (count / total_logs)
        
        anomaly_factor = cluster.get('anomaly_rate', 0) / 100.0
        severity_with_anomaly = weighted_severity * (1 + anomaly_factor * 0.5)
        
        return min(severity_with_anomaly, 1.0)
    
    def _calculate_impact_score(self, cluster: Dict) -> float:
        """计算影响范围得分"""
        size_weight = self.impact_factors.get('cluster_size_weight', 0.3)
        error_weight = self.impact_factors.get('error_rate_weight', 0.4)
        freq_weight = self.impact_factors.get('frequency_weight', 0.3)
        
        size = cluster.get('size', 0)
        max_size_in_dataset = 5000  
        normalized_size = min(size / max(max_size_in_dataset, 1), 1.0)
        
        error_count = cluster.get('level_distribution', {}).get('ERROR', 0)
        total_count = cluster.get('size', 1)
        error_rate = error_count / max(total_count, 1)
        
        duration_minutes = cluster.get('time_range', {}).get('duration_seconds', 0) / 60
        max_duration = 120  
        freq_score = min(duration_minutes / max(max_duration, 1), 1.0)
        
        impact_score = (
            size_weight * normalized_size +
            error_weight * error_rate +
            freq_weight * freq_score
        )
        
        return impact_score
    
    def _calculate_convergence_ratio(self, cluster: Dict) -> float:
        """计算收敛比（模板多样性倒数）"""
        unique_templates = cluster.get('unique_templates', 1)
        total_alerts = cluster.get('size', 1)
        
        ratio = 1 - (unique_templates / total_alerts)
        
        return ratio
    
    def _determine_urgency(self, severity_score: float, 
                          impact_score: float) -> str:
        """确定紧急程度"""
        combined_score = severity_score * 0.6 + impact_score * 0.4
        
        if combined_score >= 0.8:
            return "CRITICAL"
        elif combined_score >= 0.6:
            return "HIGH"
        elif combined_score >= 0.4:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_recommendation(self, cluster: Dict, 
                                urgency_level: str) -> List[str]:
        """生成处理建议"""
        recommendations = []
        
        level_dist = cluster.get('level_distribution', {})
        error_count = level_dist.get('ERROR', 0)
        warn_count = level_dist.get('WARN', 0)
        
        source_dist = cluster.get('source_distribution', {})
        primary_source = max(source_dist.items(), key=lambda x: x[1])[0] if source_dist else "unknown"
        
        services = list(cluster.get('top_services', {}).keys())[:3]
        
        if urgency_level == "CRITICAL":
            recommendations.append("🚨 立即通知值班人员和运维团队")
            recommendations.append("📞 启动应急响应流程")
            recommendations.append("🔍 排查根因并实施临时缓解措施")
        
        elif urgency_level == "HIGH":
            recommendations.append("⚠️ 优先级处理，建议在30分钟内响应")
            recommendations.append("📊 深入分析相关服务和依赖")
        
        elif urgency_level == "MEDIUM":
            recommendations.append("📋 加入待办事项，正常流程处理")
            recommendations.append("🔍 监控是否升级为高优先级")
        
        else:
            recommendations.append("💤 低优先级，可安排在维护窗口处理")
        
        if error_count > 10:
            recommendations.append(f"🐛 错误日志集中({error_count}条)，需排查{primary_source}问题")
        
        if warn_count > 20 and error_count < 5:
            recommendations.append("⚡ 大量警告但错误较少，可能是性能瓶颈或配置问题")
        
        if cluster.get('anomaly_rate', 0) > 50:
            recommendations.append("🔬 异常模式高度集中，可能存在系统性问题")
        
        if services:
            recommendations.append(f"🎯 重点检查服务: {', '.join(services)}")
        
        duration = cluster.get('time_range', {}).get('duration_seconds', 0) / 60
        if duration > 60:
            recommendations.append(f"⏰ 问题持续超过{duration:.0f}分钟，需关注长期趋势")
        
        return recommendations
    
    def _extract_key_findings(self, cluster: Dict) -> List[str]:
        """提取关键发现"""
        findings = []
        
        template = cluster.get('representative_template', '')
        if template:
            findings.append(f"代表模式: {template[:100]}")
        
        time_range = cluster.get('time_range', {})
        start = time_range.get('start', '')
        end = time_range.get('end', '')
        if start and end:
            findings.append(f"时间窗口: {start} ~ {end}")
        
        sources = list(cluster.get('source_distribution', {}).keys())[:3]
        if sources:
            findings.append(f"主要来源: {', '.join(sources)}")
        
        anomaly_rate = cluster.get('anomaly_rate', 0)
        if anomaly_rate > 20:
            findings.append(f"异常浓度高 ({anomaly_rate}%的日志为异常)")
        
        return findings
    
    def _prioritize_alerts(self, convergence_analysis: Dict) -> List[Dict]:
        """按优先级排序告警"""
        clusters = convergence_analysis.get('clusters_analyzed', [])
        
        urgency_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        
        sorted_clusters = sorted(
            clusters,
            key=lambda c: (
                urgency_order.get(c['urgency_level'], 4),
                -(c['severity_score'] + c['impact_score'])
            )
        )
        
        top_n = self.config.get("top_n_clusters", 10)
        return sorted_clusters[:top_n]
    
    def _generate_markdown_report(self, clustered_df: pd.DataFrame,
                                 cluster_stats: Dict,
                                 convergence_analysis: Dict,
                                 prioritized_clusters: List[Dict]) -> str:
        """生成Markdown格式报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        metrics = convergence_analysis.get('convergence_metrics', {})
        
        lines = []
        lines.append("# 🔔 运维日志告警聚合收敛报告\n")
        lines.append(f"**生成时间**: {now}\n")
        lines.append("---\n")
        
        lines.append("## 📊 执行概要\n")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 原始告警总数 | **{convergence_analysis['total_original_alerts']:,}** |")
        lines.append(f"| 唯一日志模板数 | {convergence_analysis['total_unique_templates']} |")
        lines.append(f"| 聚合后聚类数 | {len(convergence_analysis['clusters_analyzed'])} |")
        lines.append(f"| 收敛率 | **{metrics.get('compression_ratio', 'N/A'):,.1f}:1** |")
        lines.append(f"| 压缩率 | {metrics.get('convergence_rate', 'N/A'):.1%} |")
        lines.append("")
        
        lines.append("## 🎯 优先级告警列表\n")
        lines.append("以下为需要优先处理的告警聚合（按紧急程度排序）：\n")
        
        urgency_icons = {
            'CRITICAL': '🔴',
            'HIGH': '🟠',
            'MEDIUM': '🟡',
            'LOW': '🟢'
        }
        
        for i, cluster in enumerate(prioritized_clusters, 1):
            icon = urgency_icons.get(cluster['urgency_level'], '⚪')
            urgency = cluster['urgency_level']
            
            lines.append(f"### {icon} #{i} [{urgency}] 聚类 {cluster['cluster_label']}\n")
            
            lines.append("**基本信息**:")
            lines.append(f"- **原始告警数**: {cluster['original_alerts_count']:,}")
            lines.append(f"- **严重程度得分**: {cluster['severity_score']:.3f}")
            lines.append(f"- **影响范围得分**: {cluster['impact_score']:.3f}")
            lines.append(f"- **收敛比率**: {cluster['convergence_ratio']:.1%}")
            lines.append(f"- **影响服务**: {', '.join(cluster['affected_services']) or 'N/A'}")
            lines.append(f"- **持续时间**: {cluster['time_span_minutes']:.1f} 分钟")
            lines.append("")
            
            lines.append("**关键发现**:")
            for finding in cluster['key_findings']:
                lines.append(f"- {finding}")
            lines.append("")
            
            lines.append("**推荐操作**:")
            for action in cluster['recommended_actions']:
                lines.append(f"- {action}")
            lines.append("")
            
            lines.append("---\n")
        
        include_noise = self.config.get("include_noise_analysis", True)
        if include_noise:
            noise_clusters = [c for c in convergence_analysis.get('clusters_analyzed', []) 
                             if c.get('is_noise', False)]
            if noise_clusters:
                lines.append("## 🗑️ 噪声点分析\n")
                lines.append(f"共发现 **{noise_clusters[0].get('original_alerts_count', 0):,}** 条孤立/噪声告警")
                lines.append("- 这些告警未形成明显聚类，可能是：")
                lines.append("  - 罕见的一次性事件")
                lines.append("  - 数据质量问题")
                lines.append("  - 需要单独关注的特殊事件")
                lines.append("")
        
        lines.append("## 📈 技术细节\n")
        lines.append("### 算法参数")
        lines.append("- **日志解析算法**: Drain (前缀树)")
        lines.append("- **聚类算法**: DBSCAN (基于密度的空间聚类)")
        lines.append("- **特征维度**: 多维特征空间（模板+上下文+语义+统计）")
        lines.append("")
        
        lines.append("### 聚类质量指标")
        overview = cluster_stats.get('overview', {})
        lines.append(f"- **总样本数**: {overview.get('total_samples', 'N/A'):,}")
        lines.append(f"- **有效聚类数**: {overview.get('n_clusters', 'N/A')}")
        lines.append(f"- **噪声比例**: {overview.get('noise_percentage', 'N/A')}%")
        lines.append("")
        
        lines.append("---\n")
        lines.append("*报告由 Drain + DBSCAN 告警聚合系统自动生成*")
        
        return "\n".join(lines)
    
    def _print_summary(self, prioritized_clusters: List[Dict]):
        """打印摘要信息"""
        metrics = self.config
        print(f"\n✅ 告警收敛报告已生成!")
        
        print(f"\n📋 Top 优先级告警摘要:")
        print("-" * 80)
        
        urgency_icons = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}
        
        for i, cluster in enumerate(prioritized_clusters[:5], 1):
            icon = urgency_icons.get(cluster['urgency_level'], '⚪')
            print(f"{i}. {icon} [{cluster['urgency_level']}] "
                  f"聚类{cluster['cluster_label']}: "
                  f"{cluster['original_alerts_count']:,}个告警 → "
                  f"严重度:{cluster['severity_score']:.2f} "
                  f"影响度:{cluster['impact_score']:.2f}")
        
        print(f"\n💾 完整报告已保存至: {metrics['output_file']}")


def main():
    """主函数 - 用于测试"""
    from step1_log_generator import LogGenerator
    from step2_drain_parser import DrainParser
    from step3_feature_builder import FeatureBuilder
    from step4_dbscan_clustering import DBClusterer
    import json
    
    generator = LogGenerator()
    log_df = generator.generate_logs()
    
    parser = DrainParser()
    parsed_df = parser.parse_logs(log_df)
    
    builder = FeatureBuilder()
    feature_matrix, feature_df = builder.build_features(parsed_df)
    
    clusterer = DBClusterer()
    clustered_df = clusterer.cluster_alerts(feature_matrix, parsed_df)
    
    with open(DATA_DIRS["clusters"] / "cluster_statistics.json", 'r') as f:
        cluster_stats = json.load(f)
    
    converger = AlertConvergence()
    report = converger.generate_convergence_report(clustered_df, cluster_stats)
    
    print("\n\n" + "=" * 80)
    print("📄 报告预览（前2000字符）:")
    print("=" * 80)
    print(report[:2000])
    
    return report


if __name__ == "__main__":
    main()
