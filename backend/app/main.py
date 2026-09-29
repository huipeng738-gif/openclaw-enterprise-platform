import hashlib
import hmac
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import jwt
import redis.asyncio as redis
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .clients.ragflow import RagflowClient, RagflowError
from .routers.knowledge import build_knowledge_router

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
         'operator': {'tasks:read', 'tasks:write', 'agents:read', 'knowledge:read', 'knowledge:retrieve'},
         'admin': {'tasks:read', 'tasks:write', 'agents:read', 'knowledge:read', 'knowledge:write',
                   'knowledge:delete', 'knowledge:retrieve', 'audit:read', 'users:write'}}
TERMINAL = {'completed', 'failed', 'cancelled', 'timed_out'}


# 启动时检查 Redis 并创建 RAGFlow 客户端，退出时释放连接。
@asynccontextmanager
async def lifespan(app):
    await r.ping()
    app.state.ragflow = RagflowClient.from_env()
    try:
        yield
    finally:
        if app.state.ragflow:
            await app.state.ragflow.close()
        await r.aclose()


app = FastAPI(title='OpenClaw Enterprise API', lifespan=lifespan)


# 将 RAGFlow 异常转换为统一的 HTTP 错误响应。
@app.exception_handler(RagflowError)
async def ragflow_error_handler(_request, exc: RagflowError):
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})


class Login(BaseModel):
    username: str
    password: str


class UserCreate(Login):
    role: str


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    agent: str = Field(default='coordinator', pattern=r'^[a-zA-Z0-9_-]{1,48}$')
    timeout_seconds: int = Field(default=180, ge=10, le=1800)


class Metric(BaseModel):
    metric: str = Field(min_length=1, max_length=120)
    period: str = '7d'


# 使用随机盐和 PBKDF2 生成密码摘要，返回盐与摘要的组合。
def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000)
    return f'{salt}${digest.hex()}'


# 使用存储的盐校验密码，以恒定时间比较摘要；格式异常时返回 False。
def password_valid(password, stored):
    try:
        salt, _ = stored.split('$', 1)
        return hmac.compare_digest(password_hash(password, salt), stored)
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
        user = await r.hgetall(f'user:{p["sub"]}')
        if user.get('role') not in ROLES or user.get('disabled') == '1':
            raise ValueError('inactive')
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


@app.post('/api/auth/login')
async def login(body: Login, request: Request, response: Response):
    cookie_origin_guard(request)
    response.headers['Cache-Control'] = 'no-store'
    # Bound repeated password guesses without writing credentials to the audit stream.
    attempts = await r.incr(f'login-attempts:{body.username[:80]}')
    if attempts == 1:
        await r.expire(f'login-attempts:{body.username[:80]}', 60)
    if attempts > 10:
        raise HTTPException(429, 'too many login attempts; try again later')
    user = await r.hgetall(f'user:{body.username}')
    if not user or not password_valid(body.password, user.get('password', '')) or user.get('disabled') == '1':
        await audit(body.username[:80], 'auth.login', '-', 'denied')
        raise HTTPException(401, 'invalid credentials')
    await audit(body.username, 'auth.login', '-')
    await r.delete(f'login-attempts:{body.username[:80]}')
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = uuid.uuid4().hex
    await r.set(f'auth:refresh:{jti}', json.dumps({
        'username': body.username, 'created_at': now.isoformat(), 'expires_at': expires.isoformat()
    }), ex=REFRESH_TOKEN_EXPIRE_DAYS * 86400)
    refresh_token = jwt.encode({'sub': body.username, 'iss': 'enterprise-bff', 'type': 'refresh',
                               'jti': jti, 'iat': now, 'exp': expires}, SECRET, algorithm='HS256')
    # Re-login replaces the current browser session rather than leaving it usable.
    old = refresh_claims(request.cookies.get(REFRESH_COOKIE, ''))
    if old:
        await r.delete(f'auth:refresh:{old["jti"]}')
    response.set_cookie(REFRESH_COOKIE, refresh_token, httponly=True, secure=REFRESH_COOKIE_SECURE,
                        samesite='lax', path=REFRESH_COOKIE_PATH,
                        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400, expires=expires)
    return access_response(body.username, user['role'])


def cookie_origin_guard(request: Request):
    # Same-origin deployment through Vite/Nginx; reject cross-origin cookie mutations.
    origin = request.headers.get('origin')
    expected = os.getenv('AUTH_ORIGIN', '').rstrip('/') or f'{request.url.scheme}://{request.headers.get("host", "")}'
    if origin and origin.rstrip('/') != expected:
        raise HTTPException(403, 'cross-origin authentication request denied')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, 'cross-site authentication request denied')


