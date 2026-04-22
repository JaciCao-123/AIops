#!/bin/bash

set -e

K8S_MASTER="8.136.143.226"
K8S_USER="jaci"

echo "=== Deploying OTel Agent DaemonSet to K8s cluster ==="

echo "=== Uploading K8s manifests ==="
ssh ${K8S_USER}@${K8S_MASTER} "mkdir -p /home/jaci/otel-observability/k8s-agent"

scp namespace.yaml ${K8S_USER}@${K8S_MASTER}:/home/jaci/otel-observability/k8s-agent/
scp configmap.yaml ${K8S_USER}@${K8S_MASTER}:/home/jaci/otel-observability/k8s-agent/
scp rbac.yaml ${K8S_USER}@${K8S_MASTER}:/home/jaci/otel-observability/k8s-agent/
scp daemonset.yaml ${K8S_USER}@${K8S_MASTER}:/home/jaci/otel-observability/k8s-agent/
scp service.yaml ${K8S_USER}@${K8S_MASTER}:/home/jaci/otel-observability/k8s-agent/

echo "=== Files uploaded ==="

echo "=== Applying K8s manifests ==="
ssh ${K8S_USER}@${K8S_MASTER} << 'EOF'
cd /home/jaci/otel-observability/k8s-agent

echo "=== Creating namespace ==="
kubectl apply -f namespace.yaml

echo "=== Creating RBAC ==="
kubectl apply -f rbac.yaml

echo "=== Creating ConfigMap ==="
kubectl apply -f configmap.yaml

echo "=== Creating DaemonSet ==="
kubectl apply -f daemonset.yaml

echo "=== Creating Service ==="
kubectl apply -f service.yaml

echo "=== Waiting for DaemonSet to be ready ==="
sleep 10

echo "=== Checking DaemonSet status ==="
kubectl get pods -n observability -l app=otel-agent

echo "=== Checking DaemonSet logs ==="
kubectl logs -n observability -l app=otel-agent --tail=20
EOF

echo "=== Deployment completed ==="
