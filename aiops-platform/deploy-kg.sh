#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/k8s"
DOCKER_DIR="${SCRIPT_DIR}/docker"

KUBE_MASTER="8.136.226.231"
KUBE_USER="jaci"
SUDO_PASS="jaci1234"

echo "=========================================="
echo "  AIOps 知识图谱 K8S 部署脚本"
echo "=========================================="

echo ""
echo "[1/6] 在Master节点创建数据目录..."
ssh -o StrictHostKeyChecking=no ${KUBE_USER}@${KUBE_MASTER} "echo '${SUDO_PASS}' | sudo -S mkdir -p /data/neo4j && echo '${SUDO_PASS}' | sudo -S chmod 777 /data/neo4j"

echo ""
echo "[2/6] 复制K8S配置文件到Master节点..."
scp -o StrictHostKeyChecking=no ${K8S_DIR}/*.yaml ${KUBE_USER}@${KUBE_MASTER}:/tmp/

echo ""
echo "[3/6] 应用K8S配置..."
ssh -o StrictHostKeyChecking=no ${KUBE_USER}@${KUBE_MASTER} "
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/namespace.yaml
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/secrets.yaml
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/local-storage.yaml
"

echo ""
echo "[4/6] 构建Docker镜像..."
cd ${DOCKER_DIR}/kg-api
docker build -t aiops/kg-api:latest -f Dockerfile ../../../ || {
    echo "Docker镜像构建失败，尝试在远程构建..."
    ssh -o StrictHostKeyChecking=no ${KUBE_USER}@${KUBE_MASTER} "mkdir -p /tmp/kg-api"
    scp -o StrictHostKeyChecking=no ${DOCKER_DIR}/kg-api/Dockerfile ${KUBE_USER}@${KUBE_MASTER}:/tmp/kg-api/
    scp -o StrictHostKeyChecking=no ${DOCKER_DIR}/kg-api/app.py ${KUBE_USER}@${KUBE_MASTER}:/tmp/kg-api/
    scp -o StrictHostKeyChecking=no ${SCRIPT_DIR}/knowledge_graph/infra_text2cypher.py ${KUBE_USER}@${KUBE_MASTER}:/tmp/kg-api/
    scp -o StrictHostKeyChecking=no ${SCRIPT_DIR}/knowledge_graph/text2cypher.py ${KUBE_USER}@${KUBE_MASTER}:/tmp/kg-api/ 2>/dev/null || true
    ssh -o StrictHostKeyChecking=no ${KUBE_USER}@${KUBE_MASTER} "cd /tmp/kg-api && docker build -t aiops/kg-api:latest ."
}

echo ""
echo "[5/6] 部署Neo4j..."
ssh -o StrictHostKeyChecking=no ${KUBE_USER}@${KUBE_MASTER} "
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/neo4j-pvc.yaml
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/neo4j-deployment.yaml
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/neo4j-service.yaml
"

echo ""
echo "[6/6] 部署知识图谱API..."
ssh -o StrictHostKeyChecking=no ${KUBE_USER}@${KUBE_MASTER} "
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/kg-api-deployment.yaml
echo '${SUDO_PASS}' | sudo -S kubectl apply -f /tmp/kg-api-service.yaml
"

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  Neo4j Browser: http://${KUBE_MASTER}:30747"
echo "  Neo4j Bolt: bolt://${KUBE_MASTER}:30687"
echo "  KG API: http://${KUBE_MASTER}:30081"
echo ""
echo "查看状态:"
echo "  ssh ${KUBE_USER}@${KUBE_MASTER} 'sudo kubectl get pods -n aiops'"
echo ""
