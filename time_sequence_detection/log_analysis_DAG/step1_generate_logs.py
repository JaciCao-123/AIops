#!/usr/bin/env python3
"""
Step 1: 生成模拟日志文件
包含有全链路追踪 ID 和无 traceID 的日志
模拟微服务架构中的典型调用链路和故障场景
"""
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


SERVICE_REGISTRY = {
    "Frontend": {
        "type": "gateway",
        "downstream": ["OrderService", "UserService", "PaymentService"],
        "log_patterns": [
            "Request received: {method} {path}",
            "Response sent: {status} in {duration}ms",
            "Upstream timeout: {upstream_service}",
            "Connection pool exhausted",
            "Rate limit exceeded for client {client_ip}",
        ]
    },
    "OrderService": {
        "type": "service",
        "downstream": ["PaymentService", "InventoryService", "DB-Master"],
        "log_patterns": [
            "Creating order: user={user_id}, items={item_count}",
            "Order created: order_id={order_id}",
            "Payment request sent to PaymentService",
            "Inventory check: {item_count} items available",
            "DB query timeout: SELECT * FROM orders WHERE user_id={user_id}",
            "Failed to create order: {error}",
            "Order status updated: {order_id} -> {status}",
        ]
    },
    "PaymentService": {
        "type": "service",
        "downstream": ["DB-Master", "Redis-Cache", "Kafka"],
        "log_patterns": [
            "Processing payment: order={order_id}, amount={amount}",
            "Payment successful: txn_id={txn_id}",
            "Payment failed: {error}",
            "Cache miss for payment session: {session_id}",
            "DB write timeout: INSERT INTO payments",
            "Kafka publish: payment_event for order {order_id}",
            "Refund initiated: order={order_id}, reason={reason}",
        ]
    },
    "UserService": {
        "type": "service",
        "downstream": ["DB-Master", "Redis-Cache"],
        "log_patterns": [
            "User login: user_id={user_id}",
            "User profile query: user_id={user_id}",
            "Cache hit for user profile: {user_id}",
            "Cache miss for user profile: {user_id}",
            "DB query: SELECT * FROM users WHERE id={user_id}",
            "Authentication failed: invalid token",
            "Session expired: user_id={user_id}",
        ]
    },
    "InventoryService": {
        "type": "service",
        "downstream": ["DB-Master", "Redis-Cache"],
        "log_patterns": [
            "Inventory check: product={product_id}, warehouse={warehouse}",
            "Stock reserved: product={product_id}, qty={qty}",
            "Stock insufficient: product={product_id}, requested={qty}, available={avail}",
            "DB query timeout: SELECT stock FROM inventory",
            "Cache invalidation: product={product_id}",
        ]
    },
    "DB-Master": {
        "type": "database",
        "downstream": [],
        "log_patterns": [
            "Query executed: {query_type} in {duration}ms",
            "Slow query: {query_type} took {duration}ms (>500ms threshold)",
            "Connection pool: active={active}, idle={idle}, waiting={waiting}",
            "Deadlock detected: transaction {txn_id}",
            "Replication lag: {lag_seconds}s",
            "Disk usage: {usage_pct}% on /data",
            "Buffer pool hit rate: {hit_rate}%",
            "Change applied: {change_description}",
        ]
    },
    "Redis-Cache": {
        "type": "cache",
        "downstream": [],
        "log_patterns": [
            "Cache GET: key={key}, hit={hit}",
            "Cache SET: key={key}, ttl={ttl}s",
            "Memory usage: {used_memory}MB / {max_memory}MB",
            "Eviction policy triggered: evicted {count} keys",
            "Connection refused: max clients reached",
            "Master failover initiated",
        ]
    },
    "Kafka": {
        "type": "mq",
        "downstream": [],
        "log_patterns": [
            "Message produced: topic={topic}, partition={partition}, offset={offset}",
            "Consumer lag: group={group}, topic={topic}, lag={lag}",
            "Broker unreachable: broker-{broker_id}",
            "Partition reassignment: topic={topic}",
            "Replica sync: ISR={isr_count}/{replica_count}",
        ]
    },
}


