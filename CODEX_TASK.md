# OpenClaw Enterprise Platform - RAGFlow 知识库实施任务

## 一、任务目标

在现有 openclaw-enterprise-platform 中实现企业知识库模块。

采用：

- Vue：知识库管理前端
- FastAPI：知识库业务 API
- RAGFlow：知识库、文档解析、Chunk、Embedding、索引、检索
- Redis：保留现有任务、事件、会话等能力
- OpenClaw：Agent 调用知识库
- WebSocket：展示 Agent / Tool 执行过程
- Nginx：统一入口
- Docker Compose：项目容器化

不要在本项目中重新实现一套 RAG。

RAGFlow 必须作为独立服务，通过 HTTP API 集成。


# 二、重要开发约束

执行整个任务时必须遵守：

1. 首先阅读根目录以及 frontend、backend 下所有 AGENTS.md
2. 分析现有代码后再修改
3. 遵循现有项目目录结构，不要为了知识库进行无关重构
4. Python 依赖继续使用 uv
5. 禁止创建 requirements.txt
6. RAGFlow 调用使用 httpx.AsyncClient
7. 禁止使用 requests
8. RAGFLOW_API_KEY 只能存在后端
9. API Key 不得返回前端
10. API Key 不得写入日志
11. 不破坏现有登录认证
12. 不破坏现有 Session/JWT
13. 不破坏现有 RBAC
14. 不破坏 Redis Task Queue
15. 不破坏 Worker
16. 不破坏 WebSocket
17. 不破坏 OpenClaw Gateway Client
18. 不破坏现有 DeepSeek/Qwen 模型配置
19. 不要复制 RAGFlow 源码进入项目
20. 不重复实现 Chunk、Embedding、Vector DB
21. RAGFlow API URL 不允许凭空猜测
22. 必须根据当前项目实际依赖和 RAGFlow 实际 API 实现
23. 所有修改尽可能保持最小影响范围
24. 每个 Phase 完成后执行检查，通过后自动进入下一 Phase
25. 不需要等待人工确认，除非遇到无法安全决定的问题
26. 如果发现当前项目结构与本计划中的示例路径不同，以现有项目结构为准
27. 不允许因为实现知识库而删除现有功能


# 三、最终架构

目标调用链：

Vue
  ↓
Nginx
  ↓
FastAPI
  ↓
KnowledgeService
  ↓
RagflowClient
  ↓
RAGFlow


Agent 调用链：

用户
  ↓
Vue Chat
  ↓
FastAPI
  ↓
Redis Queue
  ↓
Worker
  ↓
OpenClaw Gateway
  ↓
Agent
  ↓
knowledge_search
  ↓
FastAPI Knowledge API
  ↓
RAGFlow
  ↓
Chunks + Source + Score
  ↓
Agent
  ↓
最终答案
  ↓
WebSocket
  ↓
Vue


# 四、Phase 1：分析现有项目

首先只分析，不立即修改代码。

检查：

- 项目根目录
- compose.yaml / docker-compose 文件
- .env.example
- Dockerfile
- Dockerfile.web
- nginx
- backend
- frontend
- AGENTS.md

重点分析后端：

- FastAPI app 创建方式
- Router 注册方式
- Pydantic Schema
- Redis 初始化方式
- Session/JWT
- permission()
- RBAC
- audit
- Task Queue
- Worker
- WebSocket
- OpenClaw Gateway Client
- 配置读取方式
- 异常处理方式

重点分析前端：

- Vue Router
- Pinia
- Axios
- 登录状态
- RBAC
- 页面布局
- API 封装
- WebSocket
- 组件组织方式

完成后形成内部 Implementation Plan。

必须明确：

- 新增文件
- 修改文件
- 数据流
- API
- 权限
- 环境变量
- 前端页面
- OpenClaw Tool
- 测试方法

分析完成后自动进入 Phase 2。


# 五、Phase 2：增加 RAGFlow 配置

增加：

RAGFLOW_BASE_URL
RAGFLOW_API_KEY
RAGFLOW_TIMEOUT_SECONDS=30

如果项目已有统一 Settings/config 模块，接入现有配置体系。

更新：

.env.example

但：

- 不要提交真实 API Key
- 不要在前端环境变量中保存 API Key
- 不要日志输出完整 API Key


# 六、Phase 3：实现 RagflowClient

按照现有项目结构创建合适的 RAGFlow Client。

推荐职责：

RagflowClient

至少支持：

- list_datasets()
- create_dataset()
- get_dataset()
- delete_dataset()

- list_documents(dataset_id)
- upload_document(dataset_id, file)
- delete_document(dataset_id, document_id)

- start_document_parse(dataset_id, document_id)
- get_document_status(dataset_id, document_id)

- retrieve(
    query,
    dataset_ids,
    top_k,
    similarity_threshold
  )

要求：

- httpx.AsyncClient
- async/await
- timeout
- connection pooling
- 统一异常处理
- 连接错误处理
- 超时处理
- HTTP 非 2xx 处理
- RAGFlow 错误转换成平台统一错误
- 不泄露 API Key

