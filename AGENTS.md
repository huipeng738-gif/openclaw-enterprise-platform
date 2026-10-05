# OpenClaw Enterprise Platform 开发规范

## 语言要求

- 默认使用中文与用户交流
- 代码、变量名、类名、函数名保持项目原有语言
- 技术术语可保留英文，例如 FastAPI、Redis、WebSocket、Worker、Gateway
- 解释复杂问题时优先使用通俗中文

## 一、项目说明

这是一个企业级 OpenClaw Agent 平台。

主要技术栈：

- 前端：Vue 3 + TypeScript
- 后端：Python + FastAPI
- 任务队列 / 状态持久化：Redis
- Agent Runtime：OpenClaw Gateway
- 实时通信：WebSocket
- 反向代理：Nginx
- 部署：Docker Compose
- OpenClaw 插件：plugin/
- 启动与运维脚本：scripts/

主要调用链：

Vue 前端
→ FastAPI
→ Redis Task Queue
→ Worker
→ OpenClaw Gateway
→ Agent / Tool
→ Redis Event
→ WebSocket
→ Vue 前端

处理跨模块问题前，必须先理解完整调用链。

## 二、代码修改原则

修改代码前必须：

1. 先阅读相关代码
2. 不允许仅根据文件名猜测实现
3. 排查问题时优先梳理完整调用链
4. 优先最小修改解决问题
5. 不修改与当前需求无关的代码
6. 不随意大规模重构
7. 不随意替换现有技术栈
8. 不删除现有业务逻辑，除非用户明确要求
9. 不得覆盖用户尚未提交的修改
10. 未实际验证的内容，不得声称“已经验证成功”

修 Bug 时优先定位根因，不要只处理表面异常。

推荐流程：

理解问题
→ 阅读代码
→ 梳理调用链
→ 定位根因
→ 提出最小修改方案
→ 修改代码
→ 查看 diff
→ 执行验证
→ 总结结果

## 三、目录职责

### backend/

负责：

- FastAPI API
- JWT 登录
- RBAC 权限
- Redis 任务队列
- 任务状态持久化
- Worker
- OpenClaw Gateway Client
- Agent 调用
- WebSocket
- 任务取消
- 超时
- 重试
- 审计日志

### frontend/

负责：

- Vue 页面
- 登录
- 任务提交
- 任务列表
- Agent 执行过程展示
- Tool 调用过程展示
- WebSocket 实时事件
- 任务取消 / 重试
- 错误提示

### nginx/

负责：

- Vue 静态资源
- API 反向代理
- WebSocket Upgrade
- 前端路由

### plugin/

负责：

- OpenClaw Plugin
- Tool
- Plugin 配置
- 企业数据能力扩展

### scripts/

负责：

- Windows 启动脚本
- Linux / WSL 启动脚本
- Worker 启动
- Gateway 启动
- 构建、验证、初始化脚本

不要无理由把某一模块职责迁移到其他目录。

## 四、安全规则

禁止输出、提交或泄露以下真实值：

- .env 内容
- API Key
- Access Token
- Refresh Token
- JWT Secret
- Cookie
- SSH Key
- 数据库密码
- Redis 密码
- OpenClaw 凭证

处理配置时：

- 优先读取 `.env.example`
- 如必须读取 `.env`，不要在回答中输出真实敏感值
- 日志中不要输出 Token、密码和完整 Authorization Header

未经明确允许，不执行危险命令，例如：

```text
git reset --hard
git clean -fd
git push --force
rm -rf
rmdir /s /q
docker system prune
docker volume prune
redis-cli FLUSHALL
redis-cli FLUSHDB
DROP DATABASE
DROP TABLE
```

未经用户明确要求，不修改：

- Windows 系统环境变量
- WSL 系统配置
- Docker 全局配置
- 防火墙
- 全局软件安装
- 系统服务

## 五、Git 规则

进行较大修改前优先执行：

```bash
git status
```

修改后优先执行：

```bash
git diff
```

检查：

- 是否误改无关文件
- 是否覆盖用户代码
- 是否引入不必要改动
- 是否泄露敏感信息

除非用户明确要求：

- 不执行 git commit
- 不执行 git push
- 不切换分支
- 不重写 Git 历史
- 不强制推送

