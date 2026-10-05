import asyncio
import json
import os
import time

import fakeredis.aioredis
from fastapi.testclient import TestClient

os.environ['JWT_SECRET'] = 'test-secret-' * 4
os.environ['PLUGIN_SERVICE_TOKEN'] = 'test-plugin-token'
from app import main, worker  # noqa: E402

SOURCE = 'a' * 32
TARGET = 'b' * 32
SESSION = f'agent:coordinator:enterprise:{SOURCE}'
PLUGIN = {'X-Plugin-Token': 'test-plugin-token'}


# 准备真实任务结构和三个角色，工具身份只能从 Gateway session 反查。
async def seed(redis):
    for name, role in [('operator', 'operator'), ('admin', 'admin'), ('viewer', 'viewer')]:
        await redis.hset(f'user:{name}', mapping={'password': 'unused', 'role': role, 'disabled': '0'})
    await redis.set(f'task:{SOURCE}', json.dumps({'id': SOURCE, 'owner': 'operator', 'agent': 'coordinator',
                                                  'kind': 'chat', 'sessionKey': SESSION, 'status': 'running'}))
    await redis.set(f'task:{TARGET}', json.dumps({'id': TARGET, 'owner': 'operator', 'agent': 'coordinator',
                                                  'kind': 'chat', 'status': 'queued'}))


def auth(name, role):
    return {'Authorization': 'Bearer ' + main.access_response(name, role)['access_token']}


def test_action_tool_identity_followup_and_approval_lifecycle(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setattr(worker, 'r', fake)
    asyncio.run(seed(fake))
    with TestClient(main.app) as api:
        body = {'session_key': SESSION, 'tool_call_id': 'tool-1', 'title': '催发货', 'order_no': 'ORD-DEMO-001'}
        assert api.post('/actions/task-create', json=body).status_code == 401
        assert api.post('/actions/task-create', headers=PLUGIN, json={**body, 'session_key': 'fake'}).status_code == 403
        followup = api.post('/actions/task-create', headers=PLUGIN, json=body)
        assert followup.status_code == 201
        assert api.post('/actions/task-create', headers=PLUGIN, json=body).json()['id'] == followup.json()['id']
        assert len(api.get('/api/followups', headers=auth('operator', 'operator')).json()) == 1
        assert api.get('/api/followups', headers=auth('viewer', 'viewer')).status_code == 403

        request = {'session_key': SESSION, 'tool_call_id': 'tool-2', 'target_task_id': TARGET, 'reason': '需要停止重复任务'}
        created = api.post('/actions/task-cancel/request', headers=PLUGIN, json=request)
        assert created.status_code == 202
        approval_id = created.json()['id']
        assert api.post('/actions/task-cancel/request', headers=PLUGIN, json=request).json()['id'] == approval_id
        assert asyncio.run(fake.get(f'cancel:{TARGET}')) is None
        assert api.get('/api/approvals', headers=auth('viewer', 'viewer')).status_code == 403
        assert len(api.get('/api/approvals', headers=auth('operator', 'operator')).json()) == 1
        assert api.post(f'/api/approvals/{approval_id}/approve', headers=auth('operator', 'operator')).status_code == 403
        edited = api.patch(f'/api/approvals/{approval_id}', headers=auth('admin', 'admin'),
                           json={'reason': '管理员确认需要停止重复任务'})
        assert edited.status_code == 200 and edited.json()['status'] == 'pending'
        approved = api.post(f'/api/approvals/{approval_id}/approve', headers=auth('admin', 'admin'))
        assert approved.status_code == 200 and approved.json()['status'] == 'approved'
        assert asyncio.run(fake.get(f'cancel:{TARGET}')) == '1'
        assert api.post(f'/api/approvals/{approval_id}/approve', headers=auth('admin', 'admin')).status_code == 409
        asyncio.run(worker.run(TARGET))
        assert json.loads(asyncio.run(fake.get(f'task:{TARGET}')))['status'] == 'cancelled'


def test_action_reject_expiry_role_recheck_and_target_owner(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    asyncio.run(seed(fake))
    with TestClient(main.app) as api:
        request = {'session_key': SESSION, 'tool_call_id': 'reject-1', 'target_task_id': TARGET, 'reason': '申请取消任务'}
        created = api.post('/actions/task-cancel/request', headers=PLUGIN, json=request).json()
        approval_id = created['id']
        assert api.post(f'/api/approvals/{approval_id}/reject', headers=auth('admin', 'admin')).json()['status'] == 'rejected'
        assert asyncio.run(fake.get(f'cancel:{TARGET}')) is None
        assert api.post(f'/api/approvals/{approval_id}/approve', headers=auth('admin', 'admin')).status_code == 409

        expired = api.post('/actions/task-cancel/request', headers=PLUGIN,
                           json={**request, 'tool_call_id': 'expire-1'}).json()
        expired['expiresAt'] = time.time() - 1
        asyncio.run(fake.set(f'approval:{expired["id"]}', json.dumps(expired)))
        assert api.post(f'/api/approvals/{expired["id"]}/approve', headers=auth('admin', 'admin')).status_code == 409
        assert asyncio.run(fake.get(f'cancel:{TARGET}')) is None

        asyncio.run(fake.hset('user:operator', 'role', 'viewer'))
        assert api.post('/actions/task-create', headers=PLUGIN, json={
            'session_key': SESSION, 'tool_call_id': 'denied', 'title': '新建催办任务'}).status_code == 403
        asyncio.run(fake.hset('user:operator', 'role', 'operator'))
        asyncio.run(fake.set(f'task:{TARGET}', json.dumps({'id': TARGET, 'owner': 'admin', 'status': 'running'})))
        assert api.post('/actions/task-cancel/request', headers=PLUGIN,
                        json={**request, 'tool_call_id': 'other-owner'}).status_code == 403


def test_approval_and_worker_completion_order(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setattr(worker, 'r', fake)
    asyncio.run(seed(fake))
    with TestClient(main.app) as api:
        request = {'session_key': SESSION, 'tool_call_id': 'race-1', 'target_task_id': TARGET,
                   'reason': '取消正在完成的任务'}
        approval_id = api.post('/actions/task-cancel/request', headers=PLUGIN, json=request).json()['id']
        approved = api.post(f'/api/approvals/{approval_id}/approve', headers=auth('admin', 'admin'))
        assert approved.status_code == 200
        assert asyncio.run(worker.update(TARGET, status='completed', result='late result')) == 'cancelled'
        task = json.loads(asyncio.run(fake.get(f'task:{TARGET}')))
        assert task['status'] == 'cancelled' and 'result' not in task

        asyncio.run(fake.delete(f'cancel:{TARGET}'))
        asyncio.run(fake.set(f'task:{TARGET}', json.dumps({'id': TARGET, 'owner': 'operator', 'status': 'running'})))
        later = api.post('/actions/task-cancel/request', headers=PLUGIN,
                         json={**request, 'tool_call_id': 'race-2'}).json()['id']
        assert asyncio.run(worker.update(TARGET, status='completed')) == 'completed'
        assert api.post(f'/api/approvals/{later}/approve', headers=auth('admin', 'admin')).status_code == 409
        assert asyncio.run(fake.get(f'cancel:{TARGET}')) is None
