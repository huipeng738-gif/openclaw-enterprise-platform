import hashlib
import hmac
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import jwt
from pymysql.err import IntegrityError
import redis.asyncio as redis
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .clients.ragflow import RagflowClient, RagflowError
from .clients.business_db import BusinessDatabase, BusinessDatabaseError, BusinessDatabaseTimeout
from .routers.knowledge import build_knowledge_router
from .routers.business import build_business_router
from .routers.metrics import build_metrics_router
from .routers.actions import build_action_router
from .services.observability import summarize as summarize_observability
from .services.runtime import gateway_status
from .services.settings import admit_task, dependency_status, task_policy, update_task_policy
from .services.users import UserStore, migrate_legacy_users
from .services.agents import agent_roster, available_models, create_agent, enabled_ids, set_agent_enabled

SECRET = os.getenv('JWT_SECRET', '')
if len(SECRET) < 32:
    raise RuntimeError('JWT_SECRET must be at least 32 characters')
r = redis.from_url(os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'), decode_responses=True)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '7'))
REFRESH_COOKIE_SECURE = os.getenv('REFRESH_COOKIE_SECURE', 'true').lower() == 'true'
REFRESH_COOKIE = 'openclaw_refresh'
REFRESH_COOKIE_PATH = '/api/auth'
if ACCESS_TOKEN_EXPIRE_MINUTES <= 0 or REFRESH_TOKEN_EXPIRE_DAYS <= 0:
    raise RuntimeError('Token lifetimes must be positive')
ROLES = {'viewer': {'tasks:read', 'agents:read'},
         'operator': {'tasks:read', 'tasks:write', 'agents:read', 'knowledge:read', 'knowledge:retrieve',
                      'business:read'},
         'admin': {'tasks:read', 'tasks:write', 'agents:read', 'agents:write', 'knowledge:read', 'knowledge:write',
                   'knowledge:delete', 'knowledge:retrieve', 'business:read', 'audit:read', 'users:write'}}
TERMINAL = {'completed', 'failed', 'cancelled', 'timed_out'}


# 使用异步上下文管理器管理 FastAPI 生命周期
@asynccontextmanager
async def lifespan(app):
    # 1. 检查 Redis 是否可以连接
    await r.ping()

    # 2. 创建 MySQL 业务数据库连接池
    # 并保存到 FastAPI 应用状态中
    app.state.business_db = await BusinessDatabase.from_env()

    # 3. 判断 users 对象是否已经存在
    if getattr(app.state, 'users', None) is None:

        # 4. MySQL 不可用则禁止应用启动
        if app.state.business_db is None:
            raise RuntimeError('MySQL account store is required')

        # 5. 创建用户管理对象，传入 MySQL 连接池
        app.state.users = UserStore(app.state.business_db.pool)

        # 6. 检查 MySQL 用户表结构是否存在
        await app.state.users.ensure_schema()

        # 7. 将旧版 Redis 用户数据迁移到 MySQL
        await migrate_legacy_users(r, app.state.users)

    # 8. 创建 RAGFlow 客户端
    app.state.ragflow = RagflowClient.from_env()

    try:
        # 9. 启动初始化完成，应用开始提供服务
        yield

    finally:
        # 10. 应用关闭时，释放 RAGFlow 客户端
        if app.state.ragflow:
            await app.state.ragflow.close()

        # 11. 关闭 MySQL 连接池
        if app.state.business_db:
            await app.state.business_db.close()

        # 12. 关闭 Redis 客户端连接
        await r.aclose()


app = FastAPI(title='OpenClaw Enterprise API', lifespan=lifespan)


# 将 RAGFlow 异常转换为统一的 HTTP 错误响应。
@app.exception_handler(RagflowError)
async def ragflow_error_handler(_request, exc: RagflowError):
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})


# 将业务数据库超时和连接异常映射为不暴露 SQL 及凭证的响应。
@app.exception_handler(BusinessDatabaseError)
async def business_error_handler(_request, exc: BusinessDatabaseError):
    code = 504 if isinstance(exc, BusinessDatabaseTimeout) else 503
    return JSONResponse(status_code=code, content={'detail': str(exc)})


