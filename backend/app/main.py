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
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

SECRET = os.getenv('JWT_SECRET', '')
if len(SECRET) < 32:
    raise RuntimeError('JWT_SECRET must be at least 32 characters')
r = redis.from_url(os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'), decode_responses=True)
ROLES = {'viewer': {'tasks:read', 'agents:read'},
         'operator': {'tasks:read', 'tasks:write', 'agents:read', 'knowledge:read'},
         'admin': {'tasks:read', 'tasks:write', 'agents:read', 'knowledge:read', 'audit:read', 'users:write'}}
TERMINAL = {'completed', 'failed', 'cancelled', 'timed_out'}


@asynccontextmanager
async def lifespan(app):
    await r.ping()
    yield
    await r.aclose()


app = FastAPI(title='OpenClaw Enterprise API', lifespan=lifespan)


class Login(BaseModel):
    username: str
    password: str


class UserCreate(Login):
    role: str


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    agent: str = Field(default='coordinator', pattern=r'^[a-zA-Z0-9_-]{1,48}$')
    timeout_seconds: int = Field(default=180, ge=10, le=1800)


class Search(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class Metric(BaseModel):
    metric: str = Field(min_length=1, max_length=120)
    period: str = '7d'


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000)
    return f'{salt}${digest.hex()}'


def password_valid(password, stored):
    try:
        salt, _ = stored.split('$', 1)
        return hmac.compare_digest(password_hash(password, salt), stored)
    except (ValueError, TypeError):
        return False


async def audit(actor, action, target, outcome='ok'):
    await r.xadd('audit',
                 {'at': datetime.now(timezone.utc).isoformat(), 'actor': actor, 'action': action, 'target': target,
                  'outcome': outcome}, maxlen=10000, approximate=True)


async def identity(token):
    try:
        p = jwt.decode(token, SECRET, algorithms=['HS256'], issuer='enterprise-bff')
        user = await r.hgetall(f'user:{p["sub"]}')
        if user.get('role') not in ROLES or user.get('disabled') == '1':
            raise ValueError('inactive')
        return {'username': p['sub'], 'role': user['role']}
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'invalid credentials')


async def current(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'bearer token required')
    return await identity(authorization[7:])


def permission(name):
    async def check(user=Depends(current)):
        if name not in ROLES[user['role']]:
            raise HTTPException(403, 'permission denied')
        return user

    return check


async def task_for(task_id, user):
    raw = await r.get(f'task:{task_id}')
    if not raw:
        raise HTTPException(404, 'task not found')
    task = json.loads(raw)
    if task['owner'] != user['username'] and user['role'] != 'admin':
        raise HTTPException(403, 'permission denied')
    return task


@app.get('/health')
async def health():
    await r.ping()
    return {'status': 'ok'}


