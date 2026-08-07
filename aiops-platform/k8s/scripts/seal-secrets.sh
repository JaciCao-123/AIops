#!/usr/bin/env bash
# ============================================================
# seal-secrets.sh — 用 kubeseal 生成 SealedSecret 并写入 base/
#
# 前置条件（在可访问集群的机器上执行，例如集群控制节点）：
#   1. kubectl 已配置目标集群（kubectl cluster-info 可通）
#   2. 已安装 kubeseal
#         macOS: brew install kubeseal
#         Linux: wget https://github.com/bitnami-labs/sealed-secrets/releases
#   3. 集群已安装 sealed-secrets controller
#         kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.27.2/controller.yaml
#   4. 加密输入源存在：
#         k8s/secrets-plain/secret.yaml         （AIops 平台凭据）
#         k8s/secrets-plain/ssh-secret.yaml     （由 rotate-ssh-key.sh 生成）
#
# 用法：
#   ./k8s/scripts/seal-secrets.sh
# 生成后提交 base/sealed-secrets/*.yaml 到 Git 即可（数据已加密，可安全入库）。
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAIN_DIR="$ROOT/secrets-plain"
OUT_DIR="$ROOT/base/sealed-secrets"

echo "==> 检查前置环境"
command -v kubeseal >/dev/null 2>&1 || { echo "✗ 未安装 kubeseal，请先安装"; exit 1; }
kubectl cluster-info >/dev/null 2>&1 || { echo "✗ 无法访问 Kubernetes 集群，请检查 kubectl 配置"; exit 1; }

# 检查 sealed-secrets controller 是否就绪
kubectl get pods -A -l app.kubernetes.io/name=sealed-secrets >/dev/null 2>&1 \
  || echo "⚠ 未检测到 sealed-secrets controller，请先安装（见脚本头部注释）"

seal_one() {
  local name="$1" src="$2" out="$3"
  if [ ! -f "$src" ]; then
    echo "✗ 缺少加密输入源: $src"
    echo "  说明：$4"
    exit 1
  fi
  echo "==> 加密 $name → $out"
  kubeseal --format yaml < "$src" > "$out"
  echo "   ✓ 已生成 $(basename "$out")"
}

seal_one "aiops-secrets" "$PLAIN_DIR/secret.yaml" "$OUT_DIR/aiops-secrets.yaml" \
  "AIops 平台凭据（NEO4J/OPENAI/SSH_USER/GRAFANA_PASSWORD）"

seal_one "aiops-ssh-secret" "$PLAIN_DIR/ssh-secret.yaml" "$OUT_DIR/aiops-ssh-secret.yaml" \
  "SSH 私钥。旧私钥已泄露，请先运行 ./rotate-ssh-key.sh 生成新私钥"

echo ""
echo "===================================================="
echo "✓ 完成！请提交以下文件到 Git（已加密，可安全入库）:"
echo "   $OUT_DIR/aiops-secrets.yaml"
echo "   $OUT_DIR/aiops-ssh-secret.yaml"
echo "===================================================="
