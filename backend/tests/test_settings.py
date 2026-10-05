import asyncio
import os

import fakeredis.aioredis
from fastapi.testclient import TestClient

os.environ.setdefault('JWT_SECRET', 'test-secret-' * 4)
from app import main  # noqa: E402
from app.services.users import migrate_legacy_users


# 验证管理员策略版本、默认超时、暂停入队、恢复提交和普通用户 RBAC。
def test_task_policy_closes_submission_loop(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    asyncio.run(fake.hset('user:admin', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'admin'}))
    asyncio.run(fake.hset('user:operator', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'operator'}))
    with TestClient(main.app) as api:
        admin = api.post('/api/auth/login', json={'username': 'admin', 'password': 'strongpassword123'}).json()
        operator = api.post('/api/auth/login', json={'username': 'operator', 'password': 'strongpassword123'}).json()
        ah = {'Authorization': f'Bearer {admin["access_token"]}'}
        oh = {'Authorization': f'Bearer {operator["access_token"]}'}
        assert api.get('/api/settings/task-policy', headers=oh).status_code == 403
        first = api.put('/api/settings/task-policy', headers=ah, json={
            'version': 0, 'defaultTimeoutSeconds': 75, 'submissionsPaused': False})
        assert first.status_code == 200
        created = api.post('/api/database/questions', headers=oh, json={'prompt': '销售情况'})
        assert created.status_code == 202
        assert created.json()['timeoutSeconds'] == 75
        paused = api.put('/api/settings/task-policy', headers=ah, json={
            'version': 1, 'defaultTimeoutSeconds': 75, 'submissionsPaused': True})
        assert paused.status_code == 200
        assert api.post('/api/database/questions', headers=oh, json={'prompt': '销售情况'}).status_code == 503
        assert api.put('/api/settings/task-policy', headers=ah, json={
            'version': 1, 'defaultTimeoutSeconds': 99, 'submissionsPaused': False}).status_code == 409
        assert api.put('/api/settings/task-policy', headers=ah, json={
            'version': 2, 'defaultTimeoutSeconds': 90, 'submissionsPaused': False}).status_code == 200
        assert api.post('/api/database/questions', headers=oh, json={'prompt': '再次查询'}).json()['timeoutSeconds'] == 90


# 模拟 MySQL 会话版本递增，确认旧 Access 与 Refresh Token 均不可复用。
def test_account_change_revokes_old_tokens(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    asyncio.run(fake.hset('user:alice', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'operator'}))
    with TestClient(main.app) as api:
        login = api.post('/api/auth/login', json={'username': 'alice', 'password': 'strongpassword123'})
        assert login.status_code == 200
        access = login.json()['access_token']
        assert api.get('/api/auth/me', headers={'Authorization': f'Bearer {access}'}).status_code == 200
        asyncio.run(fake.hset('user:alice', mapping={'role': 'viewer', 'sessionVersion': '1'}))
        assert api.get('/api/auth/me', headers={'Authorization': f'Bearer {access}'}).status_code == 401
        assert api.post('/api/auth/refresh').status_code == 401
        renewed = api.post('/api/auth/login', json={'username': 'alice', 'password': 'strongpassword123'})
        assert renewed.status_code == 200 and renewed.json()['role'] == 'viewer'


# 旧 Redis 用户只迁移一次，已删除的 MySQL 账号不会因旧备份在重启后复活。
def test_legacy_account_migration_is_one_time():
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    class Store:
        def __init__(self): self.rows = {}
        async def get(self, name): return self.rows.get(name)
        async def create(self, name, password, role, disabled, ignore_existing):
            self.rows[name] = {'role': role, 'password': password, 'disabled': disabled}
    store = Store()
    async def scenario():
        await fake.hset('user:legacy', mapping={'password': 'stored-hash', 'role': 'operator'})
        await migrate_legacy_users(fake, store)
        assert store.rows['legacy']['role'] == 'operator'
        store.rows.clear()
        await migrate_legacy_users(fake, store)
        assert store.rows == {}
    asyncio.run(scenario())