class Login(BaseModel):
    username: str
    password: str


class UserCreate(Login):
    role: str


class UserRoleChange(BaseModel):
    role: str


class UserAvailability(BaseModel):
    disabled: bool


class UserPasswordReset(BaseModel):
    password: str


class TaskPolicyChange(BaseModel):
    version: int = Field(ge=0)
    defaultTimeoutSeconds: int = Field(ge=10, le=1800)
    submissionsPaused: bool


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    agent: str = Field(default='coordinator', pattern=r'^[a-zA-Z0-9_-]{1,48}$')
    timeout_seconds: int | None = Field(default=None, ge=10, le=1800)


class AgentCreate(BaseModel):
    id: str = Field(pattern=r'^[a-z][a-z0-9_-]{1,47}$')
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default='', max_length=500)
    model: str = Field(min_length=3, max_length=160)
    tool_policy: str = Field(default='minimal', pattern=r'^(minimal|business_readonly)$')


class DatabaseQuestion(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)


# 使用随机盐和 PBKDF2 生成密码摘要，返回盐与摘要的组合。
def password_hash(password, salt=None):
    # 1. 如果没有传入盐值，就生成一个新的随机盐
    salt = salt or secrets.token_hex(16)

    # 2. 使用 PBKDF2-HMAC-SHA256 计算密码摘要
    digest = hashlib.pbkdf2_hmac(
        'sha256',  # 哈希算法
        password.encode(),  # 明文密码转换为 UTF-8 字节
        bytes.fromhex(salt),  # 将十六进制盐值转换为字节
        600_000  # 迭代次数：60 万次
    )

    # 3. 将盐值和摘要拼接后返回
    return f'{salt}${digest.hex()}'


# 使用存储的盐校验密码，以恒定时间比较摘要；格式异常时返回 False。
def password_valid(password, stored):
    try:
        # 1. 从数据库保存的 salt$hash 中提取 Salt
        salt, _ = stored.split('$', 1)

        # 2. 使用原 Salt 对用户输入的密码重新计算摘要
        # 3. 比较新摘要与数据库摘要是否一致
        return hmac.compare_digest(
            password_hash(password, salt),
            stored
        )

    # 4. 数据格式或类型异常时，返回密码校验失败
    except (ValueError, TypeError):
        return False


# 将操作人、动作、对象和结果写入 Redis audit Stream，保留约一万条记录。
async def audit(actor, action, target, outcome='ok'):
    await r.xadd('audit',
                 {'at': datetime.now(timezone.utc).isoformat(), 'actor': actor, 'action': action, 'target': target,
                  'outcome': outcome}, maxlen=10000, approximate=True)


# 校验 JWT 签名、有效期及签发者，再读取 Redis 用户并确认账号可用。
async def identity(token):
    try:
        p = jwt.decode(token, SECRET, algorithms=['HS256'], issuer='enterprise-bff',
                       options={'require': ['sub', 'type', 'exp']})
        if p.get('type') != 'access':
            raise ValueError('access token required')
        user = await app.state.users.get(p['sub'])
        if not user or user['role'] not in ROLES or user['disabled']:
            raise ValueError('inactive')
        if p.get('sessionVersion', 0) != user['session_version']:
            raise ValueError('session revoked')
        return {'username': p['sub'], 'role': user['role']}
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'invalid credentials')


# 从 Authorization 请求头提取 Bearer 令牌并解析当前用户。
async def current(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'bearer token required')
    return await identity(authorization[7:])


# 为指定权限生成 FastAPI 依赖，由当前用户角色决定是否放行。
def permission(name):
    # 检查当前角色是否包含所需权限，未授权时返回 403。
    async def check(user=Depends(current)):
        if name not in ROLES[user['role']]:
            raise HTTPException(403, 'permission denied')
        return user

    return check


# 读取任务并校验归属，仅任务所有者或管理员可访问。
async def task_for(task_id, user):
    raw = await r.get(f'task:{task_id}')
    if not raw:
        raise HTTPException(404, 'task not found')
    task = json.loads(raw)
    if task['owner'] != user['username'] and user['role'] != 'admin':
        raise HTTPException(403, 'permission denied')
    return task


