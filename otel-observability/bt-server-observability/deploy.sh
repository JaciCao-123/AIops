#!/bin/bash

set -e

DEPLOY_HOST="8.136.141.237"
DEPLOY_USER="jaci"
REMOTE_DIR="/home/jaci/observability"

echo "=== Uploading configuration files to bt-server-1 ==="

ssh ${DEPLOY_USER}@${DEPLOY_HOST} "mkdir -p ${REMOTE_DIR}"

scp otel-collector-config.yaml ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_DIR}/
scp docker-compose.yml ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_DIR}/

echo "=== Files uploaded successfully ==="

echo "=== Installing Docker on bt-server-1 ==="

ssh ${DEPLOY_USER}@${DEPLOY_HOST} << 'EOF'
if ! command -v docker &> /dev/null; then
    echo "=== Installing Docker ==="
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker jaci
    echo "=== Docker installed ==="
fi

echo "=== Docker version ==="
docker --version

echo "=== Starting services on bt-server-1 ==="
cd /home/jaci/observability

echo "=== Pulling Docker images ==="
sudo docker compose pull || sudo docker-compose pull

echo "=== Starting services ==="
sudo docker compose up -d || sudo docker-compose up -d

echo "=== Waiting for services to start ==="
sleep 10

echo "=== Checking service status ==="
sudo docker compose ps || sudo docker-compose ps

echo "=== Checking OTel Collector logs ==="
sudo docker logs otel-collector 2>&1 | tail -20

echo "=== Checking Grafana health ==="
curl -s http://localhost:3000/api/health

echo ""
echo "=== Services deployed ==="
echo "OTel Collector: http://10.0.1.224:4317 (gRPC)"
echo "Grafana: http://10.0.1.224:3000"
EOF

echo "=== Deployment completed ==="
