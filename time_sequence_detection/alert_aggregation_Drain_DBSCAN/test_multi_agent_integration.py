#!/usr/bin/env python3
"""
测试 Multi-Agent 调用告警聚合 Skill
生成大量模拟告警数据，通过 API 测试告警聚合功能
"""
import asyncio
import json
import random
from datetime import datetime, timedelta
import httpx

BASE_URL = "http://localhost:8000"

ALERT_TEMPLATES = [
    ("Connection to {service} timeout after {time}ms", ["Redis", "MySQL", "PostgreSQL", "MongoDB", "Elasticsearch"]),
    ("High CPU usage detected on {node}: {percent}%", ["node-1", "node-2", "node-3", "node-4", "node-5"]),
    ("Memory allocation failed for {service}", ["order-service", "payment-service", "user-service", "inventory-service"]),
    ("OutOfMemoryError in {service} on {node}", ["order-service", "payment-service", "user-service"]),
    ("Database connection pool exhausted in {service}", ["order-service", "payment-service", "api-gateway"]),
    ("Kafka consumer lag exceeded {count} messages", ["10000", "15000", "20000", "25000"]),
    ("SSL certificate expired for {domain}", ["api.example.com", "cdn.example.com", "admin.example.com"]),
    ("Disk usage warning: {percent}% on {node}", ["node-1", "node-2", "node-3"]),
    ("API Gateway timeout for service {service}", ["inventory-api", "product-api", "search-api"]),
    ("Slow query detected: {query} took {time}s", ["SELECT * FROM orders", "SELECT * FROM users", "SELECT * FROM products"]),
    ("NullPointerException in {service}.{method}", ["PaymentService.processOrder", "UserService.login", "OrderService.create"]),
    ("Redis connection refused to {host}:{port}", ["redis-master-01", "redis-slave-01", "redis-cluster"]),
    ("MySQL replication lag exceeded {seconds}s", ["60", "120", "180"]),
    ("Pod {pod} OOMKilled in namespace {namespace}", ["frontend-xyz", "backend-abc", "worker-123"]),
    ("Service {service} health check failed", ["order-service", "payment-service", "notification-service"]),
    ("Certificate validation failed for {service}", ["auth-service", "api-gateway", "payment-gateway"]),
    ("Thread pool exhausted in {service}", ["AsyncProcessor", "TaskExecutor", "RequestHandler"]),
    ("GC pause time exceeded {time}ms in {service}", ["order-service", "payment-service", "user-service"]),
    ("Nginx upstream timeout for {backend}", ["backend-service", "api-service", "static-service"]),
    ("RabbitMQ queue {queue} is full", ["orders", "notifications", "emails"]),
]

NODES = ["node-1", "node-2", "node-3", "node-4", "node-5", "node-6", "node-7", "node-8"]


def generate_alert(timestamp: datetime, template_idx: int = None) -> dict:
    if template_idx is None:
        template_idx = random.randint(0, len(ALERT_TEMPLATES) - 1)
    
    template, values = ALERT_TEMPLATES[template_idx]
    
    placeholders = {}
    for i, val_list in enumerate(values):
        key = f"val{i}"
        placeholders[key] = random.choice(val_list)
    
    if "{service}" in template:
        template = template.replace("{service}", placeholders.get("val0", "unknown-service"))
    if "{node}" in template:
        template = template.replace("{node}", placeholders.get("val0", random.choice(NODES)))
    if "{time}" in template:
        template = template.replace("{time}", placeholders.get("val0", str(random.randint(100, 5000))))
    if "{percent}" in template:
        template = template.replace("{percent}", str(random.randint(80, 99)))
    if "{count}" in template:
        template = template.replace("{count}", placeholders.get("val0", "10000"))
    if "{domain}" in template:
        template = template.replace("{domain}", placeholders.get("val0", "api.example.com"))
    if "{query}" in template:
        template = template.replace("{query}", placeholders.get("val0", "SELECT * FROM table"))
    if "{method}" in template:
        template = template.replace("{method}", placeholders.get("val0", "processRequest"))
    if "{host}" in template:
        template = template.replace("{host}", placeholders.get("val0", "localhost"))
    if "{port}" in template:
        template = template.replace("{port}", str(random.randint(3000, 9000)))
    if "{seconds}" in template:
        template = template.replace("{seconds}", placeholders.get("val0", "60"))
    if "{pod}" in template:
        template = template.replace("{pod}", f"pod-{random.randint(1000, 9999)}")
    if "{namespace}" in template:
        template = template.replace("{namespace}", placeholders.get("val0", "default"))
    if "{backend}" in template:
        template = template.replace("{backend}", placeholders.get("val0", "backend"))
    if "{queue}" in template:
        template = template.replace("{queue}", placeholders.get("val0", "default"))
    
    return {
        "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "node_id": random.choice(NODES),
        "raw_msg": template
    }


