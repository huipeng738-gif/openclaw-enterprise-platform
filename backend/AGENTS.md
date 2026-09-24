# Backend 开发规范

本规则适用于 `backend/` 目录。

同时遵守项目根目录 `AGENTS.md`。

如果本文件与根目录规则存在冲突，以本文件更具体的后端规则为准。

## 一、后端技术栈

后端主要使用：

- Python
- FastAPI
- Pydantic
- async / await
- Redis
- WebSocket
- OpenClaw Gateway
- Worker

Python 依赖统一使用：

```text
uv
```

不要直接使用 pip 修改项目依赖，除非用户明确要求。

优先使用：

```bash
uv sync
uv run ...
```

## 二、后端分层

尽量保持：

```text
Router / API
→ Service
→ Redis / Queue / Gateway Client
→ Worker / OpenClaw
```

FastAPI Router 主要负责：

- 参数接收
- 参数校验
- 权限验证
- 调用业务逻辑
- 返回结果

不要把大量 Agent 执行逻辑直接写在 Router 中。

## 三、FastAPI 规范

尽量使用：

- Depends
- Pydantic Model
- HTTPException
- async def

保留现有：

- API 路径
- Method
- Status Code
- Request Schema
- Response Schema

不要为了消除异常写：

```python
try:
    ...
except Exception:
    return {}
```

应该保留错误信息，并在合适的位置记录日志。

## 四、异步规范

禁止在 async 函数中直接使用明显阻塞代码，例如：

```python
time.sleep()
requests.get()
requests.post()
```

优先使用异步实现。

例如：

```python
await asyncio.sleep(...)
```

如果必须运行阻塞代码，可以在确认合理后使用：

```python
await asyncio.to_thread(...)
```

不要无理由把所有代码都扔进线程池。

## 五、任务队列规范

任务完整生命周期可能包括：

```text
queued
running
completed
failed
cancelled
timeout
```

修改任务逻辑时，需要同时检查：

- enqueue
- Redis queue
- Worker
- task status
- event publish
- WebSocket
- retry
- cancel
- timeout

不要只修改生产者，不修改消费者。

也不要只修改 Worker，不检查前端依赖的状态字段。

## 六、Worker 规则

Worker 负责消费任务并执行长耗时业务。

修改 Worker 前，必须明确：

- 如何取任务
- BRPOP / BLPOP / Stream / List 使用方式
- 是否阻塞
- 是否并发
- 如何更新状态
- 如何处理异常
- 如何超时
- 如何重试
- 如何取消
- 如何推送事件
- 如何调用 OpenClaw

单个任务失败不能导致整个 Worker 意外退出。

Worker 捕获任务异常后，应正确：

- 更新 failed 状态
- 保存错误信息
- 发布错误事件
- 继续处理后续任务

## 七、Redis 规范

保持现有 Redis Key 命名规则。

修改之前先确认：

- String
- Hash
- List
- Set
- Stream
- ZSet

分别承担什么用途。

Task Schema 修改时必须检查所有使用方。

不要为了调试执行：

```text
FLUSHDB
FLUSHALL
```

涉及重试时要注意：

- retry_count
- max_retry
- next_retry_at
- 幂等
- 重复执行

## 八、OpenClaw Gateway Client

Gateway 调用尽量集中在独立 Client / Service 层。

不要在多个 Router 中直接复制 Gateway 请求代码。

Gateway 调用要考虑：

- Gateway URL
- Authentication
- Agent
- Session
- Task
- Timeout
- Error
- Event

如果修改 Gateway 请求 Schema，需要同步检查所有调用方。

不要静默从真实 Gateway 自动切换到 Mock，除非明确属于开发模式。

## 九、WebSocket 规范

WebSocket 需要正确处理：

```text
连接
→ 推送事件
→ 客户端断开
→ 清理连接
```

重点考虑：

- ClientDisconnected
- WebSocketDisconnect
- 重复 close
- close 后 send
- task_id 绑定
- user 权限
- ticket 校验
- connection cleanup

用户正常关闭页面，不应该导致后端持续抛大量异常堆栈。

但也不要捕获所有 Exception 后完全忽略。

## 十、JWT 与 RBAC

不得绕过已有：

- JWT 校验
- user 解析
- permission
- role
- task owner 校验

需要同时考虑：

```text
有权限用户
无权限用户
未登录用户
资源不属于当前用户
```

不要硬编码用户、Token 或生产账号。

## 十一、审计日志

已有审计机制时，不要随意删除。

以下操作建议保留审计：

- 登录
- 创建任务
- 取消任务
- 重试任务
- 管理员操作
- 权限修改
- 配置修改

审计日志尽量包含：

- user
- action
- target
- task_id
- timestamp

不要记录秘密值。

## 十二、日志规范

日志需要帮助排查完整链路：

```text
HTTP Request
→ task_id
→ Redis
→ Worker
→ OpenClaw
→ Event
→ WebSocket
```

优先记录：

- task_id
- username
- agent
- event type
- status

禁止记录：

- 密码
- API Key
- JWT Secret
- 完整 Authorization Header
- Cookie

## 十三、Python 编码规范

优先：

- 类型注解
- 明确函数名
- 小函数
- 清晰异常处理
- 明确业务边界

避免：

- 超大函数
- 大量全局变量
- 隐式共享状态
- 无意义 try/except
- 为修一个 Bug 大范围格式化整个项目

## 十四、后端验证

修改 Python 后至少根据实际项目结构执行：

```bash
uv run python -m compileall .
```

如果存在 pytest：

```bash
uv run pytest
```

如果项目配置了 lint / type check，则使用项目已有命令。

修改任务逻辑时需要检查：

```text
enqueue
→ Redis
→ Worker
→ status
→ event
```

修改 WebSocket 时需要检查：

```text
连接
→ 收事件
→ 任务完成
→ 客户端关闭
```

如果因为 Redis、Gateway 或其他外部服务未启动导致无法验证，要明确说明。
