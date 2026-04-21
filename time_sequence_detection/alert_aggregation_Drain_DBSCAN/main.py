#!/usr/bin/env python3
"""
AlertClusterSkill Mock 演示
完整演示离线训练和在线聚合的闭环流程
"""
import asyncio
import json
import logging
from pathlib import Path

from config import DEFAULT_W2V_MODEL_PATH, Word2VecConfig
from models import AlertInput
from skill import AlertClusterSkill

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MOCK_TRAINING_LOGS = [
    "2023-01-01 ERROR [Thread-01] Connection to redis-master-01 timeout after 5000ms",
    "2023-01-02 WARN OutOfMemoryError occurred in Pod order-service-xyz",
    "2023-01-03 ERROR Connection to mysql-master failed: timeout exceeded",
    "2023-01-04 ERROR Redis connection timeout to 10.0.0.1:6379",
    "2023-01-05 WARN High CPU usage detected on node-worker-01 at 95%",
    "2023-01-06 ERROR NullPointerException in PaymentService.processOrder",
    "2023-01-07 ERROR Database connection pool exhausted in UserService",
    "2023-01-08 WARN Memory usage critical: 98% on cache-server-01",
    "2023-01-09 ERROR Kafka consumer lag exceeded threshold 10000 messages",
    "2023-01-10 ERROR API Gateway timeout for service inventory-api",
    "2023-01-11 WARN Disk usage warning: 85% on storage-node-01",
    "2023-01-12 ERROR SSL certificate expired for api.example.com",
    "2023-01-13 ERROR Connection refused to Elasticsearch cluster",
    "2023-01-14 WARN Thread pool exhausted in AsyncProcessor",
    "2023-01-15 ERROR RabbitMQ queue backup-alerts is full",
    "2023-01-16 ERROR Timeout waiting for response from payment-gateway",
    "2023-01-17 WARN Slow query detected: SELECT * FROM orders took 15s",
    "2023-01-18 ERROR Nginx upstream timeout for backend-service",
    "2023-01-19 ERROR MongoDB replica set primary election failed",
    "2023-01-20 WARN GC pause time exceeded 500ms in JVM",
    "2023-01-21 ERROR gRPC connection reset by peer: order-service",
    "2023-01-22 ERROR Consul service discovery failed for product-api",
    "2023-01-23 WARN Connection pool leak detected in DataSource",
    "2023-01-24 ERROR Zookeeper session expired for kafka-broker-01",
    "2023-01-25 ERROR Vault seal status check failed",
    "2023-01-26 WARN Prometheus scrape timeout for node-exporter",
    "2023-01-27 ERROR Jenkins build failed: OutOfMemoryError",
    "2023-01-28 ERROR Docker container oom-killed: frontend-app",
    "2023-01-29 WARN Kubernetes pod restart loop detected",
    "2023-01-30 ERROR Service mesh proxy timeout to downstream",
    "2023-01-31 ERROR Redis cluster slot migration failed",
    "2023-02-01 WARN MySQL replication lag exceeded 60s",
    "2023-02-02 ERROR PostgreSQL deadlock detected in transaction",
    "2023-02-03 ERROR Cassandra write timeout for keyspace analytics",
    "2023-02-04 WARN Etcd leader election in progress",
    "2023-02-05 ERROR HAProxy backend health check failed",
    "2023-02-06 ERROR Varnish cache purge failed",
    "2023-02-07 WARN Elasticsearch index refresh rate slow",
    "2023-02-08 ERROR Fluentd buffer overflow on log-forwarder",
    "2023-02-09 ERROR Grafana dashboard query timeout",
    "2023-02-10 WARN Jaeger trace storage nearly full",
    "2023-02-11 ERROR Istio sidecar injection failed",
    "2023-02-12 ERROR Helm release upgrade timeout",
    "2023-02-13 WARN Terraform state lock detected",
    "2023-02-14 ERROR Ansible playbook execution failed",
    "2023-02-15 ERROR Packer build image failed",
    "2023-02-16 WARN CircleCI job queued too long",
    "2023-02-17 ERROR GitHub Actions runner offline",
    "2023-02-18 ERROR SonarQube analysis timeout",
    "2023-02-19 WARN Nexus storage cleanup needed",
]

