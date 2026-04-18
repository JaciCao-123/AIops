#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 模型训练、选择与保存

功能：
1. 数据集加载与划分
2. 训练循环（支持多GPU）
3. 验证与早停
4. 模型保存/加载
5. 超参数搜索
6. 训练日志记录

使用方法:
    python step4_train_model.py --graph-data data/graphs/graph_data.npz
    python step4_train_model.py --resume checkpoints/best_model.pt
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from torch.optim.lr_scheduler import ReduceLROnPlateau, CosineAnnealingLR
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    accuracy_score, confusion_matrix, classification_report,
    roc_auc_score, average_precision_score
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    MODEL_CONFIG,
    TRAINING_CONFIG,
    DATA_DIRS,
    get_device
)
from step3_gnn_models import RootCauseGNN, ModelFactory


class GraphDataset(Dataset):
    """图数据集类"""
    
    def __init__(
        self,
        node_features: np.ndarray,
        edge_index: np.ndarray,
        labels: np.ndarray,
        edge_attr: Optional[np.ndarray] = None,
        temporal_features: Optional[Dict[int, np.ndarray]] = None,
        node_ids: Optional[List[str]] = None
    ):
        self.node_features = torch.FloatTensor(node_features)
        self.edge_index = torch.LongTensor(edge_index)
        self.labels = torch.LongTensor(labels)
        
        self.edge_attr = torch.FloatTensor(edge_attr) if edge_attr is not None else None
        self.temporal_features = {
            k: torch.FloatTensor(v) for k, v in (temporal_features or {}).items()
        }
        self.node_ids = node_ids or [str(i) for i in range(len(labels))]
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        return {
            "node_idx": idx,
            "label": self.labels[idx],
            "node_id": self.node_ids[idx]
        }


