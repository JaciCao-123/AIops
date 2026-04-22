#!/bin/bash

set -e

OBSERVABILITY_HOST="8.136.143.226"
OBSERVABILITY_USER="jaci"
REMOTE_DIR="/home/jaci/otel-observability"

echo "=== Uploading configuration files to k8s-master ==="

ssh ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST} "mkdir -p ${REMOTE_DIR}"

scp otel-collector-config.yaml ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST}:${REMOTE_DIR}/
scp tempo.yaml ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST}:${REMOTE_DIR}/
scp prometheus.yml ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST}:${REMOTE_DIR}/
scp grafana-datasources.yaml ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST}:${REMOTE_DIR}/
scp alertmanager.yml ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST}:${REMOTE_DIR}/
scp docker-compose.yml ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST}:${REMOTE_DIR}/

echo "=== Files uploaded successfully ==="

echo "=== Starting services on k8s-master ==="

ssh ${OBSERVABILITY_USER}@${OBSERVABILITY_HOST} << 'EOF'
cd /home/jaci/otel-observability

echo "=== Pulling Docker images ==="
sudo docker compose pull

echo "=== Starting services ==="
sudo docker compose up -d

echo "=== Waiting for services to start ==="
sleep 10

echo "=== Checking service status ==="
sudo docker compose ps

echo "=== Services started ==="
echo "Grafana: http://8.136.143.226:3000 (admin/admin123)"
echo "Prometheus: http://8.136.143.226:9090"
echo "Tempo: http://8.136.143.226:3200"
echo "OTel Collector: http://8.136.143.226:4317 (gRPC), http://8.136.143.226:4318 (HTTP)"
EOF

echo "=== Deployment completed ==="
