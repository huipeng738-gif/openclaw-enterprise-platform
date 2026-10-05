import asyncio
import json

import fakeredis.aioredis

from app import worker
from app.services.observability import summarize
from app.services.runtime import GATEWAY_HEALTH_KEY, gateway_status


# 使用持久化任务与 Tool 事件验证成功率、耗时分位数及未知用量边界。
def test_summary_uses_recorded_values_only():
    async def scenario():
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        tasks = [
            {'id': 'one', 'status': 'completed', 'latencyMs': 100},
            {'id': 'two', 'status': 'failed', 'latencyMs': 300},
            {'id': 'three', 'status': 'running'},
        ]
        for event in [
            {'kind': 'tool', 'name': 'order_query', 'phase': 'result', 'callId': 'a', 'isError': False},
            {'kind': 'tool', 'name': 'order_query', 'phase': 'end', 'callId': 'a', 'isError': False},
            {'kind': 'tool', 'name': 'customer_query', 'phase': 'failed', 'callId': 'b', 'isError': True},
        ]:
            await redis.xadd('events:one', {'data': json.dumps(event)})
        result = await summarize(redis, tasks)
        assert result['taskSuccessRate'] == 50
        assert result['errorRate'] == 50
        assert result['toolSuccessRate'] == 50
        assert result['p50LatencyMs'] == 100
        assert result['p95LatencyMs'] == 300
        assert result['tokenUsage'] is None
        assert result['tokenSampledTasks'] == 0
        assert result['topTools'] == [{'name': 'customer_query', 'count': 1},
                                      {'name': 'order_query', 'count': 1}]
        await redis.aclose()

    asyncio.run(scenario())


# Worker 生命周期只在实际进入 running 后记录耗时，并保留可追溯终态时间。
def test_worker_records_real_task_timing(monkeypatch):
    async def scenario():
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(worker, 'r', redis)
        await redis.set('task:timed', json.dumps({'id': 'timed', 'status': 'queued'}))
        assert await worker.update('timed', status='running') == 'running'
        assert await worker.update('timed', status='completed') == 'completed'
        task = json.loads(await redis.get('task:timed'))
        assert task['startedAt'] and task['finishedAt']
        assert isinstance(task['latencyMs'], int) and task['latencyMs'] >= 0
        await redis.aclose()

    asyncio.run(scenario())


# Gateway 列表中只能采集当前任务的精确 Session，陈旧计量不可显示为真实用量。
def test_session_telemetry_accepts_exact_fresh_row():
    class GatewayStub:
        async def rpc(self, method, params, timeout):
            assert method == 'sessions.list' and params['agentId'] == 'coordinator'
            return {'sessions': [
                {'key': 'other', 'sessionId': 'wrong', 'model': 'other',
                 'totalTokens': 999, 'totalTokensFresh': True},
                {'key': 'agent:coordinator:enterprise:task', 'sessionId': 'thread-1',
                 'model': 'test-model', 'totalTokens': 42, 'totalTokensFresh': True},
            ]}

    row = asyncio.run(worker.session_telemetry(GatewayStub(), 'agent:coordinator:enterprise:task', 'coordinator'))
    assert row == {'threadId': 'thread-1', 'model': 'test-model', 'tokenUsage': 42}

    class StaleGateway(GatewayStub):
        async def rpc(self, method, params, timeout):
            return {'sessions': [{'key': params['search'], 'totalTokens': 100, 'totalTokensFresh': False}]}

    stale = asyncio.run(worker.session_telemetry(StaleGateway(), 'agent:coordinator:enterprise:task', 'coordinator'))
    assert 'tokenUsage' not in stale


# 历史状态事件可恢复真实耗时与新鲜 Session 计量，且不覆盖已有字段或修改任务状态。
def test_backfill_recovers_recorded_observability(monkeypatch):
    async def scenario():
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(worker, 'r', redis)
        task_id = 'legacy-task'
        await redis.set(f'task:{task_id}', json.dumps({
            'id': task_id, 'status': 'completed', 'agent': 'coordinator',
            'createdAt': '2026-09-30T10:00:00+00:00', 'sessionKey': 'agent:coordinator:enterprise:legacy-task',
            'threadId': None, 'model': None, 'tokenUsage': None, 'latencyMs': None,
        }))
        await redis.sadd('tasks:all', task_id)
        for status, at in [('running', 1000.0), ('completed', 1001.25)]:
            await redis.xadd(f'events:{task_id}', {'data': json.dumps({'kind': 'status', 'status': status, 'at': at})})

        class GatewayStub:
            def __init__(self, task_id):
                self.task_id = task_id

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def rpc(self, method, params, timeout):
                assert method == 'sessions.list'
                return {'sessions': [{'key': params['search'], 'sessionId': 'thread-real',
                                      'model': 'model-real', 'totalTokens': 42, 'totalTokensFresh': True}]}

        monkeypatch.setattr(worker, 'Gateway', GatewayStub)
        await worker.backfill_observability()
        task = json.loads(await redis.get(f'task:{task_id}'))
        assert task['status'] == 'completed' and task['latencyMs'] == 1250
        assert task['startedAt'] and task['finishedAt']
        assert task['traceId'] == task_id
        assert (task['threadId'], task['model'], task['tokenUsage']) == ('thread-real', 'model-real', 42)
        assert await redis.xlen(f'events:{task_id}') == 2
        await worker.backfill_observability()
        assert json.loads(await redis.get(f'task:{task_id}')) == task
        await redis.aclose()

    asyncio.run(scenario())


# Gateway 握手心跳带 TTL；未上报、在线与过期状态均来自实际 Redis 记录。
def test_gateway_heartbeat_records_expiring_status(monkeypatch):
    async def scenario():
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr(worker, 'r', redis)
        assert (await gateway_status(redis))['status'] == 'unknown'

        class GatewayStub:
            def __init__(self, task_id):
                self.task_id = task_id

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

        monkeypatch.setattr(worker, 'Gateway', GatewayStub)
        await worker.probe_gateway()
        status = await gateway_status(redis)
        assert status['status'] == 'online' and status['latencyMs'] >= 0 and status['checkedAt']
        assert 0 < await redis.ttl(GATEWAY_HEALTH_KEY) <= 90
        class OfflineGateway(GatewayStub):
            async def __aenter__(self):
                raise OSError('connection unavailable')

        monkeypatch.setattr(worker, 'Gateway', OfflineGateway)
        await worker.probe_gateway()
        assert (await gateway_status(redis))['status'] == 'offline'
        await redis.delete(GATEWAY_HEALTH_KEY)
        assert (await gateway_status(redis))['status'] == 'unknown'
        await redis.aclose()

    asyncio.run(scenario())
