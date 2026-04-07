# Kubernetes Pod 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `Pod`, `容器`, `CrashLoopBackOff`, `OOMKilled`
- `kubectl`, `k8s`, `Kubernetes`, `Deployment`
- `ImagePullBackOff`, `ErrImagePull`, `ContainerCreating`
- `Pending`, `Evicted`, `Unknown`

### 1.2 适用条件
- Pod 无法正常启动
- Pod 频繁重启
- Pod 状态异常
- 容器运行时错误
- 资源限制问题

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 获取 Pod 状态                                       │
│  kubectl get pods -n <namespace>                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 查看 Pod 详情                                       │
│  kubectl describe pod <pod-name> -n <namespace>             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 查看容器日志                                        │
│  kubectl logs <pod-name> -n <namespace> [-c container]      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 分析事件                                            │
│  kubectl get events -n <namespace> --sort-by='.lastTimestamp'│
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位根因并提供解决方案                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 状态查看命令

#### 查看 Pod 列表
```bash
# 查看所有 Pod
kubectl get pods -A

# 查看指定命名空间
kubectl get pods -n <namespace>

# 查看详细信息
kubectl get pods -n <namespace> -o wide

# 查看所有异常状态的 Pod
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

#### 查看 Pod 详情
```bash
# 查看 Pod 详细信息
kubectl describe pod <pod-name> -n <namespace>

# 查看 Pod YAML 配置
kubectl get pod <pod-name> -n <namespace> -o yaml
```

### 3.2 日志查看命令

```bash
# 查看容器日志
kubectl logs <pod-name> -n <namespace>

# 查看指定容器日志
kubectl logs <pod-name> -n <namespace> -c <container-name>

# 查看上一个容器的日志（适用于重启的 Pod）
kubectl logs <pod-name> -n <namespace> --previous

# 实时跟踪日志
kubectl logs -f <pod-name> -n <namespace>

# 查看最近 N 行日志
kubectl logs <pod-name> -n <namespace> --tail=100
```

### 3.3 事件查看命令

```bash
# 查看命名空间事件
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# 查看特定 Pod 的事件
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>

# 查看警告事件
kubectl get events -n <namespace> --field-selector type=Warning
```

### 3.4 资源使用查看

```bash
# 查看 Pod 资源使用（需要 metrics-server）
kubectl top pods -n <namespace>

# 查看节点资源使用
kubectl top nodes

# 查看资源配额
kubectl describe resourcequota -n <namespace>

# 查看限制范围
kubectl describe limitrange -n <namespace>
```

### 3.5 进入容器调试

```bash
# 进入容器终端
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# 进入指定容器
kubectl exec -it <pod-name> -n <namespace> -c <container-name> -- /bin/sh

# 在容器中执行命令
kubectl exec <pod-name> -n <namespace> -- <command>
```

---

## 4. 常见问题与解决方案

### 4.1 CrashLoopBackOff

**现象**: Pod 不断重启，状态显示 CrashLoopBackOff

**诊断步骤**:
```bash
# 1. 查看 Pod 状态
kubectl describe pod <pod-name> -n <namespace>

# 2. 查看容器日志
kubectl logs <pod-name> -n <namespace> --previous

# 3. 检查退出码
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
```

**常见原因与解决方案**:

| 退出码 | 原因 | 解决方案 |
|--------|------|---------|
| 0 | 正常退出，但进程不应退出 | 检查应用是否为常驻进程 |
| 1 | 应用错误 | 检查应用日志修复代码问题 |
| 126 | 命令无法执行 | 检查命令权限或路径 |
| 127 | 命令未找到 | 检查镜像中是否存在该命令 |
| 128+ | 信号导致退出 | 检查是否被 OOM Kill 等 |
| 137 | OOMKilled (128+9) | 增加内存限制或优化内存使用 |
| 139 | Segmentation Fault | 检查应用代码问题 |
| 143 | SIGTERM (128+15) | 正常终止信号 |

### 4.2 OOMKilled

**现象**: Pod 因内存不足被杀死

**诊断步骤**:
```bash
# 1. 检查 OOMKilled 状态
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Last State"

# 2. 查看内存限制
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].resources}'

