"""Opt-in real API -> Redis -> Worker -> Gateway Database Agent smoke check."""
import asyncio
import json
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 创建临时身份提交真实问题，等待终态并只清理本次产生的探测任务。
async def verify():
    username = 'database_probe_' + uuid.uuid4().hex[:8]
    task_id = None
    db, _ = await create_probe_user(username, 'operator')
    try:
        token = main.access_response(username, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10) as client:
            created = await client.post('/api/database/questions',
                                        headers={'Authorization': f'Bearer {token}'},
                                        json={'prompt': '查询 Demo 数据中已支付订单的数量，仅根据数据库结果回答。'})
            assert created.status_code == 202, created.status_code
            task_id = created.json()['id']
            for _ in range(120):
                await asyncio.sleep(1)
                raw = await main.r.get(f'task:{task_id}')
                task = json.loads(raw)
                if task['status'] in main.TERMINAL:
                    stages = [json.loads(fields['data']).get('phase') for _, fields in
                              await main.r.xrange(f'events:{task_id}')
                              if json.loads(fields['data']).get('kind') == 'database_stage']
                    assert task['status'] == 'completed', (task['status'], task.get('error'), stages)
                    assert task['database']['rowCount'] >= 1
                    assert isinstance(task.get('result'), str) and task['result'].strip()
                    assert {'plan', 'validate', 'analyze', 'answer'} <= set(stages)
                    print('Real Database Agent API/Worker/Gateway integration: PASS')
                    return
            raise AssertionError('database task did not finish within 120 seconds')
    finally:
        if task_id:
            await main.r.delete(f'task:{task_id}', f'events:{task_id}', f'cancel:{task_id}')
            await main.r.srem('tasks:all', task_id)
        await delete_probe_user(db, username)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