FAULT_SCENARIOS = {
    "db_down": {
        "description": "DB-Master 宕机，导致下游服务全部报错",
        "root_service": "DB-Master",
        "affected_services": ["OrderService", "PaymentService", "UserService", "InventoryService", "Frontend"],
        "fault_logs": [
            ("DB-Master", "CRITICAL", "Connection refused: too many connections"),
            ("DB-Master", "ERROR", "Buffer pool hit rate: 12%"),
            ("OrderService", "ERROR", "DB query timeout: SELECT * FROM orders WHERE user_id=U10042"),
            ("PaymentService", "ERROR", "DB write timeout: INSERT INTO payments"),
            ("UserService", "ERROR", "DB query: SELECT * FROM users WHERE id=U10042 - timeout 30s"),
            ("InventoryService", "ERROR", "DB query timeout: SELECT stock FROM inventory"),
            ("Frontend", "WARN", "Upstream timeout: OrderService"),
            ("Frontend", "WARN", "Upstream timeout: PaymentService"),
            ("Frontend", "ERROR", "Response sent: 503 in 30045ms"),
        ]
    },
    "db_change": {
        "description": "DB-Master 刚做变更（索引变更），导致 PaymentService 变慢",
        "root_service": "DB-Master",
        "affected_services": ["PaymentService", "OrderService", "Frontend"],
        "fault_logs": [
            ("DB-Master", "INFO", "Change applied: ALTER TABLE payments ADD INDEX idx_status (status)"),
            ("DB-Master", "WARN", "Slow query: SELECT took 2340ms (>500ms threshold)"),
            ("DB-Master", "WARN", "Slow query: INSERT took 1890ms (>500ms threshold)"),
            ("PaymentService", "WARN", "Processing payment: order=ORD-20260424-0042, amount=299.00 - latency 2450ms"),
            ("PaymentService", "ERROR", "Payment failed: timeout after 30s"),
            ("OrderService", "WARN", "Payment request sent to PaymentService - latency 3200ms"),
            ("Frontend", "WARN", "Upstream timeout: PaymentService"),
        ]
    },
    "redis_failover": {
        "description": "Redis 主从切换导致缓存雪崩",
        "root_service": "Redis-Cache",
        "affected_services": ["PaymentService", "UserService", "Frontend"],
        "fault_logs": [
            ("Redis-Cache", "WARN", "Master failover initiated"),
            ("Redis-Cache", "ERROR", "Connection refused: max clients reached"),
            ("Redis-Cache", "WARN", "Eviction policy triggered: evicted 15234 keys"),
            ("PaymentService", "WARN", "Cache miss for payment session: SES-abc123"),
            ("UserService", "WARN", "Cache miss for user profile: U10042"),
            ("UserService", "WARN", "Cache miss for user profile: U10087"),
            ("Frontend", "WARN", "Upstream timeout: UserService"),
        ]
    },
    "kafka_lag": {
        "description": "Kafka 消息堆积导致消费延迟",
        "root_service": "Kafka",
        "affected_services": ["PaymentService", "OrderService"],
        "fault_logs": [
            ("Kafka", "WARN", "Consumer lag: group=payment-group, topic=payment-events, lag=52340"),
            ("Kafka", "WARN", "Broker unreachable: broker-2"),
            ("PaymentService", "WARN", "Kafka publish: payment_event for order ORD-20260424-0042 - latency 890ms"),
            ("OrderService", "WARN", "Order status updated: ORD-20260424-0042 -> pending - delayed 45s"),
        ]
    },
}


def _gen_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def _gen_span_id() -> str:
    return uuid.uuid4().hex[:8]


