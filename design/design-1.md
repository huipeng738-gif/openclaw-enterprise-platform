请分析当前 `openclaw-enterprise-platform` 项目的前后端登录认证实现，并在尽量不破坏现有 JWT + RBAC 权限体系的前提下，将登录机制升级为企业常见的：

**Access Token + Refresh Token + HttpOnly Cookie + Axios 自动刷新**

## 一、目标

实现以下登录体验：

1. 用户登录成功后，不因为浏览器 F5 刷新页面而重新登录
2. Access Token 使用短生命周期，例如 30 分钟
3. Refresh Token 使用较长生命周期，例如 7 天
4. Access Token 保存在 Vue / Pinia 内存中，不长期存储到 `localStorage`
5. Refresh Token 保存到 `HttpOnly Cookie`
6. JavaScript 不能直接读取 Refresh Token
7. Access Token 过期后，前端自动调用 `/api/auth/refresh`
8. 刷新成功后自动重试原来的请求
9. Refresh Token 失效或过期后才跳转登录页
10. 用户主动退出登录后 Refresh Token 必须失效
11. 保留现有 JWT、RBAC、Redis、Axios 请求拦截器等架构

目标流程：

```text
用户登录
   ↓
POST /api/auth/login
   ↓
FastAPI 校验用户名密码
   ↓
生成
├── Access Token（短期）
└── Refresh Token（长期）
   ↓
Access Token 返回给 Vue
Refresh Token → HttpOnly Cookie
   ↓
Vue 将 Access Token 保存到 Pinia 内存
   ↓
Axios 请求自动携带
Authorization: Bearer <access_token>
```

页面刷新：

```text
F5
 ↓
Pinia 内存 Access Token 消失
 ↓
Vue 初始化
 ↓
POST /api/auth/refresh
 ↓
浏览器自动携带 Refresh Token Cookie
 ↓
FastAPI 验证 Refresh Token
 ↓
返回新的 Access Token
 ↓
Pinia 恢复登录状态
 ↓
用户继续使用系统
```

Access Token 过期：

```text
Axios 请求
 ↓
后端返回 401
 ↓
Axios Response Interceptor
 ↓
POST /api/auth/refresh
 ↓
刷新成功
 ↓
更新 Pinia Access Token
 ↓
重新发送刚才失败的请求
```

Refresh Token 也失效：

```text
POST /api/auth/refresh
 ↓
401
 ↓
清空前端认证状态
 ↓
跳转 /login
```

## 二、后端改造

项目后端使用：

```text
FastAPI
Redis
JWT
RBAC
Python
```

请检查当前：

```text
backend/app/
```

中的认证实现，不要盲目创建重复模块。

需要实现或调整：

```text
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
```

登录成功后：

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

Access Token 通过响应 JSON 返回。

Refresh Token 不允许返回给 JavaScript，使用：

```text
Set-Cookie
HttpOnly
Secure（生产环境）
SameSite
Path
Max-Age / Expires
```

保存。

JWT 中明确区分：

```text
type = access
type = refresh
```

防止 Refresh Token 被直接拿去访问普通业务接口。

Access Token 建议：

```text
30 分钟
```

Refresh Token 建议：

```text
7 天
```

如果项目已有环境变量配置体系，把有效期配置放入 `.env`，不要硬编码。

例如：

```text
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## 三、Redis 管理 Refresh Session

项目已经使用 Redis。

请复用 Redis 管理 Refresh Token 对应的登录 Session，不要再引入新的数据库。

可以设计：

```text
auth:refresh:<jti>
```

保存：

```text
username
created_at
expires_at
```

Redis TTL 与 Refresh Token 有效期保持一致。

Refresh JWT 至少包含：

```text
sub
type
jti
iat
exp
```

调用 `/auth/refresh` 时：

```text
Cookie
 ↓
解析 Refresh JWT
 ↓
验证签名
 ↓
验证 type=refresh
 ↓
读取 jti
 ↓
Redis 检查 Session
 ↓
Session 有效
 ↓
签发新的 Access Token
```

退出登录：

```text
POST /api/auth/logout
 ↓
读取 Refresh Token
 ↓
获取 jti
 ↓
删除 Redis Session
 ↓
删除 Refresh Cookie
```

这样即使旧 Refresh Token 还没有达到 JWT `exp`，退出之后也不能继续使用。

## 四、Vue 前端改造

检查：

```text
frontend/src/
```

重点检查现有：

```text
stores/auth.ts
api/http.ts
views/Login.vue
router
App.vue / main.ts
```

不要重新实现已有功能。

Pinia 中保存：

```typescript
accessToken
user
authenticated
```

Access Token 只保存在运行时内存。

不要使用：

```typescript
localStorage.setItem('token', ...)
```

保存 Access Token。

## 五、Axios Request Interceptor

所有正常 API 请求自动添加：

```http
Authorization: Bearer <access_token>
```

例如：

```text
Axios Request
 ↓
