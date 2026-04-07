#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', '.env'))

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

class ServerInfoToNeo4j:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def create_server_node(self, server_info):
        with self.driver.session() as session:
            result = session.execute_write(self._create_server, server_info)
            return result
    
    @staticmethod
    def _create_server(tx, server_info):
        query = """
        MERGE (s:Server:Infra {ip: $ip})
        SET s.name = $name,
            s.hostname = $hostname,
            s.cpu_cores = $cpu_cores,
            s.memory_total = $memory_total,
            s.memory_used = $memory_used,
            s.memory_available = $memory_available,
            s.disk_total = $disk_total,
            s.disk_used = $disk_used,
            s.disk_available = $disk_available,
            s.disk_usage_percent = $disk_usage_percent,
            s.load_avg_1m = $load_avg_1m,
            s.load_avg_5m = $load_avg_5m,
            s.load_avg_15m = $load_avg_15m,
            s.uptime = $uptime,
            s.status = $status,
            s.provider = $provider,
            s.owner = $owner,
            s.owner_email = $owner_email,
            s.updated_at = datetime()
        RETURN s
        """
        result = tx.run(query, **server_info)
        return result.single()
    
    def create_disk_node(self, server_ip, disk_info):
        with self.driver.session() as session:
            result = session.execute_write(self._create_disk, server_ip, disk_info)
            return result
    
    @staticmethod
    def _create_disk(tx, server_ip, disk_info):
        query = """
        MATCH (s:Server {ip: $server_ip})
        MERGE (d:Storage:Infra {name: $name})
        SET d.type = 'Local Disk',
            d.size = $size,
            d.used = $used,
            d.available = $available,
            d.usage_percent = $usage_percent,
            d.mount_point = $mount_point
        MERGE (s)-[:HAS_STORAGE]->(d)
        RETURN d
        """
        result = tx.run(query, server_ip=server_ip, **disk_info)
        return result.single()

def main():
    print("=" * 60)
    print("将服务器信息存储到Neo4j知识图谱")
    print("=" * 60)
    
    server_info = {
        "ip": "8.136.226.231",
        "name": "aliyun-test-server-01",
        "hostname": "test_server",
        "cpu_cores": 2,
        "memory_total": "3.7G",
        "memory_used": "226M",
        "memory_available": "3.3G",
        "disk_total": "20G",
        "disk_used": "4.0G",
        "disk_available": "15G",
        "disk_usage_percent": 22,
        "load_avg_1m": 0.00,
        "load_avg_5m": 0.01,
        "load_avg_15m": 0.03,
        "uptime": "21 min",
        "status": "running",
        "provider": "Aliyun",
        "owner": "jaci",
        "owner_email": "jaci@example.com"
    }
    
    disk_info = {
        "name": "aliyun-test-server-01-disk",
        "size": "20G",
        "used": "4.0G",
        "available": "15G",
        "usage_percent": 22,
        "mount_point": "/"
    }
    
    print(f"\n服务器信息:")
    print(f"  IP: {server_info['ip']}")
    print(f"  名称: {server_info['name']}")
    print(f"  CPU: {server_info['cpu_cores']} 核")
    print(f"  内存: {server_info['memory_total']} (已用: {server_info['memory_used']})")
    print(f"  磁盘: {server_info['disk_total']} (已用: {server_info['disk_usage_percent']}%)")
    print(f"  状态: {server_info['status']}")
    
    try:
        loader = ServerInfoToNeo4j(
            uri=NEO4J_URI,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD
        )
        
        print(f"\n正在连接Neo4j: {NEO4J_URI}")
        
        result = loader.create_server_node(server_info)
        if result:
            print(f"✅ 服务器节点创建成功: {server_info['name']}")
        
        disk_result = loader.create_disk_node(server_info['ip'], disk_info)
        if disk_result:
            print(f"✅ 磁盘节点创建成功: {disk_info['name']}")
        
        loader.close()
        
        print("\n" + "=" * 60)
        print("✅ 服务器信息已成功存储到Neo4j知识图谱")
        print("=" * 60)
        
        print("\n查询示例:")
        print("  MATCH (s:Server {ip: '8.136.226.231'}) RETURN s")
        print("  MATCH (s:Server)-[:HAS_STORAGE]->(d:Storage) RETURN s, d")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
