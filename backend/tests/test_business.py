import asyncio
import json
import os
from datetime import datetime
from decimal import Decimal

import fakeredis.aioredis
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ['JWT_SECRET'] = 'test-secret-' * 4

from app import main  # noqa: E402
from app.clients.business_db import BusinessDatabase, BusinessDatabaseError, BusinessDatabaseTimeout  # noqa: E402
from app.repositories.business import CustomerRepository, OrderRepository  # noqa: E402
from app.services.business import CustomerService, OrderService  # noqa: E402


class FixtureDatabase:
    def __init__(self):
        self.calls = []
        self.failure = None

    async def fetchone(self, sql, params):
        self.calls.append((sql, params))
        if self.failure:
            raise self.failure
        if 'COUNT(*) AS total FROM orders' in sql:
            return {'total': 1}
        if 'COUNT(*) AS total FROM customers' in sql:
            return {'total': 1}
        if params == ('ORD-DEMO-001',):
            return {'id': 10, 'order_no': 'ORD-DEMO-001', 'status': 'shipped',
                    'total_amount': Decimal('299.00'), 'payment_status': 'paid',
                    'created_at': datetime(2026, 9, 1), 'customer_no': 'CUST-DEMO-001',
                    'customer_name': '演示客户甲'}
        if params == ('CUST-DEMO-001',):
            return {'id': 1, 'customer_no': 'CUST-DEMO-001', 'name': '演示客户甲',
                    'phone': '13800000001', 'level': 'vip', 'status': 'active',
                    'created_at': datetime(2026, 8, 1)}
        if params == (1,):
            return {'order_count': 2, 'total_amount': Decimal('299.00'),
                    'last_order_time': datetime(2026, 9, 10)}
        return None

    async def fetchall(self, sql, params):
        self.calls.append((sql, params))
        if self.failure:
            raise self.failure
        if 'FROM orders o JOIN customers c' in sql:
            return [{'order_no': 'ORD-DEMO-001', 'status': 'shipped',
                     'total_amount': Decimal('299.00'), 'payment_status': 'paid',
                     'created_at': datetime(2026, 9, 1), 'customer_no': 'CUST-DEMO-001',
                     'customer_name': '演示客户甲'}]
        if 'FROM customers c LEFT JOIN orders o' in sql:
            return [{'customer_no': 'CUST-DEMO-001', 'name': '演示客户甲',
                     'phone': '13800000001', 'level': 'vip', 'status': 'active',
                     'created_at': datetime(2026, 8, 1), 'order_count': 2,
                     'last_order_time': datetime(2026, 9, 10)}]
        if params == (10,):
            return [{'product_name': '演示键盘', 'sku': 'DEMO-KEYBOARD',
                     'quantity': 1, 'unit_price': Decimal('199.00')}]
        return [{'order_no': 'ORD-DEMO-001', 'status': 'shipped',
                 'total_amount': Decimal('299.00'), 'payment_status': 'paid',
                 'created_at': datetime(2026, 9, 1)}]

    async def close(self):
        pass


def test_repositories_and_services_use_bounded_parameterized_queries():
    db = FixtureDatabase()

    async def scenario():
        order = await OrderService(OrderRepository(db)).query('ORD-DEMO-001')
        customer = await CustomerService(CustomerRepository(db)).query('CUST-DEMO-001')
        page = await OrderService(OrderRepository(db)).list_page('100%_!', 'shipped', 'paid', 2, 10)
        customers = await CustomerService(CustomerRepository(db)).list_page('100%_!', 'vip', 'active', 1, 10)
        assert order['total_amount'] == '299.00'
        assert order['order_items'][0]['sku'] == 'DEMO-KEYBOARD'
        assert customer['phone'] == '138****0001'
        assert customer['order_count'] == 2
        assert page['items'][0]['total_amount'] == '299.00'
        assert page['page'] == 2 and page['page_size'] == 10
        assert customers['items'][0]['phone'] == '138****0001'
        assert customers['items'][0]['order_count'] == 2
        customer_filter = [call for call in db.calls if 'COUNT(*) AS total FROM customers' in call[0]]
        assert customer_filter[0][1] == ('%100!%!_!!%',) * 2 + ('vip', 'active')
        filtered = [call for call in db.calls if 'COUNT(*) AS total FROM orders' in call[0]]
        assert filtered and "ESCAPE '!'" in filtered[0][0]
        assert filtered[0][1] == ('%100!%!_!!%',) * 3 + ('shipped', 'paid')
        assert any(params[-2:] == (10, 10) for sql, params in db.calls if 'OFFSET %s' in sql)
        for sql, params in db.calls:
            assert '%s' in sql and isinstance(params, tuple)
            if isinstance(params[0], str):
                assert params[0] not in sql
        assert any('LIMIT 50' in sql for sql, _ in db.calls)
        assert any('LIMIT 5' in sql for sql, _ in db.calls)
        with pytest.raises(HTTPException) as missing:
            await OrderService(OrderRepository(db)).query('ORD-MISSING')
        assert missing.value.status_code == 404
        with pytest.raises(HTTPException) as invalid:
            await CustomerService(CustomerRepository(db)).query('CUST;DROP')
        assert invalid.value.status_code == 422

    asyncio.run(scenario())