读取 Pinia accessToken
 ↓
如果存在
 ↓
Authorization: Bearer xxx
```

同时正确配置：

```typescript
withCredentials: true
```

让浏览器能够在需要时携带 Refresh Token Cookie。

## 六、Axios Response Interceptor

如果普通业务请求：

```text
401 Unauthorized
```

自动执行：

```text
401
 ↓
检查当前请求是否已经重试
 ↓
POST /auth/refresh
 ↓
成功
 ↓
保存新的 Access Token
 ↓
更新 Authorization
 ↓
重新执行原请求
```

必须防止：

```text
401
→ refresh
→ 401
→ refresh
→ 401
→ refresh
→ 无限循环
```

给原请求增加类似：

```typescript
_retry = true
```

的标记。

`/auth/login`、`/auth/refresh` 本身不要触发无限自动刷新。

## 七、并发刷新问题

需要处理多个请求同时返回 401 的情况。

例如：

```text
request A → 401
request B → 401
request C → 401
```

不能同时发送：

```text
3 个 /auth/refresh
```

应该实现 Single Flight / Refresh Lock：

```text
A → 发起 refresh

B ─┐
C ─┼→ 等待同一个 refresh Promise
D ─┘

refresh 成功
 ↓
更新 Access Token
 ↓
A/B/C/D 分别重试
```

避免 Refresh Token 并发刷新导致异常。

## 八、应用初始化恢复登录状态

这是实现“F5 刷新不重新登录”的关键。

Vue 应用启动：

```text
main.ts / App.vue
 ↓
authStore.initialize()
 ↓
POST /auth/refresh
```

如果成功：

```text
获取新的 Access Token
 ↓
恢复 Pinia 用户状态
 ↓
进入系统
```

如果失败：

```text
Refresh Token 不存在/过期/失效
 ↓
保持未登录状态
 ↓
访问受保护页面时跳转 /login
```

增加：

```text
authInitialized
```

状态。

Router Guard 必须等待认证初始化完成，避免：

```text
F5
 ↓
Pinia 暂时没有 Token
 ↓
Router 误认为没有登录
 ↓
提前跳转 Login
 ↓
此时 refresh 才成功
```

造成页面闪烁。

正确顺序：

```text
Vue 启动
 ↓
initialize auth
 ↓
尝试 refresh
 ↓
确定最终认证状态
 ↓
Router Guard
 ↓
决定进入页面还是 Login
```

## 九、安全要求

至少检查：

```text
HttpOnly
Secure
SameSite
CORS
allow_credentials
JWT exp
JWT type
JWT jti
Redis TTL
Logout revoke
```

如果前后端不同 Origin，需要检查 FastAPI CORS：

```text
allow_credentials=True
```

并且不能错误地使用：

```text
allow_origins=["*"]
```

配合 Credential Cookie。

开发环境和生产环境的 Cookie `Secure` 配置需要区分，避免本地 HTTP 环境因为 Secure Cookie 导致登录失败。

不要在日志中输出：

```text
密码
完整 JWT
Refresh Token
Cookie
JWT_SECRET
```

## 十、不要过度设计

本次重点是：

```text
JWT
+
Access Token
+
Refresh Token
+
HttpOnly Cookie
+
Redis Session
+
Axios Interceptor
+
Pinia
```

不要为了本次改造额外引入 OAuth2 Server、Keycloak 等大型组件。

优先复用当前项目代码。

## 十一、修改方式

先完整分析现有认证调用链，再修改代码。

不要直接推翻当前认证系统。

修改完成后告诉我：

1. 修改了哪些文件
2. 每个文件为什么修改
3. 登录完整调用链
4. F5 刷新后的调用链
5. Access Token 过期后的调用链
6. Refresh Token 过期后的调用链
7. Logout 调用链
8. Redis 中新增了哪些 Key
9. Cookie 如何配置
10. Axios 如何避免无限刷新
11. 多个 401 如何避免同时 Refresh
12. 如何本地验证

最后给出可以直接执行的验证步骤，例如：

```text
1. 启动 Redis
2. 启动 FastAPI
3. 启动 Vue
4. 登录
5. F5 刷新验证
6. 查看 Redis Refresh Session
7. 模拟 Access Token 过期
8. 验证自动 Refresh
9. Logout
10. 验证旧 Refresh Token 无法继续使用
```

如果当前项目实现和以上设计存在冲突，以当前项目实际代码结构为准进行最小侵入式调整，不要为了匹配提示词而破坏已有功能。