重要：

不要凭空构造 RAGFlow API。

优先检查当前 RAGFlow 官方 API 文档或现有 SDK/API 定义。

如果 API 名称和本任务中的方法名不同：

外部接口以 RAGFlow 实际 API 为准，
内部 RagflowClient 方法可以维持上述业务语义。


# 七、Phase 4：KnowledgeService

增加 KnowledgeService。

Router 不直接操作 RAGFlow。

结构：

Router
  ↓
KnowledgeService
  ↓
RagflowClient

KnowledgeService 负责：

- 参数验证
- 权限相关业务
- RAGFlow 调用
- 返回值转换
- Audit
- 异常转换

不要把大量业务逻辑写进 Router。


# 八、Phase 5：知识库 API

实现：

GET /api/knowledge/bases

POST /api/knowledge/bases

GET /api/knowledge/bases/{id}

DELETE /api/knowledge/bases/{id}


文档：

GET
/api/knowledge/bases/{id}/documents

POST
/api/knowledge/bases/{id}/documents

DELETE
/api/knowledge/bases/{id}/documents/{document_id}

POST
/api/knowledge/bases/{id}/documents/{document_id}/parse

GET
/api/knowledge/bases/{id}/documents/{document_id}/status


检索：

POST
/api/knowledge/retrieval


检索请求建议：

{
  "query": "设备出现 E01 错误怎么办？",
  "knowledge_base_ids": ["xxx"],
  "top_k": 5,
  "similarity_threshold": 0.2
}


统一返回至少包含：

{
  "query": "...",
  "results": [
    {
      "content": "...",
      "score": 0.87,
      "document_id": "...",
      "document_name": "...",
      "knowledge_base_id": "...",
      "metadata": {}
    }
  ]
}


# 九、Phase 6：RBAC

复用现有 permission() / Depends。

增加权限：

knowledge:read
knowledge:write
knowledge:delete
knowledge:retrieve


建议：

GET：
knowledge:read

创建知识库：
knowledge:write

上传文档：
knowledge:write

重新解析：
knowledge:write

DELETE：
knowledge:delete

检索：
knowledge:retrieve


不要重新实现认证/RBAC。


# 十、Phase 7：Audit

复用现有 audit。

记录：

knowledge.create
knowledge.delete

document.upload
document.delete
document.parse

knowledge.retrieve

审计日志中不得包含：

- API Key
- 用户密码
- Session ID
- JWT
- 敏感 Header

检索审计不要保存超长文档正文。


# 十一、Phase 8：Vue 知识库管理页面

根据现有 Vue 项目结构实现。

至少增加：

1. 知识库列表
2. 创建知识库
3. 删除知识库
4. 知识库详情
5. 文档列表
6. 上传文档
7. 删除文档
8. 解析文档
9. 查看解析状态
10. 检索测试


建议页面：

KnowledgeBases.vue

KnowledgeBaseDetail.vue

KnowledgeRetrieval.vue

如果现有项目命名规范不同，遵循现有规范。


# 十二、Phase 9：知识库列表

展示：

名称
描述
文档数
状态
更新时间
操作

支持：

创建
进入详情
删除

必须：

loading
error
empty state


# 十三、Phase 10：文档管理

知识库详情展示：

文件名
状态
Chunk 数
更新时间
操作

支持：

上传
删除
重新解析
刷新状态

状态统一映射为类似：

pending
parsing
completed
failed

实际状态以 RAGFlow 返回为准。


# 十四、Phase 11：Retrieval Test

实现知识库检索测试页面。

输入：

query
knowledge_base_ids
top_k
similarity_threshold

输出：

content
score
document_name
knowledge_base
metadata

第一版 Retrieval Test：

不要调用 LLM。

只测试：

Query
  ↓
RAGFlow Retrieval
  ↓
Chunks
  ↓
Score
  ↓
Source

这样可以单独判断检索质量。


# 十五、Phase 12：OpenClaw knowledge_search Tool

在现有 OpenClaw 集成机制中增加：

knowledge_search

输入：

{
  "query": "...",
  "knowledge_base_ids": ["..."],
  "top_k": 5
}

输出：

{
  "results": [
    {
      "content": "...",
      "source": "...",
      "score": 0.91
    }
  ]
}


Agent 第一版只允许：

knowledge_search


禁止 Agent：

- 创建知识库
- 删除知识库
- 上传文件
- 删除文件
- 修改 RAGFlow 配置

知识库管理只能通过后台管理 API。


# 十六、Phase 13：Agent 调用链

保持当前任务架构：

Vue
 ↓
FastAPI
 ↓
Redis Task Queue
 ↓
Worker
 ↓
OpenClaw Gateway
 ↓
Agent

Agent 需要知识时：

Agent
 ↓
knowledge_search
 ↓
FastAPI
 ↓
KnowledgeService
 ↓
RagflowClient
 ↓
RAGFlow

不得绕过当前 Worker / Gateway 架构。


