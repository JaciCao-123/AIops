# 智能诊断架构改进

## 🎯 核心改进

根据您的建议，我已经将架构从**硬编码方法**改为**AI 智能调度**：

### ❌ 旧架构（硬编码）
```
用户查询 → 意图识别 → 硬编码的检查方法 → 执行 → 分析
                         ↓
                    _build_disk_check_tasks()
                    _build_network_check_tasks()
                    _build_memory_check_tasks()
```

### ✅ 新架构（AI 智能调度）
```
用户查询 → 意图识别 → Master Agent 智能生成诊断计划 → 执行 → 分析
                         ↓
                    读取 debug_skill.md
                    根据问题类型智能选择检查步骤
                    动态生成检查命令
```

## 🔧 技术实现

### 1. Master Agent 增强

**文件**: [master.py](file:///Users/jaci-j/AIops/aiops-platform/backend/app/agents/master.py)

**新增功能**:
```python
async def generate_diagnosis_plan(
    self,
    user_query: str,
    intent_data: Dict
) -> Dict[str, Any]:
    """
    根据用户查询和 debug_skill.md 智能生成诊断计划
    """
    # 读取 debug_skill.md 内容
    # 让 AI 根据问题类型智能选择检查步骤
    # 返回动态生成的检查计划
```

**输出格式**:
```json
{
    "check_type": "disk|network|memory|general",
    "reasoning": "为什么选择这些检查步骤",
    "commands": [
        "df -h",
        "du -h --max-depth=1 / | sort -rh | head -n 10",
        "lsof | grep deleted"
    ],
    "expected_findings": [
        "磁盘使用率是否超过阈值",
        "是否有大文件占用空间"
    ],
    "next_steps_if_anomaly_found": "如果发现异常，下一步应该做什么"
}
```

### 2. Orchestrator 改进

**文件**: [orchestrator.py](file:///Users/jaci-j/AIops/aiops-platform/backend/app/agents/orchestrator.py)

**流程变更**:
```python
# 旧流程
result["stages"]["ansible_playbook"] = await self._stage_generate_playbook(
    target_host, symptoms, metrics
)

# 新流程
result["stages"]["diagnosis_plan"] = await self.master_agent.generate_diagnosis_plan(
    user_query, result["stages"]["intent_parsing"]
)
```

**新增方法**:
```python
async def _execute_diagnosis_plan(
    self,
    target_host: str,
    diagnosis_plan: Dict
) -> Dict[str, Any]:
    """
    执行 Master Agent 生成的诊断计划
    """
    # 从诊断计划中提取命令
    # 通过 SSH 执行命令
    # 解析输出结果
```

## 📊 测试结果

### 测试 1: 磁盘空间不足

**用户查询**: "8.136.226.231磁盘空间不足"

**AI 生成的诊断计划**:
```json
{
  "check_type": "disk",
  "reasoning": "用户明确报告服务器8.136.226.231存在磁盘空间不足问题，属于典型的磁盘容量类故障。需首先确认整体磁盘使用情况（df -h），再定位高占用目录（du -h --max-depth=1 / | sort -rh | head -n 10），最后排查因进程持有已删除文件句柄导致空间无法释放的隐蔽原因（lsof | grep deleted）。",
  "commands": [
    "df -h",
    "du -h --max-depth=1 / | sort -rh | head -n 10",
    "lsof | grep deleted"
  ],
  "expected_findings": [
    "磁盘使用率是否超过阈值",
    "是否有大文件占用空间",
    "是否有被删除但未释放的文件"
  ],
  "next_steps_if_anomaly_found": "若df显示某分区使用率≥90%，结合du结果定位具体大目录；若lsof发现deleted文件，需重启对应进程或通知应用负责人释放句柄；必要时清理无用日志、临时文件或归档历史数据，并设置logrotate策略防止复发。"
}
```

### 测试 2: 网络连接超时

**用户查询**: "8.136.226.231网络连接超时"

**AI 生成的诊断计划**:
```json
{
  "check_type": "network",
  "reasoning": "用户明确报告目标服务器 8.136.226.231 出现网络连接超时，属于典型网络连通性与可达性问题；需优先验证本端到目标的路由可达性、端口连通性、防火墙策略及目标服务监听状态，排除中间链路丢包、ACL拦截、目标服务未启动或监听绑定错误等问题。",
  "commands": [
    "ping -c 4 8.136.226.231",
    "mtr -r -c 10 8.136.226.231",
    "telnet 8.136.226.231 22",
    "nc -zv 8.136.226.231 80 2>&1 | head -n 1",
    "ss -tuln | grep ':22\\|:80'",
    "iptables -L -n -v 2>/dev/null || nft list ruleset 2>/dev/null"
  ],
  "expected_findings": [
    "ping 是否出现丢包或完全不可达",
    "mtr 是否显示某跳后延迟激增或断连（定位故障节点）",
    "telnet/nc 是否能成功建立 TCP 连接（验证端口开放与服务响应）",
    "ss 是否显示对应端口正在监听且绑定正确地址",
    "iptables/nftables 规则是否显式 DROP/REJECT 目标IP或端口"
  ]
}
```

## 🌟 核心优势

### 1. **灵活性**
- ✅ 不再需要硬编码各种检查方法
- ✅ AI 根据问题类型智能选择检查步骤
- ✅ 可以处理各种复杂和未知的问题场景

### 2. **可扩展性**
- ✅ 只需更新 `debug_skill.md`，无需修改代码
- ✅ 新增排查方法只需添加到文档中
- ✅ AI 自动学习新的排查策略

### 3. **智能性**
- ✅ 根据实际情况动态调整检查策略
- ✅ 提供推理过程和预期发现
- ✅ 给出下一步行动建议

### 4. **可维护性**
- ✅ 代码更简洁，逻辑更清晰
- ✅ 知识库与代码分离
- ✅ 易于理解和维护

## 🔄 工作流程对比

### 旧流程
```
1. 用户输入查询
2. 意图识别
3. 根据关键词匹配硬编码方法
   - "disk" → _build_disk_check_tasks()
   - "network" → _build_network_check_tasks()
   - "memory" → _build_memory_check_tasks()
4. 执行固定的检查命令
5. 解析结果
6. 生成报告
```

### 新流程
```
1. 用户输入查询
2. 意图识别
3. Master Agent 智能生成诊断计划
   - 读取 debug_skill.md
   - 理解问题类型和上下文
   - 智能选择最相关的检查步骤
   - 动态生成检查命令
4. 执行动态生成的命令
5. 解析结果
6. 生成报告
```

## 📝 知识库驱动

### debug_skill.md 的作用

**旧架构**: 作为参考文档，需要人工编码实现

**新架构**: 作为知识源，AI 自动学习并应用

```markdown
# debug_skill.md 示例

1. Disk Full (磁盘空间不足)
   - df -h: 查看磁盘使用率
   - du -h --max-depth=1: 查找大目录
   - lsof | grep deleted: 查找被删除但未释放的文件

2. Network Broken (网络连接异常)
   - ping: ICMP 检测
   - mtr: 链路追踪
   - telnet/nc: 端口连通性检测

3. Out of Memory (内存溢出)
   - free -h: 查看内存使用情况
   - ps aux --sort=-%mem: 查看内存占用最高的进程
   - dmesg: 检查 OOM 事件
```

### AI 如何使用知识库

1. **理解问题**: 分析用户查询，识别问题类型
2. **检索知识**: 从 debug_skill.md 中找到相关的排查方法
3. **智能选择**: 根据实际情况选择最合适的检查步骤
4. **动态生成**: 生成具体的检查命令和预期发现
5. **提供建议**: 给出下一步行动建议

## 🚀 后续优化方向

### 1. **多轮诊断**
- 根据第一轮检查结果，动态调整后续检查策略
- 实现智能的迭代诊断流程

### 2. **知识库增强**
- 添加更多类型的排查方法
- 支持自定义知识库
- 实现知识库的版本管理

### 3. **执行优化**
- 支持并行执行多个检查命令
- 添加命令执行的超时和重试机制
- 实现检查结果的缓存

### 4. **结果分析**
- 让 AI 更智能地分析检查结果
- 提供更精准的根因分析
- 生成更详细的解决方案

## ✅ 总结

通过这次架构改进，我们实现了：

1. **从硬编码到智能调度**: 不再需要预先定义各种检查方法
2. **知识库驱动**: debug_skill.md 成为真正的知识源
3. **AI 智能决策**: Master Agent 根据实际情况动态生成诊断计划
4. **易于扩展**: 只需更新知识库，无需修改代码

这使得 AIOps 系统更加智能、灵活和可维护，完全符合您提出的"不要通过改写方法的方式去实现功能增减，而是让 master agent 根据已有的方案，通过智能调度生成临时的 ansible yaml 文件或者是其他方式的中间文件去做查询和返回"的要求。
