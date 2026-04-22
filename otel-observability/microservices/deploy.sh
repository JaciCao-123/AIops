#!/bin/bash

set -e

DEPLOY_HOST="8.136.143.226"
DEPLOY_USER="jaci"
REMOTE_DIR="/home/jaci/otel-observability/microservices"

echo "=== Uploading microservices files ==="

ssh ${DEPLOY_USER}@${DEPLOY_HOST} "mkdir -p ${REMOTE_DIR}"

scp app.py ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_DIR}/
scp requirements.txt ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_DIR}/
scp Dockerfile ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_DIR}/
scp docker-compose.yml ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_DIR}/

echo "=== Files uploaded successfully ==="

echo "=== Building and starting microservices ==="

ssh ${DEPLOY_USER}@${DEPLOY_HOST} << 'EOF'
cd /home/jaci/otel-observability/microservices

echo "=== Building Docker images ==="
sudo docker compose build

echo "=== Starting services ==="
sudo docker compose up -d

echo "=== Waiting for services to start ==="
sleep 5

echo "=== Checking service status ==="
sudo docker compose ps

echo "=== Testing frontend ==="
curl -s http://localhost:5000/ | head -20

echo ""
echo "=== Microservices deployed ==="
echo "Frontend: http://8.136.143.226:5000"
echo "Backend: http://8.136.143.226:5001"
echo "Database: http://8.136.143.226:5002"
EOF

echo "=== Deployment completed ==="