## 六、接口兼容规则

尽量保持现有接口兼容。

不要随意修改：

- REST API 路径
- HTTP Method
- 请求字段
- 返回字段
- WebSocket Event Schema
- Redis Key
- Redis Task Schema
- Gateway 请求格式
- 前后端约定

如必须做不兼容修改，需要先说明：

- 修改内容
- 修改原因
- 影响范围
- 需要同步修改的调用方

## 七、异步与并发规则

本项目包含长耗时 Agent 任务。

重点关注：

- async / await
- Redis 异步 IO
- Worker 并发
- WebSocket 生命周期
- task_id
- timeout
- retry
- cancel
- duplicate execution
- idempotency

不要使用 `sleep` 等临时手段掩盖竞态问题。

不要在 async 函数中直接执行明显阻塞操作。

## 八、Redis 规则

修改 Redis 逻辑前必须明确：

- Key 名称
- Key 类型
- 谁写入
- 谁读取
- 是否设置 TTL
- 是否存在并发问题
- 是否涉及幂等
- 是否涉及任务状态机

禁止为了调试直接执行：

```text
FLUSHALL
FLUSHDB
```

Redis Task Schema 修改时要同时检查：

- API enqueue
- Worker
- task status API
- WebSocket
- frontend

## 九、OpenClaw 规则

修改 OpenClaw 相关代码前，需要判断当前逻辑属于：

- OpenClaw CLI
- OpenClaw Gateway
- Agent
- Tool
- Plugin
- Workspace
- Session
- Device
- Model Provider
- Model
- Routing

不要把 CLI 调用与 Gateway API 调用混在一起，除非当前架构明确需要。

涉及 Agent 调用时，需要尽量保留：

- task_id
- Agent 信息
- Tool 调用事件
- Tool 执行结果
- 错误信息
- 完成事件

便于前端实时展示和问题排查。

## 十、验证规则

修改完成后必须根据实际影响范围验证。

至少需要：

1. 查看修改文件
2. 查看 git diff
3. 执行相关语法检查
4. 执行相关 build / test
5. 检查错误输出

不得在没有执行验证命令时声称：

- 已测试
- 构建成功
- 问题已彻底解决

如果因为缺少环境、依赖或服务无法验证，要明确指出：

- 哪一步没验证
- 为什么没验证
- 用户应该怎么验证

## 十一、回答格式

分析问题时优先按照以下结构回答：

1. 当前执行流程
2. 问题发生位置
3. 根本原因
4. 涉及文件
5. 修改方案
6. 实际修改内容
7. 验证结果

对于复杂代码：

先通俗解释，再讲技术实现。

## 回答层级

默认采用三级回答策略：

1. 第一层：先给结论，3～10 行
2. 第二层：用户要求“详细解释”时再展开
3. 第三层：用户要求“逐行解释”时才逐行分析代码

禁止默认一次性输出全部细节

## CLI 输出规范

- 默认使用中文回答
- 回答尽量简洁，优先给出结论和关键步骤
- 默认控制在 10～20 行以内
- 除非明确要求“详细解释”，否则不要大段展开背景知识
- 文件引用只保留相对路径，不要输出完整绝对路径
- 引用代码位置时使用：
  `frontend/src/views/Chat.vue:23`
  不要使用：
  `D:/agent_framework/openclaw-enterprise-platform/frontend/src/views/Chat.vue:23`
- 多文件说明时使用简短列表或表格
- 不要重复描述用户已经知道的上下文
- 解释调用链时优先使用：
  `前端 -> FastAPI -> Redis -> Worker -> OpenClaw -> WebSocket -> 前端`
- 如果回答较长，先给摘要；只有用户要求时再展开详细解释

## Docker 验证规则

本项目以 Docker Compose 作为主要运行与验收环境。

启动任务时：

1. 执行 `docker compose config`。
2. 执行 `docker compose ps` 检查现有服务。
3. 如果服务尚未启动，执行：
   `docker compose up -d --build`
4. 如果服务已经正常运行，不要无意义地重复完整构建。

开发过程中：

- 修改 backend 后：
  `docker compose build api worker`
  `docker compose up -d api worker`