# 通过 Redis ping 检查服务依赖是否可用。
@app.get('/health')
async def health():
    await r.ping()
    return {'status': 'ok'}


# 返回 Worker 最近一次只读 Gateway 握手的状态，过期或未上报时保持未知。
@app.get('/api/runtime/gateway')
async def runtime_gateway(user=Depends(permission('tasks:read'))):
    return await gateway_status(r)


# 注册 POST 登录接口，访问地址为 /api/auth/login。
# 用户提交用户名和密码后，FastAPI 自动将请求体解析为 Login 对象。
# request 用于获取当前请求信息、应用状态和 Cookie；
# response 用于设置响应头以及向浏览器写入 Cookie。
@app.post('/api/auth/login')
async def login(body: Login, request: Request, response: Response):
    # 检查请求来源是否合法，防止不可信站点利用浏览器 Cookie 发起跨站请求。
    # 如果来源不符合安全策略，通常会直接拒绝请求。
    cookie_origin_guard(request)

    # 设置 HTTP 响应头，禁止浏览器和中间缓存存储登录响应。
    # 避免 Access Token 等敏感登录信息被缓存。
    response.headers['Cache-Control'] = 'no-store'

    # 根据用户名生成 Redis Key，例如 login-attempts:admin。
    # 每次登录请求通过 INCR 将计数加 1。
    # 第一次请求设置 60 秒过期时间，后续请求不会重置该时间。
    # 如果在 60 秒内超过 10 次登录请求，就返回 HTTP 429，限制频繁尝试密码。
    # Redis Key 到期后自动删除，计数重新开始。
    # 注意：这里统计的是登录请求次数，而不仅仅是密码错误次数。
    attempts = await r.incr(f'login-attempts:{body.username[:80]}')
    if attempts == 1:
        await r.expire(f'login-attempts:{body.username[:80]}', 60)
    if attempts > 10:
        raise HTTPException(429, 'too many login attempts; try again later')

    # 根据用户提交的用户名，从用户存储中查询用户信息。
    # request.app.state.users 是应用启动时挂载的用户存储对象，
    # get() 返回用户记录，通常包含密码哈希、角色、禁用状态和会话版本等信息。
    user = await request.app.state.users.get(body.username)

    # 验证三个条件：
    # 1. 用户是否存在；
    # 2. 用户输入的密码是否与数据库保存的密码哈希匹配；
    # 3. 用户账号是否被禁用。
    # 只要任意条件不满足，就记录登录失败审计日志，并返回 HTTP 401。
    # 统一返回 invalid credentials，避免暴露具体是用户名错误还是密码错误。
    # password_valid() 用于验证密码，不需要保存或比较明文密码。
    if not user or not password_valid(body.password, user['password_hash']) or user['disabled']:
        await audit(body.username[:80], 'auth.login', '-', 'denied')
        raise HTTPException(401, 'invalid credentials')

    # 用户验证通过后，记录登录成功的审计日志。
    # auth.login 表示登录操作，默认结果由 audit() 的实现决定。
    await audit(body.username, 'auth.login', '-')

    # 登录成功后，删除 Redis 中当前用户的登录尝试次数。
    # 这样用户下一次登录时，计数会重新从 1 开始。
    await r.delete(f'login-attempts:{body.username[:80]}')

    # 获取当前 UTC 时间，作为 Token 的签发时间和会话创建时间。
    now = datetime.now(timezone.utc)

    # 计算 Refresh Token 的过期时间。
    # REFRESH_TOKEN_EXPIRE_DAYS 是配置的有效天数。
    # 例如配置为 7，则 Refresh Token 在签发 7 天后过期。
    expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # 生成随机且唯一的 Token ID（jti）。
    # jti 用于标识一次 Refresh Token 会话，
    # 方便在 Redis 中查找、撤销和管理该会话。
    jti = uuid.uuid4().hex

    # 将 Refresh Token 对应的会话信息保存到 Redis。
    # Redis Key 格式为 auth:refresh:唯一jti。
    # username 表示当前登录用户；
    # created_at 表示会话创建时间；
    # expires_at 表示会话过期时间。
    # ex 设置 Redis Key 的有效期，单位为秒。
    # 这样 Refresh Token 到期后，对应的 Redis 会话也会自动过期。
    # Redis 保存会话记录，可以让服务端主动撤销 Refresh Token，
    # 而不只是依赖 JWT 自身的过期时间。
    await r.set(f'auth:refresh:{jti}', json.dumps({
        'username': body.username,
        'created_at': now.isoformat(),
        'expires_at': expires.isoformat()
    }), ex=REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    # 使用 JWT 生成 Refresh Token。
    # sub：当前用户的用户名；
    # iss：Token 签发者，这里是 enterprise-bff；
    # type：Token 类型，标记为 refresh；
    # jti：当前 Refresh Token 对应的唯一会话 ID；
    # sessionVersion：用户会话版本，可用于配合服务端校验实现会话失效；
    # iat：Token 签发时间；
    # exp：Token 过期时间。
    # SECRET 是服务端的 JWT 签名密钥。
    # HS256 是对称签名算法，用于保证 Token 内容没有被非法篡改。
    # JWT 是经过签名的凭证，并不是对载荷内容进行加密。
    refresh_token = jwt.encode({
        'sub': body.username,
        'iss': 'enterprise-bff',
        'type': 'refresh',
        'jti': jti,
        'sessionVersion': user['session_version'],
        'iat': now,
        'exp': expires
    }, SECRET, algorithm='HS256')

    # 从当前浏览器请求的 Cookie 中读取旧 Refresh Token。
    # REFRESH_COOKIE 是 Refresh Token 对应的 Cookie 名称。
    # refresh_claims() 用于解析和校验旧 Token，
    # 如果校验失败，则通常返回空值。
    old = refresh_claims(request.cookies.get(REFRESH_COOKIE, ''))

    # 如果浏览器携带有效的旧 Refresh Token，
    # 就根据旧 Token 的 jti 删除对应 Redis 会话。
    # 这样当前浏览器重新登录后，旧 Refresh Token 将无法继续刷新 Access Token。
    # 注意：这不会自动使所有旧 Access Token 立即失效。
    if old:
        await r.delete(f'auth:refresh:{old["jti"]}')

    # 将新生成的 Refresh Token 写入浏览器 Cookie。
    #
    # REFRESH_COOKIE：Cookie 名称。
    # refresh_token：Cookie 保存的 Refresh Token。
    # httponly=True：禁止前端 JavaScript 读取 Cookie，降低 Token 被 XSS 窃取的风险。
    # secure=REFRESH_COOKIE_SECURE：配置为 True 时，仅通过 HTTPS 发送 Cookie。
    # samesite='lax'：限制部分跨站请求携带 Cookie，降低 CSRF 风险。
    # path=REFRESH_COOKIE_PATH：限制 Cookie 在指定路径下发送。
    # max_age：Cookie 的最大有效时长，单位为秒。
    # expires：Cookie 的绝对过期时间。
    # 浏览器会在符合 Cookie 安全策略的后续请求中自动携带它。
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=REFRESH_COOKIE_SECURE,
        samesite='lax',
        path=REFRESH_COOKIE_PATH,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        expires=expires
    )

    # 登录成功后，调用 access_response() 生成登录响应。
    # 传入用户名、角色和会话版本。
    # 通常该函数负责生成 Access Token，并返回前端需要的登录信息，
    # 具体返回内容取决于 access_response() 的实际实现。
    # 前端可使用 Access Token 访问需要身份认证的业务接口。
    return access_response(
        body.username,
        user['role'],
        user['session_version']
    )