# 十七、Phase 14：WebSocket Tool Events

复用现有事件流。

knowledge_search 调用时：

向现有事件体系发送 Tool 事件。

至少能够让前端知道：

- knowledge_search 开始
- query
- 返回结果数量
- knowledge_search 完成
- knowledge_search 失败

不要通过 WebSocket 发送：

RAGFLOW_API_KEY
Authorization Header
内部敏感配置


# 十八、Phase 15：引用来源

Agent 最终结果应支持来源。

至少保留：

document_name
document_id
knowledge_base_id
score

前端最终回答附近显示：

引用来源

例如：

[1] 设备说明书.pdf
[2] 售后FAQ.docx

不要伪造引用。

没有检索结果时：

明确返回没有匹配知识，而不是生成虚假来源。


# 十九、Phase 16：Docker / Nginx

第一版不要把 RAGFlow 源码合并进本项目。

RAGFlow 独立部署。

本项目通过：

RAGFLOW_BASE_URL

访问 RAGFlow。

检查：

Docker api 容器是否能访问 RAGFlow
Docker worker 是否需要访问 RAGFlow
Nginx 是否需要增加知识库 API 配置

原则：

Browser
 ↓
Nginx
 ↓
FastAPI
 ↓
RAGFlow

浏览器不得直接访问带 API Key 的 RAGFlow 管理 API。


# 二十、Phase 17：测试

增加必要测试。

至少覆盖：

RagflowClient：

- 正常响应
- timeout
- connection error
- 401/403
- 404
- 5xx

Knowledge API：

- 未登录
- 无权限
- 正常权限
- 创建
- 查询
- 删除
- 上传
- 检索

安全：

- API Key 不出现在响应
- API Key 不出现在日志
- 普通用户不能执行 delete
- Agent 不能调用管理接口

如果项目已有 pytest：

继续使用。

不要引入另一套测试框架。


# 二十一、Phase 18：质量检查

后端：

运行现有测试。

如果有：

ruff
mypy
pytest

按项目现有配置执行。


前端：

执行：

npm build

以及项目已有：

lint
typecheck


Docker：

执行现有 Compose config 校验。

如果当前环境允许：

构建相关镜像。


# 二十二、Phase 19：文档

更新 README 或现有部署文档。

必须写清楚：

1. RAGFlow 如何部署
2. RAGFLOW_BASE_URL
3. RAGFLOW_API_KEY
4. 如何启动项目
5. 如何创建知识库
6. 如何上传文件
7. 如何查看解析状态
8. 如何测试检索
9. Agent 如何调用 knowledge_search
10. 常见错误排查


# 二十三、Phase 20：最终验收

最终必须验证以下链路：

测试 A：

管理员登录
 ↓
创建知识库
 ↓
上传 PDF/Markdown 等文档
 ↓
RAGFlow 解析
 ↓
解析完成


测试 B：

Retrieval Test
 ↓
输入问题
 ↓
返回 Chunk
 ↓
返回 Score
 ↓
返回 Source


测试 C：

用户发送知识问题
 ↓
OpenClaw Agent
 ↓
knowledge_search
 ↓
RAGFlow
 ↓
Agent 回答
 ↓
引用来源
 ↓
WebSocket 展示 Tool 调用过程


# 二十四、错误处理规则

执行过程中如果遇到普通代码错误：

自行分析
→ 修复
→ 重新测试
→ 继续下一 Phase

如果测试失败：

不要忽略失败。

必须判断：

是本次修改导致
还是原项目已有问题。

如果是本次修改导致：

必须修复后继续。


只有遇到以下情况才停止并询问用户：

1. 需要真实 RAGFLOW_API_KEY
2. 需要用户选择具有重大架构影响的方案
3. 需要执行不可逆的数据删除
4. 需要修改生产环境数据
5. 缺少无法从项目或官方资料确定的关键配置
6. 发现现有架构与需求存在根本冲突


# 二十五、禁止事项

禁止：

- 编造 RAGFlow API
- 编造测试成功结果
- 删除现有业务
- 绕过 RBAC
- 绕过 Audit
- 把 API Key 写入源码
- 把 API Key 放到 Vue
- 把 Token 放 localStorage
- 大范围无关重构
- 改坏 OpenClaw Gateway
- 改坏 Redis Worker
- 改坏 WebSocket
- 使用 requirements.txt
- 用 requests 替代 httpx.AsyncClient


# 二十六、最终输出

全部完成后输出：

## Implementation Summary

列出：

1. 新增文件
2. 修改文件
3. 新增环境变量
4. 新增 API
5. 新增 RBAC 权限
6. 新增 Vue 页面
7. OpenClaw Tool
8. RAGFlow 数据流
9. Docker/Nginx 修改
10. 测试结果

## Deployment

给出从零启动步骤。

## Verification

给出完整验证命令。

## Remaining Issues

列出：

- 未完成项
- 需要真实环境验证项
- 已知限制

不要声称没有实际执行过的测试已经通过。