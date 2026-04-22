#!/bin/bash

set -e

echo "=== Deploying order-service on k8s-master (10.0.1.232) ==="

ssh jaci@8.136.143.226 << 'EOF'
echo "=== Loading Docker image ==="
cd /home/jaci
sudo docker load < order-service.tar.gz

echo "=== Stopping existing container if exists ==="
sudo docker stop order-service 2>/dev/null || true
sudo docker rm order-service 2>/dev/null || true

echo "=== Starting order-service container ==="
sudo docker run -d \
  --name order-service \
  --restart unless-stopped \
  -p 8000:8000 \
  -e OTEL_SERVICE_NAME=order-service \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://10.0.1.224:4317 \
  -e DOWNSTREAM_URL=http://10.0.1.233:8000 \
  order-service:latest

echo "=== Waiting for service to start ==="
sleep 5

echo "=== Checking container status ==="
sudo docker ps | grep order-service

echo "=== Testing order-service ==="
curl -s http://localhost:8000/health

echo ""
echo "=== order-service deployed successfully ==="
echo "URL: http://10.0.1.232:8000"
EOF

echo "=== Deployment completed ==="