def cookie_origin_guard(request: Request):
    # 同源部署（Vite/Nginx），拒绝跨源 Cookie 认证相关操作

    # 1. 获取请求头中的 Origin
    origin = request.headers.get('origin')

    # 2. 获取允许的来源地址
    expected = (
            os.getenv('AUTH_ORIGIN', '').rstrip('/')
            or f'{request.url.scheme}://{request.headers.get("host", "")}'
    )

    # 3. 校验 Origin 是否符合预期
    if origin and origin.rstrip('/') != expected:
        raise HTTPException(
            403,
            'cross-origin authentication request denied'
        )

    # 4. 检查请求是否属于跨站请求
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(
            403,
            'cross-site authentication request denied'
        )


def refresh_claims(token: str):
    try:
        claims = jwt.decode(token, SECRET, algorithms=['HS256'], issuer='enterprise-bff',
                            options={'require': ['sub', 'type', 'jti', 'iat', 'exp']})
        if claims['type'] != 'refresh' or not isinstance(claims['jti'], str) or not claims['jti']:
            return None
        return claims
    except jwt.PyJWTError:
        return None


def access_response(username: str, role: str, session_version: int = 0):
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': username, 'iss': 'enterprise-bff', 'type': 'access', 'iat': now,
                        'sessionVersion': session_version,
                        'exp': now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
                       SECRET, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'role': role,
            'user': {'username': username, 'role': role}}


