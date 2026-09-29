"""Single worker process. Redis is the queue, record store, and replayable event stream."""
import asyncio
import base64
import hashlib
import json
import os
import time
from pathlib import Path

import redis.asyncio as redis
import websockets
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

r = redis.from_url(os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0'), decode_responses=True)
GATEWAY = os.getenv('OPENCLAW_GATEWAY_URL', 'ws://127.0.0.1:18789')
TOKEN = os.getenv('OPENCLAW_GATEWAY_TOKEN', '')
IDENTITY = Path(os.getenv('GATEWAY_IDENTITY_PATH', '/data/gateway-device.pem'))
TERMINAL = {'completed', 'failed', 'cancelled', 'timed_out'}


async def emit(task_id, kind, **data):
    # 事件写入任务专属 Redis Stream，WebSocket 可按游标有序读取。
    await r.xadd(f'events:{task_id}',
                 {'data': json.dumps({'kind': kind, 'at': time.time(), **data}, ensure_ascii=False)}, maxlen=2000,
                 approximate=True)


# 合并并保存任务状态字段，再向任务事件流写入状态通知。
async def update(task_id, **changes):
    raw = await r.get(f'task:{task_id}')
    if not raw:
        return
    task = json.loads(raw)
    task.update(changes)
    await r.set(f'task:{task_id}', json.dumps(task, ensure_ascii=False))
    await emit(task_id, 'status', status=task['status'], error=task.get('error'))


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
    def __init__(self, task_id):
        self.task_id = task_id
        self.pending = {}
        self.run_id = None
        self.seq = -1
        self.text = ''
        self.connected = asyncio.Event()
        self.error = None
        self.early = []
        self.pump = None
        self.sources = []

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
        scopes = ['operator.read', 'operator.write']
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
                await emit(self.task_id, 'assistant', text=self.text[-20000:])
        elif stream == 'tool':
            # Never forward tool arguments or outputs; only bounded metadata.
            name = str(data.get('name', ''))[:100]
            metadata = {}
            if name == 'knowledge_search':
                arguments = self.knowledge_payload(data.get('args') or data.get('input'))
                if isinstance(arguments.get('query'), str):
                    metadata['query'] = arguments['query'][:1000]
                result = self.knowledge_payload(data.get('result') or data.get('output'))
                if isinstance(result.get('results'), list):
                    metadata['resultCount'] = len(result['results'])
                    self.sources = [
                        {key: item[key] for key in ('document_name', 'document_id', 'knowledge_base_id', 'score')
                         if key in item}
                        for item in result['results'] if isinstance(item, dict) and item.get('document_id')
                    ][:20]
            await emit(self.task_id, 'tool', phase=str(data.get('phase', ''))[:40], name=name,
                       callId=str(data.get('toolCallId', ''))[:100], **metadata)
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


async def run(task_id):
    # Worker 从队列取 task_id 后加载任务，调用 Gateway 并持续检查结果、取消和超时。
    task = json.loads(await r.get(f'task:{task_id}'))
    if await r.get(f'cancel:{task_id}'):
        await update(task_id, status='cancelled')
        return
    deadline = time.monotonic() + task['timeoutSeconds']
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
                        await update(task_id, status='completed',
                                     result=gateway.text or str(result.get('result', ''))[:20000],
                                     sources=gateway.sources)
                    else:
                        await update(task_id, status='failed',
                                     error=str(result.get('error', result.get('stopReason', 'Agent failed')))[:300])
                    return
    except Exception as exc:
        await update(task_id, status='failed', error=str(exc)[:300])


async def main():
    await r.ping()
    # A worker restart does not silently replay an accepted Agent run.
    for task_id in await r.smembers('tasks:all'):
        raw = await r.get(f'task:{task_id}')
        if raw and json.loads(raw)['status'] == 'running':
            await update(task_id, status='failed', error='worker restarted; check Gateway before retry')
    while True:
        item = await r.blpop('tasks:queue', timeout=5)
        if item:
            task_id = item[1]
            raw = await r.get(f'task:{task_id}')
            if raw and json.loads(raw)['status'] == 'queued':
                await run(task_id)


if __name__ == '__main__':
    asyncio.run(main())
