#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3: 模型训练

使用处理后的图数据训练根因定位模型
"""

import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch_geometric.data import Data
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from tqdm import tqdm
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model import create_model, save_model, GCNRootCauseModel, GATRootCauseModel, SAGERootCauseModel


class GraphDataset(Dataset):
    """图数据集"""
    
    def __init__(self, data_path: str):
        with open(data_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.services = None
        self.service_to_idx = {}
    
    def set_services(self, services: List[str]):
        self.services = services
        self.service_to_idx = {s: i for i, s in enumerate(services)}
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        
        x = np.array(item['x'], dtype=np.float32)
        edge_index = np.array(item['edge_index'], dtype=np.int64)
        y = np.array(item['y'], dtype=np.float32)
        label = item.get('label', 'normal')
        
        return {
            'x': torch.FloatTensor(x),
            'edge_index': torch.LongTensor(edge_index),
            'y': torch.FloatTensor(y),
            'label': label
        }


def collate_fn(batch):
    """自定义批处理函数"""
    return batch


class Trainer:
    """模型训练器"""
    
    def __init__(self, model: nn.Module, device: str = 'cpu',
                 learning_rate: float = 0.001, weight_decay: float = 1e-5):
        self.model = model.to(device)
        self.device = device
        
        self.optimizer = optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='min', factor=0.5, patience=5
        )
        
        self.criterion = nn.BCEWithLogitsLoss()
        
        self.train_losses = []
        self.val_losses = []
        self.train_accs = []
        self.val_accs = []
    
    def train_epoch(self, dataloader: DataLoader) -> Tuple[float, float]:
        """训练一个 epoch"""
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        for batch in tqdm(dataloader, desc="Training", leave=False):
            for item in batch:
                x = item['x'].to(self.device)
                edge_index = item['edge_index'].to(self.device)
                y = item['y'].to(self.device)
                
                self.optimizer.zero_grad()
                
                output = self.model(x, edge_index)
                
                loss = self.criterion(output, y)
                
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
                
                pred = (torch.sigmoid(output) > 0.5).float()
                correct += (pred == y).sum().item()
                total += y.numel()
        
        avg_loss = total_loss / len(dataloader)
        accuracy = correct / total
        
        return avg_loss, accuracy
    
    def validate(self, dataloader: DataLoader) -> Tuple[float, float, Dict]:
        """验证"""
        self.model.eval()
        total_loss = 0
        correct = 0
        total = 0
        
        all_preds = []
        all_labels = []
        
        with torch.no_grad():
            for batch in dataloader:
                for item in batch:
                    x = item['x'].to(self.device)
                    edge_index = item['edge_index'].to(self.device)
                    y = item['y'].to(self.device)
                    
                    output = self.model(x, edge_index)
                    loss = self.criterion(output, y)
                    
                    total_loss += loss.item()
                    
                    pred = (torch.sigmoid(output) > 0.5).float()
                    correct += (pred == y).sum().item()
                    total += y.numel()
                    
                    all_preds.append(pred.cpu().numpy())
                    all_labels.append(y.cpu().numpy())
        
        avg_loss = total_loss / len(dataloader)
        accuracy = correct / total
        
        tp = fp = tn = fn = 0
        for preds, labels in zip(all_preds, all_labels):
            for p, l in zip(preds, labels):
                if p == 1 and l == 1:
                    tp += 1
                elif p == 1 and l == 0:
                    fp += 1
                elif p == 0 and l == 0:
                    tn += 1
                else:
                    fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        metrics = {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn
        }
        
        return avg_loss, accuracy, metrics
    
    def train(self, train_loader: DataLoader, val_loader: DataLoader,
              num_epochs: int = 50, early_stopping: int = 10) -> Dict:
        """完整训练流程"""
        best_val_loss = float('inf')
        patience_counter = 0
        best_model_state = None
        
        print(f"\n开始训练，共 {num_epochs} 个 epochs...")
        
        for epoch in range(num_epochs):
            train_loss, train_acc = self.train_epoch(train_loader)
            val_loss, val_acc, val_metrics = self.validate(val_loader)
            
            self.train_losses.append(train_loss)
            self.val_losses.append(val_loss)
            self.train_accs.append(train_acc)
            self.val_accs.append(val_acc)
            
            self.scheduler.step(val_loss)
            
            print(f"Epoch {epoch+1}/{num_epochs}")
            print(f"  Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f}")
            print(f"  Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}")
            print(f"  Val Precision: {val_metrics['precision']:.4f}, "
                  f"Recall: {val_metrics['recall']:.4f}, F1: {val_metrics['f1']:.4f}")
            
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_model_state = self.model.state_dict().copy()
                print(f"  ✓ 新的最佳模型!")
            else:
                patience_counter += 1
                if patience_counter >= early_stopping:
                    print(f"\n早停: {early_stopping} 个 epoch 未改善")
                    break
        
        if best_model_state:
            self.model.load_state_dict(best_model_state)
        
        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'train_accs': self.train_accs,
            'val_accs': self.val_accs,
            'best_val_loss': best_val_loss
        }


def split_dataset(dataset: GraphDataset, train_ratio: float = 0.8):
    """划分训练集和验证集"""
    n = len(dataset)
    train_size = int(n * train_ratio)
    
    indices = list(range(n))
    np.random.seed(42)
    np.random.shuffle(indices)
    
    train_indices = indices[:train_size]
    val_indices = indices[train_size:]
    
    train_data = [dataset[i] for i in train_indices]
    val_data = [dataset[i] for i in val_indices]
    
    return train_data, val_data


def main():
    print("=" * 60)
    print("Step 3: 模型训练")
    print("=" * 60)
    
    base_dir = os.path.dirname(__file__)
    cleaned_dir = os.path.join(base_dir, 'data', 'cleaned')
    models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"\n使用设备: {device}")
    
    print("\n📂 加载数据...")
    dataset = GraphDataset(os.path.join(cleaned_dir, 'train_graph.json'))
    
    with open(os.path.join(base_dir, 'data', 'raw', 'topology.json'), 'r') as f:
        topology = json.load(f)
    dataset.set_services(topology['services'])
    
    print(f"   - 数据集大小: {len(dataset)}")
    
    print("\n📊 划分数据集...")
    train_data, val_data = split_dataset(dataset, train_ratio=0.8)
    print(f"   - 训练集: {len(train_data)}")
    print(f"   - 验证集: {len(val_data)}")
    
    train_loader = DataLoader(train_data, batch_size=32, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_data, batch_size=32, shuffle=False, collate_fn=collate_fn)
    
    configs = [
        {'name': 'GCN', 'type': 'gcn', 'hidden_dim': 64, 'num_layers': 3},
        {'name': 'GAT', 'type': 'gat', 'hidden_dim': 64, 'num_layers': 3},
        {'name': 'GraphSAGE', 'type': 'sage', 'hidden_dim': 64, 'num_layers': 3},
    ]
    
    results = {}
    
    for config in configs:
        print(f"\n{'=' * 60}")
        print(f"训练模型: {config['name']}")
        print(f"{'=' * 60}")
        
        model = create_model(
            model_type=config['type'],
            num_features=5,
            hidden_dim=config['hidden_dim'],
            num_layers=config['num_layers'],
            dropout=0.3,
            device=device
        )
        
        print(f"模型参数量: {sum(p.numel() for p in model.parameters())}")
        
        trainer = Trainer(
            model=model,
            device=device,
            learning_rate=0.001,
            weight_decay=1e-5
        )
        
        history = trainer.train(
            train_loader=train_loader,
            val_loader=val_loader,
            num_epochs=30,
            early_stopping=10
        )
        
        results[config['name']] = {
            'config': config,
            'history': history
        }
        
        model_path = os.path.join(models_dir, f"{config['type']}_model.pt")
        save_model(
            model=model,
            filepath=model_path,
            metadata={
                'model_type': config['type'],
                'hidden_dim': config['hidden_dim'],
                'num_layers': config['num_layers'],
                'train_date': datetime.now().isoformat(),
                'best_val_loss': history['best_val_loss']
            }
        )
    
    print("\n" + "=" * 60)
    print("训练结果汇总")
    print("=" * 60)
    
    for name, result in results.items():
        print(f"\n{name}:")
        print(f"  最佳验证损失: {result['history']['best_val_loss']:.4f}")
        print(f"  最终训练准确率: {result['history']['train_accs'][-1]:.4f}")
        print(f"  最终验证准确率: {result['history']['val_accs'][-1]:.4f}")
    
    with open(os.path.join(models_dir, 'training_results.json'), 'w') as f:
        json.dump({
            name: {
                'config': r['config'],
                'history': {
                    'train_losses': r['history']['train_losses'],
                    'val_losses': r['history']['val_losses'],
                    'train_accs': r['history']['train_accs'],
                    'val_accs': r['history']['val_accs'],
                    'best_val_loss': r['history']['best_val_loss']
                }
            }
            for name, r in results.items()
        }, f, indent=2)
    
    print(f"\n训练结果已保存到: {os.path.join(models_dir, 'training_results.json')}")


if __name__ == "__main__":
    main()
