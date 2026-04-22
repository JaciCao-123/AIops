#!/bin/bash

set -e

echo "=== Deploying E-commerce Demo Services ==="

echo "=== Building Docker images locally ==="
cd /Users/jaci-j/resource_provision/otel-observability/ecommerce-demo

docker build -t order-service:latest -f Dockerfile.order .
docker build -t product-service:latest -f Dockerfile.product .

echo "=== Saving Docker images to tar files ==="
docker save order-service:latest | gzip > order-service.tar.gz
docker save product-service:latest | gzip > product-service.tar.gz

echo "=== Uploading product-service to k8s-worker (10.0.1.233) ==="
scp product-service.tar.gz jaci@8.136.137.145:/home/jaci/

echo "=== Uploading order-service to k8s-master (10.0.1.232) ==="
scp order-service.tar.gz jaci@8.136.143.226:/home/jaci/

echo "=== Images uploaded successfully ==="