class RootCauseTrainer:
    """根因检测模型训练器"""
    
    def __init__(self, config: dict = None, training_config: dict = None):
        self.config = config or MODEL_CONFIG
        self.training_config = training_config or TRAINING_CONFIG
        
        self.device = get_device()
        self.model = None
        self.optimizer = None
        self.scheduler = None
        self.criterion = None
        
        self.train_history = {
            "train_loss": [],
            "val_loss": [],
            "val_precision": [],
            "val_recall": [],
            "val_f1": [],
            "val_auc": []
        }
        
        self.best_val_f1 = 0.0
        self.best_epoch = 0
        self.patience_counter = 0
    
    def setup_model(self, input_dim: int) -> None:
        """初始化模型和优化器"""
        
        print(f"\n🧠 初始化模型...")
        
        # 创建模型
        self.model = ModelFactory.create_model(
            self.config,
            input_dim=input_dim
        ).to(self.device)
        
        # 打印模型信息
        summary = ModelFactory.get_model_summary(self.model)
        print(f"   模型类型: {summary['model_type'].upper()}")
        print(f"   参数量: {summary['total_parameters']:,}")
        print(f"   模型大小: {summary['size_mb']:.2f} MB")
        
        # 损失函数（处理类别不平衡）
        class_weights = self.config.get("class_weights", {0: 1.0, 1: 3.0})
        weight_tensor = torch.tensor(
            [class_weights[0], class_weights[1]],
            dtype=torch.float32
        ).to(self.device)
        
        self.criterion = nn.BCEWithLogitsLoss(weight=weight_tensor[1])  # 二分类
        
        # 优化器
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config["learning_rate"],
            weight_decay=self.config["weight_decay"]
        )
        
        # 学习率调度器
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='max',
            factor=0.5,
            patience=5
        )
        
        # 梯度裁剪值
        self.grad_clip = self.config.get("gradient_clip_value", 5.0)
    
    def train_epoch(self, dataset: GraphDataset) -> float:
        """训练一个epoch"""
        
        self.model.train()
        total_loss = 0.0
        num_batches = 0
        
        # 对整个图进行训练（全图模式）
        node_features = dataset.node_features.to(self.device)
        edge_index = dataset.edge_index.to(self.device)
        labels = dataset.labels.float().to(self.device)
        
        edge_attr = None
        if dataset.edge_attr is not None:
            edge_attr = dataset.edge_attr.to(self.device)
        
        temporal_feats = None
        if dataset.temporal_features:
            temporal_feats = {k: v.to(self.device) 
                            for k, v in dataset.temporal_features.items()}
        
        # 前向传播
        self.optimizer.zero_grad()
        logits = self.model(node_features, edge_index, edge_attr, temporal_feats)
        logits = logits.squeeze(-1)
        
        # 计算损失
        loss = self.criterion(logits, labels)
        
        # 反向传播
        loss.backward()
        
        # 梯度裁剪
        torch.nn.utils.clip_grad_norm_(
            self.model.parameters(),
            self.grad_clip
        )
        
        # 更新参数
        self.optimizer.step()
        
        total_loss += loss.item()
        num_batches += 1
        
        return total_loss / max(num_batches, 1)
    
    @torch.no_grad()
    def evaluate(self, dataset: GraphDataset) -> Dict[str, float]:
        """评估模型"""
        
        self.model.eval()
        
        node_features = dataset.node_features.to(self.device)
        edge_index = dataset.edge_index.to(self.device)
        labels = dataset.labels.cpu().numpy()
        
        edge_attr = None
        if dataset.edge_attr is not None:
            edge_attr = dataset.edge_attr.to(self.device)
        
        temporal_feats = None
        if dataset.temporal_features:
            temporal_feats = {k: v.to(self.device) 
                            for k, v in dataset.temporal_features.items()}
        
        # 前向传播
        logits = self.model(node_features, edge_index, edge_attr, temporal_feats)
        probs = torch.sigmoid(logits.squeeze(-1))
        preds = (probs > 0.5).cpu().numpy().astype(int)
        probs_np = probs.cpu().numpy()
        
        # 计算指标
        metrics = {}
        
        metrics["loss"] = self.criterion(
            logits.squeeze(-1), 
            torch.FloatTensor(labels).to(self.device)
        ).item()
        
        metrics["accuracy"] = accuracy_score(labels, preds)
        metrics["precision"] = precision_score(labels, preds, zero_division=0)
        metrics["recall"] = recall_score(labels, preds, zero_division=0)
        metrics["f1"] = f1_score(labels, preds, zero_division=0)
        
        try:
            metrics["auc"] = roc_auc_score(labels, probs_np)
        except ValueError:
            metrics["auc"] = 0.5
        
        try:
            metrics["ap"] = average_precision_score(labels, probs_np)
        except ValueError:
            metrics["ap"] = 0.0
        
        return metrics
    
    def train(
        self,
        dataset: GraphDataset,
        epochs: int = None,
        save_dir: str = None,
        verbose: bool = True
    ) -> Dict:
        """
        完整训练流程
        
        Returns:
            训练历史和最佳指标
        """
        
        epochs = epochs or self.config["epochs"]
        save_dir = save_dir or self.training_config.get("checkpoint_dir", "checkpoints")
        os.makedirs(save_dir, exist_ok=True)
        
        patience = self.config.get("early_stopping_patience", 15)
        
        print(f"\n🚀 开始训练:")
        print(f"   Epochs: {epochs}")
        print(f"   Early stopping patience: {patience}")
        print(f"   设备: {self.device}")
        print(f"   数据集大小: {len(dataset)} 节点")
        
        start_time = datetime.now()
        
        for epoch in range(1, epochs + 1):
            
            # 训练
            train_loss = self.train_epoch(dataset)
            
            # 验证
            val_metrics = self.evaluate(dataset)
            
            # 记录历史
            self.train_history["train_loss"].append(train_loss)
            self.train_history["val_loss"].append(val_metrics["loss"])
            self.train_history["val_f1"].append(val_metrics["f1"])
            self.train_history["val_auc"].append(val_metrics["auc"])
            
            # 学习率调度
            self.scheduler.step(val_metrics["f1"])
            
            # 打印进度
            if verbose and epoch % 5 == 0:
                print(f"\nEpoch [{epoch}/{epochs}]")
                print(f"   Train Loss: {train_loss:.4f}")
                print(f"   Val Loss: {val_metrics['loss']:.4f}")
                print(f"   Val F1: {val_metrics['f1']:.4f} | AUC: {val_metrics['auc']:.4f}")
                print(f"   Precision: {val_metrics['precision']:.4f} | Recall: {val_metrics['recall']:.4f}")
            
            # 保存最佳模型
            if val_metrics["f1"] > self.best_val_f1:
                self.best_val_f1 = val_metrics["f1"]
                self.best_epoch = epoch
                self.patience_counter = 0
                
                best_path = os.path.join(save_dir, "best_model.pt")
                self.save_model(best_path, val_metrics)
                
                if verbose and epoch % 10 == 0:
                    print(f"   ✨ 新最佳模型! F1={val_metrics['f1']:.4f}")
            else:
                self.patience_counter += 1
            
            # 定期保存checkpoint
            if epoch % self.training_config.get("save_checkpoint_every", 10) == 0:
                ckpt_path = os.path.join(save_dir, f"checkpoint_epoch_{epoch}.pt")
                self.save_model(ckpt_path, val_metrics)
            
            # 早停检查
            if self.patience_counter >= patience:
                print(f"\n⏹️ Early stopping at epoch {epoch}")
                print(f"   Best F1: {self.best_val_f1:.4f} (Epoch {self.best_epoch})")
                break
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        results = {
            "best_epoch": self.best_epoch,
            "best_f1": self.best_val_f1,
            "training_time_seconds": training_time,
            "history": self.train_history,
            "final_metrics": val_metrics
        }
        
        print(f"\n✅ 训练完成!")
        print(f"   总耗时: {training_time/60:.2f} 分钟")
        print(f"   最佳F1: {self.best_val_f1:.4f} (Epoch {self.best_epoch})")
        
        return results
    
    def save_model(
        self, 
        filepath: str, 
        metrics: Optional[Dict] = None
    ) -> None:
        """保存模型"""
        
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "config": self.config,
            "metrics": metrics,
            "epoch": len(self.train_history["train_loss"]),
            "best_f1": self.best_val_f1,
            "saved_at": datetime.now().isoformat()
        }
        
        torch.save(checkpoint, filepath)
    
    def load_model(self, filepath: str) -> Dict:
        """加载模型"""
        
        print(f"\n📂 加载模型: {filepath}")
        
        checkpoint = torch.load(filepath, map_location=self.device)
        
        if self.model is None:
            input_dim = checkpoint["config"].get("node_feature_dim", 64)
            self.setup_model(input_dim)
        
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.best_val_f1 = checkpoint.get("best_f1", 0.0)
        
        print(f"   ✅ 模型加载成功!")
        print(f"   最佳F1: {self.best_val_f1:.4f}")
        print(f"   保存时间: {checkpoint.get('saved_at', 'unknown')}")
        
        return checkpoint