MOCK_ALERTS = [
    {"time": "2023-10-01 10:00:01", "node_id": "node-1", "raw_msg": "Connection to Redis 10.0.0.1 timeout"},
    {"time": "2023-10-01 10:00:03", "node_id": "node-1", "raw_msg": "Cache fetch failed from pool"},
    {"time": "2023-10-01 10:00:05", "node_id": "node-2", "raw_msg": "Connection to MySQL master timeout"},
    {"time": "2023-10-01 10:00:07", "node_id": "node-2", "raw_msg": "Database query failed after 5000ms"},
    {"time": "2023-10-01 10:00:10", "node_id": "node-3", "raw_msg": "OutOfMemoryError in Java process"},
    {"time": "2023-10-01 10:00:12", "node_id": "node-3", "raw_msg": "Memory allocation failed for container"},
    {"time": "2023-10-01 10:00:15", "node_id": "node-1", "raw_msg": "High CPU usage detected at 98%"},
    {"time": "2023-10-01 10:00:17", "node_id": "node-4", "raw_msg": "Kafka consumer lag exceeded 15000"},
    {"time": "2023-10-01 10:00:20", "node_id": "node-4", "raw_msg": "Message queue backup detected"},
    {"time": "2023-10-01 10:00:22", "node_id": "node-5", "raw_msg": "SSL certificate validation failed"},
]


async def demo_offline_training(skill: AlertClusterSkill) -> bool:
    """
    演示离线训练阶段
    """
    logger.info("=" * 60)
    logger.info("阶段1: 离线训练 Word2Vec 模型")
    logger.info("=" * 60)
    
    logger.info(f"使用 {len(MOCK_TRAINING_LOGS)} 条模拟日志进行训练...")
    
    success = await skill.train_from_texts(
        texts=MOCK_TRAINING_LOGS,
        output_model_path=str(DEFAULT_W2V_MODEL_PATH),
        vector_size=Word2VecConfig.vector_size,
        window=Word2VecConfig.window,
        min_count=1,
        workers=Word2VecConfig.workers,
        epochs=Word2VecConfig.epochs,
    )
    
    if success:
        logger.info(f"✅ 模型训练成功，已保存到: {DEFAULT_W2V_MODEL_PATH}")
    else:
        logger.error("❌ 模型训练失败")
    
    return success


async def demo_online_clustering(skill: AlertClusterSkill) -> None:
    """
    演示在线聚合阶段
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("阶段2: 在线告警聚合")
    logger.info("=" * 60)
    
    logger.info(f"输入 {len(MOCK_ALERTS)} 条告警...")
    for i, alert in enumerate(MOCK_ALERTS, 1):
        logger.info(f"  [{i}] {alert['node_id']}: {alert['raw_msg'][:50]}...")
    
    result = await skill.execute(MOCK_ALERTS)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("聚合结果")
    logger.info("=" * 60)
    
    result_dict = result.model_dump()
    logger.info(json.dumps(result_dict, indent=2, ensure_ascii=False))
    
    logger.info("")
    logger.info(f"📊 统计摘要:")
    logger.info(f"  - 输入告警总数: {result.total_input}")
    logger.info(f"  - 聚类数量: {len(result.clusters)}")
    logger.info(f"  - 噪声告警: {result.noise_count}")
    logger.info(f"  - 压缩率: {result.total_input / max(len(result.clusters), 1):.1f}:1")
    
    logger.info("")
    logger.info("📋 各聚类详情:")
    for cluster in result.clusters:
        logger.info(f"  聚类 {cluster.cluster_id}:")
        logger.info(f"    - 告警数: {cluster.alert_count}")
        logger.info(f"    - 代表告警: {cluster.representative_alert[:60]}...")
        logger.info(f"    - 影响节点: {', '.join(cluster.affected_nodes)}")


async def main() -> None:
    """
    主函数：完整演示闭环流程
    """
    logger.info("🚀 AlertClusterSkill 完整演示")
    logger.info("=" * 60)
    
    skill = AlertClusterSkill(
        w2v_model_path=str(DEFAULT_W2V_MODEL_PATH),
        auto_load=False,
        eps=0.8,
        min_samples=1,
        w_time=0.01,
        w_sem=1.0,
        w_topo=0.1,
    )
    
    success = await demo_offline_training(skill)
    
    if not success:
        logger.error("训练失败，退出演示")
        return
    
    await demo_online_clustering(skill)
    
    logger.info("")
    logger.info("✅ 演示完成！")


if __name__ == "__main__":
    asyncio.run(main())
