"""
=============================================================================
  实时监控系统 — 双层漏斗架构 + 邮件报警
  Real-Time AIOps Monitor: IF (初筛) → LSTM-AE (确诊) → Email Alert
  
  架构:
    数据流模拟器 ──→ IF Layer1 ──→ LSTM-AE Layer2 ──→ 邮件报警
                     ├─ 正常: 放行
                     ├─ 严重: 直接报警
                     └─ 疑似: 深度确诊
                              ├─ 确诊异常: 报警
                              └─ 误报: 释放
  
  启动前自动训练模型，运行时实时检测 + 邮件通知 (含防轰炸冷却)
=============================================================================
"""

import os
import sys
import time
import smtplib
import logging
import warnings
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from collections import deque

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
for d in [DATA_DIR, MODEL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

os.chdir(BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)


# ============================================================================
#  全局配置 — 从 .env 读取
# ============================================================================

ENV_PATH = Path(__file__).parent.parent.parent / "aiops-platform" / "backend" / ".env"


def load_env(env_path: str = None) -> Dict[str, str]:
    env = {}
    p = Path(env_path) if env_path else ENV_PATH
    if not p.exists():
        log.warning(f".env 不存在: {p}, 使用默认值")
        return {}
    with open(p, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


_env = load_env()

SMTP_HOST = _env.get("SMTP_HOST", "smtp.163.com")
SMTP_PORT = int(_env.get("SMTP_PORT", "465"))
SMTP_USER = _env.get("SMTP_USER", "")
SMTP_PASSWORD = _env.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = _env.get("SMTP_FROM_EMAIL", SMTP_USER)
ALERT_TO_EMAIL = _env.get("ALERT_TO_EMAIL", SMTP_USER)

ALERT_COOLDOWN = 60

STREAM_INTERVAL = 0.5
WINDOW_SIZE = 30
N_FEATURES = 3

IF_SEVERE_THRESHOLD = -0.20
IF_SUSPICIOUS_THRESHOLD = 0.05
IF_CONTAMINATION = 0.08

AE_THRESHOLD_K = 2.5
AE_WARMUP = 20


# ============================================================================
#  第一部分: 滑动窗口
# ============================================================================

class SlidingWindow:
    """
    滑动窗口 — 维护最近 N 个数据点供 LSTM-AE 使用
    
    工作方式:
      - 每次 append 新数据点 (3维: CPU, MEM, DISK)
      - 窗口满后自动淘汰最早的数据
      - get_sequence() 返回 (WINDOW_SIZE, 3) 的 numpy 数组
    """

    def __init__(self, window_size: int = WINDOW_SIZE, n_features: int = N_FEATURES):
        self.window_size = window_size
        self.n_features = n_features
        self._buffer = deque(maxlen=window_size)
        self._timestamps = deque(maxlen=window_size)

    def append(self, values: np.ndarray, timestamp: datetime = None):
        if len(values) != self.n_features:
            raise ValueError(f"期望 {self.n_features} 维, 收到 {len(values)} 维")
        self._buffer.append(values.copy())
        self._timestamps.append(timestamp or datetime.now())

    def is_ready(self) -> bool:
        return len(self._buffer) >= self.window_size

    def get_sequence(self) -> np.ndarray:
        if not self.is_ready():
            raise ValueError(f"窗口未满: {len(self._buffer)}/{self.window_size}")
        return np.array(list(self._buffer), dtype=np.float32)

    def get_timestamps(self) -> List[datetime]:
        return list(self._timestamps)

    @property
    def count(self) -> int:
        return len(self._buffer)

    def recent_values(self, n: int = 5) -> np.ndarray:
        n = min(n, len(self._buffer))
        return np.array(list(self._buffer)[-n:], dtype=np.float32)


# ============================================================================
#  第二部分: 实时数据流模拟器
# ============================================================================

class DataStreamSimulator:
    """
    实时数据流模拟器 — 逐点生成系统负载数据
    
    正常模式:
      CPU:    昼夜周期 (基线25% + 日间峰值 + 午间低谷) + 高斯噪声
      Memory: 基线45% + GC锯齿 + 与CPU相关性
      DiskIO: 基线3% + CPU依赖 + 批处理脉冲
    
    异常注入 (随机触发):
      突发异常: CPU飙至99% / CPU骤降至1% / 内存OOM
      隐蔽异常: CPU锯齿波 / 内存缓慢泄漏 / 相关性断裂
    """

    def __init__(self, seed: int = 42, explicit_prob: float = 0.03,
                 implicit_prob: float = 0.02):
        self.rng = np.random.RandomState(seed)
        self.tick = 0
        self.explicit_prob = explicit_prob
        self.implicit_prob = implicit_prob

        self._implicit_active = False
        self._implicit_type = None
        self._implicit_remaining = 0
        self._implicit_severity = 0.0

    def _base_cpu(self) -> float:
        t = self.tick
        hour = (t % 1440) / 60.0
        base = 25.0
        day = (15 * np.exp(-0.5 * ((hour - 10) / 2) ** 2) +
               20 * np.exp(-0.5 * ((hour - 16) / 2.5) ** 2))
        lunch = 8 * np.exp(-0.5 * ((hour - 12.5) / 0.8) ** 2)
        noise = self.rng.normal(0, 3)
        jitter = 2 * np.sin(2 * np.pi * t / 30 + 1.5)
        return base + day - lunch + noise + jitter

    def _base_memory(self, cpu: float) -> float:
        t = self.tick
        baseline = 45.0
        gc_phase = (t % 35) / 35
        gc_saw = 18 * gc_phase
        gc_drop = 15 if gc_phase > 0.97 else 0
        cpu_corr = (cpu - 35) / 15 * 4
        cache = 12 * (1 - np.exp(-t / 400))
        noise = self.rng.normal(0, 1.5)
        return baseline + gc_saw - gc_drop + cpu_corr + cache + noise

    def _base_disk(self, cpu: float) -> float:
        t = self.tick
        base = 3.0
        cpu_dep = cpu * 0.06
        batch = 0
        hour = (t / 60.0) % 24
        for h in [2, 10, 14, 22]:
            if abs(hour - h) < 0.1:
                batch = self.rng.uniform(6, 14)
                break
        noise = self.rng.exponential(1.5)
        return base + cpu_dep + batch + noise

    def generate_point(self) -> Tuple[np.ndarray, Dict]:
        self.tick += 1

        cpu = self._base_cpu()
        mem = self._base_memory(cpu)
        disk = self._base_disk(cpu)

        anomaly_info = {'is_anomaly': False, 'type': '', 'source': ''}

        if self._implicit_active and self._implicit_remaining > 0:
            cpu, mem, disk = self._apply_implicit(cpu, mem, disk)
            anomaly_info = {
                'is_anomaly': True,
                'type': self._implicit_type,
                'source': 'implicit'
            }
            self._implicit_remaining -= 1
            if self._implicit_remaining <= 0:
                self._implicit_active = False
        elif self.rng.random() < self.explicit_prob:
            cpu, mem, disk, anomaly_info = self._inject_explicit(cpu, mem, disk)
        elif not self._implicit_active and self.rng.random() < self.implicit_prob:
            self._start_implicit()
            cpu, mem, disk = self._apply_implicit(cpu, mem, disk)
            anomaly_info = {
                'is_anomaly': True,
                'type': self._implicit_type,
                'source': 'implicit'
            }
            self._implicit_remaining -= 1

        values = np.array([
            np.clip(cpu, 0, 100),
            np.clip(mem, 0, 100),
            np.clip(disk, 0, 100)
        ], dtype=np.float32)

        return values, anomaly_info

    def _inject_explicit(self, cpu, mem, disk) -> Tuple[float, float, float, Dict]:
        atype = self.rng.choice([
            'cpu_spike', 'cpu_crash', 'mem_oom', 'disk_storm'
        ])
        if atype == 'cpu_spike':
            cpu = 95 + self.rng.uniform(0, 4.5)
        elif atype == 'cpu_crash':
            cpu = 0.5 + self.rng.uniform(0, 2)
        elif atype == 'mem_oom':
            mem = 98 + self.rng.uniform(0, 2)
        elif atype == 'disk_storm':
            disk = 80 + self.rng.uniform(0, 18)
        return cpu, mem, disk, {
            'is_anomaly': True, 'type': atype, 'source': 'explicit'
        }

    def _start_implicit(self):
        self._implicit_active = True
        self._implicit_type = self.rng.choice([
            'sawtooth', 'slow_leak', 'correlation_break'
        ])
        self._implicit_remaining = self.rng.randint(15, 35)
        self._implicit_severity = self.rng.beta(2, 5)

    def _apply_implicit(self, cpu, mem, disk) -> Tuple[float, float, float]:
        sev = self._implicit_severity
        if self._implicit_type == 'sawtooth':
            phase = (self._implicit_remaining % 8) / 8
            osc = sev * 12 * (2 * phase - 1)
            cpu = 58 + osc
        elif self._implicit_type == 'slow_leak':
            progress = 1 - (self._implicit_remaining / 25.0)
            mem += sev * 18 * progress
        elif self._implicit_type == 'correlation_break':
            cpu += sev * 15
            disk *= (1 - sev * 0.6)
        return cpu, mem, disk


def generate_data_stream(simulator: DataStreamSimulator = None):
    """
    生成器函数 — 模拟实时数据流
    
    每次迭代:
      1. 生成一个数据点 (CPU, MEM, DISK)
      2. time.sleep(0.5) 模拟数据到达间隔
      3. yield (timestamp, values, anomaly_info)
    """
    sim = simulator or DataStreamSimulator()
    while True:
        values, anomaly_info = sim.generate_point()
        timestamp = datetime.now()
        time.sleep(STREAM_INTERVAL)
        yield timestamp, values, anomaly_info


# ============================================================================
#  第三部分: LSTM Autoencoder 模型
# ============================================================================

class LSTMAutoEncoder(nn.Module):
    """
    LSTM 自编码器 — 时序重构误差异常检测
    
    ┌─────────────────────────────────────────────────────────────┐
    │  Encoder:                                                   │
    │    Input(batch, seq_len, 3)                                 │
    │      → BiLSTM(input=3, hidden=48, layers=2, bidirectional) │
    │      → 取最后时间步输出 (batch, 96)                         │
    │      → Linear(96 → 24) + ReLU + Dropout                    │
    │      → latent vector (batch, 24)                            │
    │                                                             │
    │  Decoder:                                                   │
    │    latent (batch, 24)                                       │
    │      → repeat 到 (batch, seq_len, 24)                      │
    │      → LSTM(input=24, hidden=48, layers=2)                 │
    │      → Linear(48 → 3)                                      │
    │      → reconstructed (batch, seq_len, 3)                   │
    │                                                             │
    │  判定: MSE(input, reconstructed) → 重构误差                 │
    │    正常模式 → 重构误差小                                    │
    │    异常模式 → 重构误差大                                    │
    └─────────────────────────────────────────────────────────────┘
    """

    def __init__(self, n_features: int = 3, seq_len: int = 30,
                 hidden_size: int = 48, latent_dim: int = 24,
                 num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.n_features = n_features
        self.seq_len = seq_len
        self.latent_dim = latent_dim

        # ---- Encoder ----
        # 双向LSTM: 从两个方向扫描时序, 捕获前后文依赖
        # 输出维度 = hidden_size * 2 (双向拼接)
        self.encoder_lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=True
        )
        # 将 BiLSTM 输出压缩到低维潜在空间
        encoder_out_dim = hidden_size * 2
        self.encoder_fc = nn.Sequential(
            nn.Linear(encoder_out_dim, latent_dim),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5)
        )

        # ---- Decoder ----
        # 将潜在向量复制 seq_len 次, 逐步还原时序
        self.decoder_lstm = nn.LSTM(
            input_size=latent_dim,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0
        )
        # 映射回原始特征维度
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


# ============================================================================
#  第四部分: 动态阈值 (EWMA)
# ============================================================================

class DynamicThreshold:
    """
    EWMA 动态阈值 — 自适应判定重构误差是否异常
    
    原理:
      threshold = ewma_mean + k * ewma_std
      - ewma_mean/std 通过指数加权移动平均实时更新
      - k 控制灵敏度 (越小越敏感)
      - warmup 阶段阈值设为 inf, 避免误判
    """

    def __init__(self, alpha: float = 0.15, k: float = AE_THRESHOLD_K,
                 warmup: int = AE_WARMUP):
        self.alpha = alpha
        self.k = k
        self.warmup = warmup
        self.ewma_mean = 0.0
        self.ewma_std = 1.0
        self.count = 0
        self.ready = False
        self.history = []

    def update_and_check(self, error: float) -> Tuple[float, bool]:
        self.history.append(error)
        self.count += 1

        if self.count < self.warmup:
            return float('inf'), False

        if self.count == self.warmup:
            arr = np.array(self.history[-self.warmup:])
            self.ewma_mean = float(np.mean(arr))
            self.ewma_std = float(np.std(arr)) + 1e-8
            self.ready = True

        threshold = self.ewma_mean + self.k * self.ewma_std
        is_anomaly = self.ready and error > threshold

        delta = error - self.ewma_mean
        self.ewma_mean += self.alpha * delta
        self.ewma_std += self.alpha * (abs(delta) - self.ewma_std)

        return max(threshold, 1e-6), is_anomaly


# ============================================================================
#  第五部分: 模型训练器 — 启动前自动训练
# ============================================================================

class ModelTrainer:
    """
    模型训练器 — 自动生成训练数据并训练 IF + LSTM-AE
    
    流程:
      1. 生成 24h 正常负载数据 (无异常注入)
      2. 训练 Isolation Forest (含特征工程)
      3. 训练 LSTM Autoencoder (仅用正常数据)
      4. 保存模型和 scaler
    """

    FEATURE_COLS = ['cpu_usage', 'memory_usage', 'disk_io']

    def __init__(self):
        self.if_model: Optional[IsolationForest] = None
        self.if_scaler = MinMaxScaler()
        self.ae_model: Optional[LSTMAutoEncoder] = None
        self.ae_scaler = MinMaxScaler()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def train_all(self):
        log.info("=" * 60)
        log.info("  🏋️  开始模型训练 (IF + LSTM-AE)")
        log.info("=" * 60)

        df_normal = self._generate_training_data()
        self._train_if(df_normal)
        self._train_ae(df_normal)
        self._save_models()

        log.info("✅ 所有模型训练完成!\n")

    def _generate_training_data(self) -> pd.DataFrame:
        n = 1440
        log.info(f"📊 生成 {n} 分钟正常训练数据...")
        rng = np.random.RandomState(42)
        t = np.arange(n)
        hour = (t % 1440) / 60.0

        cpu = (25 + 15 * np.exp(-0.5 * ((hour - 10) / 2) ** 2) +
               20 * np.exp(-0.5 * ((hour - 16) / 2.5) ** 2) -
               8 * np.exp(-0.5 * ((hour - 12.5) / 0.8) ** 2) +
               rng.normal(0, 3, n))

        gc_phase = (t % 35) / 35
        mem = (45 + 18 * gc_phase - (gc_phase > 0.97) * 15 +
               (cpu - 35) / 15 * 4 + 12 * (1 - np.exp(-t / 400)) +
               rng.normal(0, 1.5, n))

        disk = (3 + cpu * 0.06 + rng.exponential(1.5, n))

        df = pd.DataFrame({
            'cpu_usage': np.clip(cpu, 0, 100).astype(np.float32),
            'memory_usage': np.clip(mem, 0, 100).astype(np.float32),
            'disk_io': np.clip(disk, 0, 100).astype(np.float32),
        })
        log.info(f"   数据范围: CPU[{df['cpu_usage'].min():.0f}~{df['cpu_usage'].max():.0f}] "
                f"MEM[{df['memory_usage'].min():.0f}~{df['memory_usage'].max():.0f}] "
                f"DISK[{df['disk_io'].min():.0f}~{df['disk_io'].max():.0f}]")
        return df

    def _build_if_features(self, df: pd.DataFrame) -> np.ndarray:
        feat = df[self.FEATURE_COLS].copy()
        for col in self.FEATURE_COLS:
            feat[f'{col}_rmean'] = df[col].rolling(10, min_periods=1).mean()
            feat[f'{col}_rstd'] = df[col].rolling(10, min_periods=1).std().fillna(0)
            feat[f'{col}_diff'] = df[col] - df[col].expanding(min_periods=1).mean()
        feat['cpu_mem_prod'] = df['cpu_usage'] * df['memory_usage'] / 10000
        feat['cpu_disk_ratio'] = df['cpu_usage'] / (df['disk_io'] + 1e-6)
        return feat.fillna(0).values

    def _train_if(self, df: pd.DataFrame):
        log.info("🌲 训练 Isolation Forest...")
        X = self._build_if_features(df)
        X_scaled = self.if_scaler.fit_transform(X)

        self.if_model = IsolationForest(
            n_estimators=200,
            contamination=IF_CONTAMINATION,
            max_samples=256,
            random_state=42
        )
        self.if_model.fit(X_scaled)
        log.info(f"   ✅ IF 训练完成, 特征维度={X_scaled.shape[1]}")

    def _train_ae(self, df: pd.DataFrame):
        log.info("🧠 训练 LSTM Autoencoder...")
        raw = df[self.FEATURE_COLS].values.astype(np.float32)
        self.ae_scaler.fit(raw)
        scaled = self.ae_scaler.transform(raw)

        X_windows = []
        for i in range(len(scaled) - WINDOW_SIZE):
            X_windows.append(scaled[i:i + WINDOW_SIZE])
        X_windows = np.array(X_windows, dtype=np.float32)

        split = int(len(X_windows) * 0.85)
        X_train, X_val = X_windows[:split], X_windows[split:]

        train_ds = TensorDataset(torch.FloatTensor(X_train))
        val_ds = TensorDataset(torch.FloatTensor(X_val))
        train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)

        self.ae_model = LSTMAutoEncoder(
            n_features=3, seq_len=WINDOW_SIZE,
            hidden_size=48, latent_dim=24, num_layers=2, dropout=0.2
        ).to(self.device)

        optimizer = torch.optim.Adam(self.ae_model.parameters(), lr=1e-3, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=60)
        criterion = nn.MSELoss()

        best_val = float('inf')
        best_state = None
        patience = 0

        for epoch in range(1, 61):
            self.ae_model.train()
            tloss = 0
            for (bx,) in train_loader:
                bx = bx.to(self.device)
                optimizer.zero_grad()
                out = self.ae_model(bx)
                loss = criterion(out['reconstructed'], bx)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.ae_model.parameters(), 5.0)
                optimizer.step()
                tloss += loss.item()
            tloss /= len(train_loader)
            scheduler.step()

            self.ae_model.eval()
            with torch.no_grad():
                vx = torch.FloatTensor(X_val).to(self.device)
                vout = self.ae_model(vx)
                vloss = criterion(vout['reconstructed'], vx).item()

            if vloss < best_val:
                best_val = vloss
                best_state = {k: v.cpu().clone() for k, v in self.ae_model.state_dict().items()}
                patience = 0
            else:
                patience += 1

            if epoch % 10 == 0:
                log.info(f"   Epoch[{epoch:3d}] Train={tloss:.6f} Val={vloss:.6f} Best={best_val:.6f}")

            if patience >= 15:
                log.info(f"   ⏹ Early Stop @ Epoch {epoch}")
                break

        if best_state:
            self.ae_model.load_state_dict(best_state)
        self.ae_model.eval()

        params = sum(p.numel() for p in self.ae_model.parameters())
        log.info(f"   ✅ LSTM-AE 训练完成, best_val={best_val:.8f}, params={params:,}")

    def _save_models(self):
        if_path = MODEL_DIR / "rt_if_model.pkl"
        with open(if_path, 'wb') as f:
            pickle.dump({'model': self.if_model, 'scaler': self.if_scaler}, f)

        ae_path = MODEL_DIR / "rt_lstm_ae.pth"
        torch.save({
            'model_state_dict': self.ae_model.state_dict(),
            'config': {
                'n_features': 3, 'seq_len': WINDOW_SIZE,
                'hidden_size': 48, 'latent_dim': 24,
                'num_layers': 2, 'dropout': 0.2
            }
        }, ae_path)

        scaler_path = MODEL_DIR / "rt_ae_scaler.pkl"
        with open(scaler_path, 'wb') as f:
            pickle.dump({'scaler': self.ae_scaler}, f)

        log.info(f"💾 IF 模型: {if_path}")
        log.info(f"💾 AE 模型: {ae_path}")
        log.info(f"💾 Scaler:  {scaler_path}")


