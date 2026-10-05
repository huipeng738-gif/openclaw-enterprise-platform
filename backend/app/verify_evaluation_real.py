"""One short live order-tool evaluation, separate from synthetic coverage."""
import asyncio
import json
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user
from app.evaluation import evaluate_case, observation_from_task


# 运行一条真实订单 Tool 任务并评分 Tool 选择，其他六类仍由显式模拟集覆盖。
async def verify():
    owner = 'evaluation_probe_' + uuid.uuid4().hex[:10]
    task_id = None
    db, _ = await create_probe_user(owner, 'operator')
    try:
        token = main.access_response(owner, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=15,
                                     headers={'Authorization': f'Bearer {token}'}) as api:
            created = await api.post('/api/chat', json={
                'prompt': '请调用 order_query 查询 ORD-DEMO-001，只简短回复订单状态。', 'agent': 'coordinator'})
            assert created.status_code == 202, created.status_code
            task_id = created.json()['id']
            for _ in range(90):
                await asyncio.sleep(1)
                raw = await main.r.get(f'task:{task_id}')
                if raw and json.loads(raw)['status'] in main.TERMINAL:
                    break
            detail = await api.get(f'/api/tasks/{task_id}')
            events = await api.get(f'/api/tasks/{task_id}/events')
            assert detail.status_code == 200 and events.status_code == 200
            observed = observation_from_task(detail.json(), events.json())
            result = evaluate_case({'id': 'live-order', 'category': 'Order',
                                    'expected': {'status': 'completed', 'tool': 'order_query'},
                                    'observed': observed})
            assert all(result['checks'].values()), result['checks']
            assert result['tokenUsage'] is not None
            print(json.dumps({'source': 'recorded_run', 'category': 'Order',
                              'checks': result['checks'], 'tokenUsagePresent': True}))
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
