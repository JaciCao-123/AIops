"""
Observability Platform Usage Examples - 可观测平台使用示例

本文件展示如何使用 AIOps 可观测平台进行：
1. 基础配置与初始化
2. Prometheus 指标采集
3. OpenTelemetry 分布式追踪
4. Tempo 链路分析
5. 根因分析（RCA）
6. Grafana 仪表盘自动生成
7. 完整的端到端工作流

使用前请确保已安装依赖：
pip install httpx opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi numpy pydantic
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.observability.config import (
    ObservabilityConfig,
    get_observability_config,
)
from app.observability.prometheus_client import (
    PrometheusClient,
    create_prometheus_client,
)
from app.observability.opentelemetry_tracer import (
    OpenTelemetryTracer,
    get_tracer,
    initialize_observability,
    trace_operation,
    SpanKind,
)
from app.observability.tempo_query import (
    TempoQueryClient,
    create_tempo_client,
)
from app.observability.root_cause_analyzer import (
    RootCauseAnalyzer,
    create_root_cause_analyzer,
)
from app.observability.grafana_dashboard import (
    GrafanaDashboardGenerator,
    DashboardTemplate,
    PanelType,
    PanelConfig,
    VariableConfig,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# 示例 1: 基础配置与初始化
# ============================================================

async def example_1_basic_setup():
    """示例1: 初始化可观测平台"""
    print("\n" + "="*60)
    print("示例 1: 基础配置与初始化")
    print("="*60)
    
    # 方式1: 使用默认配置
    config = get_observability_config()
    print(f"✓ Prometheus URL: {config.prometheus.url}")
    print(f"✓ Grafana URL: {config.grafana.url}")
    print(f"✓ Tempo URL: {config.tempo.url}")
    print(f"✓ OTEL Endpoint: {config.opentelemetry.endpoint}")
    
    # 方式2: 自定义配置
    custom_config = ObservabilityConfig(
        prometheus__url="http://prometheus:9090",
        grafana__url="http://grafana:3000",
        grafana__api_key="your-grafana-api-key",
        tempo__url="http://tempo:3200",
        opentelemetry__endpoint="http://otel-collector:4317",
        opentelemetry__service_name="my-aiops-service",
    )
    
    print(f"\n✓ 自定义配置已创建: {custom_config.opentelemetry.service_name}")


# ============================================================
# 示例 2: Prometheus 指标采集
# ============================================================

async def example_2_prometheus_metrics():
    """示例2: 使用 Prometheus 采集和分析指标"""
    print("\n" + "="*60)
    print("示例 2: Prometheus 指标采集与分析")
    print("="*60)
    
    async with create_prometheus_client() as prometheus:
        
        # 2.1 即时查询
        print("\n--- 2.1 执行即时查询 ---")
        result = await prometheus.instant_query(
            query='100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
        )
        
        if result.status == "success":
            print(f"✓ 查询成功, 获取到 {len(result.data)} 个数据点")
            for item in result.data[:3]:
                metric = item.get("metric", {})
                value = item.get("value", (None, None))
                print(f"  - Instance: {metric.get('instance')}, CPU: {value[1]:.2f}%")
        else:
            print(f"✗ 查询失败: {result.error}")
        
        # 2.2 范围查询（时间序列）
        print("\n--- 2.2 执行范围查询 ---")
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=30)
        
        range_result = await prometheus.range_query(
            query='(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
            start=start_time,
            end=end_time,
            step="5m",
        )
        
        if range_result.status == "success":
            print(f"✓ 时间序列数据获取成功, 共 {len(range_result.data)} 个序列")
        
        # 2.3 系统指标批量采集
        print("\n--- 2.3 批量采集系统指标 ---")
        system_metrics = await prometheus.collect_system_metrics(duration_minutes=10)
        
        metrics_collected = list(system_metrics.get("metrics", {}).keys())
        print(f"✓ 已采集指标类型: {len(metrics_collected)}")
        for m in metrics_collected[:5]:
            print(f"  - {m}")
        
        # 2.4 异常检测
        print("\n--- 2.4 指标异常检测 ---")
        anomaly_result = await prometheus.detect_anomalies(
            query='sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100',
            lookback_hours=6,
            zscore_threshold=2.5,
        )
        
        anomalies_count = anomaly_result.get("total_anomalies", 0)
        print(f"✓ 检测到 {anomalies_count} 个异常点")
        
        if anomalies_count > 0:
            for anomaly in anomaly_result["anomalies"][:3]:
                print(f"  ! 异常: value={anomaly['value']:.2f}, z-score={anomaly['z_score']:.2f}")
        
        # 2.5 检查告警规则
        print("\n--- 2.5 告警检查 ---")
        alerts = await prometheus.check_alert_rules()
        
        if alerts:
            print(f"⚠ 触发 {len(alerts)} 条告警:")
            for alert in alerts[:3]:
                print(f"  [{alert.severity.value.upper()}] {alert.rule_name}: {alert.message}")
        else:
            print("✓ 所有指标正常, 无告警触发")


# ============================================================
# 示例 3: OpenTelemetry 分布式追踪
# ============================================================

async def example_3_opentelemetry_tracing():
    """示例3: 使用 OpenTelemetry 进行分布式追踪"""
    print("\n" + "="*60)
    print("示例 3: OpenTelemetry 分布式追踪")
    print("="*60)
    
    # 3.1 初始化追踪器
    tracer = get_tracer()
    tracer.initialize()
    
    print("✓ OpenTelemetry SDK 已初始化")
    
    # 3.2 使用装饰器进行自动追踪
    @tracer.trace_operation(name="database_query_example", kind=SpanKind.CLIENT)
    async def simulate_database_query(user_id: str):
        """模拟数据库查询"""
        await asyncio.sleep(0.15)  # 模拟查询延迟
        
        return {"user_id": user_id, "name": "Test User"}
    
    # 3.3 使用上下文管理器
    print("\n--- 3.3 使用上下文管理器手动追踪 ---")
    
    async with tracer.async_span_context(
        name="api_request_processing",
        kind=SpanKind.SERVER,
        attributes={"http.method": "GET", "http.url": "/api/users/123"},
    ) as span:
        
        tracer.set_attribute(span, "user.id", "12345")
        
        # 子操作 1: 数据库查询
        async with tracer.async_span_context(
            name="query_user_database",
            kind=SpanKind.CLIENT,
            attributes={"db.system": "postgresql"},
        ) as db_span:
            
            result = await simulate_database_query("12345")
            tracer.set_attribute(db_span, "db.rows_returned", 1)
        
        # 子操作 2: 缓存更新
        async with tracer.async_span_context(
            name="update_cache",
            kind=SpanKind.CLIENT,
            attributes={"cache.system": "redis"},
        ) as cache_span:
            await asyncio.sleep(0.02)  # 模拟缓存操作
        
        # 记录事件
        tracer.add_event(span, event_name="request_completed", attributes={
            "status_code": "200",
            "response_size": "256 bytes",
        })
    
    print("✓ Trace 已记录完成")
    
    # 3.4 获取当前 Trace 上下文（用于跨服务传递）
    context = tracer.get_trace_context()
    if context:
        print(f"✓ 当前 Trace ID: {context['trace_id']}")
        print(f"✓ 当前 Span ID: {context['span_id']}")
    
    # 关闭
    tracer.shutdown()


# ============================================================
# 示例 4: Tempo 链路分析
# ============================================================

async def example_4_tempo_analysis():
    """示例4: 使用 Tempo 分析分布式链路"""
    print("\n" + "="*60)
    print("示例 4: Tempo 链路追踪分析")
    print("="*60)
    
    async with create_tempo_client() as tempo:
        
        # 4.1 搜索错误 Traces
        print("\n--- 4.1 搜索包含错误的 Traces ---")
        error_traces = await tempo.search_error_traces(
            service_name="aiops-platform",
            lookback="2h",
            limit=20,
        )
        
        print(f"✓ 发现 {error_traces.total} 条错误 Trace")
        
        for trace_info in error_traces.traces[:3]:
            trace_id = trace_info.get("traceID", "")
            duration = trace_info.get("durationNanos", 0)
            print(f"  - Trace: {trace_id[:16]}..., Duration: {int(duration)/1e6:.0f}ms")
        
        # 4.2 搜索慢请求
        print("\n--- 4.2 搜索慢请求 Traces ---")
        slow_traces = await tempo.search_slow_traces(
            min_duration="2s",
            lookback="1h",
            limit=10,
        )
        
        print(f"✓ 发现 {slow_traces.total} 个慢请求")
        
        # 4.3 分析特定 Trace 的性能
        if error_traces.traces or slow_traces.traces:
            sample_trace_id = (error_traces.traces or slow_traces.traces)[0].get("traceID", "")
            
            if sample_trace_id:
                print(f"\n--- 4.3 分析 Trace 性能: {sample_trace_id[:16]}... ---")
                
                perf_analysis = await tempo.analyze_trace_performance(sample_trace_id)
                
                stats = perf_analysis.get("duration_statistics", {})
                print(f"  总 Span 数: {perf_analysis.get('analysis_summary', {}).get('total_spans', 0)}")
                print(f"  平均延迟: {stats.get('mean_ms', 0):.2f}ms")
                print(f"  P99 延迟: {stats.get('p99_ms', 0):.2f}ms")
                print(f"  最大延迟: {stats.get('max_ms', 0):.2f}ms")
                
                bottlenecks = perf_analysis.get("bottleneck_analysis", [])
                if bottlenecks:
                    print(f"\n  ⚠ 发现 {len(bottlenecks)} 个性能瓶颈:")
                    for bn in bottlenecks[:3]:
                        print(f"    - {bn['operation_name']} ({bn['service_name']}): "
                              f"{bn['duration_ms']:.0f}ms [{bn['severity']}]")
        
        # 4.4 构建服务依赖图
        print("\n--- 4.4 构建服务依赖关系图 ---")
        dependency_graph = await tempo.build_service_dependency_graph(time_window_minutes=120)
        
        services = dependency_graph.get("services", [])
        dependencies = dependency_graph.get("dependencies", [])
        
        print(f"✓ 发现 {len(services)} 个服务")
        print(f"✓ 发现 {len(dependencies)} 个依赖关系")
        
        for dep in dependencies[:5]:
            print(f"  {dep['source']} → {dep['target']} "
                  f"(调用次数: {dep['call_count']}, 平均延迟: {dep['avg_duration_ms']:.0f}ms)")


# ============================================================
# 示例 5: 根因分析（RCA）
# ============================================================

async def example_5_root_cause_analysis():
    """示例5: 执行完整的根因分析"""
    print("\n" + "="*60)
    print("示例 5: 多维根因分析（RCA）")
    print("="*60)
    
    async with create_root_cause_analyzer() as rca_analyzer:
        
        # 5.1 对特定服务执行根因分析
        print("\n--- 5.1 分析服务 'order-service' ---")
        
        report = await rca_analyzer.analyze_incident(
            service_name="order-service",
            time_window_minutes=20,
        )
        
        # 输出报告摘要
        print(f"\n{'='*50}")
        print(f"📊 根因分析报告")
        print(f"{'='*50}")
        print(f"分析 ID: {report.analysis_id}")
        print(f"整体严重级别: {report.overall_severity.value.upper()}")
        print(f"根因置信度: {report.root_confidence * 100:.1f}%")
        print(f"分析耗时: {report.analysis_duration_seconds:.2f}s")
        print(f"数据源: {', '.join(report.data_sources_used)}")
        print(f"分析指标数: {report.metrics_analyzed}")
        print(f"分析链路数: {report.traces_analyzed}")
        
        print(f"\n📝 摘要:")
        print(f"  {report.summary}")
        
        # 输出 Top 假设
        if report.top_hypothesis:
            top = report.top_hypothesis
            print(f"\n🎯 最可能的根因 (置信度: {top.confidence_score*100:.1f}%):")
            print(f"  标题: {top.title}")
            print(f"  描述: {top.description}")
            print(f"  受影响组件: {top.affected_component}")
            print(f"  严重级别: {top.severity.value}")
            print(f"  证据数量: {top.evidence_count}")
            
            if top.evidences:
                print(f"\n  支持证据:")
                for ev in top.evidences[:3]:
                    print(f"    ✓ [{ev.evidence_type.value}] {ev.description} "
                          f"(可信度: {ev.confidence*100:.1f}%)")
            
            if top.remediation_steps:
                print(f"\n  🔧 修复建议:")
                for i, step in enumerate(top.remediation_steps, 1):
                    print(f"    {i}. {step}")
        
        # 输出所有假设
        print(f"\n📋 所有根因假设 ({len(report.hypotheses)} 个):")
        for i, hyp in enumerate(report.hypotheses[:5], 1):
            print(f"  {i}. [{hyp.severity.value.upper()}] {hyp.title} "
                  f"(置信度: {hyp.confidence_score*100:.1f}%)")
        
        # 输出总体建议
        if report.recommendations:
            print(f"\n💡 总体建议:")
            for rec in report.recommendations[:5]:
                print(f"  • {rec}")
        
        # 5.2 导出完整报告为 JSON
        print(f"\n--- 5.2 导出分析报告 ---")
        report_dict = report.to_dict()
        
        import json
        report_json = json.dumps(report_dict, indent=2, ensure_ascii=False, default=str)
        
        print(f"✓ 报告 JSON 大小: {len(report_json)} 字符")
        print(f"✓ 包含 {len(report.hypotheses)} 个假设的详细数据")


# ============================================================
# 示例 6: Grafana 仪表盘自动生成
# ============================================================

async def example_6_grafana_dashboard():
    """示例6: 自动生成并部署 Grafana 仪表盘"""
    print("\n" + "="*60)
    print("示例 6: Grafana 仪表盘自动生成与部署")
    print("="*60)
    
    async with create_dashboard_generator() as dashboard_gen:
        
        # 6.1 生成系统监控仪表盘
        print("\n--- 6.1 生成系统概览仪表盘 ---")
        
        system_dashboard = dashboard_gen.generate_dashboard(
            template=DashboardTemplate.SYSTEM_OVERVIEW,
            title="AIOps - 系统资源监控",
        )
        
        panel_count = len(system_dashboard.get("panels", []))
        print(f"✓ 仪表盘已生成, 包含 {panel_count} 个面板")
        
        # 6.2 生成 APM 仪表盘
        print("\n--- 6.2 生成应用性能仪表盘 ---")
        
        apm_dashboard = dashboard_gen.generate_dashboard(
            template=DashboardTemplate.APPLICATION_PERFORMANCE,
            title="AIOps - 应用性能监控",
            service_name="order-service",
        )
        
        print(f"✓ APM 仪表盘已生成, 包含 {len(apm_dashboard.get('panels', []))} 个面板")
        
        # 6.3 生成根因分析专用仪表盘
        print("\n--- 6.3 生成根因分析仪表盘 ---")
        
        rca_dashboard = dashboard_gen.generate_dashboard(
            template=DashboardTemplate.ROOT_CAUSE_ANALYSIS,
            title="AIOps - 根因分析工作台",
        )
        
        print(f"✓ RCA 仪表盘已生成, 包含 {len(rca_dashboard.get('panels', []))} 个面板")
        
        # 6.4 部署到 Grafana（需要有效的 API Key）
        print("\n--- 6.4 部署仪表盘到 Grafana ---")
        
        deploy_result = await dashboard_gen.deploy_to_grafana(
            dashboard=system_dashboard,
            overwrite=True,
        )
        
        if deploy_result.get("success"):
            print(f"✅ 部署成功!")
            print(f"   Dashboard ID: {deploy_result.get('dashboard_id')}")
            print(f"   URL: {deploy_result.get('url')}")
        else:
            print(f"❌ 部署失败: {deploy_result.get('error')}")
            print("   提示: 请确认 Grafana API Key 配置正确且 Grafana 服务可访问")
        
        # 6.5 列出现有仪表盘
        print("\n--- 6.5 列出现有仪表盘 ---")
        
        existing_dashboards = await dashboard_gen.list_dashboards()
        
        print(f"✓ 当前共有 {len(existing_dashboards)} 个仪表盘:")
        for db in existing_dashboards[:5]:
            print(f"  - {db['title']} (uid: {db['uid']})")


# ============================================================
# 示例 7: 完整工作流（端到端）
# ============================================================

async def example_7_complete_workflow():
    """示例7: 完整的可观测性工作流"""
    print("\n" + "="*60)
    print("示例 7: 完整可观测性工作流（端到端演示）")
    print("="*60)
    
    config = get_observability_config()
    
    # Step 1: 初始化所有组件
    print("\n📍 Step 1: 初始化可观测组件...")
    
    prometheus = PrometheusClient(config=config)
    await prometheus.connect()
    print("  ✓ Prometheus 客户端已连接")
    
    tempo = TempoQueryClient(config=config)
    await tempo.connect()
    print("  ✓ Tempo 客户端已连接")
    
    rca_analyzer = RootCauseAnalyzer(
        config=config,
        prometheus_client=prometheus,
        tempo_client=tempo,
    )
    print("  ✓ 根因分析器已初始化")
    
    # Step 2: 监控检查
    print("\n📍 Step 2: 执行健康检查...")
    
    prom_health = await prometheus.health_check()
    tempo_health = await tempo.health_check()
    
    print(f"  Prometheus: {prom_health['status']}")
    print(f"  Tempo: {tempo_health['status']}")
    
    # Step 3: 收集告警
    print("\n📍 Step 3: 收集当前告警...")
    
    alerts = await prometheus.check_alert_rules()
    
    if alerts:
        print(f"  ⚠ 发现 {len(alerts)} 条活跃告警")
        
        critical_alerts = [a for a in alerts if a.severity.value == "critical"]
        if critical_alerts:
            print(f"  🚨 其中 {len(critical_alerts)} 条为严重级别!")
            
            # Step 4: 触发根因分析
            print("\n📍 Step 4: 执行根因分析...")
            
            report = await rca_analyzer.analyze_incident(
                alert_events=critical_alerts,
                time_window_minutes=15,
            )
            
            # 输出关键发现
            if report.top_hypothesis:
                print(f"\n  🔍 根因分析结果:")
                print(f"     最可能原因: {report.top_hypothesis.title}")
                print(f"     置信度: {report.top_hypothesis.confidence_score*100:.1f}%")
                print(f"     受影响组件: {report.top_hypothesis.affected_component}")
                
                if report.top_hypothesis.remediation_steps:
                    print(f"\n  🔧 建议措施:")
                    for step in report.top_hypothesis.remediation_steps:
                        print(f"     → {step}")
    else:
        print("  ✅ 系统运行正常, 无告警")
    
    # Step 5: 生成可视化报告
    print("\n📍 Step 5: 生成可视化仪表盘...")
    
    dashboard_gen = GrafanaDashboardGenerator(config=config)
    await dashboard_gen.connect()
    
    if alerts:
        dashboard = dashboard_gen.generate_dashboard(
            template=DashboardTemplate.ROOT_CAUSE_ANALYSIS,
            title=f"AIOps - 事件分析 ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
        )
        
        deploy_result = await dashboard_gen.deploy_to_grafana(dashboard)
        
        if deploy_result.get("success"):
            print(f"  ✓ 分析仪表盘已部署: {deploy_result.get('url')}")
    
    # 清理
    await prometheus.close()
    await tempo.close()
    
    print("\n✅ 完整工作流执行完毕!")


# ============================================================
# 主程序入口
# ============================================================

async def main():
    """运行所有示例"""
    print("\n" + "🔷"*30)
    print("  AIOps 可观测平台 - 使用示例集合")
    print("  集成 Prometheus | Grafana | OpenTelemetry | Tempo")
    print("🔷"*30)
    
    try:
        # 运行各示例（可根据需要注释/取消注释）
        await example_1_basic_setup()
        
        await example_2_prometheus_metrics()
        
        await example_3_opentelemetry_tracing()
        
        await example_4_tempo_analysis()
        
        await example_5_root_cause_analysis()
        
        await example_6_grafana_dashboard()
        
        await example_7_complete_workflow()
        
        print("\n" + "🔷"*30)
        print("  所有示例执行完毕!")
        print("🔷"*30 + "\n")
        
    except Exception as e:
        logger.error(f"示例执行出错: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
