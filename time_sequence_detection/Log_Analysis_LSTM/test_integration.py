#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aiops-platform" / "backend"))

from app.agents.tool_registry import ToolRegistry

async def test():
    print('=' * 60)
    print('测试 detect_log_anomalies 工具集成')
    print('=' * 60)
    
    registry = ToolRegistry()
    
    tools = registry.list_tools()
    if 'detect_log_anomalies' in tools:
        print('✅ detect_log_anomalies 工具已注册')
    else:
        print('❌ detect_log_anomalies 工具未注册')
        return
    
    print()
    print('测试异常检测...')
    
    result = await registry.execute(
        'detect_log_anomalies',
        top_k=3
    )
    
    if result.get('success'):
        print('✅ 检测成功')
        print(f'  - 总日志数: {result["total_logs"]}')
        print(f'  - 异常数: {result["anomalies_detected"]}')
        print(f'  - 异常率: {result["anomaly_rate"]:.2f}%')
    else:
        print(f'❌ 检测失败: {result.get("error")}')
    
    print()
    print('✅ 测试完成!')

if __name__ == '__main__':
    asyncio.run(test())
