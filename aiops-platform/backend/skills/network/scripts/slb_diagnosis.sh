#!/bin/bash
# 阿里云 SLB 远程诊断脚本
# 用于排查 SLB 实例 lb-bp1bxqgw0jflid09i6xnq 的服务状态
# 生成时间: 2026-04-06

LOAD_BALANCER_ID="${1:-lb-bp1bxqgw0jflid09i6xnq}"
REGION="${2:-cn-hangzhou}"
OUTPUT_DIR="/Users/jaci-j/AIops/aiops-platform/backend/data/diagnosis"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/slb_diagnosis_${TIMESTAMP}.txt"

echo "========================================" | tee "$OUTPUT_FILE"
echo "阿里云 SLB 远程诊断" | tee -a "$OUTPUT_FILE"
echo "========================================" | tee -a "$OUTPUT_FILE"
echo "SLB ID: $LOAD_BALANCER_ID" | tee -a "$OUTPUT_FILE"
echo "区域: $REGION" | tee -a "$OUTPUT_FILE"
echo "诊断时间: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$OUTPUT_FILE"
echo "" | tee -a "$OUTPUT_FILE"

check_aliyun_cli() {
    echo "=== Step 1: 检查阿里云 CLI 环境 ===" | tee -a "$OUTPUT_FILE"
    
    if ! command -v aliyun &> /dev/null; then
        echo "✗ 阿里云 CLI 未安装" | tee -a "$OUTPUT_FILE"
        echo "请先安装阿里云 CLI:" | tee -a "$OUTPUT_FILE"
        echo "  macOS: brew install aliyun-cli" | tee -a "$OUTPUT_FILE"
        echo "  Linux: wget https://aliyuncli.alicdn.com/aliyun-cli-linux-latest-amd64.tgz" | tee -a "$OUTPUT_FILE"
        echo "  Windows: choco install aliyun-cli" | tee -a "$OUTPUT_FILE"
        return 1
    fi
    
    echo "✓ 阿里云 CLI 已安装: $(aliyun version 2>&1 | head -1)" | tee -a "$OUTPUT_FILE"
    
    if ! aliyun configure list &> /dev/null; then
        echo "✗ 阿里云 CLI 未配置认证信息" | tee -a "$OUTPUT_FILE"
        echo "请先配置认证信息: aliyun configure" | tee -a "$OUTPUT_FILE"
        return 1
    fi
    
    echo "✓ 阿里云 CLI 已配置认证信息" | tee -a "$OUTPUT_FILE"
    
    if ! aliyun sts GetCallerIdentity &> /dev/null; then
        echo "✗ 无法连接阿里云 API，请检查网络和认证信息" | tee -a "$OUTPUT_FILE"
        return 1
    fi
    
    echo "✓ 阿里云 API 连接正常" | tee -a "$OUTPUT_FILE"
    aliyun sts GetCallerIdentity 2>&1 | tee -a "$OUTPUT_FILE"
    return 0
}

query_slb_status() {
    echo "" | tee -a "$OUTPUT_FILE"
    echo "=== Step 2: 查询 SLB 实例状态 ===" | tee -a "$OUTPUT_FILE"
    
    SLB_INFO=$(aliyun slb DescribeLoadBalancerAttribute --LoadBalancerId "$LOAD_BALANCER_ID" --RegionId "$REGION" 2>&1)
    
    if echo "$SLB_INFO" | grep -q "LoadBalancerId"; then
        echo "✓ SLB 实例存在" | tee -a "$OUTPUT_FILE"
        echo "$SLB_INFO" | tee -a "$OUTPUT_FILE"
    else
        echo "✗ SLB 实例不存在或查询失败" | tee -a "$OUTPUT_FILE"
        echo "$SLB_INFO" | tee -a "$OUTPUT_FILE"
        return 1
    fi
}

query_backend_servers() {
    echo "" | tee -a "$OUTPUT_FILE"
    echo "=== Step 3: 查询后端服务器 ===" | tee -a "$OUTPUT_FILE"
    
    BACKENDS=$(aliyun slb DescribeLoadBalancerBackends --LoadBalancerId "$LOAD_BALANCER_ID" --RegionId "$REGION" 2>&1)
    echo "$BACKENDS" | tee -a "$OUTPUT_FILE"
}

query_health_status() {
    echo "" | tee -a "$OUTPUT_FILE"
    echo "=== Step 4: 查询健康检查状态 ===" | tee -a "$OUTPUT_FILE"
    
    HEALTH_STATUS=$(aliyun slb DescribeHealthStatus --LoadBalancerId "$LOAD_BALANCER_ID" --RegionId "$REGION" 2>&1)
    echo "$HEALTH_STATUS" | tee -a "$OUTPUT_FILE"
}

query_listeners() {
    echo "" | tee -a "$OUTPUT_FILE"
    echo "=== Step 5: 查询监听配置 ===" | tee -a "$OUTPUT_FILE"
    
    LISTENERS=$(aliyun slb DescribeLoadBalancerListeners --LoadBalancerId "$LOAD_BALANCER_ID" --RegionId "$REGION" 2>&1)
    echo "$LISTENERS" | tee -a "$OUTPUT_FILE"
}

echo "" | tee -a "$OUTPUT_FILE"
if check_aliyun_cli; then
    query_slb_status
    query_backend_servers
    query_health_status
    query_listeners
fi

echo "" | tee -a "$OUTPUT_FILE"
echo "========================================" | tee -a "$OUTPUT_FILE"
echo "诊断完成" | tee -a "$OUTPUT_FILE"
echo "========================================" | tee -a "$OUTPUT_FILE"
echo "诊断报告已保存到: $OUTPUT_FILE" | tee -a "$OUTPUT_FILE"
