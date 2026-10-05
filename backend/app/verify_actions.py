"""Opt-in real Agent -> Tool -> FastAPI action and HITL integration probe."""
import asyncio
import json
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 等待 Agent 任务到达终态，避免把 Tool 注册成功误当成实际调用成功。
async def wait_task(task_id):
    for _ in range(90):
        await asyncio.sleep(1)
        raw = await main.r.get(f'task:{task_id}')
        if raw and (task := json.loads(raw))['status'] in main.TERMINAL:
            return task
    raise AssertionError('action Agent task timed out')


# 一次性账号通过真实 API 创建 Agent 任务，并检查后端动作记录。
async def verify():
    owner = 'action_probe_' + uuid.uuid4().hex[:10]
    source_ids = []
    followup_ids = []
    approval_ids = []
    target_id = uuid.uuid4().hex
    db, _ = await create_probe_user(owner, 'operator')
    await main.r.set(f'task:{target_id}', json.dumps({'id': target_id, 'owner': owner, 'status': 'queued',
                                                      'agent': 'coordinator', 'kind': 'chat'}))
    try:
        token = main.access_response(owner, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10,
                                     headers={'Authorization': f'Bearer {token}'}) as api:
            first = await api.post('/api/chat', json={'prompt':
                '请现在调用 task_create 工具创建一条催发货任务，title 为“演示订单催发货”，order_no 为 ORD-DEMO-001，reason 为“订单需要跟进发货”。调用工具后简短确认。'})
            assert first.status_code == 202
            source_ids.append(first.json()['id'])
            assert (await wait_task(source_ids[-1]))['status'] == 'completed'
            rows = (await api.get('/api/followups')).json()
            followup_ids = [item['id'] for item in rows if item['sourceTaskId'] == source_ids[-1]]
            assert len(followup_ids) == 1, 'task_create Tool was not observed'

            second = await api.post('/api/chat', json={'prompt':
                f'请现在调用 task_cancel_request 工具，target_task_id 为 {target_id}，reason 为“演示任务需要停止”。只创建人工审批请求，不要直接取消。'})
            assert second.status_code == 202
            source_ids.append(second.json()['id'])
            assert (await wait_task(source_ids[-1]))['status'] == 'completed'
            rows = (await api.get('/api/approvals')).json()
            approval_ids = [item['id'] for item in rows if item['sourceTaskId'] == source_ids[-1]]
            assert len(approval_ids) == 1 and not await main.r.get(f'cancel:{target_id}'), 'approval boundary failed'
            print('Real Agent task_create and task_cancel_request HITL boundary: PASS')
    finally:
        for item_id in source_ids:
            await main.r.delete(f'task:{item_id}', f'events:{item_id}', f'cancel:{item_id}')
            await main.r.srem('tasks:all', item_id)
        for item_id in followup_ids:
            await main.r.delete(f'followup:{item_id}')
            await main.r.zrem('followups:index', item_id)
        for item_id in approval_ids:
            await main.r.delete(f'approval:{item_id}')
            await main.r.zrem('approvals:index', item_id)
        await delete_probe_user(db, owner)
        await main.r.delete(f'task:{target_id}', f'cancel:{target_id}')
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