class ModelSelector:
    """模型选择器（超参数搜索）"""
    
    def __init__(self, base_config: dict = None):
        self.base_config = base_config or MODEL_CONFIG
        self.results = []
    
    def grid_search(
        self,
        dataset: GraphDataset,
        param_grid: Dict[str, List],
        epochs_per_trial: int = 50
    ) -> Dict:
        """
        网格搜索最优超参数
        
        Args:
            param_grid: 参数网格，例如:
                    {
                        "hidden_dim": [64, 128, 256],
                        "num_layers": [2, 3, 4],
                        "learning_rate": [0.001, 0.0005]
                    }
        """
        
        from itertools import product
        
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        total_combinations = 1
        for values in param_values:
            total_combinations *= len(values)
        
        print(f"\n🔍 开始超参数搜索:")
        print(f"   参数组合数: {total_combinations}")
        print(f"   每个组合训练轮次: {epochs_per_trial}")
        
        best_result = {"f1": 0.0}
        trial_id = 0
        
        for combination in product(*param_values):
            trial_id += 1
            trial_params = dict(zip(param_names, combination))
            
            print(f"\n📋 Trial {trial_id}/{total_combinations}: {trial_params}")
            
            # 更新配置
            trial_config = {**self.base_config, **trial_params}
            
            # 训练
            trainer = RootCauseTrainer(trial_config)
            trainer.setup_model(dataset.node_features.shape[1])
            
            try:
                results = trainer.train(
                    dataset,
                    epochs=epochs_per_trial,
                    verbose=False
                )
                
                result_entry = {
                    **trial_params,
                    "best_f1": results["best_f1"],
                    "best_epoch": results["best_epoch"],
                    "training_time": results["training_time_seconds"]
                }
                
                self.results.append(result_entry)
                
                if results["best_f1"] > best_result["f1"]:
                    best_result = {
                        **result_entry,
                        "config": trial_config
                    }
                    
                    # 保存最佳配置
                    best_config_path = os.path.join(
                        DATA_DIRS["models"],
                        "best_hyperparams.json"
                    )
                    with open(best_config_path, 'w') as f:
                        json.dump(best_result, f, indent=2)
                    
                    print(f"   ✨ 新最佳! F1={results['best_f1']:.4f}")
                    
            except Exception as e:
                print(f"   ❌ Trial失败: {e}")
                continue
        
        print(f"\n✅ 搜索完成!")
        print(f"   最佳配置: {best_result}")
        
        # 保存所有结果
        results_df = pd.DataFrame(self.results)
        results_file = os.path.join(DATA_DIRS["models"], "grid_search_results.csv")
        results_df.to_csv(results_file, index=False)
        
        return best_result


