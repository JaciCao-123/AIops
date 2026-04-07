### AIOps 前端权限系统完整提示词

在开始之前，请先告诉 Trae 以下**全局上下文**，以确保代码风格和依赖的统一：


---

#### 第一步：定义数据结构与工具类（基础设施）

我正在开发一个 AIOps 项目的前端。请帮我创建用户权限相关的 TypeScript 类型定义文件和 API 接口定义。

**要求：**

1. **通用类型：** 在 `src/types/index.ts` 定义 `ApiResponse<T>` 接口，包含 `code`, `message`, `data`。
2. **用户类型：** 在 `src/types/user.ts` 定义：
    - `UserInfo`：包含 `userId`, `username`, `avatar`, `roles` (角色数组), `permissions` (权限标识数组，如 `'monitor:view'`), `scope` (负责的业务系统ID列表)。
    - `LoginParams` 和 `LoginResult` (包含 `token`)。
3. **API 封装：** 在 `src/api/user.ts` 使用 Axios 封装：
    - `login(data: LoginParams): Promise<LoginResult>`
    - `getUserInfo(): Promise<UserInfo>`
    - 请确保 API 函数返回的是经过 `ApiResponse` 解包后的 `data` 数据。

---

#### 第二步：实现核心逻辑（Store 与 拦截器）

请基于上一步的接口，实现用户登录的核心逻辑。

**任务：**

1. **Pinia Store (**`src/store/user.ts`**)：**
    - 定义 `token`, `userInfo`, `permissions` 状态。
    - `loginAction`：调用登录接口，存储 Token 到 `localStorage`，并触发 `getInfoAction`。
    - `getInfoAction`：获取用户信息，存储在 state 中。
    - `resetState`：清空用户信息和 Token，用于退出登录。
2. **Axios 拦截器 (**`src/utils/request.ts`**)：**
    - **请求拦截：** 自动在 Header 中携带 `Authorization: Bearer ${token}`。
    - **响应拦截：**
        - 处理业务错误码（非 200），使用 `ElMessage` 提示错误。
        - **401 处理：** 清除本地 Token，重定向到登录页。
        - **403 处理：** 提示“无权限访问”。

---

#### 第三步：实现路由权限控制（页面级安全）

现在需要实现动态路由权限控制。

**背景：** 路由分为静态路由（Login, 404）和动态路由（Dashboard, Monitor）。

**任务：**

1. **路由配置 (**`src/router/index.ts`**)：**
    - 定义 `constantRoutes` (静态) 和 `asyncRoutes` (动态模板)。
    - 初始化 Router 时只挂载静态路由。
2. **路由守卫 (**`src/permission.ts`**)：**
    - 定义**白名单** `whiteList = ['/login', '/auth-redirect']`。
    - **逻辑流程：**
        - 有 Token：
            - 去登录页 -> 重定向到首页。
            - 无用户信息 -> 调用 `getInfoAction` -> **根据权限过滤动态路由** -> `router.addRoute` -> `next({ ...to, replace: true })`。
        - 无 Token：
            - 在白名单 -> `next()`。
            - 不在白名单 -> `next('/login')`。
3. **工具函数：**
    - 实现 `filterAsyncRoutes(routes, roles)`，递归筛选出当前用户角色可访问的路由表。

---

#### 第四步：实现按钮级权限控制（指令）

我需要实现按钮级别的权限控制。

**要求：**

1. **自定义指令 (**`src/directive/permission/index.ts`**)：**
    - 指令名：`v-permission`。
    - 逻辑：获取当前用户的权限列表（从 Store）。
    - 如果当前用户是**超级管理员**，直接放行。
    - 如果绑定值（数组）中的权限不在用户权限列表中，执行 `el.parentNode.removeChild(el)`。
2. **使用示例：**
    - 在 `src/views/ai-ops/script-execute.vue` 中演示：
    - 一个“查看日志”按钮（普通权限）。
    - 一个“删除脚本”按钮（高危权限 `script:delete`）。

---

#### 第五步：AIOps 场景化增强（进阶提示）

针对 AIOps 运维场景，补充安全交互逻辑。

**任务：**

1. **高危操作组件 (**`src/components/HazardConfirmModal/index.vue`**)：**
    - 封装一个弹窗，标题为“高危操作确认”。
    - 内容显示：“您正在尝试执行 **[操作名称]**，该操作不可逆，请输入验证码/确认继续”。
    - 提供 `onConfirm` 回调。
2. **资源隔离演示：**
    - 模拟 `getUserInfo` 返回 `scope: ['System-A', 'System-B']`。
    - 在 `src/views/ai-ops/script-execute.vue` 顶部添加一个“所属系统”下拉框，仅展示用户 scope 内的系统。
3. **综合演示：**
    - 在该页面中，结合 `v-permission` 和 `HazardConfirmModal`：
    - 只有拥有 `script:kill` 权限的用户才能看到“强制终止进程”按钮。
    - 点击后，必须先通过 `HazardConfirmModal` 确认，才能执行 API 调用。