# ============================================================================
#  第六部分: 双层漏斗检测引擎
# ============================================================================

class DualFunnelDetector:
    """
    双层漏斗检测引擎 — 实时逐点检测
    
    Layer 1 (IF):
      对每个数据点构建增强特征 → IF 打分 → 三分类
        - NORMAL: 放行
        - SEVERE: 直接报警
        - SUSPICIOUS: 推送 Layer 2
    
    Layer 2 (LSTM-AE):
      从滑动窗口提取序列 → AE 重构 → 计算误差 → 动态阈值判定
        - 超阈值: 确诊异常 → 报警
        - 未超阈值: 误报释放 → 日志记录
    """

    FEATURE_COLS = ['cpu_usage', 'memory_usage', 'disk_io']

    def __init__(self, trainer: ModelTrainer):
        self.if_model = trainer.if_model
        self.if_scaler = trainer.if_scaler
        self.ae_model = trainer.ae_model
        self.ae_scaler = trainer.ae_scaler
        self.device = trainer.device

        self.threshold_engine = DynamicThreshold(
            alpha=0.15, k=AE_THRESHOLD_K, warmup=AE_WARMUP
        )

        self._history_df = pd.DataFrame(columns=self.FEATURE_COLS)
        self._stats = {
            'total': 0, 'normal': 0, 'severe': 0,
            'suspicious': 0, 'confirmed': 0, 'false_positive': 0
        }

    def detect(self, values: np.ndarray, window: SlidingWindow) -> Dict:
        """
        对单个数据点执行双层漏斗检测
        
        Args:
            values: (3,) numpy 数组 [cpu, mem, disk]
            window: 已更新的滑动窗口
        
        Returns:
            {
                'label': 'NORMAL' / 'SEVERE' / 'CONFIRMED_ANOMALY' / 'FALSE_POSITIVE',
                'if_score': float,
                'ae_error': float or None,
                'ae_threshold': float or None,
                'source': 'IF' / 'LSTM-AE' / None
            }
        """
        self._stats['total'] += 1

        point_df = pd.DataFrame([values], columns=self.FEATURE_COLS)
        self._history_df = pd.concat([self._history_df, point_df], ignore_index=True)
        if len(self._history_df) > 500:
            self._history_df = self._history_df.iloc[-500:].reset_index(drop=True)

        # ---- Layer 1: Isolation Forest ----
        if_score = self._if_score(values)

        if if_score >= IF_SUSPICIOUS_THRESHOLD:
            self._stats['normal'] += 1
            return {
                'label': 'NORMAL', 'if_score': if_score,
                'ae_error': None, 'ae_threshold': None, 'source': None
            }

        if if_score < IF_SEVERE_THRESHOLD:
            self._stats['severe'] += 1
            return {
                'label': 'SEVERE', 'if_score': if_score,
                'ae_error': None, 'ae_threshold': None, 'source': 'IF'
            }

        # ---- Layer 2: LSTM Autoencoder ----
        self._stats['suspicious'] += 1

        if not window.is_ready():
            return {
                'label': 'NORMAL', 'if_score': if_score,
                'ae_error': None, 'ae_threshold': None, 'source': None
            }

        ae_error, ae_threshold, is_anomaly = self._ae_diagnose(window)

        if is_anomaly:
            self._stats['confirmed'] += 1
            return {
                'label': 'CONFIRMED_ANOMALY', 'if_score': if_score,
                'ae_error': ae_error, 'ae_threshold': ae_threshold,
                'source': 'LSTM-AE'
            }
        else:
            self._stats['false_positive'] += 1
            return {
                'label': 'FALSE_POSITIVE', 'if_score': if_score,
                'ae_error': ae_error, 'ae_threshold': ae_threshold,
                'source': None
            }

    def _if_score(self, values: np.ndarray) -> float:
        point_df = pd.DataFrame([values], columns=self.FEATURE_COLS)
        hist = self._history_df.tail(500)
        feat = self._build_if_features_single(hist)
        X = self.if_scaler.transform(feat.values)
        return float(self.if_model.decision_function(X)[-1])

    def _build_if_features_single(self, df: pd.DataFrame) -> pd.DataFrame:
        feat = df[self.FEATURE_COLS].copy()
        for col in self.FEATURE_COLS:
            feat[f'{col}_rmean'] = df[col].rolling(10, min_periods=1).mean()
            feat[f'{col}_rstd'] = df[col].rolling(10, min_periods=1).std().fillna(0)
            feat[f'{col}_diff'] = df[col] - df[col].expanding(min_periods=1).mean()
        feat['cpu_mem_prod'] = df['cpu_usage'] * df['memory_usage'] / 10000
        feat['cpu_disk_ratio'] = df['cpu_usage'] / (df['disk_io'] + 1e-6)
        return feat.fillna(0)

    @torch.no_grad()
    def _ae_diagnose(self, window: SlidingWindow) -> Tuple[float, float, bool]:
        seq = window.get_sequence()
        scaled = self.ae_scaler.transform(seq)
        X = torch.FloatTensor(scaled[np.newaxis, :, :]).to(self.device)

        self.ae_model.eval()
        output = self.ae_model(X)
        error = float(output['reconstruction_error'][0].cpu().numpy())

        threshold, is_anomaly = self.threshold_engine.update_and_check(error)
        return error, threshold, is_anomaly

    @property
    def stats(self) -> Dict:
        return self._stats.copy()


