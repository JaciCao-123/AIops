#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNN 根因分析系统 - 主流水线脚本

一键运行完整的根因分析流程：
Step 1: 生成模拟数据（拓扑 + 告警）
Step 2: 数据清洗与图构建
Step 3: GNN模型定义（可选测试）
Step 4: 模型训练/加载
Step 5: LLM智能分析与报告

使用方法:
    python run_pipeline.py                        # 运行完整流程
    python run_pipeline.py --steps 1,2             # 只运行指定步骤
    python run_pipeline.py --skip-training         # 跳过训练，使用已有模型
    python run_pipeline.py --scenarios 30          # 自定义场景数
    python run_pipeline.py --mode inference        # 仅推理模式
"""

import os
import sys
import argparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    TOPOLOGY_CONFIG,
    ALERT_CONFIG,
    DATA_DIRS,
    MODEL_CONFIG,
    TRAINING_CONFIG,
    LLM_CONFIG,
    get_device
)


def print_banner():
    """打印系统横幅"""
    
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🧠  GNN Root Cause Analysis System v1.0                  ║
║     基于图神经网络的微服务故障根因定位系统                      ║
║                                                              ║
║     Supported Architectures:                                 ║
║     • GCN (Graph Convolutional Network)                     ║
║     • GAT (Graph Attention Network) ⭐                       ║
║     • GraphSAGE (Sample and Aggregate)                      ║
║     • TemporalGNN (Time-aware GNN)                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    
    print(banner)


def step1_generate_data(args):
    """Step 1: 生成模拟数据"""
    
    print("\n" + "="*70)
    print("📦 Step 1: 生成模拟数据")
    print("="*70)
    
    from step1_generate_data import ServiceTopologyGenerator, FaultScenarioGenerator, DataExporter
    
    # 生成拓扑
    topo_gen = ServiceTopologyGenerator(TOPOLOGY_CONFIG)
    topology = topo_gen.generate()
    
    # 生成故障场景
    scenario_gen = FaultScenarioGenerator(topology, ALERT_CONFIG)
    scenarios = scenario_gen.generate_scenarios(args.scenarios)
    
    # 导出数据
    exporter = DataExporter(DATA_DIRS["raw"])
    exporter.topology = topology
    files = exporter.export_all(topology, scenarios, args.output_prefix)
    
    return topology, scenarios, files


def step2_clean_and_build(args, files=None):
    """Step 2: 数据清洗与图构建"""
    
    print("\n" + "="*70)
    print("🧹 Step 2: 数据清洗与图构建")
    print("="*70)
    
    import json
    
    if files is None:
        # 查找最新的数据文件
        raw_dir = DATA_DIRS["raw"]
        
        topo_files = [f for f in os.listdir(raw_dir) if f.endswith("_topology.json")]
        alert_files = [f for f in os.listdir(raw_dir) if f.endswith("_alerts.csv")]
        
        if not topo_files or not alert_files:
            raise FileNotFoundError("未找到原始数据文件，请先运行 Step 1")
        
        latest_topo = sorted(topo_files)[-1]
        latest_alerts = sorted(alert_files)[-1]
        
        topo_path = os.path.join(raw_dir, latest_topo)
        alerts_path = os.path.join(raw_dir, latest_alerts)
    else:
        prefix = args.output_prefix or datetime.now().strftime("%Y%m%d_%H%M%S")
        topo_path = os.path.join(DATA_DIRS["raw"], f"{prefix}_topology.json")
        alerts_path = os.path.join(DATA_DIRS["raw"], f"{prefix}_alerts.csv")
    
    from step2_clean_and_build_graph import AlertDataCleaner, TimeSeriesAligner, HeterogeneousGraphBuilder
    
    # 加载数据
    with open(topo_path, 'r') as f:
        topology_json = json.load(f)
    
    import pandas as pd
    alerts_df = pd.read_csv(alerts_path)
    
    # 清洗
    cleaner = AlertDataCleaner()
    cleaned_df = cleaner.clean(alerts_df.copy())
    
    # 时间对齐
    aligner = TimeSeriesAligner()
    aligned_df = aligner.align(cleaned_df)
    
    # 构建图
    builder = HeterogeneousGraphBuilder()
    graph_data = builder.build_from_topology_and_alerts(topology_json, aligned_df)
    
    # 保存图数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    graph_file = os.path.join(
        DATA_DIRS["graphs"],
        f"graph_data_{timestamp}.npz"
    )
    
    import numpy as np
    np.savez(
        graph_file,
        node_features=graph_data["node_features"],
        edge_index=graph_data["edge_index"],
        edge_attr=graph_data["edge_attr"],
        labels=np.array(graph_data["labels"]),
        **{f"temporal_{k}": v for k, v in graph_data["temporal_features"].items()}
    )
    
    # 保存元数据
    meta = {
        "num_nodes": graph_data["num_nodes"],
        "feature_dim": graph_data["node_features"].shape[1],
        "topo_path": topo_path,
        "alerts_path": alerts_path,
        "graph_path": graph_file
    }
    
    meta_path = os.path.join(
        DATA_DIRS["cleaned"],
        f"metadata_{timestamp}.json"
    )
    
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)
    
    print(f"\n✅ 图数据已保存: {graph_file}")
    
    return graph_data, meta


def step3_test_model(args, metadata):
    """Step 3: 测试模型定义"""
    
    print("\n" + "="*70)
    print("🧠 Step 3: 测试GNN模型")
    print("="*70)
    
    from step3_gnn_models import RootCauseGNN, ModelFactory
    
    device = get_device()
    input_dim = metadata.get("feature_dim", 64)
    
    model = ModelFactory.create_model(MODEL_CONFIG, input_dim=input_dim)
    model = model.to(device)
    
    summary = ModelFactory.get_model_summary(model)
    
    print(f"\n   模型类型: {summary['model_type'].upper()}")
    print(f"   参数量: {summary['total_parameters']:,}")
    print(f"   模型大小: {summary['size_mb']:.2f} MB")
    
    # 快速前向传播测试
    import torch
    num_nodes = metadata.get("num_nodes", 15)
    
    test_input = torch.randn(num_nodes, input_dim).to(device)
    test_edges = torch.randint(0, num_nodes, (2, 40)).to(device)
    
    with torch.no_grad():
        output = model(test_input, test_edges)
    
    print(f"   ✅ 模型测试通过! 输出形状: {output.shape}")
    
    return model


def step4_train(args, graph_data, metadata):
    """Step 4: 训练模型"""
    
    print("\n" + "="*70)
    print("🎯 Step 4: 模型训练")
    print("="*70)
    
    from step4_train_model import RootCauseTrainer, load_graph_data, GraphDataset
    
    # 如果提供了图数据路径，直接加载
    graph_path = metadata.get("graph_path")
    
    if os.path.exists(graph_path):
        dataset, _ = load_graph_data(graph_path)
    else:
        # 从graph_data创建dataset
        import numpy as np
        import torch
        
        node_ids = list(range(len(graph_data["labels"])))
        dataset = GraphDataset(
            node_features=graph_data["node_features"],
            edge_index=graph_data["edge_index"],
            labels=np.array(graph_data["labels"]),
            edge_attr=graph_data.get("edge_attr"),
            temporal_features=graph_data.get("temporal_features", {}),
            node_ids=[str(i) for i in node_ids]
        )
    
    # 创建训练器
    trainer = RootCauseTrainer(MODEL_CONFIG, TRAINING_CONFIG)
    trainer.setup_model(metadata["feature_dim"])
    
    # 是否恢复训练
    if args.resume and os.path.exists(args.resume):
        trainer.load_model(args.resume)
    
    # 训练
    save_dir = TRAINING_CONFIG["checkpoint_dir"]
    results = trainer.train(dataset, epochs=args.epochs, save_dir=save_dir)
    
    # 最终评估
    final_metrics = trainer.evaluate(dataset)
    
    print(f"\n📊 最终指标:")
    print(f"   F1 Score: {final_metrics['f1']:.4f}")
    print(f"   AUC-ROC: {final_metrics['auc']:.4f}")
    print(f"   Precision: {final_metrics['precision']:.4f}")
    print(f"   Recall: {final_metrics['recall']:.4f}")
    
    return trainer, results, final_metrics


def step5_analyze(args, trainer, metadata):
    """Step 5: LLM分析与报告"""
    
    print("\n" + "="*70)
    print("🤖 Step 5: LLM智能分析")
    print("="*70)
    
    from step5_llm_analysis import (
        GNNResultInterpreter,
        LLMAnalyzer,
        DiagnosisReportGenerator
    )
    from step4_train_model import load_graph_data, GraphDataset
    
    import torch
    
    device = get_device()
    graph_path = metadata.get("graph_path")
    
    if not os.path.exists(graph_path):
        print("⚠️ 未找到图数据文件，跳过LLM分析")
        return None, None
    
    # 加载数据并推理
    dataset, _ = load_graph_data(graph_path)
    trainer.model.eval()
    
    with torch.no_grad():
        node_features = dataset.node_features.to(device)
        edge_index = dataset.edge_index.to(device)
        edge_attr = dataset.edge_attr.to(device) if dataset.edge_attr is not None else None
        
        temporal_feats = None
        if dataset.temporal_features:
            temporal_feats = {k: v.to(device) for k, v in dataset.temporal_features.items()}
        
        logits = trainer.model(node_features, edge_index, edge_attr, temporal_feats)
    
    # 解释结果
    interpreter = GNNResultInterpreter()
    gnn_result = interpreter.interpret_predictions(logits)
    
    print(f"\n   🎯 识别到 {gnn_result['total_suspected']} 个可疑根因:")
    for candidate in gnn_result["root_cause_candidates"][:3]:
        print(f"      • {candidate['service_name']} [{candidate['layer']}] "
              f"- {candidate['probability']:.1%}")
    
    # LLM分析
    analyzer = LLMAnalyzer(LLM_CONFIG)
    
    alerts_summary = {
        "total_alerts": 100,
        "max_severity": "critical",
        "top_alert_types": ["CPU过高", "连接超时"]
    }
    
    llm_analysis = analyzer.analyze_root_cause(
        gnn_result=gnn_result,
        topology_info={"num_nodes": metadata["num_nodes"]},
        alerts_summary=alerts_summary
    )
    
    # 生成报告
    generator = DiagnosisReportGenerator(DATA_DIRS["results"])
    
    final_meta = {
        **metadata,
        "scenario_id": f"GNN-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "model_type": MODEL_CONFIG["model_type"].upper(),
        "best_f1": trainer.best_val_f1
    }
    
    report_path, _ = generator.generate_report(
        gnn_interpretation=gnn_result,
        llm_analysis=llm_analysis,
        metadata=final_meta,
        format=args.output_format
    )
    
    return gnn_result, report_path


def main():
    parser = argparse.ArgumentParser(
        description='GNN根因分析系统主流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--steps', 
        type=str, 
        default='all',
        help='运行的步骤 (例如: 1,2,3 或 all)'
    )
    parser.add_argument('--scenarios', type=int, default=20, help='故障场景数量')
    parser.add_argument('--services', type=int, default=15, help='服务数量')
    parser.add_argument('--epochs', type=int, default=None, help='训练轮数')
    parser.add_argument('--output-prefix', type=str, default='', help='输出文件前缀')
    parser.add_argument('--output-format', choices=['markdown', 'json'], default='markdown')
    parser.add_argument('--skip-training', action='store_true', help='跳过训练步骤')
    parser.add_argument('--resume', type=str, default=None, help='恢复训练的checkpoint')
    parser.add_argument('--mode', choices=['full', 'inference'], default='full', help='运行模式')
    parser.add_argument('--model-path', type=str, default=None, help='已有模型路径(推理模式)')
    parser.add_argument('--graph-data', type=str, default=None, help='图数据路径(推理模式)')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')
    
    args = parser.parse_args()
    
    print_banner()
    
    start_time = datetime.now()
    
    # 解析步骤
    if args.steps == 'all':
        steps_to_run = [1, 2, 3, 4, 5]
    else:
        steps_to_run = [int(s.strip()) for s in args.steps.split(',')]
    
    print(f"\n⚙️ 运行配置:")
    print(f"   步骤: {steps_to_run}")
    print(f"   场景数: {args.scenarios}")
    print(f"   设备: {get_device()}")
    print(f"   模式: {args.mode}")
    
    # 存储中间结果
    topology = None
    scenarios = None
    files = None
    graph_data = None
    metadata = {}
    model = None
    trainer = None
    
    try:
        # Step 1: 生成数据
        if 1 in steps_to_run or args.mode == 'full':
            topology, scenarios, files = step1_generate_data(args)
        
        # Step 2: 清洗和建图
        if 2 in steps_to_run or args.mode == 'full':
            graph_data, metadata = step2_clean_and_build(args, files)
        
        # Step 3: 测试模型
        if 3 in steps_to_run:
            model = step3_test_model(args, metadata)
        
        # Step 4: 训练模型
        if 4 in steps_to_run and not args.skip_training:
            trainer, train_results, metrics = step4_train(args, graph_data, metadata)
        elif args.skip_training:
            print("\n⏭️ 跳过训练步骤")
            
            # 尝试加载已有模型
            ckpt_dir = TRAINING_CONFIG["checkpoint_dir"]
            best_model_path = os.path.join(ckpt_dir, "best_model.pt")
            
            if os.path.exists(best_model_path):
                from step4_train_model import RootCauseTrainer
                trainer = RootCauseTrainer(MODEL_CONFIG)
                trainer.setup_model(metadata["feature_dim"])
                trainer.load_model(best_model_path)
            else:
                print("⚠️ 未找到已训练的模型")
        
        # Step 5: LLM分析
        if 5 in steps_to_run and trainer is not None:
            gnn_result, report_path = step5_analyze(args, trainer, metadata)
            
            if report_path:
                print(f"\n🎉 完整报告已生成: {report_path}")
        
        # 统计总耗时
        total_time = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "="*70)
        print("✅ 流水线执行完成!")
        print("="*70)
        print(f"\n⏱️ 总耗时: {total_time/60:.2f} 分钟")
        print(f"📁 输出目录:")
        print(f"   原始数据: {DATA_DIRS['raw']}")
        print(f"   清洗后数据: {DATA_DIRS['cleaned']}")
        print(f"   图数据: {DATA_DIRS['graphs']}")
        print(f"   模型检查点: {TRAINING_CONFIG['checkpoint_dir']}")
        print(f"   分析报告: {DATA_DIRS['results']}")
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()