# Frontend 开发规范

本规则适用于 `frontend/` 目录。

同时遵守项目根目录 `AGENTS.md`。

如果本文件与根目录规则冲突，以本文件中更具体的前端规则为准。

## 一、前端技术栈

前端使用：

- Vue 3
- TypeScript
- Composition API
- script setup
- npm
- REST API
- WebSocket

保持现有 Vue 技术栈。

不要无理由替换为 React 或其他框架。

不要因为一个小需求就增加大型 UI 框架或状态管理框架。

## 二、Vue 编码风格

优先使用：

```vue
<script setup lang="ts">
</script>
```

常用 Vue API：

```ts
ref()
reactive()
computed()
watch()
onMounted()
onUnmounted()
```

优先通过响应式状态控制页面。

不要可以用 Vue 状态解决的问题却直接操作 DOM。

## 三、TypeScript 规范

减少无意义的：

```ts
any
```

优先定义：

```ts
interface Task
interface TaskEvent
interface AgentEvent
interface ToolEvent
interface User
```

保持前端类型与后端返回结构一致。

不要为了消除类型错误大量使用：

```ts
as any
```

## 四、HTTP API 规范

如果项目已有统一 API Client，例如：

```text
src/api/http.ts
```

则继续通过统一 Client 请求。

不要在多个 Vue 页面中分别新建 Axios Instance。

不要在组件中硬编码：

```text
http://127.0.0.1:8000
http://localhost:8000
```

优先遵守已有：

- baseURL
- Authorization Header
- interceptor
- error handling
- timeout
- environment config

## 五、WebSocket 规范

WebSocket 生命周期需要完整处理：

```text
创建连接
→ open
→ message
→ error
→ close
→ 页面销毁清理
```

在组件卸载时：

```ts
onUnmounted()
```

及时关闭 WebSocket。

避免同一个任务重复创建多个未清理连接。

如果重新创建连接，先检查旧连接是否应该关闭。

需要考虑：

- 页面刷新
- 页面切换
- Task 切换
- 用户取消任务
- 服务端关闭
- 网络异常
- Ticket 失效

## 六、Task 状态规范

前端状态必须和后端保持一致。

例如：

```text
queued
running
completed
failed
cancelled
timeout
```

不要自己创建一套与后端不同的 Task 状态含义。

对于：

```text
failed
timeout
cancelled
```

应该给用户明确提示。

不要任务失败后 UI 仍然一直显示 Loading。

## 七、Agent / Tool 事件展示

实时事件可能包括：

```text
Task Created
Agent Started
Tool Called
Tool Result
Agent Message
Error
Completed
```

尽量保持事件顺序。

处理未知 Event Type 时，优先兼容，不要直接导致整个页面报错。

Tool 调用展示要尽量保留：

- Tool 名称
- 调用状态
- 结果摘要
- 错误信息

不要在页面展示 Secret、Token 等敏感参数。

## 八、Loading 管理

Loading 状态必须覆盖：

```text
成功
HTTP 失败
WebSocket 失败
任务失败
Timeout
Cancel
```

优先使用：

```ts
try {
    ...
} catch {
    ...
} finally {
    ...
}
```

避免异常发生后：

```text
loading = true
```

一直无法恢复。

## 九、错误处理

不要静默吞掉错误。

需要向用户展示可理解信息，例如：

```text
任务提交失败
WebSocket 连接失败
任务执行超时
Gateway 调用失败
```

不要直接把完整后端 Stack Trace 显示给普通用户。

开发日志也不要输出：

- JWT
- Cookie
- Password
- API Key

## 十、登录与权限

不要削弱现有认证逻辑。

保留：

- Token 存储
- 请求拦截器
- Authorization Header
- Logout 清理
- Router 权限控制

不要把真正的后端 Secret 放进 Vue 环境变量。

前端环境变量不是秘密存储。

## 十一、组件拆分

保持组件职责清晰。

大型页面可以适当拆分：

```text
API
WebSocket
Task 状态
Agent 事件
Tool 事件
UI 展示
```

但不要因为一个简单页面就拆十几个无意义文件。

修 Bug 时，不要顺便大规模重构页面样式。

## 十二、状态管理

优先使用当前项目已有方案。

简单局部状态优先：

```ts
ref
reactive
computed
```

除非确实需要全局状态，不要为了一个小功能额外增加：

```text
Pinia
Vuex
```

## 十三、配置规范

不要在业务组件中硬编码：

```text
API URL
WebSocket URL
生产域名
Token
Secret
```

如果当前项目通过：

- Vite env
- Nginx
- 相对路径

处理 API，则保持一致。

WebSocket 要注意：

```ts
location.protocol === 'https:' ? 'wss' : 'ws'
```

避免 HTTPS 页面连接 ws:// 导致 Mixed Content。

## 十四、前端验证

修改完成后先查看：

```bash
npm run
```

确认项目实际提供哪些脚本。

至少执行：

```bash
npm run build
```

如果项目已有：

```bash
npm run lint
npm run test
```

再根据修改范围执行。

不要调用 package.json 中不存在的命令。

修改 WebSocket 页面后，需要检查完整流程：

```text
用户发送问题
→ POST /chat
→ 获得 task_id
→ 获取 ws-ticket
→ 创建 WebSocket
→ 收到 Agent / Tool Event
→ 更新 UI
→ Completed / Failed
→ 关闭 WebSocket
```

如果 npm 依赖未安装导致无法 build，要明确说明，不得声称已经构建成功。
