"""Real HTTP and Redis observability probe using temporary synthetic tasks."""
import asyncio
import json
import uuid
from datetime import datetime, timezone

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 写入并清理一次性模拟任务，验证真实 API 聚合、权限和事件读取。
async def verify():
    owner = 'observability_probe_' + uuid.uuid4().hex[:10]
    task_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    task = {'id': task_id, 'owner': owner, 'prompt': 'synthetic observability probe',
            'agent': 'coordinator', 'status': 'completed', 'kind': 'chat',
            'createdAt': datetime.now(timezone.utc).isoformat(), 'traceId': trace_id,
            'threadId': None, 'model': None, 'tokenUsage': None, 'latencyMs': 125}
    db, _ = await create_probe_user(owner, 'operator')
    try:
        await main.r.set(f'task:{task_id}', json.dumps(task))
        await main.r.sadd('tasks:all', task_id)
        await main.r.xadd(f'events:{task_id}', {'data': json.dumps({
            'kind': 'tool', 'name': 'order_query', 'phase': 'result', 'callId': 'probe',
            'isError': False, 'durationMs': 48})})
        token = main.access_response(owner, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=15,
                                     headers={'Authorization': f'Bearer {token}'}) as api:
            dashboard = await api.get('/api/dashboard')
            assert dashboard.status_code == 200, dashboard.status_code
            metrics = dashboard.json()['observability']
            assert metrics['taskSuccessRate'] == 100
            assert metrics['p50LatencyMs'] == 125
            assert metrics['toolSuccessRate'] == 100
            assert metrics['tokenUsage'] is None
            detail = await api.get(f'/api/tasks/{task_id}')
            assert detail.status_code == 200 and detail.json()['traceId'] == trace_id
            events = await api.get(f'/api/tasks/{task_id}/events')
            assert events.status_code == 200 and events.json()[0]['durationMs'] == 48
        print('Synthetic observability HTTP and Redis integration: PASS')
    finally:
        await main.r.delete(f'task:{task_id}', f'events:{task_id}')
        await delete_probe_user(db, owner)
        await main.r.srem('tasks:all', task_id)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