# ============================================================================
#  第七部分: 邮件报警模块
# ============================================================================

class EmailAlerter:
    """
    邮件报警器 — 含防轰炸冷却机制
    
    防轰炸逻辑:
      - 记录上次报警时间
      - 若距上次报警 < ALERT_COOLDOWN 秒, 抑制发送
      - 仅打印日志: "[Suppressed] Too frequent alerts"
    
    邮件内容:
      - 异常发生时间
      - 异常指标数值 (CPU/MEM/DISK)
      - 判定来源 (IF 直接拦截 / LSTM-AE 确诊)
    """

    def __init__(self):
        self._last_alert_time: Optional[float] = None
        self._suppressed_count = 0
        self._sent_count = 0

    def alert(self, result: Dict, values: np.ndarray,
              timestamp: datetime = None) -> bool:
        ts = timestamp or datetime.now()
        now = time.time()

        if self._last_alert_time is not None:
            elapsed = now - self._last_alert_time
            if elapsed < ALERT_COOLDOWN:
                self._suppressed_count += 1
                log.warning(
                    f"[Suppressed] Too frequent alerts "
                    f"(冷却中: {ALERT_COOLDOWN - elapsed:.0f}s 剩余, "
                    f"已抑制 {self._suppressed_count} 次)"
                )
                return False

        source_map = {
            'IF': 'Isolation Forest 直接拦截 (严重异常)',
            'LSTM-AE': 'LSTM Autoencoder 确诊 (隐性异常)'
        }
        source_text = source_map.get(result.get('source', ''), '未知来源')

        subject = f"🚨 AIOps 异常报警 — {source_text.split('(')[0].strip()}"
        body = self._build_email_body(ts, values, result, source_text)

        sent = self._send_email(subject, body)
        if sent:
            self._last_alert_time = now
            self._sent_count += 1
        return sent

    def _build_email_body(self, ts: datetime, values: np.ndarray,
                          result: Dict, source_text: str) -> str:
        cpu, mem, disk = values[0], values[1], values[2]
        label = result.get('label', 'UNKNOWN')
        if_score = result.get('if_score', 'N/A')
        ae_error = result.get('ae_error')
        ae_threshold = result.get('ae_threshold')

        lines = [
            "<h2>🚨 系统负载异常报警</h2>",
            "<hr>",
            f"<p><b>报警时间:</b> {ts.strftime('%Y-%m-%d %H:%M:%S')}</p>",
            f"<p><b>判定来源:</b> {source_text}</p>",
            f"<p><b>异常等级:</b> <span style='color:red;font-weight:bold'>{label}</span></p>",
            "<hr>",
            "<h3>📊 异常指标数值</h3>",
            "<table border='1' cellpadding='8' cellspacing='0'>",
            "<tr><th>指标</th><th>当前值</th><th>正常范围</th><th>状态</th></tr>",
            f"<tr><td>CPU Usage</td><td>{cpu:.1f}%</td><td>10~70%</td>"
            f"<td>{'🔴 异常' if cpu > 90 or cpu < 5 else '🟡 偏高' if cpu > 70 else '🟢 正常'}</td></tr>",
            f"<tr><td>Memory Usage</td><td>{mem:.1f}%</td><td>30~80%</td>"
            f"<td>{'🔴 异常' if mem > 95 or mem < 20 else '🟡 偏高' if mem > 80 else '🟢 正常'}</td></tr>",
            f"<tr><td>Disk IO</td><td>{disk:.1f}%</td><td>0~30%</td>"
            f"<td>{'🔴 异常' if disk > 70 else '🟡 偏高' if disk > 30 else '🟢 正常'}</td></tr>",
            "</table>",
            "<hr>",
            "<h3>🔍 检测详情</h3>",
            f"<p><b>IF 异常分数:</b> {if_score:.4f} "
            f"(阈值: 严重&lt;{IF_SEVERE_THRESHOLD}, 疑似&lt;{IF_SUSPICIOUS_THRESHOLD})</p>",
        ]
        if ae_error is not None:
            lines.append(
                f"<p><b>LSTM-AE 重构误差:</b> {ae_error:.6f} / 阈值: {ae_threshold:.6f}</p>"
            )
        lines += [
            "<hr>",
            "<p style='color:gray;font-size:12px'>"
            "此邮件由 AIOps 双层漏斗异常检测系统自动发送</p>",
        ]
        return "\n".join(lines)

    def _send_email(self, subject: str, body: str) -> bool:
        if not SMTP_USER or not SMTP_PASSWORD:
            log.error("❌ 邮件配置缺失 (SMTP_USER / SMTP_PASSWORD), 跳过发送")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = SMTP_FROM_EMAIL
            msg['To'] = ALERT_TO_EMAIL
            msg.attach(MIMEText(body, 'html', 'utf-8'))

            import ssl
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_FROM_EMAIL, [ALERT_TO_EMAIL], msg.as_string())

            log.info(f"📧 报警邮件已发送 → {ALERT_TO_EMAIL}")
            return True
        except Exception as e:
            log.error(f"❌ 邮件发送失败: {e}")
            return False

    @property
    def summary(self) -> str:
        return (f"邮件已发: {self._sent_count} | "
                f"已抑制: {self._suppressed_count}")