def _gen_timestamp(base_time: datetime, offset_seconds: int = 0) -> str:
    t = base_time + timedelta(seconds=offset_seconds)
    return t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _fill_pattern(pattern: str) -> str:
    placeholders = {
        "{method}": random.choice(["GET", "POST", "PUT"]),
        "{path}": random.choice(["/api/orders", "/api/payments", "/api/users", "/api/inventory"]),
        "{status}": str(random.choice([200, 200, 200, 201, 400, 500, 503])),
        "{duration}": str(random.randint(5, 5000)),
        "{upstream_service}": random.choice(["OrderService", "PaymentService", "UserService"]),
        "{client_ip}": f"10.0.{random.randint(1,255)}.{random.randint(1,255)}",
        "{user_id}": f"U{random.randint(10000, 99999)}",
        "{item_count}": str(random.randint(1, 10)),
        "{order_id}": f"ORD-20260424-{random.randint(1,9999):04d}",
        "{product_id}": f"PRD-{random.randint(1000, 9999)}",
        "{warehouse}": random.choice(["wh-east", "wh-west", "wh-north"]),
        "{qty}": str(random.randint(1, 5)),
        "{avail}": str(random.randint(0, 100)),
        "{amount}": f"{random.uniform(10, 999):.2f}",
        "{txn_id}": f"TXN-{uuid.uuid4().hex[:8].upper()}",
        "{session_id}": f"SES-{uuid.uuid4().hex[:8]}",
        "{error}": random.choice(["timeout", "connection refused", "internal error", "rate limit"]),
        "{reason}": random.choice(["user_request", "duplicate", "fraud_detected"]),
        "{query_type}": random.choice(["SELECT", "INSERT", "UPDATE", "DELETE"]),
        "{active}": str(random.randint(10, 80)),
        "{idle}": str(random.randint(5, 20)),
        "{waiting}": str(random.randint(0, 50)),
        "{txn_id}": f"TX-{random.randint(10000, 99999)}",
        "{lag_seconds}": str(random.randint(1, 300)),
        "{usage_pct}": str(random.randint(50, 98)),
        "{hit_rate}": f"{random.uniform(80, 99.5):.1f}",
        "{change_description}": random.choice([
            "ALTER TABLE payments ADD INDEX idx_status",
            "UPDATE config SET value='new_pool_size' WHERE key='connection_pool'",
            "CREATE INDEX idx_created_at ON orders(created_at)",
        ]),
        "{key}": random.choice(["user:profile:U10042", "payment:session:SES-abc", "inventory:stock:PRD-5001"]),
        "{ttl}": str(random.choice([300, 600, 1800, 3600])),
        "{hit}": random.choice(["true", "false"]),
        "{used_memory}": str(random.randint(1024, 8192)),
        "{max_memory}": "16384",
        "{count}": str(random.randint(100, 50000)),
        "{topic}": random.choice(["payment-events", "order-events", "user-events"]),
        "{partition}": str(random.randint(0, 11)),
        "{offset}": str(random.randint(100000, 9999999)),
        "{group}": random.choice(["payment-group", "order-group", "user-group"]),
        "{lag}": str(random.randint(0, 100000)),
        "{broker_id}": str(random.randint(1, 5)),
        "{isr_count}": str(random.randint(1, 3)),
        "{replica_count}": "3",
    }
    result = pattern
    for ph, val in placeholders.items():
        result = result.replace(ph, val)
    return result


def generate_normal_logs(
    base_time: datetime,
    count: int = 200,
    trace_ratio: float = 0.6,
) -> List[Dict[str, Any]]:
    """
    生成正常流量日志
    """
    logs = []
    services = list(SERVICE_REGISTRY.keys())
    
    for i in range(count):
        service = random.choice(services)
        svc_info = SERVICE_REGISTRY[service]
        pattern = random.choice(svc_info["log_patterns"])
        message = _fill_pattern(pattern)
        level = random.choices(
            ["INFO", "WARN", "ERROR"],
            weights=[0.8, 0.15, 0.05]
        )[0]
        
        has_trace = random.random() < trace_ratio
        trace_id = _gen_trace_id() if has_trace else "-"
        span_id = _gen_span_id() if has_trace else "-"
        parent_span = _gen_span_id() if has_trace and random.random() < 0.7 else "-"
        
        log_entry = {
            "timestamp": _gen_timestamp(base_time, i),
            "level": level,
            "service": service,
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span,
            "message": message,
        }
        logs.append(log_entry)
    
    return logs


def generate_trace_chain_logs(
    base_time: datetime,
    chain_count: int = 30,
) -> List[Dict[str, Any]]:
    """
    生成完整的调用链日志（同一 trace_id 贯穿多个服务）
    """
    logs = []
    
    call_chains = [
        ["Frontend", "OrderService", "PaymentService", "DB-Master"],
        ["Frontend", "OrderService", "InventoryService", "DB-Master"],
        ["Frontend", "UserService", "DB-Master"],
        ["Frontend", "UserService", "Redis-Cache"],
        ["Frontend", "PaymentService", "Redis-Cache"],
        ["Frontend", "PaymentService", "DB-Master"],
        ["Frontend", "PaymentService", "Kafka"],
        ["OrderService", "PaymentService", "DB-Master"],
        ["OrderService", "InventoryService", "Redis-Cache"],
    ]
    
    for i in range(chain_count):
        chain = random.choice(call_chains)
        trace_id = _gen_trace_id()
        parent_span = "-"
        offset = i * 3
        
        for j, service in enumerate(chain):
            span_id = _gen_span_id()
            svc_info = SERVICE_REGISTRY[service]
            pattern = random.choice(svc_info["log_patterns"])
            message = _fill_pattern(pattern)
            level = "INFO" if j == 0 else random.choice(["INFO", "INFO", "WARN"])
            
            log_entry = {
                "timestamp": _gen_timestamp(base_time, offset + j),
                "level": level,
                "service": service,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span if j > 0 else "-",
                "message": message,
            }
            logs.append(log_entry)
            parent_span = span_id
    
    return logs


