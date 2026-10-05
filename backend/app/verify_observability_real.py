"""One short real Gateway run to verify persisted session telemetry."""
import asyncio
import json
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 使用一次性账号执行一条极短任务，只输出计量状态并清理平台测试数据。
async def verify():
    owner = 'trace_probe_' + uuid.uuid4().hex[:10]
    task_id = None
    db, _ = await create_probe_user(owner, 'operator')
    try:
        token = main.access_response(owner, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=15,
                                     headers={'Authorization': f'Bearer {token}'}) as api:
            created = await api.post('/api/chat', json={'prompt': '只回复 OK。', 'agent': 'coordinator'})
            assert created.status_code == 202, created.status_code
            task_id = created.json()['id']
            for _ in range(90):
                await asyncio.sleep(1)
                raw = await main.r.get(f'task:{task_id}')
                if raw and json.loads(raw)['status'] in main.TERMINAL:
                    break
            detail = await api.get(f'/api/tasks/{task_id}')
            assert detail.status_code == 200
            task = detail.json()
            assert task['status'] == 'completed', task['status']
            assert task['traceId'] and task['latencyMs'] >= 0
            assert task['threadId'] and task['model'] and isinstance(task['tokenUsage'], int), {
                'thread': bool(task.get('threadId')), 'model': bool(task.get('model')),
                'tokens': task.get('tokenUsage')}
            print(json.dumps({'status': task['status'], 'latencyMs': task['latencyMs'],
                              'threadPresent': True, 'modelPresent': True,
                              'tokenUsagePresent': True}))
    finally:
        if task_id:
            raw = await main.r.get(f'task:{task_id}')
            if raw and json.loads(raw)['status'] in main.TERMINAL:
                await main.r.delete(f'task:{task_id}', f'events:{task_id}', f'cancel:{task_id}')
                await main.r.srem('tasks:all', task_id)
            else:
                await main.r.set(f'cancel:{task_id}', '1', ex=3600)
        await delete_probe_user(db, owner)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
