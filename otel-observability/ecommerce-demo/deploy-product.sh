#!/bin/bash

set -e

echo "=== Deploying product-service on k8s-worker (10.0.1.233) ==="

ssh jaci@8.136.137.145 << 'EOF'
echo "=== Loading Docker image ==="
cd /home/jaci
sudo docker load < product-service.tar.gz

echo "=== Stopping existing container if exists ==="
sudo docker stop product-service 2>/dev/null || true
sudo docker rm product-service 2>/dev/null || true

echo "=== Starting product-service container ==="
sudo docker run -d \
  --name product-service \
  --restart unless-stopped \
  -p 8000:8000 \
  -e OTEL_SERVICE_NAME=product-service \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://10.0.1.224:4317 \
  -e DOWNSTREAM_URL= \
  product-service:latest

echo "=== Waiting for service to start ==="
sleep 5

echo "=== Checking container status ==="
sudo docker ps | grep product-service

echo "=== Testing product-service ==="
curl -s http://localhost:8000/health

echo ""
echo "=== product-service deployed successfully ==="
echo "URL: http://10.0.1.233:8000"
EOF

echo "=== Deployment completed ==="
