#!/bin/bash

set -e

echo "=========================================="
echo "  E-commerce Demo Deployment Script"
echo "=========================================="
echo ""

echo "=== Step 1: Building Docker images ==="
cd /Users/jaci-j/resource_provision/otel-observability/ecommerce-demo

docker build -t order-service:latest -f Dockerfile.order .
docker build -t product-service:latest -f Dockerfile.product .

echo ""
echo "=== Step 2: Saving Docker images ==="
docker save order-service:latest | gzip > order-service.tar.gz
docker save product-service:latest | gzip > product-service.tar.gz

echo ""
echo "=== Step 3: Uploading images to servers ==="
echo "Uploading product-service to k8s-worker..."
scp product-service.tar.gz jaci@8.136.137.145:/home/jaci/

echo "Uploading order-service to k8s-master..."
scp order-service.tar.gz jaci@8.136.143.226:/home/jaci/

echo ""
echo "=== Step 4: Deploying product-service on k8s-worker ==="
ssh -tt jaci@8.136.137.145 << 'EOF'
cd /home/jaci
echo jaci1234 | sudo -S docker load < product-service.tar.gz
echo jaci1234 | sudo -S docker stop product-service 2>/dev/null || true
echo jaci1234 | sudo -S docker rm product-service 2>/dev/null || true
echo jaci1234 | sudo -S docker run -d \
  --name product-service \
  --restart unless-stopped \
  -p 8000:8000 \
  -e OTEL_SERVICE_NAME=product-service \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://10.0.1.224:4317 \
  -e DOWNSTREAM_URL= \
  product-service:latest
sleep 3
exit
EOF

echo ""
echo "=== Step 5: Deploying order-service on k8s-master ==="
ssh -tt jaci@8.136.143.226 << 'EOF'
cd /home/jaci
echo jaci1234 | sudo -S docker load < order-service.tar.gz
echo jaci1234 | sudo -S docker stop order-service 2>/dev/null || true
echo jaci1234 | sudo -S docker rm order-service 2>/dev/null || true
echo jaci1234 | sudo -S docker run -d \
  --name order-service \
  --restart unless-stopped \
  -p 8000:8000 \
  -e OTEL_SERVICE_NAME=order-service \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://10.0.1.224:4317 \
  -e DOWNSTREAM_URL=http://10.0.1.233:8000 \
  order-service:latest
sleep 3
exit
EOF

echo ""
echo "=== Step 6: Verifying deployments ==="
echo "Checking product-service..."
ssh jaci@8.136.137.145 'curl -s http://localhost:8000/health && echo ""'

echo "Checking order-service..."
ssh jaci@8.136.143.226 'curl -s http://localhost:8000/health && echo ""'

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  - product-service: http://10.0.1.233:8000 (k8s-worker)"
echo "  - order-service:   http://10.0.1.232:8000 (k8s-master)"
echo ""
echo "Test commands:"
echo "  curl http://8.136.137.145:8000/api/product"
echo "  curl http://8.136.143.226:8000/api/order"
echo ""
echo "Grafana: http://10.0.1.224:3000"
echo "=========================================="
