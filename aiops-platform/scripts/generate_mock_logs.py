import requests
import random
import json

API_URL = "http://localhost:8003/api/logs/ingest"

levels = ["INFO", "WARN", "ERROR", "DEBUG"]
services = ["web-server", "api-gateway", "user-service", "order-service", "payment-service", "redis", "mysql", "kafka"]

log_templates = [
    ("INFO", "Request processed successfully in {time}ms"),
    ("INFO", "Connection established to {service}"),
    ("INFO", "Cache hit ratio: {ratio}%"),
    ("INFO", "User {user_id} logged in from {ip}"),
    ("INFO", "Database query executed: {query}"),
    ("INFO", "Health check passed for {service}"),
    ("WARN", "High memory usage detected: {mem}% on {host}"),
    ("WARN", "Slow query detected: {time}ms for {query}"),
    ("WARN", "Connection pool near capacity: {used}/{total}"),
    ("WARN", "Rate limit approaching for API endpoint: {endpoint}"),
    ("ERROR", "Connection timeout to {service} after {time}s"),
    ("ERROR", "Failed to process request: {error}"),
    ("ERROR", "Database connection failed: {db_error}"),
    ("ERROR", "Authentication failed for user {user_id}: invalid token"),
    ("ERROR", "Out of memory error in {service}"),
    ("DEBUG", "Processing request headers: {headers}"),
    ("DEBUG", "Cache lookup for key: {key}"),
    ("DEBUG", "Executing scheduled task: {task}"),
]

print("开始生成模拟日志...\n")

for i in range(20):
    level, template = random.choice(log_templates)
    
    content = template.format(
        time=random.randint(10, 5000),
        service=random.choice(services),
        ratio=random.randint(70, 99),
        user_id=f"user_{random.randint(1000, 9999)}",
        ip=f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
        query=f"SELECT * FROM {random.choice(['users', 'orders', 'products'])} WHERE id = {random.randint(1,100)}",
        host=f"server-{random.randint(1,10)}",
        mem=random.randint(70, 98),
        used=random.randint(80, 95),
        total=100,
        endpoint=random.choice(["/api/users", "/api/orders", "/api/products"]),
        error=random.choice(["timeout", "connection refused", "OOM", "invalid input"]),
        db_error=random.choice(["too many connections", "deadlock", "lock wait timeout"]),
        headers="{Content-Type: application/json}",
        key=f"cache_key_{random.randint(1,100)}",
        task=random.choice(["cleanup", "backup", "sync", "report"])
    )
    
    payload = {
        "level": level,
        "content": content,
        "source": random.choice(services)
    }
    
    try:
        response = requests.post(API_URL, json=payload)
        result = response.json()
        anomaly_marker = "🔴" if result.get("is_anomaly") else "🟢"
        print(f"{anomaly_marker} [{level}] {content[:60]}... (score: {result.get('anomaly_score', 0):.2f})")
    except Exception as e:
        print(f"Error: {e}")

print("\n日志生成完成!")

stats = requests.get("http://localhost:8003/api/logs/stats").json()
print(f"\n统计信息:")
print(f"   总日志数: {stats['total_logs']}")
print(f"   异常日志数: {stats['anomaly_count']}")
print(f"   异常率: {stats['anomaly_rate']*100:.1f}%")