def generate_alert_storm(
    num_alerts: int = 100,
    time_window_minutes: int = 5,
    cluster_pattern: bool = True
) -> list:
    """
    生成告警风暴数据
    
    Args:
        num_alerts: 告警总数
        time_window_minutes: 时间窗口（分钟）
        cluster_pattern: 是否生成聚类模式（相似告警集中出现）
    """
    alerts = []
    base_time = datetime.now() - timedelta(minutes=time_window_minutes)
    
    if cluster_pattern:
        num_clusters = random.randint(3, 8)
        alerts_per_cluster = num_alerts // num_clusters
        
        for cluster_id in range(num_clusters):
            template_idx = random.randint(0, len(ALERT_TEMPLATES) - 1)
            cluster_start = base_time + timedelta(minutes=random.randint(0, time_window_minutes - 1))
            
            for i in range(alerts_per_cluster):
                timestamp = cluster_start + timedelta(seconds=random.randint(0, 59))
                alert = generate_alert(timestamp, template_idx)
                alerts.append(alert)
        
        remaining = num_alerts - len(alerts)
        for _ in range(remaining):
            timestamp = base_time + timedelta(seconds=random.randint(0, time_window_minutes * 60))
            alerts.append(generate_alert(timestamp))
    else:
        for _ in range(num_alerts):
            timestamp = base_time + timedelta(seconds=random.randint(0, time_window_minutes * 60))
            alerts.append(generate_alert(timestamp))
    
    alerts.sort(key=lambda x: x["time"])
    return alerts


async def login() -> str:
    """登录获取 token"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "admin", "password": "admin123"}
        )
        if response.status_code == 200:
            data = response.json()
            return data["data"]["token"]
        else:
            raise Exception(f"Login failed: {response.text}")


async def test_cluster_alerts_direct(alerts: list, token: str):
    """直接测试 cluster_alerts 工具（通过 Multi-Agent 流程）"""
    print("\n" + "=" * 60)
    print("直接测试 cluster_alerts 工具")
    print("=" * 60)
    
    alert_summary = f"共 {len(alerts)} 条告警"
    
    query = f"""请使用 cluster_alerts 工具对以下告警进行聚合分析：

告警数据:
{json.dumps(alerts, ensure_ascii=False)}

请分析告警聚类结果，告诉我主要的问题类型和影响范围。"""
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/multi-agent/process",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 聚合请求已发送!")
            print(f"  - 查询: {result.get('query', '')[:50]}...")
            print(f"  - 耗时: {result.get('duration_seconds', 0):.2f}s")
            
            final_decision = result.get("final_decision", {})
            if final_decision:
                print(f"\n📊 最终决策:")
                print(f"  - 问题类型: {final_decision.get('problem_type', 'N/A')}")
                print(f"  - 根因: {final_decision.get('root_cause', 'N/A')[:100]}...")
                print(f"  - 建议: {final_decision.get('recommendation', 'N/A')[:100]}...")
            
            return result
        else:
            print(f"❌ 测试失败: {response.text}")
            return None


async def test_multi_agent_query(alerts: list, token: str):
    """测试 Multi-Agent 查询"""
    print("\n" + "=" * 60)
    print("测试 Multi-Agent 告警聚合查询")
    print("=" * 60)
    
    alert_summary = f"共 {len(alerts)} 条告警，时间范围: {alerts[0]['time']} ~ {alerts[-1]['time']}"
    
    query = f"""我收到了大量告警，请帮我进行告警聚合分析。

告警摘要: {alert_summary}

告警数据:
{json.dumps(alerts, ensure_ascii=False)}

请使用 cluster_alerts 工具对这些告警进行聚合分析，告诉我主要的问题类型和影响范围。"""
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/multi-agent/process",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Multi-Agent 查询成功!")
            print(f"  - 耗时: {result.get('duration_seconds', 0):.2f}s")
            
            final_decision = result.get("final_decision", {})
            if final_decision:
                print(f"\n📊 最终决策:")
                print(f"  - 问题类型: {final_decision.get('problem_type', 'N/A')}")
                print(f"  - 根因: {final_decision.get('root_cause', 'N/A')}")
                print(f"  - 影响: {final_decision.get('impact', 'N/A')}")
                print(f"  - 建议: {final_decision.get('recommendation', 'N/A')}")
                print(f"  - 置信度: {final_decision.get('confidence', 'N/A')}")
            
            stages = result.get("stages", {})
            if "skill_matching" in stages:
                print(f"\n📋 Skill 匹配:")
                print(f"  - 匹配的 Skills: {stages['skill_matching'].get('matched_skills', [])}")
            
            return result
        else:
            print(f"❌ 查询失败: {response.text}")
            return None


async def main():
    print("🚀 测试 Multi-Agent 告警聚合功能")
    print("=" * 60)
    
    print("\n1. 生成模拟告警数据...")
    alerts = generate_alert_storm(num_alerts=100, time_window_minutes=5, cluster_pattern=True)
    print(f"   ✅ 已生成 {len(alerts)} 条告警")
    print(f"   时间范围: {alerts[0]['time']} ~ {alerts[-1]['time']}")
    
    print("\n2. 登录获取 token...")
    token = await login()
    print(f"   ✅ Token: {token[:20]}...")
    
    print("\n3. 测试 Multi-Agent 告警聚合查询...")
    await test_multi_agent_query(alerts, token)
    
    print("\n" + "=" * 60)
    print("✅ 测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
