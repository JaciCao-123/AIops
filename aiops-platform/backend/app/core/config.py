import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "AIOps Platform"
    DEBUG: bool = True
    
    SECRET_KEY: str = "aiops-secret-key-change-in-production-please"
    
    DATABASE_URL: str = "sqlite:///./data/aiops.db"
    
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    RAG_SERVICE_URL: str = "http://localhost:8001"
    
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    OPENAI_MODEL: str = "qwen-plus"
    
    ALIYUN_ACCESS_KEY_ID: str = ""
    ALIYUN_ACCESS_KEY_SECRET: str = ""
    ALIYUN_REGION_ID: str = "cn-hangzhou"
    
    SMTP_HOST: str = "smtp.163.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    
    OPS_RAG_PATH: str = str(Path.home() / "ops_rag")
    KNOWLEDGE_GRAPH_PATH: str = str(Path(__file__).parent.parent.parent.parent.parent / "knowledge_graph")
    
    CMDB_SERVICE_LIST: list = [
        "order-service",
        "payment-service", 
        "user-service",
        "inventory-service",
        "notification-service",
        "api-gateway",
        "redis-cluster",
        "mysql-master",
        "mysql-slave",
        "kafka-cluster",
        "elasticsearch-cluster"
    ]
    
    DATA_SOURCES: dict = {
        "local": {
            "type": "filesystem",
            "base_path": str(Path.home() / "AIops" / "GNN"),
            "description": "本地文件系统数据源"
        },
        "prometheus": {
            "type": "monitoring",
            "url": "http://localhost:9090",
            "description": "Prometheus 监控系统"
        },
        "elasticsearch": {
            "type": "logging",
            "url": "http://localhost:9200",
            "index_pattern": "logstash-*",
            "description": "Elasticsearch 日志平台"
        },
        "loki": {
            "type": "logging",
            "url": "http://localhost:3100",
            "description": "Grafana Loki 日志系统"
        },
        "aliyun_monitor": {
            "type": "cloud_monitoring",
            "enabled": True,
            "description": "阿里云云监控"
        },
        "jaeger": {
            "type": "tracing",
            "url": "http://localhost:16686",
            "description": "Jaeger 链路追踪"
        }
    }
    
    DEFAULT_DATA_SOURCE: str = "local"
    
    DANGEROUS_COMMANDS: list = [
        "rm -rf",
        "dd if=",
        "mkfs",
        "fdisk",
        "shutdown",
        "reboot",
        "init 0",
        "init 6",
        ":(){ :|:& };:",
        "chown -R",
        "> /dev/sda",
        "systemctl stop",
        "systemctl disable",
        "service.*stop",
        "kill -9 -1",
        "pkill -9",
        "drop database",
        "truncate table",
        "delete from"
    ]
    
    SAFE_COMMANDS: list = [
        "ls", "cat", "head", "tail", "grep", "awk", "sed", "cut",
        "df", "du", "free", "top", "htop", "ps", "uptime",
        "netstat", "ss", "lsof", "iostat", "vmstat", "sar",
        "ping", "traceroute", "nslookup", "dig", "curl", "wget --spider",
        "journalctl", "dmesg", "last", "w", "who",
        "systemctl status", "service.*status",
        "docker ps", "docker logs", "docker inspect", "docker stats",
        "kubectl get", "kubectl describe", "kubectl logs"
    ]
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