def load_graph_data(data_path: str) -> Tuple[GraphDataset, Dict]:
    """加载图数据并创建数据集"""
    
    print(f"\n📥 加载图数据: {data_path}")
    
    data = np.load(data_path, allow_pickle=True)
    
    node_features = data["node_features"]
    edge_index = data["edge_index"]
    labels = data["labels"].tolist()
    
    edge_attr = data.get("edge_attr", None)
    temporal_features = {}
    
    # 加载时序特征
    for key in data.files:
        if key.startswith("temporal_"):
            node_idx = int(key.split("_")[1])
            temporal_features[node_idx] = data[key]
    
    # 尝试加载元数据获取节点ID映射
    meta_path = data_path.replace("_graph_data.npz", "_metadata.json")
    node_ids = None
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            node_id_map = metadata.get("node_id_mapping", {})
            node_ids = [None] * len(labels)
            for node_id, idx in node_id_map.items():
                if idx < len(node_ids):
                    node_ids[idx] = node_id
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"   ⚠️ 无法加载元数据文件: {e}")
            node_ids = [str(i) for i in range(len(labels))]
    
    dataset = GraphDataset(
        node_features=node_features,
        edge_index=edge_index,
        labels=np.array(labels),
        edge_attr=edge_attr,
        temporal_features=temporal_features,
        node_ids=node_ids
    )
    
    metadata = {
        "num_nodes": len(labels),
        "num_edges": len(edge_index[0]),
        "feature_dim": node_features.shape[1],
        "num_root_causes": sum(labels),
        "num_normal": len(labels) - sum(labels),
        "has_temporal": len(temporal_features) > 0
    }
    
    print(f"   节点数: {metadata['num_nodes']}")
    print(f"   边数: {metadata['num_edges']}")
    print(f"   特征维度: {metadata['feature_dim']}")
    print(f"   根因节点: {metadata['num_root_causes']} ({metadata['num_root_causes']/metadata['num_nodes']*100:.1f}%)")
    
    return dataset, metadata


def main():
    parser = argparse.ArgumentParser(description='训练GNN根因分析模型')
    parser.add_argument('--graph-data', type=str, required=True, help='图数据NPZ文件路径')
    parser.add_argument('--epochs', type=int, default=None, help='训练轮数')
    parser.add_argument('--resume', type=str, default=None, help='恢复训练的checkpoint路径')
    parser.add_argument('--search', action='store_true', help='执行超参数搜索')
    parser.add_argument('--output-dir', type=str, default=None, help='输出目录')
    args = parser.parse_args()
    
    print("="*70)
    print("🎯 Step 4/5: 模型训练、选择与保存 - GNN根因分析系统")
    print("="*70)
    
    # 1. 加载数据
    dataset, metadata = load_graph_data(args.graph_data)
    
    output_dir = args.output_dir or TRAINING_CONFIG["checkpoint_dir"]
    
    if args.search:
        # 超参数搜索模式
        selector = ModelSelector(MODEL_CONFIG)
        
        param_grid = {
            "hidden_dim": [64, 128, 256],
            "num_layers": [2, 3, 4],
            "dropout": [0.2, 0.3, 0.4],
            "learning_rate": [0.001, 0.0005, 0.0001]
        }
        
        best_config = selector.grid_search(dataset, param_grid, epochs_per_trial=30)
        
        print(f"\n🏆 最优配置:")
        for k, v in best_config.items():
            if not isinstance(v, dict):
                print(f"   {k}: {v}")
        
    else:
        # 正常训练模式
        trainer = RootCauseTrainer(MODEL_CONFIG, TRAINING_CONFIG)
        trainer.setup_model(metadata["feature_dim"])
        
        # 如果指定了恢复训练
        if args.resume:
            trainer.load_model(args.resume)
        
        # 训练
        results = trainer.train(
            dataset,
            epochs=args.epochs,
            save_dir=output_dir
        )
        
        # 最终评估
        final_metrics = trainer.evaluate(dataset)
        
        print(f"\n📊 最终评估指标:")
        print(f"   Accuracy:  {final_metrics['accuracy']:.4f}")
        print(f"   Precision: {final_metrics['precision']:.4f}")
        print(f"   Recall:    {final_metrics['recall']:.4f}")
        print(f"   F1 Score:  {final_metrics['f1']:.4f}")
        print(f"   AUC-ROC:   {final_metrics['auc']:.4f}")
        print(f"   AP:        {final_metrics['ap']:.4f}")
        
        # 保存最终报告
        report = {
            "metadata": metadata,
            "final_metrics": {k: float(v) for k, v in final_metrics.items()},
            "training_results": {
                "best_epoch": results["best_epoch"],
                "best_f1": results["best_f1"],
                "training_time_minutes": results["training_time_seconds"] / 60
            },
            "model_config": MODEL_CONFIG,
            "saved_at": datetime.now().isoformat()
        }
        
        report_path = os.path.join(output_dir, "training_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 报告已保存: {report_path}")


if __name__ == "__main__":
    main()