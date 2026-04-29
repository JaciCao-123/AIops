#!/usr/bin/env python3
"""
Log Analysis DAG - 主入口
整合完整的日志分析 DAG 流水线：
  Step 1: 生成模拟日志文件
  Step 2: Drain 日志解析
  Step 3: 构建 DAG（去环+降噪）
  Step 4: 告警收敛
  Step 5: 变更关联
"""
import json
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from step1_generate_logs import generate_all_logs
from step2_drain_parse import parse_logs
from step3_build_dag import build_dag, ServiceDAG
from step4_alert_convergence import run_alert_convergence, AlertConverger, Alert
from step5_change_correlation import run_change_correlation, ChangeCorrelator, AnomalyEvent


def run_full_pipeline():
    print("=" * 70)
    print("  Log Analysis DAG - 完整流水线")
    print("  日志生成 → Drain解析 → DAG构建 → 告警收敛 → 变更关联")
    print("=" * 70)
    
    total_start = time.time()
    
    # ===== Step 1: 生成模拟日志 =====
    print("\n" + "─" * 70)
    print("Step 1: 生成模拟日志文件")
    print("─" * 70)
    t1 = time.time()
    log_files = generate_all_logs(
        output_dir=str(BASE_DIR / "data" / "raw")
    )
    print(f"  耗时: {time.time() - t1:.2f}s")
    
    # ===== Step 2: Drain 日志解析 =====
    print("\n" + "─" * 70)
    print("Step 2: Drain 日志解析")
    print("─" * 70)
    t2 = time.time()
    parsed_files = parse_logs(
        input_dir=str(BASE_DIR / "data" / "raw"),
        output_dir=str(BASE_DIR / "data" / "parsed"),
    )
    print(f"  耗时: {time.time() - t2:.2f}s")
    
    # ===== Step 3: 构建 DAG =====
    print("\n" + "─" * 70)
    print("Step 3: 构建 DAG（去环 + 降噪）")
    print("─" * 70)
    t3 = time.time()
    dag = build_dag(
        edges_file=str(BASE_DIR / "data" / "parsed" / "call_edges.json"),
        error_summary_file=str(BASE_DIR / "data" / "parsed" / "error_summary.json"),
        output_dir=str(BASE_DIR / "data" / "dag"),
    )
    print(f"  耗时: {time.time() - t3:.2f}s")
    
    # ===== Step 4: 告警收敛 =====
    print("\n" + "─" * 70)
    print("Step 4: 告警收敛")
    print("─" * 70)
    t4 = time.time()
    convergence_results = run_alert_convergence(
        dag_file=str(BASE_DIR / "data" / "dag" / "service_dag.json"),
        output_dir=str(BASE_DIR / "data" / "results"),
    )
    print(f"  耗时: {time.time() - t4:.2f}s")
    
    # ===== Step 5: 变更关联 =====
    print("\n" + "─" * 70)
    print("Step 5: 变更关联")
    print("─" * 70)
    t5 = time.time()
    correlation_results = run_change_correlation(
        dag_file=str(BASE_DIR / "data" / "dag" / "service_dag.json"),
        output_dir=str(BASE_DIR / "data" / "results"),
    )
    print(f"  耗时: {time.time() - t5:.2f}s")
    
    # ===== 汇总 =====
    total_time = time.time() - total_start
    print("\n" + "=" * 70)
    print("  流水线执行完成")
    print("=" * 70)
    print(f"  总耗时: {total_time:.2f}s")
    print(f"\n  生成文件:")
    print(f"    日志:   {BASE_DIR / 'data' / 'raw'}")
    print(f"    解析:   {BASE_DIR / 'data' / 'parsed'}")
    print(f"    DAG:    {BASE_DIR / 'data' / 'dag'}")
    print(f"    结果:   {BASE_DIR / 'data' / 'results'}")
    
    # 关键指标
    print(f"\n  关键指标:")
    if "db_down" in convergence_results:
        db_result = convergence_results["db_down"]
        print(f"    告警压缩率 (DB宕机): {db_result['compression_ratio']}%")
        print(f"    原始告警: {db_result['total_input']} → 根因告警: {db_result['root_cause_count']}")
    
    if "payment_slow" in correlation_results:
        pay_result = correlation_results["payment_slow"]
        print(f"    变更关联置信度 (PaymentService): {pay_result['confidence']}")
        print(f"    关联变更数: {len(pay_result['related_changes'])}")
    
    return {
        "log_files": log_files,
        "parsed_files": parsed_files,
        "convergence": convergence_results,
        "correlation": correlation_results,
    }


