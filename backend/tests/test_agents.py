import asyncio
import json
import os
from datetime import datetime, timezone

import fakeredis.aioredis
from fastapi.testclient import TestClient

os.environ['JWT_SECRET'] = 'test-secret-' * 4
from app import main  # noqa: E402
from app.services import agents as service  # noqa: E402


class FakeGateway:
    entries = [
        {'id': 'coordinator', 'name': 'coordinator', 'model': {'primary': 'test/model'}},
        {'id': 'database', 'name': 'database', 'model': {'primary': 'test/model'}},
    ]
    calls = []

    def __init__(self, _task_id, scopes=None):
        self.scopes = scopes

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def rpc(self, method, params, timeout=15):
        self.calls.append((method, params, self.scopes))
        if method == 'agents.list':
            return {'agents': self.entries}
        if method == 'models.list':
            return {'models': [{'provider': 'test', 'id': 'model'}]}
        if method == 'agents.create':
            self.entries.append({'id': params['name'], 'name': params['name'], 'model': {'primary': params['model']}})
            return {'agentId': params['name']}
        if method == 'config.get':
            return {'hash': 'snapshot'}
        if method == 'config.patch':
            return {'changedPaths': ['agents.entries.new-agent.tools']}
        raise AssertionError(method)


# 验证真实 Gateway 清单投影、管理员创建与停用后的任务准入。
def test_agent_management_create_and_availability(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setattr(service, 'Gateway', FakeGateway)
    FakeGateway.entries = FakeGateway.entries[:2]
    FakeGateway.calls = []

    async def seed():
        for username, role in [('admin', 'admin'), ('viewer', 'viewer')]:
            await fake.hset(f'user:{username}', mapping={
                'password': main.password_hash('strongpassword123'), 'role': role,
            })
        for task_id, status in [('done', 'completed'), ('failed', 'failed')]:
            await fake.set(f'task:{task_id}', json.dumps({
                'id': task_id, 'agent': 'coordinator', 'kind': 'chat', 'status': status,
                'createdAt': datetime.now(timezone.utc).isoformat(),
            }))
            await fake.sadd('tasks:all', task_id)
        await fake.xadd('events:done', {'data': json.dumps({
            'kind': 'tool', 'phase': 'start', 'name': 'metrics_query',
        })})
    asyncio.run(seed())
    with TestClient(main.app) as client:
        def auth(username):
            token = client.post('/api/auth/login', json={
                'username': username, 'password': 'strongpassword123',
            }).json()['access_token']
            return {'Authorization': f'Bearer {token}'}

        admin = auth('admin')
        viewer = auth('viewer')
        assert [row['id'] for row in client.get('/api/agents', headers=viewer).json()] == ['coordinator']
        listing = client.get('/api/agents/manage', headers=viewer).json()
        assert {row['id'] for row in listing} == {'coordinator', 'database'}
        coordinator = next(row for row in listing if row['id'] == 'coordinator')
        assert coordinator['taskCount'] == 2 and coordinator['successRate'] == 50.0
        assert coordinator['tools'] == [{'name': 'metrics_query', 'count': 1}]
        assert next(row for row in listing if row['id'] == 'database')['enabled'] is False
        assert client.post('/api/agents', headers=viewer, json={
            'id': 'new-agent', 'name': 'New Agent', 'model': 'test/model',
        }).status_code == 403
        assert client.get('/api/agents/models', headers=admin).json() == ['test/model']
        created = client.post('/api/agents', headers=admin, json={
            'id': 'new-agent', 'name': '新智能体', 'description': '用于验证',
            'model': 'test/model', 'tool_policy': 'business_readonly',
        })
        assert created.status_code == 201
        patch = next(params for method, params, _ in FakeGateway.calls if method == 'config.patch')
        assert json.loads(patch['raw'])['agents']['entries']['new-agent']['tools'] == {
            'profile': 'minimal', 'alsoAllow': service.READ_ONLY_TOOLS,
        }
        assert next(scopes for method, _, scopes in FakeGateway.calls if method == 'agents.create') == [
            'operator.read', 'operator.admin',
        ]
        agent = next(row for row in client.get('/api/agents/manage', headers=admin).json() if row['id'] == 'new-agent')
        assert agent['name'] == '新智能体' and agent['enabled'] is True
        assert client.post('/api/tasks', headers=admin, json={'prompt': 'hello', 'agent': 'new-agent'}).status_code == 202
        assert client.post('/api/agents/new-agent/availability?enabled=false', headers=admin).status_code == 200
        assert client.post('/api/tasks', headers=admin, json={'prompt': 'hello', 'agent': 'new-agent'}).status_code == 400
        assert client.post('/api/agents/database/availability?enabled=true', headers=admin).status_code == 404


# 验证 Gateway 已创建但策略写入失败时，平台不会开放该 Agent。
def test_create_policy_failure_keeps_agent_disabled(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    FakeGateway.entries = FakeGateway.entries[:2]

    class FailingGateway(FakeGateway):
        async def rpc(self, method, params, timeout=15):
            if method == 'config.patch':
                raise RuntimeError('policy write failed')
            return await super().rpc(method, params, timeout)

    monkeypatch.setattr(service, 'Gateway', FailingGateway)
    asyncio.run(fake.hset('user:admin', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'admin',
    }))
    with TestClient(main.app) as client:
        token = client.post('/api/auth/login', json={
            'username': 'admin', 'password': 'strongpassword123',
        }).json()['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        result = client.post('/api/agents', headers=headers, json={
            'id': 'incomplete-agent', 'name': '未完成', 'model': 'test/model',
        })
        assert result.status_code == 502
        assert asyncio.run(fake.sismember(service.DISABLED_KEY, 'incomplete-agent'))
        assert 'incomplete-agent' not in {row['id'] for row in client.get('/api/agents', headers=headers).json()}