@app.post('/api/auth/refresh')
async def refresh(request: Request, response: Response):
    cookie_origin_guard(request)
    response.headers['Cache-Control'] = 'no-store'
    claims = refresh_claims(request.cookies.get(REFRESH_COOKIE, ''))
    if not claims:
        raise HTTPException(401, 'invalid refresh session')
    raw = await r.get(f'auth:refresh:{claims["jti"]}')
    if not raw or json.loads(raw)['username'] != claims['sub']:
        raise HTTPException(401, 'invalid refresh session')
    user = await request.app.state.users.get(claims['sub'])
    if not user or user['role'] not in ROLES or user['disabled']:
        raise HTTPException(401, 'inactive account')
    if claims.get('sessionVersion', 0) != user['session_version']:
        raise HTTPException(401, 'invalid refresh session')
    return access_response(claims['sub'], user['role'], user['session_version'])


@app.post('/api/auth/logout')
async def logout(request: Request, response: Response):
    cookie_origin_guard(request)
    claims = refresh_claims(request.cookies.get(REFRESH_COOKIE, ''))
    if claims:
        await r.delete(f'auth:refresh:{claims["jti"]}')
        await audit(claims['sub'], 'auth.logout', '-')
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH,
                           secure=REFRESH_COOKIE_SECURE, httponly=True, samesite='lax')
    return {'status': 'ok'}


# 返回认证依赖解析出的当前用户名和角色。
@app.get('/api/auth/me')
async def me(user=Depends(current)):
    return user


# 校验新用户信息，避免覆盖已有密码，并记录创建审计。
@app.post('/api/users', status_code=201)
async def add_user(body: UserCreate, user=Depends(permission('users:write'))):
    if body.role not in ROLES or len(body.password) < 12 or not body.username.isidentifier() or len(body.username) > 80:
        raise HTTPException(400, 'invalid username, role or password')
    try:
        await app.state.users.create(body.username, password_hash(body.password), body.role)
    except IntegrityError:
        raise HTTPException(409, 'user exists')
    await audit(user['username'], 'user.create', body.username)
    return {'username': body.username, 'role': body.role}


# 扫描账号 Hash 并只返回非敏感字段；不公开密码摘要或会话版本。
@app.get('/api/users')
async def list_users(user=Depends(permission('users:write'))):
    return await app.state.users.list()


# MySQL 事务统一保护账号变更及最后一个可用管理员。
async def change_user(username, **fields):
    updated = await app.state.users.change(username, **fields)
    if updated is None:
        raise HTTPException(404, 'user not found')
    if updated is False:
        raise HTTPException(409, 'last active admin must remain enabled')
    return updated


# 修改账号角色，当前权限从 Redis 即时生效并撤销旧会话。
@app.put('/api/users/{username}/role')
async def set_user_role(username: str, body: UserRoleChange, user=Depends(permission('users:write'))):
    if body.role not in ROLES:
        raise HTTPException(400, 'invalid role')
    updated = await change_user(username, role=body.role)
    await audit(user['username'], 'user.role', username)
    return updated