# ============================================================================
#  第八部分: 控制台状态显示
# ============================================================================

class ConsoleDisplay:
    """控制台实时状态显示"""

    STATUS_ICONS = {
        'NORMAL': '🟢',
        'SEVERE': '🔴',
        'CONFIRMED_ANOMALY': '🟣',
        'FALSE_POSITIVE': '🟡',
    }

    @staticmethod
    def render(timestamp: datetime, values: np.ndarray,
               result: Dict, stats: Dict, alerter_summary: str,
               anomaly_info: Dict = None):
        cpu, mem, disk = values[0], values[1], values[2]
        label = result['label']
        icon = ConsoleDisplay.STATUS_ICONS.get(label, '⚪')

        ts_str = timestamp.strftime('%H:%M:%S')

        status_line = (
            f"{icon} [{ts_str}] CPU={cpu:5.1f}% MEM={mem:5.1f}% "
            f"DISK={disk:5.1f}% │ {label}"
        )

        if result.get('if_score') is not None:
            status_line += f" │ IF={result['if_score']:+.3f}"

        if result.get('ae_error') is not None:
            status_line += f" │ AE_err={result['ae_error']:.5f}"

        print(status_line)

        if label in ('SEVERE', 'CONFIRMED_ANOMALY'):
            source = result.get('source', '?')
            detail = "IF直接拦截" if source == 'IF' else "LSTM-AE确诊"
            print(f"   ⚠️  >>> 异常报警! 来源: {detail} | {alerter_summary}")

        if anomaly_info and anomaly_info.get('is_anomaly'):
            print(f"   🏷️  [Ground Truth] type={anomaly_info['type']} "
                  f"source={anomaly_info['source']}")

    @staticmethod
    def render_stats(stats: Dict):
        total = max(stats['total'], 1)
        print(f"\n{'─' * 60}")
        print(f"  📊 检测统计: 总计={stats['total']}")
        print(f"     🟢 正常:       {stats['normal']:4d} ({stats['normal']/total*100:5.1f}%)")
        print(f"     🔴 IF严重:     {stats['severe']:4d} ({stats['severe']/total*100:5.1f}%)")
        print(f"     🟡 IF疑似:     {stats['suspicious']:4d} ({stats['suspicious']/total*100:5.1f}%)")
        print(f"     🟣 AE确诊:     {stats['confirmed']:4d} ({stats['confirmed']/total*100:5.1f}%)")
        print(f"     🟡 AE误报释放: {stats['false_positive']:4d} ({stats['false_positive']/total*100:5.1f}%)")
        print(f"{'─' * 60}\n")