def refresh_claims(token: str):
    try:
        claims = jwt.decode(token, SECRET, algorithms=['HS256'], issuer='enterprise-bff',
                            options={'require': ['sub', 'type', 'jti', 'iat', 'exp']})
        if claims['type'] != 'refresh' or not isinstance(claims['jti'], str) or not claims['jti']:
            return None
        return claims
    except jwt.PyJWTError:
        return None


def access_response(username: str, role: str):
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': username, 'iss': 'enterprise-bff', 'type': 'access', 'iat': now,
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
    user = await r.hgetall(f'user:{claims["sub"]}')
    if user.get('role') not in ROLES or user.get('disabled') == '1':
        raise HTTPException(401, 'inactive account')
    return access_response(claims['sub'], user['role'])


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
    if body.role not in ROLES or len(body.password) < 12 or not body.username.isidentifier():
        raise HTTPException(400, 'invalid username, role or password')
    if not await r.hsetnx(f'user:{body.username}', 'password', password_hash(body.password)):
        raise HTTPException(409, 'user exists')
    await r.hset(f'user:{body.username}', mapping={'role': body.role, 'disabled': '0'})
    await audit(user['username'], 'user.create', body.username)
    return {'username': body.username, 'role': body.role}


# 返回配置中允许使用的 Agent 列表。
@app.get('/api/agents')
async def agents(user=Depends(permission('agents:read'))):
    return [{'id': a, 'name': a} for a in
            os.getenv('ALLOWED_AGENTS', 'coordinator,researcher,writer,reviewer').split(',')]


# 统计当前用户可见任务的运行与完成数量，并返回 Agent 数量。
@app.get('/api/dashboard')
async def dashboard(user=Depends(permission('tasks:read'))):
    tasks = [json.loads(v) for k in await r.smembers('tasks:all') if (v := await r.get(f'task:{k}'))]
    visible = [t for t in tasks if user['role'] == 'admin' or t['owner'] == user['username']]
    return {'agentCount': len(os.getenv('ALLOWED_AGENTS', 'coordinator,researcher,writer,reviewer').split(',')),
            'runningTasks': sum(t['status'] == 'running' for t in visible),
            'completedTasks': sum(t['status'] == 'completed' for t in visible)}


async def enqueue(body, user):
    if body.agent not in os.getenv('ALLOWED_AGENTS', 'coordinator,researcher,writer,reviewer').split(','):
        raise HTTPException(400, 'agent not allowed')
    task_id = uuid.uuid4().hex
    task = {'id': task_id, 'owner': user['username'], 'prompt': body.prompt, 'agent': body.agent,
            'timeoutSeconds': body.timeout_seconds, 'status': 'queued',
            'createdAt': datetime.now(timezone.utc).isoformat(), 'result': None, 'error': None}
    # 保存任务与索引后入 Redis 队列；API 随即返回，Worker 在后台执行。
    await r.set(f'task:{task_id}', json.dumps(task, ensure_ascii=False))
    await r.sadd('tasks:all', task_id)
    await r.rpush('tasks:queue', task_id)
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
async def task_events(task_id: str, user=Depends(permission('tasks:read'))):
    await task_for(task_id, user)
    return [{'id': key, **json.loads(fields['data'])} for key, fields in await r.xrange(f'events:{task_id}', count=200)]


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
    new = await enqueue(TaskCreate(prompt=old['prompt'], agent=old['agent'], timeout_seconds=old['timeoutSeconds']),
                        user)
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
async def ws_task(ws: WebSocket, task_id: str, ticket: str = ''):
    # ws-ticket 有效期短且只允许使用一次，验证通过后才接受 WebSocket。
    ownership = await r.getdel(f'ws-ticket:{ticket}') if ticket else None
    if not ownership or ownership.split(':', 1)[-1] != task_id:
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        latest = '0-0'
        while True:
            raw = await r.get(f'task:{task_id}')
            if not raw:
                break
            task = json.loads(raw)
            # 先发任务快照，再按 Redis Stream 游标推事件；终态快照带最终结果或错误。
            await ws.send_json({'type': 'snapshot', 'task': task})
            events = await r.xread({f'events:{task_id}': latest}, count=50, block=1000)
            for _, rows in events:
                for event_id, fields in rows:
                    latest = event_id
                    await ws.send_json({'type': 'event', 'id': event_id, 'event': json.loads(fields['data'])})
            if task['status'] in TERMINAL:
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


# 保留指标查询入口；实际指标服务尚未接入，返回 501。
@app.post('/metrics/query')
async def metrics(body: Metric, _=Depends(plugin_guard)):
    raise HTTPException(501, 'connect existing metrics service')


app.include_router(build_knowledge_router(permission, plugin_guard, audit, lambda: r))
