import asyncio
import os
from datetime import date
from decimal import Decimal

import fakeredis.aioredis
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ['JWT_SECRET'] = 'test-secret-' * 4

from app import main  # noqa: E402
from app.clients.business_db import BusinessDatabase  # noqa: E402
from app.repositories.metrics import MetricsRepository  # noqa: E402
from app.services.metrics import MetricsService, REGISTRY  # noqa: E402


class FixtureDatabase:
    def __init__(self):
        self.calls = []

    async def fetchone(self, sql, params):
        self.calls.append((sql, params))
        if 'total_amount' in sql:
            return {'value': Decimal('428.00')}
        if 'refunded' in sql:
            return {'value': Decimal('0.00')}
        return {'value': 2 if 'customers' in sql else 3}

    async def fetchall(self, sql, params):
        self.calls.append((sql, params))
        return [{'bucket': '2026-09-01', 'value': Decimal('299.00')}]

    async def close(self):
        pass


def test_metric_registry_accuracy_and_sql_binding():
    db = FixtureDatabase()

    async def scenario():
        service = MetricsService(MetricsRepository(db))
        result = await service.query('sales_amount', date(2026, 9, 1), date(2026, 9, 30), 'day')
        assert result['total'] == '428.00'
        assert result['points'] == [{'period': '2026-09-01', 'value': '299.00'}]
        assert set(REGISTRY) == {'sales_amount', 'order_count', 'refund_rate', 'active_customer_count'}
        for sql, params in db.calls:
            assert 'created_at >= %s AND created_at < %s' in sql
            assert '2026-09-01' not in sql
            assert 'LIMIT 400' in sql or 'GROUP BY' not in sql
            assert params[-1].date() == date(2026, 10, 1)
        with pytest.raises(HTTPException):
            await service.query('made_up', date(2026, 9, 1), date(2026, 9, 30), 'day')
        with pytest.raises(HTTPException):
            await service.query('order_count', date(2026, 9, 30), date(2026, 9, 1), 'day')
        with pytest.raises(HTTPException):
            await service.query('order_count', date(2025, 1, 1), date(2026, 9, 30), 'day')
        with pytest.raises(HTTPException):
            await service.query('order_count', date(2026, 9, 1), date(2026, 9, 30), 'hour')

    asyncio.run(scenario())


def test_metrics_api_permissions_and_plugin(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db = FixtureDatabase()
    monkeypatch.setattr(main, 'r', redis)
    monkeypatch.setenv('PLUGIN_SERVICE_TOKEN', 'test-plugin-token')

    async def load_db(_cls):
        return db

    monkeypatch.setattr(BusinessDatabase, 'from_env', classmethod(load_db))
    for username, role in [('operator', 'operator'), ('viewer', 'viewer')]:
        asyncio.run(redis.hset(f'user:{username}', mapping={
            'password': main.password_hash('strongpassword123'), 'role': role}))
    payload = {'metric': 'sales_amount', 'start_date': '2026-09-01',
               'end_date': '2026-09-30', 'group_by': 'day'}

    with TestClient(main.app) as api:
        def headers(username):
            token = api.post('/api/auth/login', json={
                'username': username, 'password': 'strongpassword123'}).json()['access_token']
            return {'Authorization': 'Bearer ' + token}

        operator, viewer = headers('operator'), headers('viewer')
        assert api.post('/api/metrics/query', json=payload).status_code == 401
        assert api.post('/api/metrics/query', json=payload, headers=viewer).status_code == 403
        result = api.post('/api/metrics/query', json=payload, headers=operator)
        assert result.status_code == 200 and result.json()['total'] == '428.00'
        assert result.headers['Cache-Control'] == 'no-store'
        assert api.post('/api/metrics/query', headers=operator,
                        json={**payload, 'metric': 'unknown'}).status_code == 422
        assert api.post('/api/metrics/query', headers=operator,
                        json={**payload, 'group_by': 'hour'}).status_code == 422
        assert api.post('/metrics/query', json=payload).status_code == 401
        assert api.post('/metrics/query', json=payload,
                        headers={'X-Plugin-Token': 'test-plugin-token'}).status_code == 200
    audits = asyncio.run(redis.xrange('audit'))
    assert any(entry['action'] == 'metric.query' and entry['outcome'] == 'ok' for _, entry in audits)