- 修改 frontend 后：
  `docker compose build web`
  `docker compose up -d web`

- 修改 compose.yaml / Dockerfile / 依赖文件后：
  `docker compose build`
  `docker compose up -d`

每个 Phase 完成后必须验证：

- `docker compose ps`
- Redis healthy
- `redis-cli ping` 返回 PONG
- API → Redis 正常
- Worker → Redis 正常
- GET /health 返回 200
- 受影响服务 logs 无启动错误
- backend/frontend 对应测试通过

Docker 验证失败时：
修复 → 重新 build → up → test。

Engineering Gate 全部 PASS 后才能进入下一 Phase。

阶段验收分为两个独立门禁：

- Engineering Gate：build、frontend/backend tests、Docker、Redis、health check 全部通过时标记 PASS。
- Browser Acceptance：浏览器不可用时，登录、刷新、退出、RBAC、页面交互和视觉检查标记 BLOCKED_BY_ENVIRONMENT，不得伪造 PASS；这不阻塞 Engineering Gate PASS 后继续下一 Phase。
- 浏览器恢复后必须补做所有未完成的 Browser Acceptance，并更新 `design/design-2-progress.md`。
- 优先使用已有或低成本增加的 Playwright E2E 验证登录、刷新、退出、路由和 RBAC；能自动验证的项目不得跳过。
- HTTP 200 不能证明 UI 或视觉验收通过；自动交互测试和视觉验收分别记录。

Compose 内：
API/Worker Redis URL = `redis://redis:6379/0`

禁止使用：
`redis://127.0.0.1:6379/0`
`redis://127.0.0.1:6380/0`

OpenClaw Gateway 保持运行于 WSL Ubuntu。
RAGFlow 使用独立 Docker Compose。

## 外部环境操作规则

Codex 可能以 `--dangerously-bypass-approvals-and-sandbox`
模式运行。

允许自主操作：

- 当前项目目录及其所有文件
- Docker build / compose / logs / exec
- 项目相关容器和镜像
- 项目测试和构建命令
- WSL 中项目相关目录
- OpenClaw 项目相关配置
- RAGFlow 项目相关配置

即使当前运行于最高权限模式，以下操作仍禁止自动执行：

- 删除当前项目之外的目录
- 删除 Docker volume
- `docker system prune`
- 修改 Windows 注册表
- 修改 Windows 系统级网络配置
- 修改 Docker Desktop 全局配置
- 修改 WSL 全局系统配置
- 删除或覆盖 `.git`
- 删除用户数据
- 修改真实 API Key / Token / Password
- 执行不可逆数据库操作
- 修改与当前项目无关的文件

上述高风险操作必须先说明：
1. 为什么需要；
2. 将修改什么；
3. 影响范围；
4. 回滚方式；

然后等待人工

## UI 实现规则

`design/ui-reference/` 是本项目 UI 的视觉设计基准。

实现或修改前端页面时，必须先检查对应 UI 参考图，再修改代码。

优先级：

1. 用户当前指令
2. design/ui-reference/ 中对应页面
3. design/design-2.md
4. 当前项目已有 Design System
5. 自主设计

参考图存在时，不得自行重新设计页面。

必须尽量还原：

- 页面整体布局
- Sidebar / Header
- 内容区域宽度
- Grid / Flex 布局
- 卡片尺寸和排列
- 间距
- 圆角
- 边框
- 阴影
- 字体层级
- 图标位置
- 按钮尺寸
- 表格结构
- 输入框结构
- 空状态
- Loading 状态
- Hover / Active 状态

允许根据项目实际业务调整：

- 文案
- 数据字段
- API 数据
- Agent 状态
- Tool Call 信息
- 权限控制

禁止为了“更好看”而大幅改变参考图的视觉结构。

技术栈保持：

Vue 3 + TypeScript + Element Plus + Pinia

不要为了还原 UI 重写为 React。

优先复用组件，不要复制大量重复页面代码。

页面完成后必须执行：

1. frontend build
2. Docker Compose build
3. Docker Compose up
4. 页面运行验证
5. 检查 console error
6. 检查 API 请求
7. 更新 design/design-2-progress.md

## 代码注释
1.需要在方法名上注释代码含义，前端和后端都需要
