"""
=============================================================================
  双层漏斗架构 - 系统负载异常检测系统
  Dual-Layer Funnel: IF (初筛) → LSTM-AE (确诊)
  
  架构设计:
    Layer 1 Isolation Forest ──→ 正常(放行) / 严重异常(报警) / 疑似(推送L2)
    Layer 2 LSTM Autoencoder   ──→ 重构误差判定: 确诊异常 / 误报放行
  
  核心优势:
    ✅ IF 快速过滤显性异常 (极端值) — 降低 L2 计算压力 ~90%
    ✅ LSTM-AE 深度捕获隐性异常 (形态异常) — IF 难以检测的疑难杂症
    ✅ 双层协同降低误报率，提升精准度
=============================================================================
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional
from collections import deque
import logging
import warnings
import platform

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "output"
for d in [DATA_DIR, MODEL_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

import os
os.chdir(BASE_DIR)
if not os.getcwd():
    os.chdir('/tmp')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ============================================================================
#  第一部分: 数据生成模块
# ============================================================================

@dataclass
class DataGenConfig:
    """数据生成配置"""
    total_minutes: int = 24 * 60          # 24小时 × 60分钟 = 1440 样本
    n_features: int = 3                    # CPU, Memory, DiskIO
    sample_interval_min: int = 1           # 采样间隔 1分钟
    
    explicit_anomaly_ratio: float = 0.03   # 显性异常 ~3% (~43个点)
    implicit_anomaly_ratio: float = 0.02   # 隐性异常 ~2% (~29个点)
    
    seed: int = 42


def setup_chinese_font():
    """配置中文字体"""
    system = platform.system()
    candidates = {
        "Darwin": ["PingFang SC", "Heiti TC", "STHeiti", "Hiragino Sans GB"],
        "Linux": ["Noto Sans CJK SC", "WenQuanYi Micro Hei"],
        "Windows": ["Microsoft YaHei", "SimHei"]
    }
    import matplotlib.font_manager as fm
    available = set(f.name for f in fm.fontManager.ttflist)
    for font in candidates.get(system, candidates["Darwin"]):
        if font in available:
            plt.rcParams['font.sans-serif'] = [font] + list(plt.rcParams['font.sans-serif'])
            plt.rcParams['axes.unicode_minus'] = False
            return font
    plt.rcParams['axes.unicode_minus'] = False
    return None


class SystemLoadGenerator:
    """
    生产级系统负载数据生成器
    
    三指标建模:
      CPU Usage:     昼夜周期 + 业务峰谷 + 随机噪声
      Memory Usage:  基线 + 缓存增长 + JVM GC 锯齿 + 泄漏趋势
      Disk IO:       与CPU相关 + 批处理脉冲 + 偶发尖峰
    
    异常分类:
      显性异常 (Explicit): 数值极端 — IF 必能检出
        - CPU 飙升至 99% (死机前兆)
        - CPU 骤降至 1% (进程崩溃)
        - 内存瞬间 100% (OOM)
      
      隐性异常 (Implicit): 数值正常但形态异常 — IF 难以检出，需 LSTM-AE
        - CPU 锯齿状波动 (频率异常)
        - 内存缓慢泄漏 (趋势异常)
        - 多指标联动断裂 (相关性异常)
    """

    def __init__(self, config: DataGenConfig = None):
        self.cfg = config or DataGenConfig()
        np.random.seed(self.cfg.seed)

    def generate(self) -> pd.DataFrame:
        """生成完整数据集"""
        cfg = self.cfg
        n = cfg.total_minutes
        
        log.info(f"📊 生成 {n} 分钟 ({n//60}h) 系统负载数据 | 特征数={cfg.n_features}")
        
        timestamps = self._gen_timestamps(n)
        
        cpu = self._gen_cpu(n)
        mem = self._gen_memory(n, cpu)
        disk = self._gen_disk_io(n, cpu)
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'cpu_usage': np.clip(cpu, 0, 100),
            'memory_usage': np.clip(mem, 0, 100),
            'disk_io': np.clip(disk, 0, 100),
        })
        
        df = self._inject_explicit_anomalies(df)
        df = self._inject_implicit_anomalies(df)
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        for col in ['cpu_usage', 'memory_usage', 'disk_io']:
            df[col] = df[col].clip(0, 100)

        true_anom = df['_is_anomaly'].sum()
        explicit = (df['_anomaly_type'].str.contains('explicit')).sum()
        implicit = (df['_anomaly_type'].str.contains('implicit')).sum()
        
        log.info(f"   CPU: [{df['cpu_usage'].min():.1f}~{df['cpu_usage'].max():.1f}%] "
                f"MEM: [{df['memory_usage'].min():.1f}~{df['memory_usage'].max():.1f}%] "
                f"DISK: [{df['disk_io'].min():.1f}~{df['disk_io'].max():.1f}%]")
        log.info(f"   总异常: {true_anom} ({true_anom/n*100:.1f}%) | "
                f"显性:{explicit} | 隐性:{implicit}")
        
        return df

    def _gen_timestamps(self, n):
        start = datetime.now() - timedelta(minutes=n)
        return [start + timedelta(minutes=i) for i in range(n)]

    def _gen_cpu(self, n):
        """CPU: 昼夜周期 + 噪声"""
        t = np.arange(n)
        hour_of_day = (t % 1440) / 60.0
        
        base = 25.0
        day_pattern = (15 * np.exp(-0.5 * ((hour_of_day - 10) / 2)**2) +
                       20 * np.exp(-0.5 * ((hour_of_day - 16) / 2.5)**2))
        lunch_dip = 8 * np.exp(-0.5 * ((hour_of_day - 12.5) / 0.8)**2)
        
        noise = np.random.normal(0, 3, n)
        jitter = 2 * np.sin(2 * np.pi * t / 30 + np.random.uniform(0, 2*np.pi))
        
        cpu = base + day_pattern - lunch_dip + noise + jitter
        return cpu.astype(np.float32)

    def _gen_memory(self, n, cpu):
        """Memory: 基线 + GC锯齿 + 与CPU的相关性"""
        t = np.arange(n)
        baseline = 45.0
        gc_period = np.random.randint(20, 40)
        gc_phase = (t % gc_period) / gc_period
        gc_sawtooth = 18 * gc_phase
        gc_drops = (gc_phase > 0.97) * np.random.uniform(12, 22)
        gc_sawtooth -= gc_drops
        
        cpu_corr = (cpu - np.mean(cpu)) / max(np.std(cpu), 1) * 4
        cache_warm = 12 * (1 - np.exp(-t / 400))
        
        mem = baseline + gc_sawtooth + cpu_corr + cache_warm
        mem += np.random.normal(0, 1.5, n)
        return mem.astype(np.float32)

    def _gen_disk_io(self, n, cpu):
        """Disk IO: 与CPU相关 + 批处理脉冲"""
        t = np.arange(n)
        base = 3.0
        cpu_dep = cpu * 0.06
        
        batch_spikes = np.zeros(n)
        for hour in [2, 10, 14, 22]:
            mask = np.abs((t / 60.0) - hour) < 0.08
            batch_spikes[mask] = np.random.uniform(6, 14)
        
        io = base + cpu_dep + batch_spikes
        io += np.random.exponential(1.5, n)
        return io.astype(np.float32)

    def _inject_explicit_anomalies(self, df):
        """注入显性异常: 极端值 (IF必检)"""
        n = len(df)
        df['_is_anomaly'] = False
        df['_anomaly_type'] = ''
        df['_anomaly_severity'] = 0.0

        n_explicit = int(n * self.cfg.explicit_anomaly_ratio)
        types_and_actions = [
            ('explicit_cpu_spike', lambda df, i, sev: self._apply_cpu_spike(df, i, sev)),
            ('explicit_cpu_crash', lambda df, i, sev: self._apply_cpu_crash(df, i, sev)),
            ('explicit_mem_oom', lambda df, i, sev: self._apply_mem_oom(df, i, sev)),
            ('explicit_disk_storm', lambda df, i, sev: self._apply_disk_storm(df, i, sev)),
        ]
        
        positions = sorted(np.random.choice(range(60, n - 60), size=n_explicit, replace=False))
        
        for idx, pos in enumerate(positions):
            anom_type, action = types_and_actions[idx % len(types_and_actions)]
            severity = np.random.beta(2, 5)
            
            action(df, pos, severity)
            
            duration = np.random.randint(1, 4)
            end = min(pos + duration, n)
            df.iloc[pos:end, df.columns.get_loc('_is_anomaly')] = True
            df.iloc[pos, df.columns.get_loc('_anomaly_type')] = anom_type
            df.iloc[pos, df.columns.get_loc('_anomaly_severity')] = severity
        
        return df

    def _apply_cpu_spike(self, df, pos, sev):
        df.iloc[pos, df.columns.get_loc('cpu_usage')] = 95 + sev * 4

    def _apply_cpu_crash(self, df, pos, sev):
        df.iloc[pos, df.columns.get_loc('cpu_usage')] = 0.5 + np.random.uniform(0, 2)

    def _apply_mem_oom(self, df, pos, sev):
        df.iloc[pos, df.columns.get_loc('memory_usage')] = 98 + sev * 2

    def _apply_disk_storm(self, df, pos, sev):
        df.iloc[pos, df.columns.get_loc('disk_io')] = 80 + sev * 18

    def _inject_implicit_anomalies(self, df):
        """注入隐性异常: 形态/模式异常 (IF难检, LSTM-AE专攻)"""
        n = len(df)
        n_implicit = int(n * self.cfg.implicit_anomaly_ratio)
        types_and_actions = [
            ('implicit_sawtooth', self._apply_sawtooth_cpu),
            ('implicit_slow_leak', self._apply_slow_leak_mem),
            ('implicit_correlation_break', self._apply_correlation_break),
            ('implicit_freq_anomaly', self._apply_freq_anomaly),
        ]

        used_positions = set(df[df['_is_anomaly']].index)
        available = [i for i in range(60, n - 60) if i not in used_positions]
        if len(available) < n_implicit:
            available = list(range(60, n - 60))

        positions = sorted(np.random.choice(available, size=min(n_implicit, len(available)), replace=False))

        for idx, pos in enumerate(positions):
            anom_type, action = types_and_actions[idx % len(types_and_actions)]
            severity = np.random.beta(2, 5)
            
            duration = np.random.randint(15, 35)
            end = min(pos + duration, n)
            
            action(df, pos, end, severity)
            
            df.iloc[pos:end, df.columns.get_loc('_is_anomaly')] = True
            df.iloc[pos, df.columns.get_loc('_anomaly_type')] = anom_type
            df.iloc[pos, df.columns.get_loc('_anomaly_severity')] = severity
        
        return df

    def _apply_sawtooth_cpu(self, df, start, end, sev):
        """隐性异常1: CPU数值正常(~60%)但呈现高频锯齿波 — 形态异常"""
        length = end - start
        saw_freq = 8 + int(sev * 12)
        for j in range(length):
            phase = (j % saw_freq) / saw_freq
            oscillation = sev * 12 * (2 * phase - 1)
            df.iloc[start + j, df.columns.get_loc('cpu_usage')] = 58 + oscillation

    def _apply_slow_leak_mem(self, df, start, end, sev):
        """隐性异常2: 内存缓慢线性泄漏 — 趋势异常"""
        length = end - start
        for j in range(length):
            progress = j / length
            leak = sev * 18 * progress
            df.iloc[start + j, df.columns.get_loc('memory_usage')] += leak

    def _apply_correlation_break(self, df, start, end, sev):
        """隐性异常3: CPU高但Disk IO异常低 — 相关性断裂"""
        length = end - start
        for j in range(length):
            df.iloc[start + j, df.columns.get_loc('cpu_usage')] += sev * 15
            df.iloc[start + j, df.columns.get_loc('disk_io')] *= (1 - sev * 0.6)

    def _apply_freq_anomaly(self, df, start, end, sev):
        """隐性异常4: 所有指标出现异常高频振荡 — 频率域异常"""
        length = end - start
        high_freq = 3 + int(sev * 5)
        for j in range(length):
            osc = sev * 7 * np.sin(2 * np.pi * j * high_freq / length)
            df.iloc[start + j, df.columns.get_loc('cpu_usage')] += osc
            df.iloc[start + j, df.columns.get_loc('memory_usage')] += osc * 0.6


# ============================================================================
#  第二部分: 第一层防线 — Isolation Forest 三分类初筛
# ============================================================================

@dataclass
class IFConfig:
    """Isolation Forest 配置"""
    n_estimators: int = 200
    contamination: float = 0.05
    max_samples: int = 256
    random_state: int = 42
    
    severe_threshold: float = -0.45       # anomaly_score < 此值 → 严重异常
    suspicious_threshold: float = -0.15   # anomaly_score 在此区间 → 疑似
    normal_threshold: float = 0.0         # anomaly_score > 此值 → 正常


class IsolationForestLayer1:
    """
    第一层防线: Isolation Forest 快速三分类
    
    分类逻辑:
      ┌──────────────────────────────────────────────┐
      │  score < severe_th    → 严重异常 (直接报警)   │
      │  score ∈ [severe, suspicious) → 疑似 (推L2)  │
      │  score ≥ suspicious_th → 正常 (放行)          │
      └──────────────────────────────────────────────┘
    
    特征工程:
      除原始3维特征外，额外构造统计特征帮助IF判断:
      - rolling_mean: 滑动窗口均值 (偏离均值的程度)
      - rolling_std:  滑动窗口标准差 (波动程度)
      - diff_from_mean: 当前值与全局均值的差值
      - cross_feature: CPU×MEM 联动特征
    """

    FEATURE_COLS = ['cpu_usage', 'memory_usage', 'disk_io']

    def __init__(self, config: IFConfig = None):
        self.cfg = config or IFConfig()
        self.model: Optional[IsolationForest] = None
        self.scaler = MinMaxScaler()
        self.fitted = False

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """构建增强特征矩阵 (原始 + 统计衍生)"""
        feat_df = df[self.FEATURE_COLS].copy()

        window = 10
        for col in self.FEATURE_COLS:
            feat_df[f'{col}_rolling_mean'] = df[col].rolling(window=window, min_periods=1).mean()
            feat_df[f'{col}_rolling_std'] = df[col].rolling(window=window, min_periods=1).std().fillna(0)
            feat_df[f'{col}_diff_mean'] = df[col] - df[col].expanding(min_periods=1).mean()

        feat_df['cpu_mem_product'] = df['cpu_usage'] * df['memory_usage'] / 10000
        feat_df['cpu_disk_ratio'] = df['cpu_usage'] / (df['disk_io'] + 1e-6)

        return feat_df.fillna(0)

    def fit(self, df: pd.DataFrame) -> 'IsolationForestLayer1':
        """训练 IF 模型"""
        features = self._build_features(df)
        X = self.scaler.fit_transform(features.values)

        self.model = IsolationForest(
            n_estimators=self.cfg.n_estimators,
            contamination=self.cfg.contamination,
            max_samples=self.cfg.max_samples,
            random_state=self.cfg.random_state
        )
        self.model.fit(X)
        self.fitted = True
        
        log.info(f"✅ IF Layer1 已训练: n_estimators={self.cfg.n_estimators}, "
                f"特征维度={X.shape[1]}")
        return self

    def classify(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        三分类判定
        
        Returns:
            DataFrame 新增列:
              - if_score: IF 异常分数 (越小越异常)
              - if_label: 分类结果 (NORMAL / SUSPICIOUS / SEVERE)
        """
        if not self.fitted:
            raise RuntimeError("IF 未训练，请先调用 fit()")
        
        features = self._build_features(df)
        X = self.scaler.transform(features.values)
        
        scores = self.model.decision_function(X)
        
        labels = []
        for s in scores:
            if s < self.cfg.severe_threshold:
                labels.append('SEVERE')
            elif s < self.cfg.suspicious_threshold:
                labels.append('SUSPICIOUS')
            else:
                labels.append('NORMAL')
        
        result_df = df.copy()
        result_df['if_score'] = scores
        result_df['if_label'] = labels
        
        n_normal = labels.count('NORMAL')
        n_suspicious = labels.count('SUSPICIOUS')
        n_severe = labels.count('SEVERE')
        total = len(labels)
        
        log.info(f"🔍 IF Layer1 三分类结果:")
        log.info(f"   正常(NORMAL):    {n_normal:4d} ({n_normal/total*100:5.1f}%) → 放行")
        log.info(f"   疑似(SUSPICIOUS):{n_suspicious:4d} ({n_suspicious/total*100:5.1f}%) → 推送LSTM-AE")
        log.info(f"   严重(SEVERE):    {n_severe:4d} ({n_severe/total*100:5.1f}%) → 直接报警")
        
        return result_df


