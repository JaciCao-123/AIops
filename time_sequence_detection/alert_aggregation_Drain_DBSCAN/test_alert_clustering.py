#!/usr/bin/env python3
"""
测试 Multi-Agent 调用 alert_cluster_skill 告警聚合功能
生成大量模拟告警数据，验证告警聚合逻辑
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
    
    for i, val_list in enumerate(values):
        placeholder = f"{{val{i}}}"
        if placeholder in template:
            template = template.replace(placeholder, random.choice(val_list))
    
    if "{service}" in template:
        template = template.replace("{service}", random.choice(["order-service", "payment-service", "user-service"]))
    if "{node}" in template:
        template = template.replace("{node}", random.choice(NODES))
    if "{time}" in template:
        template = template.replace("{time}", str(random.randint(100, 5000)))
    if "{percent}" in template:
        template = template.replace("{percent}", str(random.randint(80, 99)))
    if "{count}" in template:
        template = template.replace("{count}", str(random.randint(10000, 25000)))
    if "{domain}" in template:
        template = template.replace("{domain}", random.choice(["api.example.com", "cdn.example.com"]))
    if "{query}" in template:
        template = template.replace("{query}", "SELECT * FROM table")
    if "{method}" in template:
        template = template.replace("{method}", "processRequest")
    if "{host}" in template:
        template = template.replace("{host}", random.choice(["redis-master-01", "redis-slave-01"]))
    if "{port}" in template:
        template = template.replace("{port}", str(random.randint(3000, 9000)))
    if "{seconds}" in template:
        template = template.replace("{seconds}", str(random.randint(60, 180)))
    if "{pod}" in template:
        template = template.replace("{pod}", f"pod-{random.randint(1000, 9999)}")
    if "{namespace}" in template:
        template = template.replace("{namespace}", "default")
    if "{backend}" in template:
        template = template.replace("{backend}", random.choice(["backend-service", "api-service"]))
    if "{queue}" in template:
        template = template.replace("{queue}", random.choice(["orders", "notifications"]))
    
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
        num_clusters = random.randint(5, 10)
        alerts_per_cluster = num_alerts // num_clusters
        
        for cluster_id in range(num_clusters):
            template_idx = cluster_id % len(ALERT_TEMPLATES)
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


async def test_alert_clustering(alerts: list, token: str):
    """
    测试告警聚合功能
    明确使用 alert_cluster_skill 进行告警聚合
    """
    print("\n" + "=" * 70)
    print("测试 Multi-Agent 告警聚合 (alert_cluster_skill)")
    print("=" * 70)
    
    print(f"\n📊 告警数据概览:")
    print(f"   - 告警总数: {len(alerts)}")
    print(f"   - 时间范围: {alerts[0]['time']} ~ {alerts[-1]['time']}")
    
    print(f"\n📋 告警样本 (前5条):")
    for i, alert in enumerate(alerts[:5], 1):
        print(f"   [{i}] {alert['node_id']}: {alert['raw_msg'][:60]}...")
    
    query = f"""请帮我进行告警聚合分析。

我收到了告警风暴，需要进行告警聚合压缩。请使用 cluster_alerts 工具对以下告警进行聚类分析：

告警数据:
{json.dumps(alerts, ensure_ascii=False)}

请告诉我：
1. 聚类结果（有多少个聚类，每个聚类的代表告警）
2. 主要的问题类型
3. 受影响的节点
4. 压缩率"""

    print(f"\n🚀 发送请求到 Multi-Agent...")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/multi-agent/process",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✅ Multi-Agent 处理成功!")
            print(f"   - 处理耗时: {result.get('duration_seconds', 0):.2f}s")
            
            stages = result.get("stages", {})
            if "skill_matching" in stages:
                print(f"\n📋 Skill 匹配结果:")
                matched = stages['skill_matching'].get('matched_skills', [])
                print(f"   - 匹配的 Skills: {matched}")
                if 'alert_cluster_skill' in matched:
                    print(f"   ✅ alert_cluster_skill 已匹配!")
                else:
                    print(f"   ⚠️ alert_cluster_skill 未匹配，可能需要调整查询关键词")
            
            if "intent_parsing" in stages:
                intent = stages['intent_parsing']
                print(f"\n🔍 意图识别:")
                print(f"   - 意图: {intent.get('intent', 'N/A')}")
                entities = intent.get('entities', {})
                if entities:
                    print(f"   - 实体: {json.dumps(entities, ensure_ascii=False)[:100]}...")
            
            final_decision = result.get("final_decision", {})
            if final_decision:
                print(f"\n📊 最终诊断结果:")
                print(f"   - 问题类型: {final_decision.get('problem_type', 'N/A')}")
                print(f"   - 根因分析: {final_decision.get('root_cause', 'N/A')}")
                print(f"   - 影响范围: {final_decision.get('impact', 'N/A')}")
                print(f"   - 建议措施: {final_decision.get('recommendation', 'N/A')}")
                print(f"   - 置信度: {final_decision.get('confidence', 'N/A')}")
            
            execution_result = result.get("execution_result", {})
            if execution_result:
                print(f"\n🔧 执行结果:")
                history = execution_result.get("execution_history", [])
                for i, step in enumerate(history[:5], 1):
                    tool = step.get("tool", "unknown")
                    if tool == "cluster_alerts":
                        print(f"\n   ✅ cluster_alerts 工具调用成功!")
                        tool_result = step.get("result", {})
                        print(f"      - 输入告警数: {tool_result.get('total_input', 'N/A')}")
                        print(f"      - 聚类数量: {tool_result.get('cluster_count', 'N/A')}")
                        print(f"      - 噪声告警: {tool_result.get('noise_count', 'N/A')}")
                        print(f"      - 压缩率: {tool_result.get('compression_ratio', 'N/A')}")
                        
                        clusters = tool_result.get("clusters", [])
                        print(f"\n      📋 聚类详情:")
                        for cluster in clusters[:5]:
                            print(f"         聚类 {cluster['cluster_id']}:")
                            print(f"           - 告警数: {cluster['alert_count']}")
                            print(f"           - 代表告警: {cluster['representative_alert'][:50]}...")
                            print(f"           - 影响节点: {', '.join(cluster['affected_nodes'])}")
            
            return result
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return None


async def main():
    print("=" * 70)
    print("🚀 测试 Multi-Agent 告警聚合功能 (alert_cluster_skill)")
    print("=" * 70)
    
    print("\n[步骤 1] 生成模拟告警风暴数据...")
    alerts = generate_alert_storm(
        num_alerts=150,
        time_window_minutes=5,
        cluster_pattern=True
    )
    print(f"   ✅ 已生成 {len(alerts)} 条告警")
    
    print("\n[步骤 2] 登录系统获取 Token...")
    token = await login()
    print(f"   ✅ 登录成功")
    
    print("\n[步骤 3] 测试告警聚合...")
    await test_alert_clustering(alerts, token)
    
    print("\n" + "=" * 70)
    print("✅ 测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
