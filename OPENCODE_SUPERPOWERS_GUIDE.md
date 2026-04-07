# OpenCode + Superpowers 使用指南

## 🚀 快速开始

### 1. 安装配置

在项目根目录创建 `opencode.json`（已创建）：
```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]
}
```

### 2. 重启OpenCode
```bash
# 退出当前OpenCode会话
# 重新启动OpenCode
```

### 3. 验证安装
在OpenCode中输入：
```
Tell me about your superpowers
```

---

## 📚 Skills使用步骤

### 查看可用Skills

在OpenCode中输入：
```
use skill tool to list skills
```

### 加载特定Skill

```
use skill tool to load superpowers/brainstorming
use skill tool to load superpowers/writing-plans
use skill tool to load superpowers/subagent-driven-development
```

---

## 🎯 核心Skills

### 1. brainstorming - 头脑风暴

**触发条件：** 需要设计新功能或架构时

**使用命令：**
```
help me plan this feature
```

**或手动加载：**
```
use skill tool to load superpowers/brainstorming
```

**功能：**
- 澄清需求
- 探索替代方案
- 分块展示设计供你审核

---

### 2. writing-plans - 编写实现计划

**触发条件：** 需要制定详细实施计划时

**使用命令：**
```
请帮我制定实现计划
```

**功能：**
- 将工作分解为小任务（每个2-5分钟）
- 每个任务有精确的文件路径
- 包含完整的代码和验证步骤

---

### 3. subagent-driven-development - 子代理驱动开发

**触发条件：** 需要并行处理多个任务时

**使用命令：**
```
请使用子代理驱动开发来处理这个任务
```

**功能：**
- 为每个任务启动子代理
- 两阶段审查（规格合规、代码质量）
- 自主工作数小时不偏离计划

---

### 4. test-driven-development - TDD开发

**触发条件：** 需要使用TDD方式开发时

**使用命令：**
```
请使用TDD方式开发这个功能
```

**功能：**
- RED-GREEN-REFACTOR循环
- 写失败测试 → 看测试失败 → 写最小代码 → 看测试通过 → 提交

---

### 5. systematic-debugging - 系统化调试

**触发条件：** 需要调试问题时

**使用命令：**
```
let's debug this issue
```

**功能：**
- 4阶段根因分析
- 防御性编程
- 基于条件的等待技术

---

### 6. requesting-code-review - 代码审查

**触发条件：** 任务之间需要代码审查时

**使用命令：**
```
请进行代码审查
```

**功能：**
- 对照计划审查
- 按严重程度报告问题
- 关键问题阻止进度

---

## 💡 常用工作流

### 方式1：自然触发（推荐）

Superpowers会自动检测合适的技能触发，不需要手动调用。

**示例对话：**

```
你：我想开发一个新的用户认证功能
Superpowers：*触发brainstorming技能* - 在开始写代码之前，让我先了解一下你的需求...
```

### 方式2：手动请求

如果自动触发不工作，手动加载技能：

```
你：我想为这个功能写一个详细的实现计划
Superpowers：*加载writing-plans技能* - 好的，让我帮你制定一个详细的实现计划...
```

### 方式3：使用skill工具

```
use skill tool to load superpowers/writing-plans
```

---

## 🔧 故障排除

### Skills不工作？

1. 检查插件是否加载：
```
use skill tool to list skills
```

2. 重启OpenCode

3. 检查 `opencode.json` 配置：
```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]
}
```

### 工具映射

Superpowers原本为Claude Code编写，会自动适配到OpenCode：

| Claude Code工具 | OpenCode工具 |
|----------------|-------------|
| TodoWrite | todowrite |
| Task（子代理） | @mention |
| Skill tool | skill tool |
| 文件操作 | 原生文件工具 |

---

## 📖 更多资源

- Superpowers README: `/Users/jaci-j/AIops/skills/superpowers/README.md`
- Skills目录: `/Users/jaci-j/AIops/skills/superpowers/skills/`
- OpenCode文档: `/Users/jaci-j/AIops/skills/superpowers/docs/README.opencode.md`

---

## 🎉 开始使用

1. **启动新会话**（或在当前OpenCode中重启）

2. **验证安装**：
   ```
   Tell me about your superpowers
   ```

3. **开始项目**：
   ```
   help me plan this feature
   ```

4. **Superpowers会自动**：
   - 触发合适的技能
   - 引导你完成设计
   - 制定详细计划
   - 执行并审查代码

**Enjoy your Superpowers!** 💪
