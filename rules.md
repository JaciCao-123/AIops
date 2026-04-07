AIOps 智能运维平台（Demo版）开发规则
1. 开发规范
1.1 语言与框架
前端：TypeScript + React（函数组件 + Hooks），使用 Ant Design 组件库。

后端：TypeScript + Express，使用 Prisma 作为 ORM。

算法：Python 3.9 + Flask，依赖 scikit-learn。

所有代码必须通过 ESLint / Prettier 格式化。

1.2 命名规则
文件/目录：小写字母 + 连字符，如 log-upload.tsx。

React 组件：PascalCase，如 LogList。

变量/函数：camelCase，如 fetchLogs。

常量：UPPER_SNAKE_CASE。

CSS 类名：kebab-case（若使用 CSS Modules 则用 camelCase）。

1.3 文件组织
前端：按功能模块划分目录，每个模块包含 components/, pages/, hooks/, types/。

后端：按业务模块划分路由，routes/, controllers/, services/, models/。

单文件行数上限：300 行（超出需拆分）。

禁止将所有代码堆在一个文件内，必须由开发者主动拆分。

1.4 注释与文档
复杂函数必须写 JSDoc 注释。

关键业务逻辑需添加行内注释。

更新代码后同步更新 project.md 中的进度。

2. Git 版本管理策略
2.1 分支模型
main：稳定版本，随时可部署。

develop：开发主干，功能分支从此合并。

feature/*：新功能开发，如 feature/log-upload。

bugfix/*：问题修复。

2.2 提交规范
提交信息格式：<type>(<scope>): <subject>

type: feat/fix/docs/style/refactor/test/chore

scope: 模块名（如 frontend, backend）

subject: 简短描述（英文/中文均可，但建议英文）

示例：feat(backend): add log upload API

2.3 回滚机制
若 AI 修改导致崩溃，立即 git reset --hard HEAD^ 回退到上一稳定版本。

禁止在混乱状态下继续叠加修改。

3. 质量闸门
3.1 代码审查
每次合并到 develop 前必须经过另一位开发者（或 AI 辅助）审查。

审查重点：逻辑正确性、安全漏洞、是否符合规范。

3.2 自动化测试
关键功能必须编写单元测试（Jest + React Testing Library / Mocha）。

每次提交自动运行测试，测试失败禁止合并。

3.3 构建检查
前端 npm run build 必须通过。

后端 npm run build 必须通过。

Docker Compose 本地启动必须正常。

4. 安全规则
4.1 API 密钥与敏感信息
绝对禁止将任何密钥、密码、token 提交到代码仓库。

使用环境变量（.env 文件）存储敏感信息，.env 加入 .gitignore。

前端调用后端 API 时，密钥等应放在后端，前端只发请求。

4.2 输入校验与授权
后端必须校验所有前端输入（类型、范围、恶意内容）。

虽然 demo 无用户系统，但 API 应设计简单 token 防止随意调用（可选）。

数据库查询使用 ORM 参数化查询，防止 SQL 注入。

4.3 错误处理
不得将原始堆栈信息返回给客户端，应统一返回友好错误码和消息。

日志中记录完整错误，便于调试。

5. AI 协作规则
5.1 状态摘要
每次与 AI 交互时，在消息末尾添加当前上下文摘要，例如：

【当前任务】实现日志上传前端表单。
【已修改文件】frontend/src/pages/Upload.tsx, backend/src/routes/log.ts
【下一步】完成后端接收文件并保存到临时目录。
【限制】只修改我点名的文件，不要动 UI 全局样式，不要重构无关模块。

5.2 限制 AI 权限
AI 只能修改指定文件和范围，禁止擅自修改未提及的部分。

若 AI 提议大规模重构，应先记录到 project.md 中再单独决策。

5.3 报错处理流程
最小复现：将问题缩小到最简示例。

加日志/断点：打印关键变量状态。

写测试：锁定当前行为是否预期。

两次无进展则回滚：git reset --hard 到上一个稳定点，重新尝试不同方案。

6. 参考实现（reference 目录）
项目根目录下建立 reference/，存放已验证的标准实现片段：

button-example.tsx：符合风格的按钮组件。

form-example.tsx：表单 + 校验示例。

websocket-example.ts：WebSocket 连接管理。

api-client.ts：前端 API 调用封装。

AI 在实现类似功能时应“照着抄”这些参考，确保风格一致。