# 启停账号，停用后旧会话不可在恢复时重新使用。
@app.put('/api/users/{username}/availability')
async def set_user_availability(username: str, body: UserAvailability,
                                user=Depends(permission('users:write'))):
    updated = await change_user(username, disabled=body.disabled)
    await audit(user['username'], 'user.disable' if body.disabled else 'user.enable', username)
    return updated


# 重置密码并递增会话版本，所有旧 Access/Refresh Token 立即失效。
@app.put('/api/users/{username}/password')
async def reset_user_password(username: str, body: UserPasswordReset,
                              user=Depends(permission('users:write'))):
    if len(body.password) < 12:
        raise HTTPException(400, 'password must be at least 12 characters')
    await change_user(username, password_hash=password_hash(body.password))
    await audit(user['username'], 'user.password_reset', username)
    return {'username': username, 'reset': True}


# 读取持久化任务策略，供管理员看到实际生效值和版本。
@app.get('/api/settings/task-policy')
async def get_task_policy(user=Depends(permission('users:write'))):
    return await task_policy(r)


# 按版本保存超时与暂停开关，避免管理员并发覆盖。
@app.put('/api/settings/task-policy')
async def set_task_policy(body: TaskPolicyChange, user=Depends(permission('users:write'))):
    updated = await update_task_policy(r, body.version, body.defaultTimeoutSeconds, body.submissionsPaused)
    if updated is None:
        raise HTTPException(409, 'task policy changed; reload and retry')
    await audit(user['username'], 'settings.task_policy', f'version:{updated["version"]}')
    return updated


# 实际探测可访问依赖并返回最小诊断信息。
@app.get('/api/settings/dependencies')
async def get_dependencies(request: Request, user=Depends(permission('users:write'))):
    return await dependency_status(r, request.app.state.business_db, request.app.state.ragflow)


# 返回 Gateway 中确实存在且平台启用的 Agent，保留原有 id/name 字段。
@app.get('/api/agents')
async def agents(user=Depends(permission('agents:read'))):
    return await agent_roster(r)


# 展示 Gateway 中全部普通 Agent 的真实配置及近 30 天平台任务统计。
@app.get('/api/agents/manage')
async def manage_agents(user=Depends(permission('agents:read'))):
    return await agent_roster(r, include_unavailable=True)


# 返回当前 Gateway 可选模型，供新增 Agent 表单选择。
@app.get('/api/agents/models')
async def agent_models(user=Depends(permission('agents:write'))):
    return await available_models()


# 创建真实 Gateway Agent，设置 Tool 策略后登记平台元数据并写审计。
@app.post('/api/agents', status_code=201)
async def add_agent(body: AgentCreate, user=Depends(permission('agents:write'))):
    agent_id = await create_agent(r, body)
    await audit(user['username'], 'agent.create', agent_id)
    return {'id': agent_id}


# 管理员切换 Agent 在平台聊天任务中的可用性，不删除 Gateway 配置。
@app.post('/api/agents/{agent_id}/availability')
async def agent_availability(agent_id: str, enabled: bool, user=Depends(permission('agents:write'))):
    await set_agent_enabled(r, agent_id, enabled)
    await audit(user['username'], 'agent.enable' if enabled else 'agent.disable', agent_id)
    return {'id': agent_id, 'enabled': enabled}


