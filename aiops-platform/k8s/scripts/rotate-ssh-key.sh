#!/usr/bin/env bash
# ============================================================
# rotate-ssh-key.sh — 轮换跳板机 SSH root 私钥
#
# 背景：旧私钥曾以明文提交到 Git 仓库（commit 54a4e7e），已视为泄露，
#       必须更换密钥对，否则泄露的私钥仍可登录跳板机。
#
# 流程（安全顺序，避免锁死）：
#   1. 用旧私钥登录跳板机，生成新密钥对
#   2. 追加新公钥到跳板机 authorized_keys
#   3. 验证新私钥可登录
#   4. 从 authorized_keys 精确移除旧公钥（旧私钥立即失效）
#   5. 新私钥写入 gitignored 的 k8s/secrets-plain/ssh-secret.yaml
#      （下一步由 seal-secrets.sh 加密入库）
#
# 用法：
#   ./k8s/scripts/rotate-ssh-key.sh [目标主机] [旧私钥路径]
#   默认： 目标主机 root@47.76.53.232，旧私钥 ~/.ssh/id_rsa
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAIN_DIR="$ROOT/secrets-plain"
mkdir -p "$PLAIN_DIR"

TARGET_HOST="${1:-root@47.76.53.232}"
OLD_KEY="${2:-$HOME/.ssh/id_rsa}"

[ -f "$OLD_KEY" ] || { echo "✗ 旧私钥不存在: $OLD_KEY"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
NEW_KEY="$TMP/id_ed25519"
STAMP="$(date +%Y%m%d%H%M)"

echo "==> 1. 生成新密钥对 (ed25519)"
ssh-keygen -t ed25519 -N "" -f "$NEW_KEY" -C "aiops-k8s-$STAMP" >/dev/null

echo "==> 2. 用旧私钥登录 $TARGET_HOST 追加新公钥"
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$OLD_KEY" "$TARGET_HOST" \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && grep -qF '$(cat "$NEW_KEY.pub")' ~/.ssh/authorized_keys || echo '$(cat "$NEW_KEY.pub")' >> ~/.ssh/authorized_keys"

echo "==> 3. 验证新私钥可登录"
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$NEW_KEY" "$TARGET_HOST" \
  'echo "   ✓ 新密钥登录成功: $(hostname)"' || { echo "✗ 新密钥登录失败，已中止（旧公钥未移除）"; exit 1; }

echo "==> 4. 从 authorized_keys 移除旧公钥（使已泄露的旧私钥失效）"
OLD_PUB="$(ssh-keygen -y -f "$OLD_KEY" 2>/dev/null)" || { echo "⚠ 无法从旧私钥推导公钥，跳过移除（请手动检查）"; }
if [ -n "${OLD_PUB:-}" ]; then
  ssh -o StrictHostKeyChecking=no -i "$NEW_KEY" "$TARGET_HOST" \
    "grep -vF '$OLD_PUB' ~/.ssh/authorized_keys > /tmp/ak.new && mv /tmp/ak.new ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo '   ✓ 已移除旧公钥'"
fi

echo "==> 5. 写入 gitignored 的 secrets-plain/ssh-secret.yaml"
NEW_PRIV_B64="$(base64 < "$NEW_KEY" | tr -d '\n')"
cat > "$PLAIN_DIR/ssh-secret.yaml" <<EOF
# ⚠️ 明文私钥源文件 —— 已被 .gitignore 忽略，禁止提交！
# 由 rotate-ssh-key.sh 于 $STAMP 生成，对应公钥:
#   $(cat "$NEW_KEY.pub")
apiVersion: v1
kind: Secret
metadata:
  name: aiops-ssh-secret
  namespace: aiops
type: Opaque
data:
  id_rsa: "${NEW_PRIV_B64}"
EOF
chmod 600 "$PLAIN_DIR/ssh-secret.yaml"

echo ""
echo "===================================================="
echo "✓ 私钥轮换完成！"
echo "   新私钥: $PLAIN_DIR/ssh-secret.yaml（本地，gitignored）"
echo "   下一步：在可访问集群的机器上运行 ./seal-secrets.sh 加密后提交"
echo "   建议：旧私钥文件 $OLD_KEY 已泄露，请一并从本地删除或废弃"
echo "===================================================="
