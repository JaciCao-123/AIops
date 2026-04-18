#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: DBSCAN 聚类层

功能：
1. 基于密度的空间聚类算法
2. 自动发现相似告警簇
3. 无需预先指定聚类数量
4. 处理噪声点
5. 聚类质量评估

核心算法：DBSCAN (Density-Based Spatial Clustering of Applications with Noise)
"""

import json
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score

sys.path.insert(0, str(Path(__file__).parent))

from config import DBSCAN_CONFIG, DATA_DIRS


class DBClusterer:
    """
    DBSCAN 告警聚类器
    
    将相似的告警向量聚合在一起，自动发现告警模式
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or DBSCAN_CONFIG
        
        self.eps = self.config["eps"]
        self.min_samples = self.config["min_samples"]
        
        self.metric = self.config.get("metric", "euclidean")
        self.algorithm = self.config.get("algorithm", "auto")
        self.n_jobs = self.config.get("n_jobs", -1)
        
        self.dbscan_model: Optional[DBSCAN] = None
        
        self.cluster_labels: Optional[np.ndarray] = None
        self.cluster_centers: Optional[Dict[int, np.ndarray]] = None
    
    def cluster_alerts(self, feature_matrix: np.ndarray, 
                      original_df: pd.DataFrame) -> pd.DataFrame:
        """执行DBSCAN聚类"""
        print("\n" + "=" * 60)
        print("🎯 Step 4: DBSCAN 告警聚类")
        print("=" * 60)
        
        print(f"\n⚙️  DBSCAN配置:")
        print(f"   • eps (邻域半径): {self.eps}")
        print(f"   • min_samples (最小样本数): {self.min_samples}")
        print(f"   • 距离度量: {self.metric}")
        print(f"   • 算法: {self.algorithm}")
        
        self.dbscan_model = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric=self.metric,
            algorithm=self.algorithm,
            n_jobs=self.n_jobs
        )
        
        print(f"\n🔄 开始聚类...")
        self.cluster_labels = self.dbscan_model.fit_predict(feature_matrix)
        
        result_df = original_df.copy()
        result_df['cluster_id'] = self.cluster_labels
        
        noise_handling = self.config.get("noise_handling", "separate_cluster")
        if noise_handling == "separate_cluster":
            prefix = self.config.get("cluster_label_prefix", "CLUSTER_")
            result_df['cluster_label'] = result_df['cluster_id'].apply(
                lambda x: f"{prefix}{x}" if x >= 0 else "NOISE"
            )
        else:
            result_df['cluster_label'] = result_df['cluster_id'].astype(str)
        
        cluster_stats = self._calculate_cluster_statistics(feature_matrix, result_df)
        cluster_centers = self._calculate_cluster_centers(feature_matrix, result_df)
        
        quality_metrics = self._evaluate_clustering_quality(feature_matrix)
        
        output_files = self.config["output_files"]
        
        with open(output_files['cluster_labels'], 'w', encoding='utf-8') as f:
            json.dump({
                'labels': self.cluster_labels.tolist(),
                'n_clusters': len(set(self.cluster_labels)) - (1 if -1 in self.cluster_labels else 0),
                'n_noise': list(self.cluster_labels).count(-1)
            }, f, indent=2)
        
        with open(output_files['cluster_centers'], 'w', encoding='utf-8') as f:
            centers_serializable = {
                str(k): v.tolist() for k, v in cluster_centers.items()
            }
            json.dump(centers_serializable, f, indent=2)
        
        with open(output_files['cluster_stats'], 'w', encoding='utf-8') as f:
            json.dump(self._convert_to_native_types(cluster_stats), f, ensure_ascii=False, indent=2)
        
        result_file = DATA_DIRS["clusters"] / "clustered_logs.csv"
        result_df.to_csv(result_file, index=False)
        
        self._print_clustering_results(cluster_stats, quality_metrics, result_df)
        
        return result_df
    
    def _calculate_cluster_statistics(self, feature_matrix: np.ndarray,
                                    result_df: pd.DataFrame) -> Dict:
        """计算每个聚类的统计信息"""
        stats = {}
        
        unique_labels = set(self.cluster_labels)
        n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
        n_noise = list(self.cluster_labels).count(-1)
        
        stats['overview'] = {
            'total_samples': len(self.cluster_labels),
            'n_clusters': n_clusters,
            'n_noise_points': n_noise,
            'noise_percentage': round(n_noise / len(self.cluster_labels) * 100, 2),
            'clusters_with_noise': n_clusters + 1 if n_noise > 0 else n_clusters
        }
        
        stats['clusters'] = []
        
        for label in sorted(unique_labels):
            mask = self.cluster_labels == label
            cluster_data = result_df[mask]
            
            is_noise = label == -1
            
            level_distribution = cluster_data['level'].value_counts().to_dict()
            
            source_distribution = cluster_data['source'].value_counts().to_dict()
            
            time_range = {
                'start': str(cluster_data['timestamp'].min()),
                'end': str(cluster_data['timestamp'].max()),
                'duration_seconds': (
                    pd.to_datetime(cluster_data['timestamp'].max()) -
                    pd.to_datetime(cluster_data['timestamp'].min())
                ).total_seconds()
            }
            
            template_diversity = cluster_data['template_id'].nunique()
            
            anomaly_rate = cluster_data['is_anomaly'].mean() if 'is_anomaly' in cluster_data.columns else 0
            
            try:
                max_template_idx = cluster_data.groupby('template_id')['template_id'].transform('count').idxmax()
                representative_template = cluster_data.loc[max_template_idx, 'template_str']
                if not isinstance(representative_template, str):
                    representative_template = str(representative_template)
            except Exception:
                representative_template = cluster_data['template_str'].iloc[0] if len(cluster_data) > 0 else ""
            
            cluster_info = {
                'cluster_id': int(label),
                'cluster_label': f"CLUSTER_{label}" if not is_noise else "NOISE",
                'is_noise': is_noise,
                'size': int(mask.sum()),
                'percentage': round(mask.sum() / len(self.cluster_labels) * 100, 2),
                'level_distribution': level_distribution,
                'source_distribution': source_distribution,
                'time_range': time_range,
                'unique_templates': template_diversity,
                'anomaly_rate': round(anomaly_rate * 100, 2),
                'representative_template': representative_template[:200] if isinstance(representative_template, str) else "",
                'top_services': cluster_data['service'].value_counts().head(5).to_dict()
            }
            
            stats['clusters'].append(cluster_info)
        
        stats['clusters'] = sorted(stats['clusters'], 
                                   key=lambda x: (-x['size'], x['cluster_id']))
        
        return stats
    
    def _calculate_cluster_centers(self, feature_matrix: np.ndarray,
                                  result_df: pd.DataFrame) -> Dict[int, np.ndarray]:
        """计算每个聚类的中心点"""
        centers = {}
        
        for label in set(self.cluster_labels):
            if label == -1:
                continue
            
            mask = self.cluster_labels == label
            cluster_features = feature_matrix[mask]
            
            center = cluster_features.mean(axis=0)
            centers[label] = center
        
        self.cluster_centers = centers
        return centers
    
    def _evaluate_clustering_quality(self, feature_matrix: np.ndarray) -> Dict:
        """评估聚类质量"""
        metrics = {}
        
        non_noise_mask = self.cluster_labels != -1
        non_noise_features = feature_matrix[non_noise_mask]
        non_noise_labels = self.cluster_labels[non_noise_mask]
        
        unique_non_noise = set(non_noise_labels)
        
        if len(unique_non_noise) > 1 and len(non_noise_features) > len(unique_non_noise):
            try:
                silhouette_avg = silhouette_score(non_noise_features, non_noise_labels)
                metrics['silhouette_score'] = round(silhouette_avg, 4)
            except Exception as e:
                metrics['silhouette_score'] = None
                metrics['silhouette_error'] = str(e)
            
            try:
                ch_score = calinski_harabasz_score(non_noise_features, non_noise_labels)
                metrics['calinski_harabasz_score'] = round(ch_score, 2)
            except Exception as e:
                metrics['calinski_harabasz_score'] = None
                metrics['ch_error'] = str(e)
            
            try:
                db_score = davies_bouldin_score(non_noise_features, non_noise_labels)
                metrics['davies_bouldin_score'] = round(db_score, 4)
            except Exception as e:
                metrics['davies_bouldin_score'] = None
                metrics['db_error'] = str(e)
        else:
            metrics['note'] = "样本不足或只有一个聚类，无法计算评估指标"
        
        total_samples = len(self.cluster_labels)
        n_clusters = len(unique_non_noise)
        n_noise = (~non_noise_mask).sum()
        
        metrics['clustering_summary'] = {
            'total_samples': total_samples,
            'n_clusters': n_clusters,
            'noise_ratio': round(n_noise / total_samples * 100, 2),
            'avg_cluster_size': round((total_samples - n_noise) / max(n_clusters, 1), 1)
        }
        
        return metrics
    
    def _convert_to_native_types(self, obj):
        """将numpy类型转换为Python原生类型（用于JSON序列化）"""
        if isinstance(obj, dict):
            return {k: self._convert_to_native_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_native_types(item) for item in obj]
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    def _print_clustering_results(self, cluster_stats: Dict, 
                                 quality_metrics: Dict,
                                 result_df: pd.DataFrame):
        """打印聚类结果"""
        overview = cluster_stats['overview']
        
        print(f"\n✅ DBSCAN聚类完成!")
        print(f"\n📊 聚类概览:")
        print(f"   总样本数: {overview['total_samples']:,}")
        print(f"   发现聚类数: {overview['n_clusters']}")
        print(f"   噪声点数: {overview['n_noise_points']:,} ({overview['noise_percentage']}%)")
        
        print(f"\n🎯 聚类质量评估:")
        summary = quality_metrics.get('clustering_summary', {})
        print(f"   平均聚类大小: {summary.get('avg_cluster_size', 'N/A'):.1f}")
        
        if 'silhouette_score' in quality_metrics:
            score = quality_metrics['silhouette_score']
            if score is not None:
                print(f"   轮廓系数 (Silhouette): {score:.4f}", end="")
                if score > 0.7:
                    print(" ✅ 优秀")
                elif score > 0.5:
                    print(" 👍 良好")
                elif score > 0.25:
                    print(" ⚠️ 一般")
                else:
                    print(" ❌ 较差")
        
        if 'calinski_harabasz_score' in quality_metrics:
            print(f"   Calinski-Harabasz指数: {quality_metrics['calinski_harabasz_score']:.2f}")
        
        if 'davies_bouldin_score' in quality_metrics:
            db_score = quality_metrics['davies_bouldin_score']
            if db_score is not None:
                print(f"   Davies-Bouldin指数: {db_score:.4f}")
        
        print(f"\n🔝 Top 10 最大聚类:")
        print("-" * 80)
        top_clusters = sorted(cluster_stats['clusters'], 
                            key=lambda x: x['size'], reverse=True)[:10]
        
        for i, cluster in enumerate(top_clusters, 1):
            noise_tag = " 🗑️ 噪声" if cluster['is_noise'] else ""
            error_count = cluster['level_distribution'].get('ERROR', 0)
            warn_count = cluster['level_distribution'].get('WARN', 0)
            
            template_preview = cluster['representative_template'][:60] + "..." \
                if len(cluster['representative_template']) > 60 \
                else cluster['representative_template']
            
            print(f"{i:2d}. [{cluster['cluster_label']}] "
                  f"样本数: {cluster['size']:>5} ({cluster['percentage']:>5.1f}%){noise_tag}")
            print(f"     错误/警告: {error_count}/{warn_count} | "
                  f"异常率: {cluster['anomaly_rate']}% | "
                  f"模板数: {cluster['unique_templates']}")
            print(f"     代表模板: {template_preview}")
        
        print(f"\n💾 聚类结果已保存至: {DATA_DIRS['clusters']}")


def main():
    """主函数 - 用于测试"""
    from step1_log_generator import LogGenerator
    from step2_drain_parser import DrainParser
    from step3_feature_builder import FeatureBuilder
    
    generator = LogGenerator()
    log_df = generator.generate_logs()
    
    parser = DrainParser()
    parsed_df = parser.parse_logs(log_df)
    
    builder = FeatureBuilder()
    feature_matrix, feature_df = builder.build_features(parsed_df)
    
    clusterer = DBClusterer()
    clustered_df = clusterer.cluster_alerts(feature_matrix, parsed_df)
    
    return clustered_df


if __name__ == "__main__":
    main()