def test_business_api_rbac_plugin_audit_and_errors(monkeypatch):
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db = FixtureDatabase()
    monkeypatch.setattr(main, 'r', fake_redis)
    monkeypatch.setenv('PLUGIN_SERVICE_TOKEN', 'test-plugin-token')

    async def load_db(_cls):
        return db

    monkeypatch.setattr(BusinessDatabase, 'from_env', classmethod(load_db))
    for username, role in [('operator', 'operator'), ('viewer', 'viewer')]:
        asyncio.run(fake_redis.hset(f'user:{username}', mapping={
            'password': main.password_hash('strongpassword123'), 'role': role}))

    with TestClient(main.app) as api:
        def headers(username):
            token = api.post('/api/auth/login', json={
                'username': username, 'password': 'strongpassword123'}).json()['access_token']
            return {'Authorization': 'Bearer ' + token}

        operator, viewer = headers('operator'), headers('viewer')
        assert api.get('/api/orders/ORD-DEMO-001').status_code == 401
        assert api.get('/api/orders').status_code == 401
        assert api.get('/api/orders', headers=viewer).status_code == 403
        assert api.get('/api/customers').status_code == 401
        assert api.get('/api/customers', headers=viewer).status_code == 403
        listing = api.get('/api/orders?search=DEMO&status=shipped&page_size=10', headers=operator)
        assert listing.status_code == 200 and listing.json()['items'][0]['order_no'] == 'ORD-DEMO-001'
        assert listing.json()['total'] == 1 and listing.headers['Cache-Control'] == 'no-store'
        assert api.get('/api/orders?page_size=101', headers=operator).status_code == 422
        assert api.get('/api/orders?status=shipped%3BDROP', headers=operator).status_code == 422
        customers = api.get('/api/customers?search=DEMO&level=vip&status=active', headers=operator)
        assert customers.status_code == 200 and customers.json()['total'] == 1
        assert customers.json()['items'][0]['phone'] == '138****0001'
        assert customers.headers['Cache-Control'] == 'no-store'
        assert api.get('/api/customers?level=admin', headers=operator).status_code == 422
        assert api.get('/api/orders/ORD-DEMO-001', headers=viewer).status_code == 403
        order = api.get('/api/orders/ORD-DEMO-001', headers=operator)
        assert order.status_code == 200 and order.json()['customer']['customer_no'] == 'CUST-DEMO-001'
        assert order.headers['Cache-Control'] == 'no-store'
        customer = api.get('/api/customers/CUST-DEMO-001', headers=operator)
        assert customer.status_code == 200 and customer.json()['phone'] == '138****0001'
        assert '13800000001' not in customer.text
        assert api.get('/api/orders/ORD-MISSING', headers=operator).status_code == 404
        assert api.get('/api/customers/CUST-MISSING', headers=operator).status_code == 404
        assert api.get('/api/orders/INVALID;SQL', headers=operator).status_code == 422
        assert api.post('/business/orders/query', json={'order_no': 'ORD-DEMO-001'}).status_code == 401
        tool = {'X-Plugin-Token': 'test-plugin-token'}
        assert api.post('/business/orders/query', headers=tool,
                        json={'order_no': 'ORD-DEMO-001'}).status_code == 200
        assert api.post('/business/customers/query', headers=tool,
                        json={'customer_no': 'CUST-DEMO-001'}).status_code == 200
        assert api.post('/business/customers/query', headers=tool,
                        json={'customer_no': 'CUST;DROP'}).status_code == 422
        db.failure = BusinessDatabaseError('business database unavailable')
        assert api.get('/api/orders/ORD-DEMO-001', headers=operator).status_code == 503
        db.failure = BusinessDatabaseTimeout('business database query timed out')
        assert api.get('/api/customers/CUST-DEMO-001', headers=operator).status_code == 504

    audits = asyncio.run(fake_redis.xrange('audit'))
    query_audits = [entry for _, entry in audits if entry['action'] in {'order.query', 'customer.query', 'order.list'}]
    assert any(entry['outcome'] == 'ok' for entry in query_audits)
    assert any(entry['outcome'] == 'failed' for entry in query_audits)
    assert all('CUST-DEMO' not in json.dumps(entry) for entry in query_audits)


def test_business_database_enforces_query_timeout():
    class SlowPool:
        def acquire(self):
            return self

        async def __aenter__(self):
            await asyncio.sleep(0.03)

        async def __aexit__(self, *_):
            pass

    async def scenario():
        db = BusinessDatabase(SlowPool(), timeout=0.001)
        with pytest.raises(BusinessDatabaseTimeout):
            await db.fetchone('SELECT 1', ())

    asyncio.run(scenario())
