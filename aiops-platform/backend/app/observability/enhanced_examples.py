"""
Enhanced RCA Usage Examples - 增强型根因分析使用示例

本文件演示如何将 Observability 平台与 time_sequence_detection 算法库
联合起来进行更强大的根因分析。

核心能力：
1. Isolation Forest + Prometheus 指标 → 异常检测
2. Prophet 时序预测 → 趋势偏差发现
3. GNN 图神经网络 + Tempo 链路 → 微服务根因定位
4. 多算法融合 → 综合置信度评估

使用前确保：
- Prometheus 服务运行中 (localhost:9090)
- Tempo 服务运行中 (localhost:3200)
- 已安装依赖: pip install scikit-learn prophet torch torch_geometric
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_1_enhanced_rca_basic():
    """
    示例 1: 增强型根因分析基础用法
    
    展示如何使用 EnhancedRootCauseAnalyzer 进行多算法联合分析
    """
    print("\n" + "="*70)
    print("示例 1: 增强型根因分析（多算法融合）")
    print("="*70)
    
    from app.observability.enhanced_rca import (
        EnhancedRootCauseAnalyzer,
        create_enhanced_analyzer,
        AlgorithmType,
        FusionStrategy,
    )
    
    # 创建增强型分析器（自动启用所有算法）
    async with create_enhanced_analyzer() as analyzer:
        
        print("\n📋 分析器配置:")
        print(f"   ✓ GNN 引擎: {'启用' if analyzer.enable_gnn else '禁用'}")
        print(f"   ✓ Isolation Forest: {'启用' if analyzer.enable_isolation_forest else '禁用'}")
        print(f"   ✓ Prophet: {'启用' if analyzer.enable_prophet else '禁用'}")
        print(f"   ✓ 融合策略: {analyzer.fusion_strategy.value}")
        
        # 执行增强型分析
        print("\n🚀 开始执行增强型根因分析...")
        
        fused_report = await analyzer.analyze_enhanced(
            service_name="order-service",
            time_window_minutes=30,
        )
        
        # 输出结果
        report_dict = fused_report.to_dict()
        
        print(f"\n{'='*60}")
        print(f"📊 增强型根因分析报告")
        print(f"{'='*60}")
        print(f"\n🔹 基本信息:")
        print(f"   分析 ID: {report_dict['analysis_id']}")
        print(f"   整体严重级别: {report_dict['overall_severity'].upper()}")
        print(f"   根因置信度: {report_dict['root_confidence']*100:.1f}%")
        print(f"   分析耗时: {report_dict['analysis_duration_seconds']:.2f}s")
        
        enhanced = report_dict.get('enhanced_analysis', {})
        print(f"\n🔹 算法执行情况:")
        print(f"   执行算法数: {enhanced.get('algorithms_executed', 0)}")
        print(f"   成功算法数: {enhanced.get('algorithms_successful', 0)}")
        print(f"   算法总耗时: {enhanced.get('total_algorithm_time_ms', 0):.1f}ms")
        
        if enhanced.get('algorithm_details'):
            print(f"\n   算法详情:")
            for algo in enhanced['algorithm_details']:
                status = "✅" if algo.get('success') else "❌"
                print(f"     {status} [{algo['type']}] {algo['algorithm']}")
                print(f"        置信度: {algo.get('confidence', 0)*100:.1f}%")
                print(f"        耗时: {algo.get('execution_time_ms', 0):.1f}ms")
        
        if fused_report.base_report.top_hypothesis:
            top = fused_report.base_report.top_hypothesis
            print(f"\n🎯 最可能的根因:")
            print(f"   标题: {top.title}")
            print(f"   受影响组件: {top.affected_component}")
            print(f"   综合置信度: {top.confidence_score*100:.1f}%")
            print(f"   证据数量: {top.evidence_count}")
            
            if top.evidences:
                print(f"\n   支持证据 (来自多个算法):")
                for ev in top.evidences[:5]:
                    print(f"     ✓ [{ev.source}] {ev.description}")


async def example_2_isolation_forest_detection():
    """
    示例 2: 单独使用 Isolation Forest 异常检测
    
    从 Prometheus 采集指标数据，使用 Isolation Forest 检测异常点
    """
    print("\n" + "="*70)
    print("示例 2: Isolation Forest 异常检测")
    print("="*70)
    
    from app.observability.prometheus_client import PrometheusClient, create_prometheus_client
    from app.observability.enhanced_rca import (
        TimeSeriesDataBridge,
        IsolationForestDetector,
    )
    
    async with create_prometheus_client() as prometheus:
        
        # 使用数据桥接层将 Prometheus 数据转换为时间序列
        bridge = TimeSeriesDataBridge()
        
        queries = [
            '100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
        ]
        
        print(f"\n📥 从 Prometheus 采集指标...")
        ts_data = await bridge.prometheus_to_timeseries(
            prometheus=prometheus,
            queries=queries,
            duration_minutes=60,
            step="1m",
        )
        
        for metric_name, df in ts_data.items():
            print(f"\n📊 指标: {metric_name}")
            print(f"   数据点数: {len(df)}")
            print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
            
            if len(df) > 10:
                detector = IsolationForestDetector(contamination=0.05)
                detector.fit(df["value"].values)
                
                result = detector.detect_from_dataframe(df)
                
                print(f"\n   🕵️ Isolation Forest 检测结果:")
                print(f"      总数据点: {result['total_points']}")
                print(f"      异常点数: {result['anomaly_count']}")
                print(f"      异常比例: {result['anomaly_ratio']*100:.2f}%")
                print(f"      统计信息:")
                print(f"         平均异常分数: {result['statistics']['mean_score']:.4f}")
                print(f"         最小分数: {result['statistics']['min_score']:.4f}")
                
                if result["anomalies"]:
                    print(f"\n      ⚠️ Top 异常点:")
                    for anomaly in result["anomalies"][:5]:
                        print(f"         • 时间: {anomaly['timestamp']}")
                        print(f"           值: {anomaly['value']:.2f}, "
                              f"异常分: {anomaly['anomaly_score']:.4f}")


async def example_3_prophet_trend_analysis():
    """
    示例 3: Prophet 时序预测与趋势异常检测
    
    使用 Prophet 预测正常趋势，检测偏离预期的异常
    """
    print("\n" + "="*70)
    print("示例 3: Prophet 时序预测与趋势分析")
    print("="*70)
    
    from app.observability.prometheus_client import PrometheusClient, create_prometheus_client
    from app.observability.enhanced_rca import (
        TimeSeriesDataBridge,
        ProphetForecaster,
    )
    
    async with create_prometheus_client() as prometheus:
        
        bridge = TimeSeriesDataBridge()
        
        queries = [
            'sum(rate(http_requests_total[5m]))',
            'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000',
        ]
        
        print(f"\n📥 采集应用性能指标...")
        ts_data = await bridge.prometheus_to_timeseries(
            prometheus=prometheus,
            queries=queries,
            duration_minutes=120,
            step="5m",
        )
        
        for metric_name, df in ts_data.items():
            print(f"\n📈 指标: {metric_name}")
            print(f"   数据点数: {len(df)}")
            
            if len(df) > 30:
                forecaster = ProphetForecaster(
                    changepoint_prior_scale=0.03,
                    seasonality_mode="additive",
                )
                
                print(f"\n   🔮 训练 Prophet 模型...")
                forecaster.fit(df)
                
                print(f"\n   🕵️ 检测趋势异常 (阈值 σ=2.5)...")
                result = forecaster.detect_anomalies(df, threshold_sigma=2.5)
                
                print(f"\n   检测结果:")
                print(f"      总数据点: {result['total_points']}")
                print(f"      异常点数: {result['anomaly_count']}")
                print(f"      异常比例: {result['anomaly_ratio']*100:.2f}%")
                
                if result["anomalies"]:
                    print(f"\n      ⚠️ 趋势偏离异常:")
                    for anomaly in result["anomalies"][:5]:
                        actual = anomaly["actual_value"]
                        predicted = anomaly["predicted_value"]
                        deviation = ((actual - predicted) / predicted * 100) if predicted != 0 else 0
                        
                        print(f"         • 时间: {anomaly['timestamp']}")
                        print(f"           实际值: {actual:.2f}")
                        print(f"           预测值: {predicted:.2f}")
                        print(f"           偏离度: {deviation:+.1f}%")
                        print(f"           Z-Score: {anomaly['z_score']:.2f}")


async def example_4_gnn_root_cause_analysis():
    """
    示例 4: GNN 图神经网络微服务根因定位
    
    从 Tempo 提取服务调用链，构建图结构，
    使用 GNN 模型识别最可能的故障根因节点
    """
    print("\n" + "="*70)
    print("示例 4: GNN 图神经网络微服务根因定位")
    print("="*70)
    
    from app.observability.tempo_query import TempoQueryClient, create_tempo_client
    from app.observability.enhanced_rca import (
        TimeSeriesDataBridge,
        GNRootCauseEngine,
    )
    
    async with create_tempo_client() as tempo:
        
        bridge = TimeSeriesDataBridge()
        
        print(f"\n🔍 从 Tempo 提取 Trace 数据并构建服务调用图...")
        graph_data = await bridge.tempo_to_graph_data(
            tempo=tempo,
            lookback_minutes=60,
            limit=200,
        )
        
        print(f"\n📊 图结构统计:")
        print(f"   服务节点数: {graph_data['num_nodes']}")
        print(f"   调用边数: {graph_data['num_edges']}")
        print(f"   分析 Traces 数: {graph_data['traces_analyzed']}")
        
        if graph_data["nodes"]:
            print(f"\n🏗️ 服务节点列表:")
            for node in graph_data["nodes"][:10]:
                avg_dur = node.get("total_duration", 0) / max(node.get("span_count", 1), 1)
                err_rate = node.get("error_count", 0) / max(node.get("request_count", 1), 1) * 100
                
                print(f"   • {node['id']}")
                print(f"      Span数: {node['span_count']}, "
                      f"平均延迟: {avg_dur:.0f}ms, 错误率: {err_rate:.1f}%")
        
        if graph_data["edges"]:
            print(f"\n🔗 调用关系 (Top 10):")
            for edge in graph_data["edges"][:10]:
                print(f"   {edge['source']} → {edge['target']} (调用次数: {edge['count']})")
        
        # 初始化 GNN 引擎
        print(f"\n🧠 初始化 GNN 根因引擎...")
        gnn_engine = GNRootCauseEngine(model_type="gat")
        model_loaded = gnn_engine.load_pretrained_model()
        
        if model_loaded:
            print(f"   ✅ GNN 模型加载成功")
        else:
            print(f"   ℹ️ 使用 Rule-Based 降级方案")
        
        # 执行根因预测
        print(f"\n🎯 执行根因预测...")
        prediction = gnn_engine.predict_root_causes(
            graph_data=graph_data,
            top_k=5,
        )
        
        print(f"\n{'='*50}")
        print(f"🎯 GNN 根因分析结果")
        print(f"{'='*50}")
        print(f"   算法: {prediction['algorithm']}")
        print(f"   成功: {prediction['success']}")
        
        candidates = prediction.get("top_candidates", [])
        if candidates:
            print(f"\n   🏆 Top-{len(candidates)} 可能的根因节点:")
            for cand in candidates:
                metrics = cand.get("metrics", {})
                print(f"\n     #{cand['rank']} {cand['service']} (评分: {cand['score']:.4f})")
                print(f"        Span数: {metrics.get('span_count', 'N/A')}")
                print(f"        错误数: {metrics.get('error_count', 'N/A')}")
                print(f"        平均延迟: {metrics.get('avg_duration', 0):.1f}ms")


async def example_5_full_pipeline_comparison():
    """
    示例 5: 完整流程对比
    
    对比：基础 RCA vs 增强 RCA 的效果差异
    """
    print("\n" + "="*70)
    print("示例 5: 基础 RCA vs 增强 RCA 对比分析")
    print("="*70)
    
    from app.observability.root_cause_analyzer import RootCauseAnalyzer, create_root_cause_analyzer
    from app.observability.enhanced_rca import (
        EnhancedRootCauseAnalyzer,
        create_enhanced_analyzer,
    )
    
    service_name = "order-service"
    time_window = 20
    
    # ===== 基础 RCA =====
    print(f"\n{'─'*50}")
    print(f"📍 [A] 运行基础根因分析器...")
    print(f"{'─'*50}")
    
    start_a = datetime.now()
    
    async with create_root_cause_analyzer() as base_analyzer:
        base_report = await base_analyzer.analyze_incident(
            service_name=service_name,
            time_window_minutes=time_window,
        )
    
    duration_a = (datetime.now() - start_a).total_seconds()
    
    base_top_confidence = base_report.root_confidence
    base_hypotheses_count = len(base_report.hypotheses)
    base_evidence_count = sum(h.evidence_count for h in base_report.hypotheses)
    
    print(f"\n   ✅ 基础 RCA 完成")
    print(f"   耗时: {duration_a:.2f}s")
    print(f"   假设数: {base_hypotheses_count}")
    print(f"   证据总数: {base_evidence_count}")
    print(f"   最高置信度: {base_top_confidence*100:.1f}%")
    
    if base_report.top_hypothesis:
        print(f"   Top假设: {base_report.top_hypothesis.title}")
    
    # ===== 增强 RCA =====
    print(f"\n{'─'*50}")
    print(f"📍 [B] 运行增强型根因分析器...")
    print(f"{'─'*50}")
    
    start_b = datetime.now()
    
    async with create_enhanced_analyzer() as enhanced_analyzer:
        enhanced_report = await enhanced_analyzer.analyze_enhanced(
            service_name=service_name,
            time_window_minutes=time_window,
        )
    
    duration_b = (datetime.now() - start_b).total_seconds()
    
    enhanced_top_confidence = enhanced_report.base_report.root_confidence
    enhanced_hypotheses_count = len(enhanced_report.base_report.hypotheses)
    enhanced_evidence_count = sum(h.evidence_count for h in enhanced_report.base_report.hypotheses)
    algorithms_used = enhanced_report.algorithms_used
    
    print(f"\n   ✅ 增强 RCA 完成")
    print(f"   耗时: {duration_b:.2f}s")
    print(f"   假设数: {enhanced_hypotheses_count}")
    print(f"   证据总数: {enhanced_evidence_count}")
    print(f"   最高置信度: {enhanced_top_confidence*100:.1f}%")
    print(f"   使用算法: {', '.join(algorithms_used)}")
    
    if enhanced_report.base_report.top_hypothesis:
        print(f"   Top假设: {enhanced_report.base_report.top_hypothesis.title}")
    
    # ===== 对比总结 =====
    print(f"\n{'='*60}")
    print(f"📊 对比分析总结")
    print(f"{'='*60}")
    
    comparison_data = [
        ("指标", "基础 RCA", "增强 RCA", "提升"),
        ("─"*15, "─"*12, "─"*12, "─"*8),
        ("耗时 (s)", f"{duration_a:.2f}", f"{duration_b:.2f}", 
         f"+{duration_b-duration_a:+.2f}"),
        ("假设数量", str(base_hypotheses_count), str(enhanced_hypotheses_count),
         f"+{enhanced_hypotheses_count-base_hypotheses_count:+d}"),
        ("证据总数", str(base_evidence_count), str(enhanced_evidence_count),
         f"+{enhanced_evidence_count-base_evidence_count:+d}"),
        ("最高置信度", f"{base_top_confidence*100:.1f}%", f"{enhanced_top_confidence*100:.1f}%",
         f"+{(enhanced_top_confidence-base_top_confidence)*100:+.1f}%"),
        ("算法来源", "规则+统计", f"{len(algorithms_used)}个算法", "多源融合"),
    ]
    
    for row in comparison_data:
        print(f"   {row[0]:<15} {row[1]:>12} {row[2]:>12} {row[3]:>8}")
    
    print(f"\n💡 结论:")
    print(f"   增强 RCA 通过整合多种时间序列检测算法，能够：")
    print(f"   • 发现更多维度的异常模式（统计+时序+图结构）")
    print(f"   • 收集更多交叉验证的证据")
    print(f"   • 提供更高的根因定位置信度")


async def example_6_custom_algorithm_pipeline():
    """
    示例 6: 自定义算法流水线
    
    用户可以自由组合不同的算法和分析步骤
    """
    print("\n" + "="*70)
    print("示例 6: 自定义算法流水线组合")
    print("="*70)
    
    from app.observability.prometheus_client import PrometheusClient, create_prometheus_client
    from app.observability.tempo_query import TempoQueryClient, create_tempo_client
    from app.observability.enhanced_rca import (
        TimeSeriesDataBridge,
        IsolationForestDetector,
        ProphetForecaster,
        GNRootCauseEngine,
    )
    
    # 初始化客户端
    prometheus = await create_prometheus_client()
    tempo = await create_tempo_client()
    
    bridge = TimeSeriesDataBridge()
    
    try:
        print("\n🔧 自定义流水线配置:")
        print("   Step 1: Prometheus 指标采集")
        print("   Step 2: Isolation Forest CPU/内存异常检测")
        print("   Step 3: Prophet 错误率趋势分析")
        print("   Step 4: Tempo → Graph 构建")
        print("   Step 5: GNN 根因推理")
        print("   Step 6: 结果汇总")
        
        # Step 1 & 2: 指标采集 + IF 检测
        print("\n▶ Step 1-2: 指标采集 + Isolation Forest...")
        queries = ['100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)']
        ts_data = await bridge.prometheus_to_timeseries(prometheus, queries, duration_minutes=45)
        
        if_results = {}
        for name, df in ts_data.items():
            if len(df) > 10:
                det = IsolationForestDetector(contamination=0.04)
                det.fit(df["value"].values)
                if_results[name] = det.detect_from_dataframe(df)
        
        # Step 3: Prophet 分析
        print("▶ Step 3: Prophet 趋势分析...")
        error_queries = ['sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100']
        error_ts = await bridge.prometheus_to_timeseries(prometheus, error_queries, duration_minutes=90)
        
        prophet_results = {}
        for name, df in error_ts.items():
            if len(df) > 30:
                fc = ProphetForecaster()
                fc.fit(df)
                prophet_results[name] = fc.detect_anomalies(df)
        
        # Step 4 & 5: Graph + GNN
        print("▶ Step 4-5: 构建服务图 + GNN 推理...")
        graph_data = await bridge.tempo_to_graph_data(tempo, lookback_minutes=45)
        
        gnn_engine = GNRootCauseEngine(model_type="gat")
        gnn_engine.load_pretrained_model()
        
        gnn_result = None
        if graph_data["num_nodes"] >= 2:
            gnn_result = gnn_engine.predict_root_causes(graph_data, top_k=3)
        
        # Step 6: 汇总
        print("\n▶ Step 6: 结果汇总")
        print(f"{'─'*55}")
        
        summary = {
            "pipeline": "custom_isolationforest_prophet_gnn",
            "timestamp": datetime.now().isoformat(),
            "results": {
                "isolation_forest": {
                    k: {"anomalies": v.get("anomaly_count", 0), "ratio": v.get("anomaly_ratio", 0)}
                    for k, v in if_results.items()
                },
                "prophet": {
                    k: {"anomalies": v.get("anomaly_count", 0), "ratio": v.get("anomaly_ratio", 0)}
                    for k, v in prophet_results.items()
                },
                "gnn": {
                    "graph_nodes": graph_data["num_nodes"],
                    "graph_edges": graph_data["num_edges"],
                    "top_candidates": gnn_result.get("top_candidates", []) if gnn_result else []
                }
            }
        }
        
        print(f"\n📋 自定义流水线执行完成!")
        print(f"   IF 异常检测: {sum(v['anomalies'] for v in summary['results']['isolation_forest'].values())} 个异常")
        print(f"   Prophet 趋势: {sum(v['anomalies'] for v in summary['results']['prophet'].values())} 个偏离")
        print(f"   GNN 根因: {len(summary['results']['gnn'].get('top_candidates', []))} 个候选")
        
        print(f"\n📝 完整报告 JSON (预览):")
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str)[:800] + "...")
        
    finally:
        await prometheus.close()
        await tempo.close()


async def main():
    """运行所有增强型 RCA 示例"""
    print("\n" + "🔷"*35)
    print("  AIOps 增强型根因分析 - Observability × time_sequence_detection")
    print("  整合: Prometheus | Tempo | GNN | IsolationForest | Prophet")
    print("🔷"*35)
    
    try:
        # 可选择运行不同示例
        
        # 最推荐：完整的增强型分析
        await example_1_enhanced_rca_basic()
        
        # 各算法单独演示
        # await example_2_isolation_forest_detection()
        # await example_3_prophet_trend_analysis()
        # await example_4_gnn_root_cause_analysis()
        
        # 对比分析
        # await example_5_full_pipeline_comparison()
        
        # 自定义流水线
        # await example_6_custom_algorithm_pipeline()
        
        print("\n" + "🔷"*35)
        print("  所有示例执行完毕!")
        print("🔷"*35 + "\n")
        
    except Exception as e:
        logger.error(f"示例执行出错: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