@app.post('/api/auth/login')
async def login(body: Login):
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
    token = jwt.encode(
        {'sub': body.username, 'iss': 'enterprise-bff', 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET,
        algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'role': user['role']}


@app.get('/api/auth/me')
async def me(user=Depends(current)):
    return user


@app.post('/api/users', status_code=201)
async def add_user(body: UserCreate, user=Depends(permission('users:write'))):
    if body.role not in ROLES or len(body.password) < 12 or not body.username.isidentifier():
        raise HTTPException(400, 'invalid username, role or password')
    if not await r.hsetnx(f'user:{body.username}', 'password', password_hash(body.password)):
        raise HTTPException(409, 'user exists')
    await r.hset(f'user:{body.username}', mapping={'role': body.role, 'disabled': '0'})
    await audit(user['username'], 'user.create', body.username)
    return {'username': body.username, 'role': body.role}


@app.get('/api/agents')
async def agents(user=Depends(permission('agents:read'))):
    return [{'id': a, 'name': a} for a in
            os.getenv('ALLOWED_AGENTS', 'coordinator,researcher,writer,reviewer').split(',')]


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
    await r.set(f'task:{task_id}', json.dumps(task, ensure_ascii=False))
    await r.sadd('tasks:all', task_id)
    await r.rpush('tasks:queue', task_id)
    await audit(user['username'], 'task.create', task_id)
    return task


@app.post('/api/tasks', status_code=202)
async def create_task(body: TaskCreate, user=Depends(permission('tasks:write'))):
    return await enqueue(body, user)


@app.post('/api/chat', status_code=202)
async def chat(body: TaskCreate, user=Depends(permission('tasks:write'))):
    return await enqueue(body, user)


@app.get('/api/tasks')
async def list_tasks(user=Depends(permission('tasks:read'))):
    tasks = [json.loads(v) for k in await r.smembers('tasks:all') if (v := await r.get(f'task:{k}'))]
    return sorted((t for t in tasks if user['role'] == 'admin' or t['owner'] == user['username']),
                  key=lambda t: t['createdAt'], reverse=True)[:100]


@app.get('/api/tasks/{task_id}')
async def get_task(task_id: str, user=Depends(permission('tasks:read'))):
    return await task_for(task_id, user)


@app.get('/api/tasks/{task_id}/events')
async def task_events(task_id: str, user=Depends(permission('tasks:read'))):
    await task_for(task_id, user)
    return [{'id': key, **json.loads(fields['data'])} for key, fields in await r.xrange(f'events:{task_id}', count=200)]


@app.post('/api/tasks/{task_id}/cancel')
async def cancel(task_id: str, user=Depends(permission('tasks:write'))):
    task = await task_for(task_id, user)
    if task['status'] in TERMINAL:
        raise HTTPException(409, 'task already terminal')
    await r.set(f'cancel:{task_id}', '1', ex=3600)
    await audit(user['username'], 'task.cancel', task_id)
    return {'accepted': True}


@app.post('/api/tasks/{task_id}/retry', status_code=202)
async def retry(task_id: str, user=Depends(permission('tasks:write'))):
    old = await task_for(task_id, user)
    if old['status'] not in {'failed', 'cancelled', 'timed_out'}:
        raise HTTPException(409, 'only unsuccessful terminal tasks can be retried')
    new = await enqueue(TaskCreate(prompt=old['prompt'], agent=old['agent'], timeout_seconds=old['timeoutSeconds']),
                        user)
    await audit(user['username'], 'task.retry', f'{task_id}->{new["id"]}')
    return new


@app.post('/api/tasks/{task_id}/ws-ticket')
async def ws_ticket(task_id: str, user=Depends(permission('tasks:read'))):
    await task_for(task_id, user)
    ticket = secrets.token_urlsafe(32)
    await r.set(f'ws-ticket:{ticket}', f'{user["username"]}:{task_id}', ex=30)
    return {'ticket': ticket}


@app.websocket('/ws/tasks/{task_id}')
async def ws_task(ws: WebSocket, task_id: str, ticket: str = ''):
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


@app.post('/api/knowledge/search')
async def knowledge_ui(body: Search, user=Depends(permission('knowledge:read'))):
    raise HTTPException(501, 'connect existing knowledge service')


@app.get('/api/audit')
async def audit_list(user=Depends(permission('audit:read'))):
    return [{'id': k, **v} for k, v in await r.xrevrange('audit', count=100)]


def plugin_guard(token: str = Header(default='', alias='X-Plugin-Token')):
    configured = os.getenv('PLUGIN_SERVICE_TOKEN', '')
    if not configured or not hmac.compare_digest(token, configured):
        raise HTTPException(401, 'plugin credential required')


@app.post('/knowledge/search')
async def knowledge(body: Search, _=Depends(plugin_guard)):
    raise HTTPException(501, 'connect existing knowledge service')


@app.post('/metrics/query')
async def metrics(body: Metric, _=Depends(plugin_guard)):
    raise HTTPException(501, 'connect existing metrics service')