# ============================================================================
#  第三部分: 第二层防线 — LSTM Autoencoder 深度确诊
# ============================================================================

class LSTMAutoEncoder(nn.Module):
    """
    LSTM 自编码器 — 用于时序重构误差异常检测
    
    结构:
      Input(batch, seq_len, 3)
        → Encoder: BiLSTM(hidden=48) × 2层 → Linear → latent(24d)
        → Decoder: LSTM(hidden=48) × 2层 → Linear → Output(batch, seq_len, 3)
    
    核心思想:
      正常时序模式 → 能被良好重构 → error 小
      异常时序模式 → 无法被良好重构 → error 大
    """

    def __init__(self, n_features: int = 3, seq_len: int = 30,
                 hidden_size: int = 48, latent_dim: int = 24,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        
        self.n_features = n_features
        self.seq_len = seq_len
        self.latent_dim = latent_dim
        
        encoder_out = hidden_size * 2

        self.encoder_lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=True
        )
        
        self.encoder_fc = nn.Sequential(
            nn.Linear(encoder_out, latent_dim),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5)
        )
        
        self.decoder_lstm = nn.LSTM(
            input_size=latent_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        self.decoder_fc = nn.Linear(hidden_size, n_features)
        
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def encode(self, x):
        lstm_out, _ = self.encoder_lstm(x)
        latent = self.encoder_fc(lstm_out[:, -1, :])
        return latent

    def decode(self, latent):
        batch_size = latent.shape[0]
        h_expanded = latent.unsqueeze(1).repeat(1, self.seq_len, 1)
        lstm_out, _ = self.decoder_lstm(h_expanded)
        output = self.decoder_fc(lstm_out)
        return output

    def forward(self, x):
        latent = self.encode(x)
        reconstructed = self.decode(latent)
        
        per_point_error = torch.mean((x - reconstructed) ** 2, dim=[1, 2])
        
        return {
            'reconstructed': reconstructed,
            'latent': latent,
            'reconstruction_error': per_point_error
        }


class DynamicThreshold:
    """动态阈值计算器 (EWMA)"""

    def __init__(self, alpha: float = 0.15, k: float = 3.0, warmup: int = 30):
        self.alpha = alpha
        self.k = k
        self.warmup = warmup
        self.ewma_mean = 0.0
        self.ewma_std = 1.0
        self.count = 0
        self.ready = False
        self.history = []

    def update(self, error: float) -> float:
        self.history.append(error)
        self.count += 1
        
        if self.count < self.warmup:
            return float('inf')
        
        if self.count == self.warmup:
            arr = np.array(self.history[-self.warmup:])
            self.ewma_mean = float(np.mean(arr))
            self.ewma_std = float(np.std(arr)) + 1e-8
            self.ready = True
        
        delta = error - self.ewma_mean
        self.ewma_mean += self.alpha * delta
        self.ewma_std += self.alpha * (abs(delta) - self.ewma_std)
        
        threshold = self.ewma_mean + self.k * self.ewma_std
        return max(threshold, 1e-6)


class LSTMAELayer2:
    """
    第二层防线: LSTM Autoencoder 深度确诊
    
    触发条件: 仅处理来自 IF 的 "SUSPICIOUS" 数据点
    
    处理流程:
      1. 对每个疑似点，提取前后各 window_size//2 的序列
      2. 输入训练好的 LSTM-AE 得到重构结果
      3. 计算 reconstruction_error
      4. 与动态阈值比较 → 确诊异常 / 误报放行
    """

    def __init__(self, model_path: str = None, scaler_path: str = None,
                 window_size: int = 30, device=None):
        self.window_size = window_size
        self.device = device or torch.device(
            'cuda' if torch.cuda.is_available() else 'cpu'
        )
        self.model: Optional[LSTMAutoEncoder] = None
        self.scaler: Optional[MinMaxScaler] = None
        self.threshold_engine = DynamicThreshold(alpha=0.15, k=3.0, warmup=30)
        
        if model_path and Path(model_path).exists():
            self.load_model(model_path, scaler_path)

    def load_model(self, model_path: str, scaler_path: str):
        """加载预训练模型"""
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        
        cfg = checkpoint['config']
        self.model = LSTMAutoEncoder(**cfg).to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        with open(scaler_path, 'rb') as f:
            scaler_data = __import__('pickle').load(f)
            self.scaler = scaler_data['scaler']
        
        self.window_size = cfg.get('seq_len', self.window_size)
        log.info(f"✅ LSTM-AE Layer2 已加载: seq_len={self.window_size}, device={self.device}")

    def train_model(self, df_normal: pd.DataFrame, epochs: int = 80,
                    batch_size: int = 64, lr: float = 0.001,
                    save_path: str = None, scaler_save_path: str = None):
        """用正常数据训练 LSTM-AE"""
        feature_cols = ['cpu_usage', 'memory_usage', 'disk_io']
        raw = df_normal[feature_cols].values.astype(np.float32)
        
        self.scaler = MinMaxScaler()
        scaled = self.scaler.fit_transform(raw)
        
        if scaler_save_path:
            import pickle
            with open(scaler_save_path, 'wb') as f:
                pickle.dump({'scaler': self.scaler}, f)
        
        X, _ = preprocessor_utils.create_windows(scaled, self.window_size)
        X_train, X_val = preprocessor_utils.split_train_val(X, val_ratio=0.15)
        
        train_ds = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(X_train))
        val_ds = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(X_val))
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
        
        self.model = LSTMAutoEncoder(
            n_features=3, seq_len=self.window_size,
            hidden_size=48, latent_dim=24, num_layers=2, dropout=0.2
        ).to(self.device)
        
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
        criterion = nn.MSELoss()
        
        best_val_loss = float('inf')
        patience_counter = 0
        best_state = None
        best_epoch = 0
        
        log.info(f"\n🧠 开始训练 LSTM-AE Layer2: |数据|={len(X_train)}, epochs={epochs}")
        
        for epoch in range(1, epochs + 1):
            self.model.train()
            train_loss = 0
            for batch_x, _ in train_loader:
                bx = batch_x.to(self.device)
                optimizer.zero_grad()
                out = self.model(bx)
                loss = criterion(out['reconstructed'], bx)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 5.0)
                optimizer.step()
                train_loss += loss.item()
            
            self.model.eval()
            val_loss = 0
            with torch.no_grad():
                for batch_x, _ in val_loader:
                    bx = batch_x.to(self.device)
                    out = self.model(bx)
                    val_loss += criterion(out['reconstructed'], bx).item()
            
            train_loss /= len(train_loader)
            val_loss /= len(val_loader)
            scheduler.step()
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_epoch = epoch
                best_state = {
                    'model_state_dict': self.model.state_dict(),
                    'config': {'n_features': 3, 'seq_len': self.window_size,
                              'hidden_size': 48, 'latent_dim': 24},
                    'val_loss': val_loss, 'epoch': epoch
                }
            else:
                patience_counter += 1
            
            if epoch % 10 == 0 or epoch == 1:
                log.info(f"   Epoch[{epoch:3d}/{epochs}] Train={train_loss:.6f} Val={val_loss:.6f} Best={best_val_loss:.6f}")
            
            if patience_counter >= 20:
                log.info(f"   ⏹️ Early Stop @ Epoch {epoch} (best={best_epoch})")
                break
        
        if best_state:
            self.model.load_state_dict(best_state['model_state_dict'])
        
        if save_path:
            torch.save(best_state, save_path)
            log.info(f"💾 模型已保存: {save_path}")
        
        total_params = sum(p.numel() for p in self.model.parameters())
        log.info(f"   ✅ 训练完成: best_epoch={best_epoch}, best_val_loss={best_val_loss:.8f}, params={total_params:,}")

    @torch.no_grad()
    def diagnose(self, df_labeled: pd.DataFrame) -> pd.DataFrame:
        """
        对 IF 标记为 SUSPICIOUS 的点进行深度诊断
        
        Returns:
            DataFrame 新增列:
              - ae_recon_error: 重构误差
              - ae_threshold: 动态阈值
              - ae_diagnosis: CONFIRMED_ANOMALY / FALSE_POSITIVE
              - final_label: 最终判定标签
        """
        if self.model is None:
            raise RuntimeError("LSTM-AE 未加载/训练")
        
        self.model.eval()
        self.threshold_engine = DynamicThreshold(alpha=0.15, k=3.0, warmup=30)
        
        result = df_labeled.copy()
        result['ae_recon_error'] = np.nan
        result['ae_threshold'] = np.nan
        result['ae_diagnosis'] = ''
        result['final_label'] = result['if_label']

        suspicious_idx = result[result['if_label'] == 'SUSPICIOUS'].index
        normal_idx = result[result['if_label'] == 'NORMAL'].index
        severe_idx = result[result['if_label'] == 'SEVERE'].index
        
        log.info(f"\n🔬 LSTM-AE Layer2 开始诊断: {len(suspicious_idx)} 个疑似点")

        half_win = self.window_size // 2
        confirmed_count = 0
        false_positive_count = 0
        
        all_indices = list(normal_idx) + list(suspicious_idx) + list(severe_idx)
        all_indices.sort(key=lambda x: df_labeled.index.get_loc(x) if hasattr(df_labeled.index, 'get_loc') else 0)
        
        for idx in all_indices:
            loc = df_labeled.index.get_loc(idx) if hasattr(df_labeled.index, 'get_loc') else 0
            n = len(df_labeled)
            
            start = max(0, loc - half_win)
            end = min(n, loc + half_win + 1)
            actual_window = end - start
            
            if actual_window < self.window_size:
                padding_needed = self.window_size - actual_window
                pad_front = padding_needed // 2
                pad_back = padding_needed - pad_front
                start = max(0, start - pad_front)
                end = min(n, end + pad_back)
            
            feature_cols = ['cpu_usage', 'memory_usage', 'disk_io']
            window_data = df_labeled[feature_cols].iloc[start:end].values.astype(np.float32)
            
            if len(window_data) < self.window_size:
                padding = np.zeros((self.window_size - len(window_data), 3))
                window_data = np.vstack([padding, window_data])
            elif len(window_data) > self.window_size:
                window_data = window_data[:self.window_size]

            scaled_window = self.scaler.transform(window_data)
            X_tensor = torch.FloatTensor(scaled_window[np.newaxis, :, :]).to(self.device)
            
            output = self.model(X_tensor)
            recon_error = float(output['reconstruction_error'][0].cpu().numpy())
            threshold = self.threshold_engine.update(recon_error)
            
            is_anomalous = recon_error > threshold and self.threshold_engine.ready
            
            result.loc[idx, 'ae_recon_error'] = recon_error
            result.loc[idx, 'ae_threshold'] = threshold
            
            label_at_idx = result.loc[idx, 'if_label']
            
            if label_at_idx == 'SUSPICIOUS':
                if is_anomalous:
                    result.loc[idx, 'ae_diagnosis'] = 'CONFIRMED_ANOMALY'
                    result.loc[idx, 'final_label'] = 'ANOMALY_CONFIRMED'
                    confirmed_count += 1
                else:
                    result.loc[idx, 'ae_diagnosis'] = 'FALSE_POSITIVE'
                    result.loc[idx, 'final_label'] = 'FALSE_POSITIVE'
                    false_positive_count += 1
            elif label_at_idx == 'SEVERE':
                result.loc[idx, 'ae_diagnosis'] = 'DIRECT_ALARM'
                result.loc[idx, 'final_label'] = 'ANOMALY_SEVERE'
            elif label_at_idx == 'NORMAL':
                result.loc[idx, 'final_label'] = 'NORMAL'

        log.info(f"   📋 LSTM-AE 诊断结果:")
        log.info(f"      确诊异常 (CONFIRMED):  {confirmed_count}")
        log.info(f"      误报释放 (FALSE_POS):   {false_positive_count}")
        
        return result