# 统计当前用户可见任务的运行与完成数量，并返回 Agent 数量。
@app.get('/api/dashboard')
async def dashboard(user=Depends(permission('tasks:read'))):
    tasks = [json.loads(v) for k in await r.smembers('tasks:all') if (v := await r.get(f'task:{k}'))]
    visible = [t for t in tasks if user['role'] == 'admin' or t['owner'] == user['username']]
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    terminal = [t for t in visible if t['status'] in TERMINAL]
    completed = sum(t['status'] == 'completed' for t in terminal)
    recent = sorted(visible, key=lambda t: t.get('createdAt', ''), reverse=True)

    def summary(task):
        return {key: task.get(key) for key in ('id', 'prompt', 'agent', 'status', 'createdAt', 'latencyMs')}

    observability = await summarize_observability(r, recent)
    trend = []
    for days_ago in range(6, -1, -1):
        day = (now - timedelta(days=days_ago)).date().isoformat()
        trend.append({'date': day, 'count': sum(t.get('createdAt', '').startswith(day) for t in visible)})
    return {'agentCount': len(await enabled_ids(r)),
            'runningTasks': sum(t['status'] == 'running' for t in visible),
            'completedTasks': completed,
            'todayTasks': sum(t.get('createdAt', '').startswith(today) for t in visible),
            'successRate': round(completed / len(terminal) * 100, 1) if terminal else None,
            'taskTrend': trend,
            'recentTasks': [summary(t) for t in recent[:5]],
            'failedTasks': [summary(t) for t in recent if t['status'] in {'failed', 'timed_out'}][:5],
            'observability': observability, 'gateway': await gateway_status(r)}


async def enqueue(body, user, kind='chat'):
    if kind != 'database' and body.agent not in await enabled_ids(r):
        raise HTTPException(400, 'agent not allowed')
    task_id = uuid.uuid4().hex

    # 任务策略与入队使用 WATCH/MULTI 建立顺序；Worker 使用快照中的有效超时。
    def task_factory(policy):
        return {'id': task_id, 'owner': user['username'], 'prompt': body.prompt, 'agent': body.agent,
                'kind': kind, 'timeoutSeconds': body.timeout_seconds or policy['defaultTimeoutSeconds'],
                'status': 'queued', 'createdAt': datetime.now(timezone.utc).isoformat(),
                'result': None, 'error': None, 'traceId': uuid.uuid4().hex,
                'threadId': None, 'model': None, 'tokenUsage': None}

    task = await admit_task(r, task_id, task_factory)
    if task is None:
        raise HTTPException(503, 'new task submissions are paused')
    await audit(user['username'], 'task.create', task_id)
    return task


# 受理任务创建请求，返回入队后的任务记录。
@app.post('/api/tasks', status_code=202)
async def create_task(body: TaskCreate, user=Depends(permission('tasks:write'))):
    return await enqueue(body, user)


@app.post('/api/chat', status_code=202)
async def chat(body: TaskCreate, user=Depends(permission('tasks:write'))):
    # 依赖链先校验 Bearer JWT 和 tasks:write 权限，通过后才创建任务。
    return await enqueue(body, user)


# 受理开放式数据库分析问题，继续使用现有任务队列和状态接口。
@app.post('/api/database/questions', status_code=202)
async def database_question(body: DatabaseQuestion, user=Depends(permission('business:read'))):
    task = await enqueue(TaskCreate(prompt=body.prompt, agent='database'), user, kind='database')
    await audit(user['username'], 'database.question', task['id'])
    return task


# 按创建时间倒序返回当前用户可见的最近一百个任务。
@app.get('/api/tasks')
async def list_tasks(user=Depends(permission('tasks:read'))):
    tasks = [json.loads(v) for k in await r.smembers('tasks:all') if (v := await r.get(f'task:{k}'))]
    return sorted((t for t in tasks if user['role'] == 'admin' or t['owner'] == user['username']),
                  key=lambda t: t['createdAt'], reverse=True)[:100]


# 校验任务访问权限后返回任务状态与结果。
@app.get('/api/tasks/{task_id}')
async def get_task(task_id: str, user=Depends(permission('tasks:read'))):
    return await task_for(task_id, user)


# 校验任务访问权限后读取最多两百条历史事件。
@app.get('/api/tasks/{task_id}/events')
async def task_events(task_id: str, after: str = Query('0-0', pattern=r'^\d+-\d+$'),
                      limit: int = Query(200, ge=1, le=200), user=Depends(permission('tasks:read'))):
    await task_for(task_id, user)
    return [{'id': key, **json.loads(fields['data'])} for key, fields in
            await r.xrange(f'events:{task_id}', min=f'({after}', count=limit)]