def run_interactive_demo():
    """交互式演示"""
    print("\n" + "=" * 70)
    print("  Log Analysis DAG - 交互式演示")
    print("=" * 70)
    
    # 检查是否已有数据
    dag_file = BASE_DIR / "data" / "dag" / "service_dag.json"
    if not dag_file.exists():
        print("\n未找到 DAG 数据，先执行完整流水线...")
        run_full_pipeline()
    
    # 加载 DAG
    with open(dag_file, "r", encoding="utf-8") as f:
        dag_data = json.load(f)
    dag = ServiceDAG.from_dict(dag_data)
    
    while True:
        print("\n" + "─" * 50)
        print("选择操作:")
        print("  1. 查看服务 DAG 拓扑")
        print("  2. 查询服务上游/下游")
        print("  3. 模拟告警收敛")
        print("  4. 模拟变更关联")
        print("  5. 重新生成数据并运行")
        print("  0. 退出")
        print("─" * 50)
        
        choice = input("请选择 (0-5): ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            print(f"\nDAG 拓扑 ({len(dag.nodes)} 节点, {len(dag.edges)} 边):")
            print(f"拓扑排序: {' → '.join(dag.topological_sort())}")
            for name, node in dag.nodes.items():
                downstream = dag.get_downstream(name)
                upstream = dag.get_upstream(name)
                print(f"\n  [{node.node_type}] {name}")
                print(f"    上游: {', '.join(upstream) if upstream else '无'}")
                print(f"    下游: {', '.join(downstream) if downstream else '无'}")
                if node.is_anomaly:
                    print(f"    ⚠️ 异常: 错误率 {node.error_rate}%")
        
        elif choice == "2":
            service = input("输入服务名: ").strip()
            if service in dag.nodes:
                upstream = dag.get_upstream(service)
                downstream = dag.get_downstream(service)
                print(f"\n{service} 的上游: {', '.join(upstream) if upstream else '无'}")
                print(f"{service} 的下游: {', '.join(downstream) if downstream else '无'}")
            else:
                print(f"服务 {service} 不在 DAG 中")
                print(f"可用服务: {', '.join(dag.nodes.keys())}")
        
        elif choice == "3":
            print("\n模拟告警场景:")
            print("  1. DB-Master 宕机")
            print("  2. Redis-Cache 故障")
            print("  3. 自定义")
            sub = input("选择 (1-3): ").strip()
            
            converger = AlertConverger(dag)
            
            if sub == "1":
                alerts = [
                    Alert("A1", "2026-04-24 12:00:01", "DB-Master", "CRITICAL", "Connection refused"),
                    Alert("A2", "2026-04-24 12:00:02", "OrderService", "ERROR", "DB query timeout"),
                    Alert("A3", "2026-04-24 12:00:03", "PaymentService", "ERROR", "DB write timeout"),
                    Alert("A4", "2026-04-24 12:00:04", "Frontend", "WARN", "Upstream timeout"),
                ]
                result = converger.converge_batch(alerts)
                print(f"\n输入: {result['total_input']} 条 → 根因: {result['root_cause_count']} 条")
                for g in result["groups"]:
                    print(f"  根因: {g['root_cause']} | 收敛: {g['suppressed_count']} 条 | 影响: {g['affected_services']}")
            elif sub == "2":
                alerts = [
                    Alert("A1", "2026-04-24 14:00:01", "Redis-Cache", "ERROR", "Master failover"),
                    Alert("A2", "2026-04-24 14:00:02", "PaymentService", "WARN", "Cache miss"),
                    Alert("A3", "2026-04-24 14:00:03", "UserService", "WARN", "Cache miss"),
                ]
                result = converger.converge_batch(alerts)
                print(f"\n输入: {result['total_input']} 条 → 根因: {result['root_cause_count']} 条")
                for g in result["groups"]:
                    print(f"  根因: {g['root_cause']} | 收敛: {g['suppressed_count']} 条 | 影响: {g['affected_services']}")
            else:
                service = input("告警服务: ").strip()
                level = input("告警级别 (INFO/WARN/ERROR/CRITICAL): ").strip() or "ERROR"
                msg = input("告警消息: ").strip() or "Service error"
                alert = Alert("CUSTOM-1", "2026-04-24 12:00:00", service, level, msg)
                result = converger.add_alert(alert)
                print(f"\n动作: {result['action']}")
                print(f"原因: {result['reason']}")
                if result.get("root_cause"):
                    print(f"根因: {result['root_cause']}")
        
        elif choice == "4":
            service = input("输入异常服务名: ").strip()
            anomaly_type = input("异常类型 (latency_spike/timeout/error_rate): ").strip() or "latency_spike"
            
            if service in dag.nodes:
                correlator = ChangeCorrelator(dag)
                correlator.load_change_records([
                    {
                        "change_id": "CHG-DEMO-001",
                        "service": "DB-Master",
                        "change_type": "normal",
                        "description": "ALTER TABLE payments ADD INDEX idx_status",
                        "timestamp": "2026-04-24 13:45:00",
                        "operator": "DBA-Zhang",
                        "risk_level": "HIGH",
                    },
                ])
                
                anomaly = AnomalyEvent(
                    event_id="EVT-DEMO",
                    service=service,
                    anomaly_type=anomaly_type,
                    description=f"{service} {anomaly_type}",
                    timestamp="2026-04-24 14:00:00",
                )
                
                result = correlator.correlate(anomaly)
                print(f"\n根因假设 (置信度: {result.confidence}):")
                print(f"  {result.root_cause_hypothesis}")
                print(f"\n关联变更: {len(result.related_changes)} 条")
                for ch in result.related_changes:
                    print(f"  {ch['service']} | {ch['description'][:50]}")
                print(f"\n建议:")
                print(f"  {result.recommendation}")
            else:
                print(f"服务 {service} 不在 DAG 中")
        
        elif choice == "5":
            run_full_pipeline()
            with open(dag_file, "r", encoding="utf-8") as f:
                dag_data = json.load(f)
            dag = ServiceDAG.from_dict(dag_data)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        run_interactive_demo()
    else:
        run_full_pipeline()