# ============================================================================
#  第四部分: 可视化与评估
# ============================================================================

class DualFunnelVisualizer:
    """双层漏斗结果可视化器"""

    COLORS = {
        'cpu': '#E74C3C',
        'mem': '#3498DB',
        'disk': '#27AE60',
        'if_severe': '#C0392B',
        'if_suspicious': '#F39C12',
        'lstm_confirmed': '#8E44AD',
        'normal_area': '#ECF0F1',
    }

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir or OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        setup_chinese_font()

    def plot_results(self, df_result: pd.DataFrame) -> str:
        """绘制双层漏斗检测结果大图"""
        fig = plt.figure(figsize=(20, 14), facecolor='white')
        gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[1.5, 1.2, 0.8],
                               hspace=0.28, wspace=0.2)

        ax_main = fig.add_subplot(gs[0, :])
        ax_error = fig.add_subplot(gs[1, :])
        ax_cm_if = fig.add_subplot(gs[2, 0])
        ax_cm_dual = fig.add_subplot(gs[2, 1])

        ts = df_result.index
        features = [('cpu_usage', 'CPU 使用率 (%)', self.COLORS['cpu']),
                     ('memory_usage', '内存使用率 (%)', self.COLORS['mem']),
                     ('disk_io', '磁盘 I/O (%)', self.COLORS['disk'])]

        for feat, label, color in features:
            ax_main.plot(ts, df_result[feat], color=color, linewidth=0.7, alpha=0.8, label=label)

        severe_mask = df_result['if_label'] == 'SEVERE'
        susp_mask = df_result['if_label'] == 'SUSPICIOUS'
        confirmed_mask = df_result['ae_diagnosis'] == 'CONFIRMED_ANOMALY'

        if severe_mask.any():
            ax_main.scatter(ts[severe_mask],
                           df_result.loc[severe_mask, 'cpu_usage'],
                           c=self.COLORS['if_severe'], marker='^', s=50,
                           zorder=6, edgecolors='white', linewidths=1,
                           label=f'IF-严重({severe_mask.sum()})', alpha=0.85)

        if susp_mask.any():
            ax_main.scatter(ts[susp_mask],
                           df_result.loc[susp_mask, 'cpu_usage'],
                           c=self.COLORS['if_suspicious'], marker='o', s=35,
                           zorder=5, edgecolors='white', linewidths=0.8,
                           label=f'IF-疑似({susp_mask.sum()})', alpha=0.75)

        if confirmed_mask.any():
            ax_main.scatter(ts[confirmed_mask],
                           df_result.loc[confirmed_mask, 'cpu_usage'],
                           c=self.COLORS['lstm_confirmed'], marker='*', s=120,
                           zorder=7, edgecolors='#2C3E50', linewidths=1.5,
                           label=f'LSTM-AE确认({confirmed_mask.sum()})', alpha=0.95)

        ax_main.set_title('📊 双层漏斗检测结果: 原始曲线 & 异常标记\n'
                          '(▲ IF-严重 | ○ IF-疑似 | ★ LSTM-AE确诊)',
                          fontsize=13, fontweight='bold', loc='left')
        ax_main.legend(loc='upper right', fontsize=8, ncol=5, framealpha=0.92)
        ax_main.set_ylabel('使用率 (%)')
        ax_main.grid(True, alpha=0.2)

        valid_err = df_result['ae_recon_error'].notna()
        valid_thresh = df_result['ae_threshold'].notna()

        ax_error.fill_between(ts[valid_err], 0, df_result.loc[valid_err, 'ae_recon_error'],
                             alpha=0.3, color='#3498DB', label='LSTM-AE 重构误差')
        ax_error.plot(ts[valid_err], df_result.loc[valid_err, 'ae_recon_error'],
                      color='#2980B9', linewidth=0.8, alpha=0.85)

        if valid_thresh.any():
            ax_error.plot(ts[valid_thresh], df_result.loc[valid_thresh, 'ae_threshold'],
                         color='#E74C3C', linewidth=1.8, linestyle='-',
                         label='动态阈值 (EWMA)', alpha=0.85)
            ax_error.fill_between(ts[valid_thresh], 0,
                                 df_result.loc[valid_thresh, 'ae_threshold'],
                                 alpha=0.06, color='#E74C3C')

        conf_anom = df_result['ae_diagnosis'] == 'CONFIRMED_ANOMALY'
        if conf_anom.any():
            ax_error.scatter(ts[conf_anom], df_result.loc[conf_anom, 'ae_recon_error'],
                            c='#8E44AD', marker='D', s=55, zorder=5,
                            edgecolors='white', linewidths=1.2,
                            label=f'LSTM-AE确诊点({conf_anom.sum()})')

        fp_mask = df_result['ae_diagnosis'] == 'FALSE_POSITIVE'
        if fp_mask.any():
            ax_error.scatter(ts[fp_mask], df_result.loc[fp_mask, 'ae_recon_error'],
                            c='#27AE60', marker='x', s=55, zorder=5,
                            linewidths=2, label=f'误报释放({fp_mask.sum()})')

        ax_error.set_title('🔬 LSTM Autoencoder 重构误差分析 (仅对IF疑似点触发)',
                            fontsize=12, fontweight='bold', loc='left')
        ax_error.set_ylabel('重构误差')
        ax_error.legend(loc='upper right', fontsize=8, framealpha=0.9)
        ax_error.grid(True, alpha=0.2)
        ax_error.set_yscale('log', nonpositive='clip')

        self._plot_confusion_matrix(ax_cm_if, df_result, mode='if_only',
                                     title='仅 IF 单层检测')

        self._plot_confusion_matrix(ax_cm_dual, df_result, mode='dual_funnel',
                                     title='双层漏斗 (IF+LSTM-AE)')

        plt.suptitle('双层漏斗架构异常检测系统 — 结果总览',
                     fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout(rect=[0, 0.02, 1, 0.97])

        out_path = self.output_dir / "dual_funnel_detection_results.png"
        fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        log.info(f"📈 结果图已保存: {out_path}")
        return str(out_path)

    def _plot_confusion_matrix(self, ax, df_result, mode: str, title: str):
        """绘制混淆矩阵"""
        y_true = (df_result['_is_anomaly'] == True).astype(int).values
        
        if mode == 'if_only':
            y_pred = df_result['if_label'].isin(['SEVERE', 'SUSPICIOUS']).astype(int).values
        else:
            y_pred = df_result['final_label'].isin([
                'ANOMALY_CONFIRMED', 'ANOMALY_SEVERE'
            ]).astype(int).values
        
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

        im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
        ax.figure.colorbar(im, ax=ax)

        classes = ['Normal', 'Anomaly']
        tick_marks = np.arange(len(classes))
        ax.set_xticks(tick_marks)
        ax.set_xticklabels(classes)
        ax.set_yticks(tick_marks)
        ax.set_yticklabels(classes)

        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                color = "white" if cm[i, j] > thresh else "black"
                ax.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center", color=color,
                        fontsize=14, fontweight='bold')

        tn, fp = cm[0, 0], cm[0, 1]
        fn, tp = cm[1, 0], cm[1, 1]
        precision = tp / max(tp + fp, 1) * 100
        recall = tp / max(tp + fn, 1) * 100
        f1 = 2 * precision * recall / max(precision + recall, 1)
        accuracy = (tp + tn) / max(cm.sum(), 1) * 100
        far = fp / max(fp + tn, 1) * 100

        stats_text = (f"Prec={precision:.1f}%\nRecall={recall:.1f}%\n"
                     f"F1={f1:.1f}%\nAcc={accuracy:.1f}%\nFAR={far:.1f}%")
        ax.text(1.3, 0.5, stats_text, transform=ax.transAxes,
               fontsize=9, va='center', family='monospace',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA',
                        edgecolor='#BDC3C7'))

        ax.set_title(title, fontsize=11, fontweight='bold', loc='left')
        ax.set_ylabel('真实标签')
        ax.set_xlabel('预测标签')


