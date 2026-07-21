# Open Spec — AIOps 功能规格定义

## 流程

```
1. 创建 Spec
   └── openspec/<category>/YYYY-MM-DD_feature-name.md
   　　基于 template.md 编写
   
2. 评审
   └── 状态: Draft → Reviewing → Approved
   
3. 实现
   └── 状态: Implemented
   
4. 关闭
   └── 状态: Rejected（如不需要）
```

## 目录结构

```
openspec/
├── README.md              # 本文件
├── template.md            # Spec 模板
├── skills/                # Skill 类功能 Spec（对应 skills/ 目录）
├── agents/                # Agent 节点类 Spec（对应 nodes/ 目录）
├── tools/                 # 工具类 Spec（对应 tool_registry.py）
└── architecture/          # 架构变更类 Spec
```

## 文件命名

```
YYYY-MM-DD_功能英文名.md
```

示例：
- `2026-07-08_tomcat-skill.md`
- `2026-07-08_approval-node.md`

## Spec 状态流转

```
Draft → Reviewing → Approved → Implemented
                 ↘ Rejected
```

每个 Spec 文件头部维护 `状态` 字段，实现完成后改为 `Implemented`。
