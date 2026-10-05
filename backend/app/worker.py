"""Single worker process. Redis is the queue, record store, and replayable event stream."""
import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as redis
import websockets
from redis.exceptions import WatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.agents.database.query import UnsafeQuery, execute_query, parse_plan, prepare_query, schema_prompt
from app.clients.business_db import BusinessDatabase
from app.services.users import UserStore
from app.services.runtime import GATEWAY_HEALTH_KEY, GATEWAY_HEALTH_TTL

r = redis.from_url(os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'), decode_responses=True)
users = None
GATEWAY = os.getenv('OPENCLAW_GATEWAY_URL', 'ws://127.0.0.1:18789')
TOKEN = os.getenv('OPENCLAW_GATEWAY_TOKEN', '')
IDENTITY = Path(os.getenv('GATEWAY_IDENTITY_PATH', '/data/gateway-device.pem'))
TERMINAL = {'completed', 'failed', 'cancelled', 'timed_out'}
log = logging.getLogger(__name__)


async def emit(task_id, kind, **data):
    # 事件写入任务专属 Redis Stream，WebSocket 可按游标有序读取。
    await r.xadd(f'events:{task_id}',
                 {'data': json.dumps({'kind': kind, 'at': time.time(), **data}, ensure_ascii=False)}, maxlen=2000,
                 approximate=True)


# 合并并保存任务状态字段，再向任务事件流写入状态通知。
async def update(task_id, **changes):
    task_key = f'task:{task_id}'
    cancel_key = f'cancel:{task_id}'
    for _ in range(5):
        async with r.pipeline() as pipe:
            try:
                await pipe.watch(task_key, cancel_key)
                raw = await pipe.get(task_key)
                if not raw:
                    return None
                task = json.loads(raw)
                if task['status'] in TERMINAL:
                    return task['status']
                next_changes = changes.copy()
                if next_changes.get('status') == 'completed' and await pipe.get(cancel_key):
                    next_changes = {'status': 'cancelled'}
                if next_changes.get('status') == 'running' and not task.get('startedAt'):
                    next_changes['startedAt'] = datetime.now(timezone.utc).isoformat()
                if next_changes.get('status') in TERMINAL:
                    finished = datetime.now(timezone.utc)
                    next_changes['finishedAt'] = finished.isoformat()
                    if task.get('startedAt'):
                        started = datetime.fromisoformat(task['startedAt'])
                        next_changes['latencyMs'] = max(0, round((finished - started).total_seconds() * 1000))
                old_status = task['status']
                task.update(next_changes)
                pipe.multi()
                pipe.set(task_key, json.dumps(task, ensure_ascii=False))
                await pipe.execute()
                if task['status'] != old_status:
                    await emit(task_id, 'status', status=task['status'], error=task.get('error'))
                return task['status']
            except WatchError:
                continue
    raise RuntimeError('task status changed concurrently')


# 加载或首次生成 Ed25519 设备私钥，返回签名密钥、设备 ID 和编码后的公钥。
def device():
    IDENTITY.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not IDENTITY.exists():
        key = Ed25519PrivateKey.generate()
        IDENTITY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        IDENTITY.chmod(0o600)
    key = serialization.load_pem_private_key(IDENTITY.read_bytes(), password=None)
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, hashlib.sha256(pub).hexdigest(), base64.urlsafe_b64encode(pub).decode().rstrip('=')


class Gateway:
    # 初始化当前任务的 RPC 等待表、事件游标、答复缓冲及知识来源。
    def __init__(self, task_id, scopes=None):
        self.task_id = task_id
        self.scopes = scopes or ['operator.read', 'operator.write']
        self.pending = {}
        self.run_id = None
        self.seq = -1
        self.text = ''
        self.connected = asyncio.Event()
        self.error = None
        self.early = []
        self.pump = None
        self.sources = []
        self.tool_started: dict[str, float] = {}
        self.emit_assistant = True

    # 兼容 JSON 字符串、字典和 Tool 文本内容封装，无法解析时返回空字典。
    @staticmethod
    def knowledge_payload(value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return {}
        if isinstance(value, dict) and isinstance(value.get('content'), list):
            first = next((part.get('text') for part in value['content'] if
                          isinstance(part, dict) and part.get('type') == 'text'), None)
            return Gateway.knowledge_payload(first)
        return value if isinstance(value, dict) else {}

    # 连接 Gateway，完成设备签名认证握手后启动后台消息接收任务。
    async def __aenter__(self):
        if not TOKEN:
            raise RuntimeError('OPENCLAW_GATEWAY_TOKEN is missing')
        self.ws = await websockets.connect(GATEWAY, max_size=8 * 1024 * 1024, open_timeout=10)
        challenge = json.loads(await asyncio.wait_for(self.ws.recv(), 10))
        p = challenge.get('payload', {})
        if challenge.get('event') != 'connect.challenge' or not isinstance(p.get('ts'), int):
            raise RuntimeError('Gateway challenge invalid')
        key, device_id, pub = device()
        scopes = self.scopes
        platform = 'win32' if os.name == 'nt' else 'linux'
        fields = ['v3', device_id, 'gateway-client', 'backend', 'operator', ','.join(scopes), str(p['ts']), TOKEN,
                  p['nonce'], platform, '']
        signature = base64.urlsafe_b64encode(key.sign('|'.join(fields).encode())).decode().rstrip('=')
        params = {'minProtocol': 4, 'maxProtocol': 4,
                  'client': {'id': 'gateway-client', 'version': '2026.8.1', 'platform': platform, 'mode': 'backend'},
                  'role': 'operator', 'scopes': scopes, 'caps': ['tool-events'], 'commands': [], 'permissions': {},
                  'auth': {'token': TOKEN}, 'locale': 'zh-CN',
                  'device': {'id': device_id, 'publicKey': pub, 'signature': signature, 'signedAt': p['ts'],
                             'nonce': p['nonce']}}
        await self.ws.send(json.dumps({'type': 'req', 'id': 'connect', 'method': 'connect', 'params': params}))
        hello = json.loads(await asyncio.wait_for(self.ws.recv(), 15))
        if not hello.get('ok') or hello.get('payload', {}).get('type') != 'hello-ok':
            raise RuntimeError('Gateway connect failed: ' + str(hello.get('error', {}))[:300])
        self.pump = asyncio.create_task(self.receive())
        return self

    # 退出上下文时取消后台接收任务并关闭 Gateway WebSocket。
    async def __aexit__(self, *args):
        if self.pump:
            self.pump.cancel()
        await self.ws.close()

    # 分发 RPC 响应和当前 runId 的 Agent 事件，并缓存启动确认前到达的事件。
    async def receive(self):
        try:
            async for data in self.ws:
                frame = json.loads(data)
                if frame.get('type') == 'res':
                    future = self.pending.pop(frame.get('id'), None)
                    if future and not future.done():
                        if frame.get('ok'):
                            future.set_result(frame.get('payload', {}))
                        else:
                            future.set_exception(RuntimeError(str(frame.get('error', {}))[:300]))
                elif frame.get('type') == 'event' and frame.get('event') == 'agent':
                    p = frame.get('payload', {})
                    if self.run_id is None:
                        self.early.append(p)
                        continue
                    if p.get('runId') != self.run_id:
                        continue
                    await self.handle_event(p)
        except Exception as exc:
            self.error = str(exc)[:200]
        finally:
            for fut in self.pending.values():
                if not fut.done():
                    fut.set_exception(RuntimeError(self.error or 'Gateway connection closed'))

    async def handle_event(self, p):
        seq = p.get('seq')
        if isinstance(seq, int) and seq <= self.seq:
            return
        if isinstance(seq, int):
            self.seq = seq
        stream = p.get('stream', '')
        data = p.get('data') or {}
        if stream == 'assistant':
            text = data.get('text') or data.get('delta')
            if isinstance(text, str):
                self.text = text if text.startswith(self.text) else self.text + text
                if self.emit_assistant:
                    await emit(self.task_id, 'assistant', text=self.text[-20000:])
        elif stream == 'tool':
            # Only forward whitelisted parameters and bounded summaries, never raw outputs/secrets.
            name = str(data.get('name', ''))[:100]
            phase = str(data.get('phase', ''))[:40]
            call_id = str(data.get('toolCallId', ''))[:100]
            tool_key = call_id or name
            metadata = {}
            if phase == 'start':
                self.tool_started[tool_key] = time.monotonic()
            if phase in {'result', 'end', 'completed', 'error', 'failed'}:
                result_data = data.get('result') or data.get('output')
                metadata['isError'] = bool(data.get('isError') or data.get('error') or
                                           phase in {'error', 'failed'} or
                                           (isinstance(result_data, dict) and result_data.get('isError')))
                metadata['resultSummary'] = '工具执行失败' if metadata['isError'] else '工具执行完成'
                started = self.tool_started.pop(tool_key, None)
                if started is not None:
                    metadata['durationMs'] = round((time.monotonic() - started) * 1000)
            if name == 'knowledge_search':
                arguments = self.knowledge_payload(data.get('args') or data.get('input'))
                if isinstance(arguments.get('query'), str):
                    metadata['query'] = arguments['query'][:1000]
                result = self.knowledge_payload(data.get('result') or data.get('output'))
                if isinstance(result.get('results'), list):
                    metadata['resultCount'] = len(result['results'])
                    if not metadata.get('isError'):
                        metadata['resultSummary'] = f"检索到 {len(result['results'])} 条来源"
                    self.sources = [
                        {key: item[key] for key in ('document_name', 'document_id', 'knowledge_base_id', 'score')
                         if key in item}
                        for item in result['results'] if isinstance(item, dict) and item.get('document_id')
                    ][:20]
            await emit(self.task_id, 'tool', phase=phase, name=name, callId=call_id, **metadata)
        elif stream == 'lifecycle':
            await emit(self.task_id, 'lifecycle', phase=str(data.get('phase', ''))[:40])

    # 用独立请求 ID 关联 RPC 响应，在超时或结束后清理等待表。
    async def rpc(self, method, params, timeout=15):
        req_id = os.urandom(12).hex()
        future = asyncio.get_running_loop().create_future()
        self.pending[req_id] = future
        await self.ws.send(json.dumps({'type': 'req', 'id': req_id, 'method': method, 'params': params}))
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(req_id, None)


# 在同一个任务连接中运行一个 Gateway 阶段，保留取消和总时限检查。
async def database_agent_stage(gateway, task_id, session, message, stage, deadline):
    gateway.run_id = None
    gateway.seq = -1
    gateway.text = ''
    gateway.emit_assistant = stage == 'answer'
    accepted = await gateway.rpc('agent', {'message': message, 'agentId': os.getenv('DATABASE_GATEWAY_AGENT', 'coordinator'),
                                           'sessionKey': session, 'idempotencyKey': f'{task_id}:{stage}',
                                           'deliver': False})
    gateway.run_id = accepted['runId']
    for early in gateway.early:
        if early.get('runId') == gateway.run_id:
            await gateway.handle_event(early)
    gateway.early.clear()
    await update(task_id, runId=gateway.run_id)
    await emit(task_id, 'database_stage', phase=stage)
    while True:
        if await r.get(f'cancel:{task_id}'):
            await gateway.rpc('chat.abort', {'sessionKey': session, 'runId': gateway.run_id})
            raise asyncio.CancelledError()
        if time.monotonic() >= deadline:
            await gateway.rpc('chat.abort', {'sessionKey': session, 'runId': gateway.run_id})
            raise TimeoutError('database agent task timed out')
        result = await gateway.rpc('agent.wait', {'runId': gateway.run_id, 'timeoutMs': 1000}, timeout=5)
        if result.get('status') == 'error':
            raise RuntimeError('database agent stage failed')
        if result.get('status') == 'ok':
            return gateway.text or str(result.get('result', ''))


# 仅读取与当前任务完全匹配的 Gateway Session 元数据，不读取对话内容或发起模型请求。
async def session_telemetry(gateway, session, agent):
    try:
        result = await gateway.rpc('sessions.list', {'agentId': agent, 'search': session, 'limit': 10}, timeout=5)
    except Exception:
        return {}
    rows = result.get('sessions', []) if isinstance(result, dict) else []
    row = next((item for item in rows if isinstance(item, dict) and item.get('key') == session), None)
    if not row:
        return {}
    telemetry = {}
    if isinstance(row.get('sessionId'), str):
        telemetry['threadId'] = row['sessionId'][:120]
    if isinstance(row.get('model'), str):
        telemetry['model'] = row['model'][:120]
    tokens = row.get('totalTokens')
    if row.get('totalTokensFresh') is True and isinstance(tokens, int) and not isinstance(tokens, bool) and tokens >= 0:
        telemetry['tokenUsage'] = tokens
    return telemetry


# 从历史状态事件恢复确实记录过的开始、结束时间与执行耗时。
async def recorded_timing(task_id):
    started = None
    finished = None
    for _, fields in await r.xrange(f'events:{task_id}'):
        event = json.loads(fields['data'])
        if event.get('kind') != 'status' or not isinstance(event.get('at'), (int, float)):
            continue
        if event.get('status') == 'running' and started is None:
            started = event['at']
        if event.get('status') in TERMINAL and started is not None and event['at'] >= started:
            finished = event['at']
    if started is None or finished is None:
        return {}
    return {'startedAt': datetime.fromtimestamp(started, timezone.utc).isoformat(),
            'finishedAt': datetime.fromtimestamp(finished, timezone.utc).isoformat(),
            'latencyMs': round((finished - started) * 1000)}


# 使用 Redis WATCH 只填充终态旧任务缺失的可信观测字段，不改状态或追加事件。
async def fill_observability(task_id, values):
    if not values:
        return
    task_key = f'task:{task_id}'
    for _ in range(5):
        async with r.pipeline() as pipe:
            try:
                await pipe.watch(task_key)
                raw = await pipe.get(task_key)
                if not raw:
                    return
                task = json.loads(raw)
                if task.get('status') not in TERMINAL:
                    return
                missing = {key: value for key, value in values.items() if task.get(key) is None}
                if not missing:
                    return
                task.update(missing)
                pipe.multi()
                pipe.set(task_key, json.dumps(task, ensure_ascii=False))
                await pipe.execute()
                return
            except WatchError:
                continue
    raise RuntimeError('task observability changed concurrently')


# 启动时只读查询历史事件和 Gateway Session，回填最近百条旧任务可恢复的元数据。
async def backfill_observability():
    tasks = []
    for task_id in await r.smembers('tasks:all'):
        raw = await r.get(f'task:{task_id}')
        if raw:
            task = json.loads(raw)
            if task.get('status') in TERMINAL:
                tasks.append(task)
    tasks.sort(key=lambda task: task.get('createdAt', ''), reverse=True)
    tasks = tasks[:100]
    for task in tasks:
        if not task.get('traceId'):
            await fill_observability(task['id'], {'traceId': task['id']})
        if task.get('latencyMs') is None:
            await fill_observability(task['id'], await recorded_timing(task['id']))
    try:
        async with Gateway('observability-backfill') as gateway:
            for task in tasks:
                if not task.get('sessionKey') or all(task.get(key) is not None for key in ('threadId', 'model', 'tokenUsage')):
                    continue
                metadata = await session_telemetry(gateway, task['sessionKey'], task['agent'])
                await fill_observability(task['id'], metadata)
    except Exception as exc:
        log.warning('Observability backfill Gateway lookup failed: %s', type(exc).__name__)
        return


# 与 Gateway 完成真实设备握手，并把在线/离线结果写入有 TTL 的 Redis String。
async def probe_gateway():
    started = time.monotonic()
    status = 'offline'
    latency = None
    try:
        async with Gateway('runtime-health'):
            status = 'online'
            latency = round((time.monotonic() - started) * 1000)
    except Exception as exc:
        log.warning('Gateway health probe failed: %s', type(exc).__name__)
    await r.set(GATEWAY_HEALTH_KEY, json.dumps({
        'status': status, 'checkedAt': datetime.now(timezone.utc).isoformat(), 'latencyMs': latency
    }), ex=GATEWAY_HEALTH_TTL)


# 每三十秒更新 Gateway 真实连接状态；任务执行循环不等待健康探测。
async def gateway_heartbeat():
    while True:
        await probe_gateway()
        await asyncio.sleep(30)


# 每十五秒写入带 TTL 的 Worker 心跳，系统设置据此判断消费端是否仍存活。
async def worker_heartbeat():
    while True:
        await r.set('runtime:worker', json.dumps({'checkedAt': datetime.now(timezone.utc).isoformat()}), ex=45)
        await asyncio.sleep(15)


# 以 Redis 中的任务归属和当前角色再次校验权限，模型内容不得决定数据库权限。
async def run_database(task_id, task, deadline):
    owner = task['owner']
    db = None
    session = f'agent:{os.getenv("DATABASE_GATEWAY_AGENT", "coordinator")}:enterprise-db:{task_id}'
    await update(task_id, status='running', sessionKey=session)
    outcome = 'failed'
    try:
        user = await users.get(owner)
        if not user or user['role'] not in {'operator', 'admin'} or user['disabled']:
            await update(task_id, status='failed', error='database access denied')
            outcome = 'denied'
            return
        db = await BusinessDatabase.from_env()
        if db is None:
            raise RuntimeError('business database is not configured')
        async with Gateway(task_id) as gateway:
            question = task['prompt']
            plan_message = ('你是企业数据库分析规划器。只输出一个 JSON 对象，格式为 {"sql":"SELECT ..."}。'
                            '不得执行工具，不得输出解释。只使用下列可见表列，不查询手机号。'
                            '查询需有明确业务筛选；没有数据时不能编造。\n'
                            f'可见结构：\n{schema_prompt()}\n用户问题：{question}')
            for attempt in range(2):
                phase = 'plan' if attempt == 0 else 'plan_retry'
                proposed = await database_agent_stage(gateway, task_id, session, plan_message, phase, deadline)
                await emit(task_id, 'database_stage', phase='validate')
                try:
                    sql = parse_plan(proposed)
                    prepare_query(sql)
                    break
                except UnsafeQuery as exc:
                    if attempt == 1:
                        raise
                    plan_message += ('\n上一次候选查询未通过安全校验：' + str(exc) +
                                     '。请重新给出符合约束的 JSON SQL，不要解释。')
            result = await execute_query(db, sql)
            if await r.get(f'cancel:{task_id}'):
                raise asyncio.CancelledError()
            await emit(task_id, 'database_stage', phase='analyze', rowCount=result['row_count'])
            evidence = json.dumps({'question': question, 'rows': result['rows'],
                                   'row_count': result['row_count'], 'truncated': result['truncated']},
                                  ensure_ascii=False, default=str)[:30000]
            if not result['rows']:
                answer = '查询未返回记录，无法据此得出结论。'
            else:
                answer_message = ('你是数据分析说明员。仅依据以下真实查询结果回答原问题；'
                                  '不能把缺失记录当作零，无法比较的时间区间明确说数据不足。'
                                  '不要调用工具，不要重复 SQL，不要声称执行了未提供的查询。\n'
                                  f'查询结果：{evidence}')
                answer = await database_agent_stage(gateway, task_id, session, answer_message, 'answer', deadline)
            telemetry = await session_telemetry(gateway, session, os.getenv('DATABASE_GATEWAY_AGENT', 'coordinator'))
            final_status = await update(task_id, status='completed', result=answer[:20000],
                                        database={'sql': result['sql'], 'rowCount': result['row_count'],
                                                  'truncated': result['truncated'], 'preview': result['rows'][:20]},
                                        **telemetry)
            outcome = 'cancelled' if final_status == 'cancelled' else 'ok'
    except asyncio.CancelledError:
        await update(task_id, status='cancelled')
        outcome = 'cancelled'
    except TimeoutError:
        await update(task_id, status='timed_out', error='database agent timeout')
        outcome = 'timeout'
    except UnsafeQuery as exc:
        await update(task_id, status='failed', error=f'database query rejected: {exc}')
        outcome = 'rejected'
    except Exception:
        await update(task_id, status='failed', error='database analysis failed')
    finally:
        if db:
            await db.close()
        await r.xadd('audit', {'at': time.time(), 'actor': owner, 'action': 'database.query',
                              'target': task_id, 'outcome': outcome}, maxlen=10000, approximate=True)


async def run(task_id):
    # Worker 从队列取 task_id 后加载任务，调用 Gateway 并持续检查结果、取消和超时。
    task = json.loads(await r.get(f'task:{task_id}'))
    if await r.get(f'cancel:{task_id}'):
        await update(task_id, status='cancelled')
        return
    deadline = time.monotonic() + task['timeoutSeconds']
    if task.get('kind') == 'database':
        await run_database(task_id, task, deadline)
        return
    session = f'agent:{task["agent"]}:enterprise:{task_id}'
    await update(task_id, status='running', sessionKey=session)
    try:
        async with Gateway(task_id) as gateway:
            # Gateway 立即确认启动并返回 runId；执行过程由后续事件和 agent.wait 跟踪。
            accepted = await gateway.rpc('agent',
                                         {'message': task['prompt'], 'agentId': task['agent'], 'sessionKey': session,
                                          'idempotencyKey': task_id, 'deliver': False})
            gateway.run_id = accepted['runId']
            for early in gateway.early:
                if early.get('runId') == gateway.run_id:
                    await gateway.handle_event(early)
            gateway.early.clear()
            await update(task_id, runId=gateway.run_id)
            await emit(task_id, 'accepted', runId=gateway.run_id)
            while True:
                if await r.get(f'cancel:{task_id}'):
                    await gateway.rpc('chat.abort', {'sessionKey': session, 'runId': gateway.run_id})
                    await update(task_id, status='cancelled')
                    return
                if time.monotonic() >= deadline:
                    await gateway.rpc('chat.abort', {'sessionKey': session, 'runId': gateway.run_id})
                    await update(task_id, status='timed_out', error='execution timeout')
                    return
                result = await gateway.rpc('agent.wait', {'runId': gateway.run_id, 'timeoutMs': 1000}, timeout=5)
                if result.get('status') in {'ok', 'error'}:
                    if result['status'] == 'ok':
                        telemetry = await session_telemetry(gateway, session, task['agent'])
                        await update(task_id, status='completed',
                                     result=gateway.text or str(result.get('result', ''))[:20000],
                                     sources=gateway.sources, **telemetry)
                    else:
                        await update(task_id, status='failed',
                                     error=str(result.get('error', result.get('stopReason', 'Agent failed')))[:300])
                    return
    except Exception as exc:
        await update(task_id, status='failed', error=str(exc)[:300])


async def main():
    global users
    await r.ping()
    user_db = await BusinessDatabase.from_env()
    if user_db is None:
        raise RuntimeError('MySQL account store is required')
    users = UserStore(user_db.pool)
    heartbeat = asyncio.create_task(gateway_heartbeat())
    worker_pulse = asyncio.create_task(worker_heartbeat())
    # A worker restart does not silently replay an accepted Agent run.
    for task_id in await r.smembers('tasks:all'):
        raw = await r.get(f'task:{task_id}')
        if raw and json.loads(raw)['status'] == 'running':
            await update(task_id, status='failed', error='worker restarted; check Gateway before retry')
    try:
        await backfill_observability()
        while True:
            item = await r.blpop('tasks:queue', timeout=5)
            if item:
                task_id = item[1]
                raw = await r.get(f'task:{task_id}')
                if raw and json.loads(raw)['status'] == 'queued':
                    await run(task_id)
    finally:
        heartbeat.cancel()
        worker_pulse.cancel()
        await asyncio.gather(heartbeat, worker_pulse, return_exceptions=True)
        await user_db.close()


if __name__ == '__main__':
    asyncio.run(main())