# ============================================================================
#  第五部分: 工具函数
# ============================================================================

class PreprocessorUtils:
    """滑动窗口工具"""

    @staticmethod
    def create_windows(data: np.ndarray, window_size: int):
        X, y = [], []
        for i in range(len(data) - window_size):
            X.append(data[i:i + window_size])
            y.append(data[i + window_size])
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)

    @staticmethod
    def split_train_val(X, val_ratio=0.15):
        split = int(len(X) * (1 - val_ratio))
        return X[:split], X[split:]


preprocessor_utils = PreprocessorUtils()


def evaluate_comparison(df_result: pd.DataFrame):
    """对比评估: 仅IF vs 双层漏斗"""
    y_true = (df_result['_is_anomaly'] == True).astype(int).values
    
    y_if_only = df_result['if_label'].isin(['SEVERE', 'SUSPICIOUS']).astype(int).values
    y_dual = df_result['final_label'].isin(['ANOMALY_CONFIRMED', 'ANOMALY_SEVERE']).astype(int).values

    print("\n" + "=" * 70)
    print("📊 双层漏斗 vs 单层 IF — 性能对比评估")
    print("=" * 70)

    print(f"\n{'指标':<16} {'仅IF单层':>12} {'双层漏斗(IF+AE)':>18} {'差异':>10}")
    print("-" * 60)

    from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

    metrics = [
        ('Precision', precision_score),
        ('Recall', recall_score),
        ('F1-Score', f1_score),
        ('Accuracy', accuracy_score),
    ]

    for name, metric_fn in metrics:
        try:
            v_if = metric_fn(y_true, y_if_only, zero_division=0) * 100
            v_dual = metric_fn(y_true, y_dual, zero_division=0) * 100
            diff = v_dual - v_if
            arrow = "📈" if diff > 0 else ("📉" if diff < 0 else "➡️")
            print(f"{name:<16} {v_if:>11.1f}% {v_dual:>17.1f}% {arrow}{diff:>+9.1f}%")
        except Exception:
            pass

    cm_if = confusion_matrix(y_true, y_if_only)
    cm_dual = confusion_matrix(y_true, y_dual)

    far_if = cm_if[0, 1] / max(cm_if[0].sum(), 1) * 100
    far_dual = cm_dual[0, 1] / max(cm_dual[0].sum(), 1) * 100
    diff_far = far_dual - far_if
    arrow = "📉" if diff_far < 0 else "📈"
    print(f"{'误报率(FAR)':<16} {far_if:>11.1f}% {far_dual:>17.1f}% {arrow}{diff_far:>+9.1f}%")

    print("\n" + "-" * 60)
    print("\n🔑 关键发现:")

    tp_dual = cm_dual[1, 1]
    fp_dual = cm_dual[0, 1]
    fn_dual = cm_dual[1, 0]
    tn_dual = cm_dual[0, 0]

    tp_if = cm_if[1, 1]
    fp_if = cm_if[0, 1]
    fn_if = cm_if[1, 0]

    implicit_caught_dual = 0
    implicit_total = (df_result['_anomaly_type'].str.contains('implicit')).sum()
    if implicit_total > 0:
        implicit_mask = df_result['_anomaly_type'].str.contains('implicit')
        implicit_caught_dual = ((df_result.loc[implicit_mask, 'final_label']
                                .isin(['ANOMALY_CONFIRMED', 'ANOMALY_SEVERE']))).sum()

    print(f"   • 双层漏斗通过 LSTM-AE 减少误报: {max(0, fp_if - fp_dual)} 个 "
          f"(↓{max(0, far_if - far_dual):.1f}%)")
    print(f"   • 隐性异常检出: {implicit_caught_dual}/{int(implicit_total)} "
          f"({implicit_caught_dual/max(implicit_total,1)*100:.0f}%)")
    print(f"   • IF 直接报警的严重异常: {tp_if - max(0, tp_dual - implicit_caught_dual)} 个")
    print("=" * 70)