# ============================================================================
#  第九部分: 主循环
# ============================================================================

def main():
    print("\n" + "=" * 60)
    print("  🔱  AIOps 实时监控系统 — 双层漏斗 + 邮件报警")
    print("  Layer1: Isolation Forest (快速初筛)")
    print("  Layer2: LSTM Autoencoder (深度确诊)")
    print(f"  报警冷却: {ALERT_COOLDOWN}s | 数据间隔: {STREAM_INTERVAL}s")
    print("=" * 60 + "\n")

    # ---- Step 1: 训练模型 ----
    trainer = ModelTrainer()
    trainer.train_all()

    # ---- Step 2: 初始化组件 ----
    detector = DualFunnelDetector(trainer)
    window = SlidingWindow(window_size=WINDOW_SIZE, n_features=N_FEATURES)
    alerter = EmailAlerter()
    simulator = DataStreamSimulator(seed=int(time.time()) % 10000)

    log.info("🚀 实时监控启动!\n")
    log.info(f"   邮件配置: {SMTP_HOST}:{SMTP_PORT} | 发件: {SMTP_FROM_EMAIL} → 收件: {ALERT_TO_EMAIL}")
    log.info(f"   IF 阈值: 严重<{IF_SEVERE_THRESHOLD}, 疑似<{IF_SUSPICIOUS_THRESHOLD}")
    log.info(f"   AE 阈值: k={AE_THRESHOLD_K}, warmup={AE_WARMUP}")
    log.info(f"   滑动窗口: {WINDOW_SIZE} 点\n")

    # ---- Step 3: 主循环 ----
    data_stream = generate_data_stream(simulator)
    tick = 0
    stats_interval = 50

    try:
        while True:
            timestamp, values, anomaly_info = next(data_stream)

            window.append(values, timestamp)

            result = detector.detect(values, window)

            ConsoleDisplay.render(
                timestamp, values, result,
                detector.stats, alerter.summary, anomaly_info
            )

            if result['label'] in ('SEVERE', 'CONFIRMED_ANOMALY'):
                alerter.alert(result, values, timestamp)

            tick += 1
            if tick % stats_interval == 0:
                ConsoleDisplay.render_stats(detector.stats)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("  ⏹️  监控系统已停止 (Ctrl+C)")
        ConsoleDisplay.render_stats(detector.stats)
        print(f"  📧 {alerter.summary}")
        print("=" * 60)


if __name__ == "__main__":
    main()