# 3. 查看实际内存使用
kubectl top pod <pod-name> -n <namespace>
```

**解决方案**:
```bash
# 增加内存限制
kubectl set resources deployment/<deployment-name> -n <namespace> \
  --limits=memory=<new-limit> \
  --requests=memory=<new-request>
```

### 4.3 ImagePullBackOff / ErrImagePull

**现象**: 无法拉取镜像

**诊断步骤**:
```bash
# 1. 查看事件
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Events"

# 2. 检查镜像名称
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].image}'
```

**常见原因与解决方案**:

| 原因 | 解决方案 |
|------|---------|
| 镜像不存在 | 检查镜像名称和标签是否正确 |
| 私有镜像无权限 | 创建/配置 imagePullSecrets |
| 镜像仓库不可达 | 检查网络连接和 DNS |
| 镜像过大拉取超时 | 增加拉取超时时间或使用更小的镜像 |

### 4.4 Pending

**现象**: Pod 一直处于 Pending 状态

**诊断步骤**:
```bash
# 1. 查看事件
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Events"

# 2. 检查节点资源
kubectl describe nodes | grep -A5 "Allocated resources"

# 3. 检查节点标签
kubectl get nodes --show-labels
```

**常见原因与解决方案**:

| 原因 | 解决方案 |
|------|---------|
| 资源不足 | 增加节点或减少资源请求 |
| 节点选择器不匹配 | 检查 nodeSelector 或 nodeAffinity |
| 污点/容忍度问题 | 添加容忍度或移除污点 |
| PVC 未绑定 | 检查 PV 和 StorageClass |
| 调度限制 | 检查 PodAntiAffinity 设置 |

### 4.5 ContainerCreating

**现象**: Pod 长时间处于 ContainerCreating 状态

**诊断步骤**:
```bash
# 1. 查看事件
kubectl describe pod <pod-name> -n <namespace> | grep -A10 "Events"

# 2. 检查镜像拉取进度
kubectl get events -n <namespace> --field-selector reason=Pulling

# 3. 检查存储挂载
kubectl get pvc -n <namespace>
```

**常见原因与解决方案**:

| 原因 | 解决方案 |
|------|---------|
| 镜像拉取慢 | 使用本地镜像仓库或镜像预热 |
| 存储挂载失败 | 检查 PV/PVC 配置 |
| CNI 插件问题 | 检查网络插件状态 |
| Init 容器阻塞 | 检查 init 容器日志 |

### 4.6 Evicted

**现象**: Pod 被驱逐

**诊断步骤**:
```bash
# 1. 查看驱逐原因
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Reason"

# 2. 检查节点压力
kubectl describe node <node-name> | grep -A10 "Conditions"
```

**常见原因与解决方案**:

| 原因 | 解决方案 |
|------|---------|
| 节点磁盘压力 | 清理节点磁盘空间 |
| 节点内存压力 | 增加节点内存或减少 Pod 密度 |
| 节点 PID 压力 | 减少 Pod 数量或调整 PID 限制 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
kubectl get, describe, logs, top, events
kubectl exec (仅查看命令)
```

### 5.2 需要确认的操作
```bash
kubectl delete pod
kubectl scale deployment
kubectl rollout restart
kubectl set resources
kubectl patch
```

### 5.3 危险操作禁止执行
```bash
kubectl delete namespace
kubectl delete deployment --all
kubectl delete pv,pvc --all
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
```

---

## 6. 快速诊断模板

```bash
#!/bin/bash
# Pod 快速诊断脚本

NAMESPACE="${1:-default}"
POD_NAME="$2"

echo "=== Pod 状态 ==="
kubectl get pod $POD_NAME -n $NAMESPACE -o wide

echo -e "\n=== Pod 详情 ==="
kubectl describe pod $POD_NAME -n $NAMESPACE

echo -e "\n=== 容器日志 (最近 50 行) ==="
kubectl logs $POD_NAME -n $NAMESPACE --tail=50

echo -e "\n=== 相关事件 ==="
kubectl get events -n $NAMESPACE --field-selector involvedObject.name=$POD_NAME

echo -e "\n=== 资源使用 ==="
kubectl top pod $POD_NAME -n $NAMESPACE 2>/dev/null || echo "metrics-server 未安装"
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-05
- 维护者: AIOps Team