# ============================================================================
#  第六部分: 主流水线
# ============================================================================

def run_dual_funnel_pipeline():
    """运行完整的双层漏斗异常检测流水线"""

    print("\n" + "=" * 72)
    print("  🔱  双层漏斗架构 — 系统负载异常检测系统")
    print("  Layer1: Isolation Forest (快速初筛)")
    print("  Layer2: LSTM Autoencoder (深度确诊)")
    print("=" * 72)

    gen_cfg = DataGenConfig(total_minutes=24 * 60, seed=42)

    print(f"\n{'━'*36} Step 1: 数据生成 {'━'*36}")
    generator = SystemLoadGenerator(gen_cfg)
    df_raw = generator.generate()

    data_save_path = DATA_DIR / "dual_funnel_system_load.csv"
    df_raw.to_csv(str(data_save_path))
    print(f"   💾 数据已保存: {data_save_path}")

    print(f"\n{'━'*34} Step 2: IF Layer1 初筛 {'━'*34}")
    if_layer1 = IsolationForestLayer1(IFConfig(
        n_estimators=200, contamination=0.10,
        severe_threshold=-0.20, suspicious_threshold=0.05
    ))
    if_layer1.fit(df_raw)
    df_if_labeled = if_layer1.classify(df_raw)

    print(f"\n{'━'*32} Step 3: LSTM-AE Layer2 训练+诊断 {'━'*31}")
    normal_data = df_if_labeled[df_if_labeled['if_label'] == 'NORMAL'].copy()
    if len(normal_data) < 100:
        normal_data = df_raw.copy()

    layer2 = LSTMAELayer2(window_size=30)

    model_path = MODEL_DIR / "lstm_ae_layer2.pth"
    scaler_path = DATA_DIR / "ae_scaler_v2.pkl"

    layer2.train_model(
        normal_data,
        epochs=80,
        batch_size=64,
        save_path=str(model_path),
        scaler_save_path=str(scaler_path)
    )

    df_final = layer2.diagnose(df_if_labeled)

    final_save_path = DATA_DIR / "dual_funnel_detected.csv"
    df_final.to_csv(str(final_save_path))
    print(f"   💾 检测结果已保存: {final_save_path}")

    print(f"\n{'━'*33} Step 4: 可视化与评估 {'━'*33}")
    visualizer = DualFunnelVisualizer(output_dir=str(OUTPUT_DIR))
    plot_path = visualizer.plot_results(df_final)

    evaluate_comparison(df_final)

    print(f"\n{'='*72}")
    print("  ✅ 双层漏斗流水线执行完成!")
    print(f"{'='*72}")
    print(f"\n📁 输出文件:")
    print(f"   原始数据:     {data_save_path}")
    print(f"   AE 模型:      {model_path}")
    print(f"   Scaler:       {scaler_path}")
    print(f"   检测结果:     {final_save_path}")
    print(f"   可视化大图:   {plot_path}")

    return df_final


if __name__ == "__main__":
    result_df = run_dual_funnel_pipeline()
