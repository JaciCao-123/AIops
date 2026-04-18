#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 1: 原始日志流生成器

功能：
1. 模拟真实运维日志（应用/系统/中间件/数据库）
2. 支持多种日志格式
3. 注入异常模式（错误/警告/超时）
4. 生成时间序列数据
"""

import os
import re
import random
import sys
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_GENERATOR_CONFIG, DATA_DIRS


class LogGenerator:
    """运维日志生成器"""
    
    def __init__(self, config: Dict = None):
        self.config = config or LOG_GENERATOR_CONFIG
        self.templates = self._load_log_templates()
        
    def _load_log_templates(self) -> Dict[str, List[str]]:
        """加载日志模板库"""
        return {
            "application": [
                "[{timestamp}] {level} {service} - Connection to {host}:{port} timed out after {duration}",
                "[{timestamp}] {level} {service} - Request {request_id} failed with status {status_code}: {error_msg}",
                "[{timestamp}] {level} {service} - User {user_id} login failed from IP {ip_address}",
                "[{timestamp}] {level} {service} - Database query took {duration}, exceeding threshold of 1000ms",
                "[{timestamp}] {level} {service} - Memory usage at {percent}%, approaching critical threshold",
                "[{timestamp}] INFO {service} - Processed {count} requests in last minute",
                "[{timestamp}] INFO {service} - Health check passed for all dependencies",
                "[{timestamp}] DEBUG {service} - Cache hit ratio: {ratio}% for endpoint /api/{endpoint}",
                "[{timestamp}] WARN {service} - High latency detected on endpoint /api/{endpoint}: {duration}ms",
                "[{timestamp}] ERROR {service} - NullPointerException in {class_name}.{method_name} at line {line_number}"
            ],
            "system": [
                "[{timestamp}] {level} kernel - CPU usage spike detected: {cpu_percent}% on core {core_id}",
                "[{timestamp}] {level} systemd - Service {service_name} entered failed state",
                "[{timestamp}] {level} disk - Partition {partition} usage at {disk_percent}%, warning threshold reached",
                "[{timestamp}] WARN memory - Available memory dropped below {memory_mb}MB",
                "[{timestamp}] ERROR network - Interface {interface} lost connection to gateway {gateway_ip}",
                "[{timestamp}] INFO sshd - Accepted publickey for {username} from {ip_address} port {port}",
                "[{timestamp}] DEBUG cron - Job {job_name} completed successfully",
                "[{timestamp}] WARN systemd - Process {process_name} (PID {pid}) using excessive CPU",
                "[{timestamp}] ERROR kernel - Out of memory: Kill process {process_name} (PID {pid}) score {score}",
                "[{timestamp}] INFO udev - Added device {device_path}"
            ],
            "middleware": [
                "[{timestamp}] {level} nginx - Upstream response time too slow: {duration}s for request to {upstream}",
                "[{timestamp}] {level} redis - Connection pool exhausted, waiting for available connection",
                "[{timestamp}] WARN kafka - Consumer lag increasing: {lag_count} messages behind for topic {topic_name}",
                "[{timestamp}] ERROR elasticsearch - Cluster health status changed from green to {health_status}",
                "[{timestamp}] INFO nginx - Access log: {ip_address} - [{time}] \"{method} {url}\" {status_code} {response_size}",
                "[{timestamp}] DEBUG kafka - Message produced to topic {topic_name} with key {message_key}",
                "[{timestamp}] WARN redis - High memory usage: {memory_usage}MB used out of {max_memory}MB total",
                "[{timestamp}] ERROR nginx - SSL handshake failed for client {ip_address}: {ssl_error}",
                "[{timestamp}] INFO elasticsearch - Index {index_name} refreshed successfully",
                "[{timestamp}] WARN kafka - Partition rebalancing triggered for consumer group {group_id}"
            ],
            "database": [
                "[{timestamp}] {level} mysql - Slow query detected: Query took {duration}s on table {table_name}",
                "[{timestamp}] ERROR mysql - Too many connections: Current {current_connections}/{max_connections}",
                "[{timestamp}] WARN mysql - Replication lag detected: Slave is {lag_seconds} seconds behind master",
                "[{timestamp}] INFO mysql - Backup completed successfully: {backup_size}GB in {duration}",
                "[{timestamp}] DEBUG mysql - Query cache hit rate: {cache_hit_rate}%",
                "[{timestamp}] ERROR mysql - Deadlock detected involving transaction IDs {tx_ids}",
                "[{timestamp}] WARN mysql - Table {table_name} size exceeded {size_threshold}MB",
                "[{timestamp}] INFO mysql - Binary log rotated: {log_file}",
                "[{timestamp}] DEBUG mysql - InnoDB buffer pool usage: {buffer_usage}%",
                "[{timestamp}] ERROR mysql - Disk I/O bottleneck: {io_wait_percent}% iowait time"
            ]
        }
    
    def generate_logs(self) -> pd.DataFrame:
        """生成完整的日志数据集"""
        print("\n" + "=" * 60)
        print("📦 Step 1: 原始日志流生成")
        print("=" * 60)
        
        num_logs = self.config["num_logs"]
        time_range_hours = self.config["time_range_hours"]
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_range_hours)
        
        logs = []
        
        anomaly_patterns = self.config["anomaly_patterns"]
        anomaly_injection_rate = self.config["anomaly_injection_rate"]
        
        for i in range(num_logs):
            timestamp = start_time + timedelta(
                hours=random.uniform(0, time_range_hours),
                seconds=random.uniform(0, 60),
                microseconds=random.randint(0, 999999)
            )
            
            source = self._select_weighted_random(self.config["log_sources"])
            templates = self.templates[source]
            
            template = random.choice(templates)
            
            level_config = self.config["log_levels"]
            level = self._select_weighted_random(level_config)
            
            if random.random() < anomaly_injection_rate and level in ["ERROR", "WARN"]:
                template = self._inject_anomaly(template, random.choice(anomaly_patterns))
            
            log_entry = self._fill_template(template, level, source, timestamp)
            
            logs.append({
                "timestamp": timestamp,
                "raw_message": log_entry,
                "source": source,
                "level": level,
                "service": self._get_service_for_source(source),
                "is_anomaly": 1 if random.random() < anomaly_injection_rate else 0
            })
        
        df = pd.DataFrame(logs)
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        output_file = self.config["output_file"]
        df.to_csv(output_file, index=False)
        
        print(f"\n✅ 日志生成完成:")
        print(f"   总日志数: {len(df):,}")
        print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
        print(f"   日志来源分布:")
        for source, count in df['source'].value_counts().items():
            print(f"      • {source}: {count:,} ({count/len(df)*100:.1f}%)")
        print(f"   日志级别分布:")
        for level, count in df['level'].value_counts().items():
            print(f"      • {level}: {count:,} ({count/len(df)*100:.1f}%)")
        print(f"   异常日志数: {df['is_anomaly'].sum():,} ({df['is_anomaly'].mean()*100:.1f}%)")
        print(f"\n💾 数据已保存至: {output_file}")
        
        return df
    
    def _select_weighted_random(self, weighted_dict: Dict) -> str:
        """按权重随机选择"""
        items = list(weighted_dict.keys())
        weights = [item.get("weight", 1.0) if isinstance(item, dict) else item 
                  for item in weighted_dict.values()]
        return random.choices(items, weights=weights, k=1)[0]
    
    def _fill_template(self, template: str, level: str, source: str, timestamp: datetime) -> str:
        """填充模板变量"""
        services = self.config["services"]
        
        replacements = {
            "{timestamp}": timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "{level}": level,
            "{service}": random.choice(services),
            "{host}": f"192.168.{random.randint(1,255)}.{random.randint(1,254)}",
            "{port}": str(random.choice([8080, 8081, 8082, 3306, 6379, 9200, 5432])),
            "{duration}": f"{random.uniform(0.001, 10):.3f}s",
            "{request_id}": ''.join(random.choices('abcdef0123456789', k=16)),
            "{status_code}": str(random.choice([200, 201, 400, 401, 403, 404, 500, 502, 503])),
            "{error_msg}": random.choice([
                "Connection refused", "Timeout", "Internal Server Error", 
                "Bad Gateway", "Service Unavailable"
            ]),
            "{user_id}": f"user_{random.randint(10000,99999)}",
            "{ip_address}": f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            "{percent}": f"{random.uniform(60,99):.1f}",
            "{count}": str(random.randint(100, 10000)),
            "{ratio}": f"{random.uniform(70,99):.1f}",
            "{endpoint}": random.choice(["users", "orders", "products", "payments", "inventory"]),
            "{class_name}": random.choice(["OrderService", "UserService", "PaymentHandler"]),
            "{method_name}": random.choice(["processOrder", "validateUser", "handlePayment"]),
            "{line_number}": str(random.randint(100, 2000)),
            "{cpu_percent}": f"{random.uniform(70,100):.1f}",
            "{core_id}": str(random.randint(0, 7)),
            "{service_name}": random.choice(["nginx", "mysql", "redis", "kafka"]),
            "{partition}": random.choice(["/dev/sda1", "/dev/sdb1", "/home"]),
            "{disk_percent}": f"{random.uniform(75,98):.1f}",
            "{memory_mb}": str(random.randint(100, 1000)),
            "{interface}": random.choice(["eth0", "eth1", "ens192"]),
            "{gateway_ip}": f"192.168.{random.randint(1,255)}.1",
            "{username}": random.choice(["root", "admin", "deploy", "app_user"]),
            "{port_ssh}": str(random.randint(1024, 65535)),
            "{job_name}": random.choice(["backup", "cleanup", "report", "sync"]),
            "{process_name}": random.choice(["java", "python", "nginx", "mysql"]),
            "{pid}": str(random.randint(1000, 50000)),
            "{score}": f"{random.uniform(800,1200):.0f}",
            "{device_path}": f"/dev/sd{chr(ord('a') + random.randint(0,5))}",
            "{upstream}": random.choice(["backend-server-1", "backend-server-2", "api-service"]),
            "{topic_name}": random.choice(["orders", "users", "notifications", "events"]),
            "{health_status}": random.choice(["yellow", "red"]),
            "{method}": random.choice(["GET", "POST", "PUT", "DELETE"]),
            "{url}": random.choice(["/api/users", "/api/orders", "/api/products", "/health"]),
            "{response_size}": f"{random.randint(100, 50000)}",
            "{message_key}": f"key-{random.randint(1000,9999)}",
            "{memory_usage}": f"{random.uniform(512,2048):.0f}",
            "{max_memory}": str(random.choice([2048, 4096, 8192])),
            "{ssl_error}": random.choice(["certificate_unknown", "bad_certificate", "certificate_expired"]),
            "{index_name}": random.choice(["logs-2024", "metrics-2024", "events-2024"]),
            "{group_id}": random.choice(["consumer-group-1", "consumer-group-2"]),
            "{table_name}": random.choice(["orders", "users", "products", "transactions"]),
            "{current_connections}": str(random.randint(150, 300)),
            "{max_connections}": str(random.choice([200, 250, 300])),
            "{lag_seconds}": f"{random.uniform(5, 60):.1f}",
            "{backup_size}": f"{random.uniform(1, 20):.1f}",
            "{cache_hit_rate}": f"{random.uniform(85,99):.1f}",
            "{tx_ids}": ','.join([str(random.randint(1000,9999)) for _ in range(random.randint(2,5))]),
            "{size_threshold}": str(random.choice([1024, 2048, 4096])),
            "{log_file}": f"mysql-bin.{random.randint(1,999):04d}",
            "{buffer_usage}": f"{random.uniform(70,95):.1f}",
            "{io_wait_percent}": f"{random.uniform(30,80):.1f}",
            "{time}": timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000)")
        }
        
        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        
        return result
    
    def _inject_anomaly(self, template: str, pattern: str) -> str:
        """注入异常模式"""
        anomaly_templates = {
            "connection_timeout": [
                "[{timestamp}] ERROR {service} - Connection timeout after 30s to database host",
                "[{timestamp}] CRITICAL {service} - Unable to establish connection to upstream server"
            ],
            "high_cpu_usage": [
                "[{timestamp}] ALERT {service} - CPU usage at 99.9%, throttling enabled",
                "[{timestamp}] CRITICAL system - CPU thermal shutdown imminent on core 0"
            ],
            "memory_leak": [
                "[{timestamp}] ERROR java.lang.OutOfMemoryError: Java heap space in {service}",
                "[{timestamp}] WARN {service} - Memory leak detected: Heap growing continuously"
            ],
            "disk_space_full": [
                "[{timestamp}] CRITICAL system - No space left on device /dev/sda1 (100% used)",
                "[{timestamp}] ERROR {service} - Write failed: No space left on device"
            ],
            "database_connection_exhausted": [
                "[{timestamp}] ERROR mysql - Too many connections: 500/500 active connections",
                "[{timestamp}] CRITICAL {service} - Connection pool exhausted, rejecting new requests"
            ],
            "service_unavailable": [
                "[{timestamp}] CRITICAL {service} - Service health check FAILED: All endpoints down",
                "[{timestamp}] ERROR load_balancer - No healthy upstream servers available"
            ],
            "authentication_failure": [
                "[{timestamp}] SECURITY WARNING - Brute force attack detected from IP {ip_address}",
                "[{timestamp}] ERROR auth - Invalid credentials attempt #{attempt_num} for user admin"
            ],
            "ssl_certificate_error": [
                "[{timestamp}] SECURITY CRITICAL - SSL certificate EXPIRED for domain {domain}",
                "[{timestamp}] ERROR nginx - TLS handshake failed: certificate verify error"
            ]
        }
        
        if pattern in anomaly_templates:
            return random.choice(anomaly_templates[pattern])
        
        return template
    
    def _get_service_for_source(self, source: str) -> str:
        """根据日志源获取服务名"""
        service_mapping = {
            "application": random.choice(self.config["services"][:6]),
            "system": "server-host",
            "middleware": random.choice(self.config["services"][6:]),
            "database": random.choice(["mysql-master", "mysql-slave"])
        }
        return service_mapping.get(source, "unknown")


def main():
    """主函数"""
    generator = LogGenerator()
    df = generator.generate_logs()
    
    print("\n\n📊 样本日志预览:")
    print("-" * 80)
    for _, row in df.head(10).iterrows():
        print(row['raw_message'][:100] + "..." if len(str(row['raw_message'])) > 100 else row['raw_message'])
    
    return df


if __name__ == "__main__":
    main()
