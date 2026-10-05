"""Temporary API-backed approval fixtures for real browser acceptance."""
import asyncio
import json
import os
import sys
import uuid

import httpx

from app import main


# 通过真实插件入口创建两条审批申请，或清理当前验收生成的数据。
async def run():
    payload = json.load(sys.stdin)
    owner = payload['owner']
    if not owner.startswith('phase7_browser_probe_'):
        raise ValueError('temporary probe owner required')
    try:
        if payload['action'] == 'create':
            source, target = uuid.uuid4().hex, uuid.uuid4().hex
            session = f'agent:coordinator:enterprise:{source}'
            await main.r.set(f'task:{source}', json.dumps({'id': source, 'owner': owner, 'status': 'running',
                                                            'agent': 'coordinator', 'kind': 'chat', 'sessionKey': session}))
            await main.r.set(f'task:{target}', json.dumps({'id': target, 'owner': owner, 'status': 'queued',
                                                            'agent': 'coordinator', 'kind': 'chat'}))
            approval_ids = []
            async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10,
                                         headers={'X-Plugin-Token': os.environ['PLUGIN_SERVICE_TOKEN']}) as api:
                for index in (1, 2):
                    response = await api.post('/actions/task-cancel/request', json={
                        'session_key': session, 'tool_call_id': f'browser-{index}', 'target_task_id': target,
                        'reason': f'演示审批申请 {index}'})
                    assert response.status_code == 202, response.status_code
                    approval_ids.append(response.json()['id'])
            print(json.dumps({'source': source, 'target': target, 'approvals': approval_ids}))
        elif payload['action'] == 'cleanup':
            for task_id in (payload['source'], payload['target']):
                await main.r.delete(f'task:{task_id}', f'events:{task_id}', f'cancel:{task_id}')
            for approval_id in payload['approvals']:
                await main.r.delete(f'approval:{approval_id}')
                await main.r.zrem('approvals:index', approval_id)
        elif payload['action'] == 'check':
            records = [json.loads(await main.r.get(f'approval:{approval_id}')) for approval_id in payload['approvals']]
            assert all(item['status'] == 'pending' for item in records)
            assert await main.r.exists(f'task:{payload["target"]}')
            assert not await main.r.get(f'cancel:{payload["target"]}')
            print('Pending approvals and target task survived restart: PASS')
        else:
            raise ValueError('invalid fixture action')
    finally:
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(run())
