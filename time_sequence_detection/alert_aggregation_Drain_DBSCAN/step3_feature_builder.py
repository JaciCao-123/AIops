#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: 特征构建层

功能：
1. 将模板信息 + 上下文信息转化为向量
2. 构建多维特征空间：
   - 模板特征（ID编码、频率、长度）
   - 上下文特征（时间戳、来源服务、日志级别）
   - 语义特征（TF-IDF向量化）
   - 统计特征（时间窗口内出现次数）
3. 特征标准化和降维
"""

import re
import json
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler, LabelEncoder, MinMaxScaler
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).parent))

from config import FEATURE_BUILDER_CONFIG, DATA_DIRS


class FeatureBuilder:
    """
    特征构建器
    
    将解析后的日志转换为可用于聚类的数值特征向量
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or FEATURE_BUILDER_CONFIG
        
        self.feature_types = self.config["feature_types"]
        
        self.tfidf_vectorizer = None
        self.scaler = None
        
        self.label_encoders = {}
        
        self.feature_names = []
    
    def build_features(self, parsed_df: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
        """构建完整特征矩阵"""
        print("\n" + "=" * 60)
        print("🔧 Step 3: 特征构建")
        print("=" * 60)
        
        feature_matrices = []
        self.feature_names = []
        
        if self.feature_types.get("template_id_embedding", True):
            template_features, names = self._build_template_features(parsed_df)
            feature_matrices.append(template_features)
            self.feature_names.extend(names)
            print(f"   ✓ 模板特征维度: {template_features.shape[1]}")
        
        if self.feature_types.get("log_level_encoding", True):
            level_features, names = self._build_log_level_features(parsed_df)
            feature_matrices.append(level_features)
            self.feature_names.extend(names)
            print(f"   ✓ 日志级别特征维度: {level_features.shape[1]}")
        
        if self.feature_types.get("time_features", True):
            time_features, names = self._build_time_features(parsed_df)
            feature_matrices.append(time_features)
            self.feature_names.extend(names)
            print(f"   ✓ 时间特征维度: {time_features.shape[1]}")
        
        if self.feature_types.get("statistical_features", True):
            stat_features, names = self._build_statistical_features(parsed_df)
            feature_matrices.append(stat_features)
            self.feature_names.extend(names)
            print(f"   ✓ 统计特征维度: {stat_features.shape[1]}")
        
        if self.feature_types.get("tfidf_vectorization", True):
            tfidf_features, names = self._build_tfidf_features(parsed_df)
            feature_matrices.append(tfidf_features)
            self.feature_names.extend(names)
            print(f"   ✓ TF-IDF特征维度: {tfidf_features.shape[1]}")
        
        feature_matrix = np.hstack(feature_matrices) if feature_matrices else np.array([])
        
        feature_matrix, final_names = self._normalize_and_reduce(
            feature_matrix, 
            self.feature_names,
            parsed_df
        )
        
        feature_df = pd.DataFrame(
            feature_matrix,
            columns=final_names[:feature_matrix.shape[1]] if len(final_names) >= feature_matrix.shape[1] 
                   else [f"feature_{i}" for i in range(feature_matrix.shape[1])]
        )
        
        output_file = self.config["output_file"]
        np.savez_compressed(output_file, 
                           features=feature_matrix,
                           feature_names=np.array(final_names))
        
        metadata = {
            "total_samples": len(parsed_df),
            "feature_dimension": feature_matrix.shape[1],
            "feature_names": final_names,
            "feature_types_used": [k for k, v in self.feature_types.items() if v]
        }
        
        metadata_file = DATA_DIRS["features"] / "feature_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        self._print_statistics(feature_matrix, metadata)
        
        return feature_matrix, feature_df
    
    def _build_template_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """构建模板相关特征"""
        features = []
        names = []
        
        label_encoder = LabelEncoder()
        template_ids_encoded = label_encoder.fit_transform(df['template_id'])
        self.label_encoders['template_id'] = label_encoder
        
        features.append(template_ids_encoded.reshape(-1, 1))
        names.append('template_id_encoded')
        
        template_counts = df.groupby('template_id').transform('count')['raw_message']
        normalized_count = (template_counts - template_counts.mean()) / (template_counts.std() + 1e-8)
        features.append(normalized_count.values.reshape(-1, 1))
        names.append('template_frequency_normalized')
        
        template_lengths = df['template_str'].str.len()
        normalized_length = (template_lengths - template_lengths.mean()) / (template_lengths.std() + 1e-8)
        features.append(normalized_length.values.reshape(-1, 1))
        names.append('template_length_normalized')
        
        param_counts = df['parameters'].apply(lambda x: len(x) if isinstance(x, list) else 0)
        features.append(param_counts.values.reshape(-1, 1))
        names.append('parameter_count')
        
        return np.hstack(features), names
    
    def _build_log_level_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """构建日志级别编码特征"""
        level_mapping = {'DEBUG': 0, 'INFO': 1, 'WARN': 2, 'ERROR': 3}
        level_encoded = df['level'].map(lambda x: level_mapping.get(x, 0)).values.reshape(-1, 1)
        
        is_error = (df['level'] == 'ERROR').astype(int).values.reshape(-1, 1)
        is_warning = (df['level'] == 'WARN').astype(int).values.reshape(-1, 1)
        
        severity_weights = {'DEBUG': 0.1, 'INFO': 0.2, 'WARN': 0.6, 'ERROR': 1.0}
        severity_score = df['level'].map(lambda x: severity_weights.get(x, 0)).values.reshape(-1, 1)
        
        features = np.hstack([level_encoded, is_error, is_warning, severity_score])
        names = ['log_level_encoded', 'is_error', 'is_warning', 'severity_score']
        
        return features, names
    
    def _build_time_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """构建时间相关特征"""
        timestamps = pd.to_datetime(df['timestamp'])
        
        hour_of_day = ((timestamps.dt.hour * 3600 + 
                       timestamps.dt.minute * 60 + 
                       timestamps.dt.second) / 86400).values.reshape(-1, 1)
        
        day_of_week = timestamps.dt.dayofweek.values.reshape(-1, 1)
        
        minute_bucket = (timestamps.dt.hour * 60 + timestamps.dt.minute).values.reshape(-1, 1)
        minute_bucket_norm = (minute_bucket - minute_bucket.min()) / (minute_bucket.max() - minute_bucket.min() + 1e-8)
        
        time_diffs = timestamps.diff().fillna(pd.Timedelta(seconds=0)).dt.total_seconds().values.reshape(-1, 1)
        time_diffs_norm = (time_diffs - time_diffs.mean()) / (time_diffs.std() + 1e-8)
        
        features = np.hstack([hour_of_day, day_of_week, minute_bucket_norm, time_diffs_norm])
        names = ['hour_of_day', 'day_of_week', 'minute_bucket_normalized', 'time_interval']
        
        return features, names
    
    def _build_statistical_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """构建统计特征"""
        window_seconds = self.config.get("time_window_seconds", 300)
        timestamps = pd.to_datetime(df['timestamp'])
        
        error_numeric = (df['level'] == 'ERROR').astype(int)
        anomaly_numeric = df.get('is_anomaly', pd.Series([0] * len(df))).astype(int)
        
        df_temp = df.copy()
        df_temp['_error_flag'] = error_numeric
        df_temp['_anomaly_flag'] = anomaly_numeric
        df_temp['_timestamp'] = timestamps
        
        rolling_window = df_temp.rolling(
            window=f"{window_seconds}s",
            on='_timestamp',
            min_periods=1
        )
        
        try:
            error_rate = (
                rolling_window['_error_flag'].mean()
                .fillna(0)
                .values
                .reshape(-1, 1)
            )
        except Exception:
            error_rate = np.zeros((len(df), 1))
        
        try:
            log_density = (
                rolling_window['raw_message'].count()
                .fillna(1)
                .values
                .reshape(-1, 1)
            )
            log_density_norm = (log_density - log_density.mean()) / (log_density.std() + 1e-8)
        except Exception:
            log_density_norm = np.zeros((len(df), 1))
        
        try:
            anomaly_rate = (
                rolling_window['_anomaly_flag'].mean()
                .fillna(0)
                .values
                .reshape(-1, 1)
            )
        except Exception:
            anomaly_rate = np.zeros((len(df), 1))
        
        template_counts = df.groupby('template_id').cumcount() + 1
        template_freq_normalized = (template_counts - template_counts.mean()) / (template_counts.std() + 1e-8)
        
        features = np.hstack([error_rate, log_density_norm, 
                             template_freq_normalized.values.reshape(-1, 1),
                             anomaly_rate])
        names = ['error_rate_in_window', 'log_density_normalized', 
                 'template_frequency_trend', 'anomaly_rate_in_window']
        
        return features, names
    
    def _build_tfidf_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """构建TF-IDF文本特征"""
        tfidf_params = self.config.get("tfidf_params", {})
        
        documents = df['template_str'].tolist()
        
        self.tfidf_vectorizer = TfidfVectorizer(**tfidf_params)
        tfidf_matrix = self.tfidf_vectorizer.fit_transform(documents)
        
        feature_names_tfidf = [
            f'tfidf_{name}' for name in self.tfidf_vectorizer.get_feature_names_out()
        ]
        
        return tfidf_matrix.toarray(), feature_names_tfidf
    
    def _normalize_and_reduce(self, feature_matrix: np.ndarray, 
                             feature_names: List[str],
                             original_df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """特征标准化和可选的降维"""
        normalization_method = self.config.get("normalization", "standard")
        
        if normalization_method == "standard":
            self.scaler = StandardScaler()
        elif normalization_method == "minmax":
            self.scaler = MinMaxScaler()
        else:
            self.scaler = StandardScaler()
        
        normalized_features = self.scaler.fit_transform(feature_matrix)
        
        final_features = normalized_features
        final_names = feature_names
        
        if final_features.shape[1] > 50 and final_features.shape[0] > 100:
            n_components = min(50, int(np.sqrt(final_features.shape[1])))
            
            pca = PCA(n_components=n_components)
            reduced_features = pca.fit_transform(final_features)
            
            explained_variance = sum(pca.explained_variance_ratio_)
            print(f"\n   📐 PCA降维:")
            print(f"      原始维度: {final_features.shape[1]}")
            print(f"      降至维度: {reduced_features.shape[1]}")
            print(f"      解释方差比: {explained_variance:.2%}")
            
            final_features = reduced_features
            final_names = [f'pca_component_{i}' for i in range(reduced_features.shape[1])]
        
        return final_features, final_names
    
    def _print_statistics(self, feature_matrix: np.ndarray, metadata: Dict):
        """打印统计信息"""
        print(f"\n📊 特征构建结果:")
        print(f"   总样本数: {metadata['total_samples']:,}")
        print(f"   最终特征维度: {metadata['feature_dimension']}")
        print(f"   使用的特征类型: {', '.join(metadata['feature_types_used'])}")
        
        print(f"\n   特征分布统计:")
        print(f"      均值范围: [{feature_matrix.mean(axis=0).min():.4f}, "
              f"{feature_matrix.mean(axis=0).max():.4f}]")
        print(f"      标准差范围: [{feature_matrix.std(axis=0).min():.4f}, "
              f"{feature_matrix.std(axis=0).max():.4f}]")
        
        print(f"\n💾 特征数据已保存至: {DATA_DIRS['features']}")


def main():
    """主函数 - 用于测试"""
    from step1_log_generator import LogGenerator
    from step2_drain_parser import DrainParser
    
    generator = LogGenerator()
    log_df = generator.generate_logs()
    
    parser = DrainParser()
    parsed_df = parser.parse_logs(log_df)
    
    builder = FeatureBuilder()
    feature_matrix, feature_df = builder.build_features(parsed_df)
    
    return feature_matrix, feature_df


if __name__ == "__main__":
    main()