# 为未结束任务设置一小时有效的取消标记，交由 Worker 处理并记录审计。
@app.post('/api/tasks/{task_id}/cancel')
async def cancel(task_id: str, user=Depends(permission('tasks:write'))):
    task = await task_for(task_id, user)
    if task['status'] in TERMINAL:
        raise HTTPException(409, 'task already terminal')
    await r.set(f'cancel:{task_id}', '1', ex=3600)
    await audit(user['username'], 'task.cancel', task_id)
    return {'accepted': True}


# 根据失败、取消或超时任务创建新任务，保留原任务并记录重试关系。
@app.post('/api/tasks/{task_id}/retry', status_code=202)
async def retry(task_id: str, user=Depends(permission('tasks:write'))):
    old = await task_for(task_id, user)
    if old['status'] not in {'failed', 'cancelled', 'timed_out'}:
        raise HTTPException(409, 'only unsuccessful terminal tasks can be retried')
    kind = old.get('kind', 'chat')
    new = await enqueue(TaskCreate(prompt=old['prompt'], agent=old['agent'], timeout_seconds=old['timeoutSeconds']),
                        user, kind=kind)
    await audit(user['username'], 'task.retry', f'{task_id}->{new["id"]}')
    return new


# 校验任务归属后签发绑定用户与任务、有效期三十秒的一次性连接票据。
@app.post('/api/tasks/{task_id}/ws-ticket')
async def ws_ticket(task_id: str, user=Depends(permission('tasks:read'))):
    await task_for(task_id, user)
    ticket = secrets.token_urlsafe(32)
    await r.set(f'ws-ticket:{ticket}', f'{user["username"]}:{task_id}', ex=30)
    return {'ticket': ticket}


@app.websocket('/ws/tasks/{task_id}')
async def ws_task(ws: WebSocket, task_id: str, ticket: str = '',
                  after: str = Query('0-0', pattern=r'^\d+-\d+$')):
    # ws-ticket 有效期短且只允许使用一次，验证通过后才接受 WebSocket。
    ownership = await r.getdel(f'ws-ticket:{ticket}') if ticket else None
    if not ownership or ownership.split(':', 1)[-1] != task_id:
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        latest = after
        while True:
            raw = await r.get(f'task:{task_id}')
            if not raw:
                break
            task = json.loads(raw)
            # 先发任务快照，再按 Redis Stream 游标推事件；终态快照带最终结果或错误。
            await ws.send_json({'type': 'snapshot', 'task': task})
            # 终态任务也须排空回放事件，避免首批 50 条之后的 Tool/文本丢失。
            if task['status'] in TERMINAL:
                rows = await r.xrange(f'events:{task_id}', min=f'({latest}', count=50)
                events = [(f'events:{task_id}', rows)]
            else:
                events = await r.xread({f'events:{task_id}': latest}, count=50, block=1000)
            batch_size = 0
            for _, rows in events:
                batch_size += len(rows)
                for event_id, fields in rows:
                    latest = event_id
                    await ws.send_json({'type': 'event', 'id': event_id, 'event': json.loads(fields['data'])})
            if task['status'] in TERMINAL and batch_size < 50:
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass


# 返回最近一百条审计记录，按时间倒序排列。
@app.get('/api/audit')
async def audit_list(user=Depends(permission('audit:read'))):
    return [{'id': k, **v} for k, v in await r.xrevrange('audit', count=100)]


# 以恒定时间比较插件请求凭证，未配置或不匹配时拒绝访问。
def plugin_guard(token: str = Header(default='', alias='X-Plugin-Token')):
    configured = os.getenv('PLUGIN_SERVICE_TOKEN', '')
    if not configured or not hmac.compare_digest(token, configured):
        raise HTTPException(401, 'plugin credential required')


app.include_router(build_knowledge_router(permission, plugin_guard, audit, lambda: r))
app.include_router(build_action_router(permission, plugin_guard, audit, lambda: r, lambda: app.state.users))
app.include_router(build_business_router(permission, plugin_guard, audit))
app.include_router(build_metrics_router(permission, plugin_guard, audit))