def generate_fault_logs(
    base_time: datetime,
    scenario_name: str,
) -> List[Dict[str, Any]]:
    """
    生成故障场景日志
    """
    scenario = FAULT_SCENARIOS[scenario_name]
    logs = []
    trace_id = _gen_trace_id()
    
    for i, (service, level, message) in enumerate(scenario["fault_logs"]):
        has_trace = random.random() < 0.5
        log_entry = {
            "timestamp": _gen_timestamp(base_time, i * 2),
            "level": level,
            "service": service,
            "trace_id": trace_id if has_trace else "-",
            "span_id": _gen_span_id() if has_trace else "-",
            "parent_span_id": _gen_span_id() if has_trace and i > 0 else "-",
            "message": message,
        }
        logs.append(log_entry)
    
    return logs


def generate_all_logs(output_dir: str = None) -> Dict[str, str]:
    """
    生成所有模拟日志文件
    
    Returns:
        生成的文件路径字典
    """
    if output_dir is None:
        output_dir = str(Path(__file__).parent / "data" / "raw")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    base_time = datetime(2026, 4, 24, 10, 0, 0)
    
    files = {}
    
    # 1. 正常流量日志
    normal_logs = generate_normal_logs(base_time, count=200, trace_ratio=0.6)
    normal_file = output_path / "normal_traffic.log"
    with open(normal_file, "w", encoding="utf-8") as f:
        for log in normal_logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
    files["normal_traffic"] = str(normal_file)
    print(f"[1/5] 正常流量日志: {normal_file} ({len(normal_logs)} 条)")
    
    # 2. 调用链日志
    chain_logs = generate_trace_chain_logs(base_time, chain_count=30)
    chain_file = output_path / "trace_chain.log"
    with open(chain_file, "w", encoding="utf-8") as f:
        for log in chain_logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
    files["trace_chain"] = str(chain_file)
    print(f"[2/5] 调用链日志: {chain_file} ({len(chain_logs)} 条)")
    
    # 3. DB 宕机故障日志
    db_down_logs = generate_fault_logs(base_time + timedelta(hours=2), "db_down")
    db_down_file = output_path / "fault_db_down.log"
    with open(db_down_file, "w", encoding="utf-8") as f:
        for log in db_down_logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
    files["fault_db_down"] = str(db_down_file)
    print(f"[3/5] DB宕机故障日志: {db_down_file} ({len(db_down_logs)} 条)")
    
    # 4. DB 变更故障日志
    db_change_logs = generate_fault_logs(base_time + timedelta(hours=4), "db_change")
    db_change_file = output_path / "fault_db_change.log"
    with open(db_change_file, "w", encoding="utf-8") as f:
        for log in db_change_logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
    files["fault_db_change"] = str(db_change_file)
    print(f"[4/5] DB变更故障日志: {db_change_file} ({len(db_change_logs)} 条)")
    
    # 5. 混合日志（正常 + 故障）
    mixed_logs = (
        generate_normal_logs(base_time, count=100, trace_ratio=0.5)
        + generate_trace_chain_logs(base_time, chain_count=15)
        + generate_fault_logs(base_time + timedelta(hours=1), "redis_failover")
        + generate_fault_logs(base_time + timedelta(hours=3), "kafka_lag")
    )
    random.shuffle(mixed_logs)
    mixed_logs.sort(key=lambda x: x["timestamp"])
    mixed_file = output_path / "mixed_all.log"
    with open(mixed_file, "w", encoding="utf-8") as f:
        for log in mixed_logs:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
    files["mixed_all"] = str(mixed_file)
    print(f"[5/5] 混合日志: {mixed_file} ({len(mixed_logs)} 条)")
    
    # 保存故障场景元数据
    meta_file = output_path / "fault_scenarios.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            name: {
                "description": sc["description"],
                "root_service": sc["root_service"],
                "affected_services": sc["affected_services"],
            }
            for name, sc in FAULT_SCENARIOS.items()
        }, f, ensure_ascii=False, indent=2)
    files["fault_scenarios"] = str(meta_file)
    
    print(f"\n所有日志文件已生成到: {output_path}")
    return files


if __name__ == "__main__":
    generate_all_logs()
