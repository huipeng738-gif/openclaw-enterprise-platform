"""Opt-in real HTTP smoke check for the isolated Demo MySQL business tools."""
import asyncio
import os
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 创建临时 MySQL 身份，经运行中的 API 验证 JWT、RBAC、MySQL 和 Tool 入口，最后清理。
async def verify():
    username = 'business_probe_' + uuid.uuid4().hex[:8]
    db, users = await create_probe_user(username, 'operator')
    try:
        token = main.access_response(username, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10) as client:
            headers = {'Authorization': 'Bearer ' + token}
            listing = await client.get('/api/orders', headers=headers)
            assert listing.status_code == 200 and listing.json()['total'] == 3
            assert [row['order_no'] for row in listing.json()['items']] == [
                'ORD-DEMO-003', 'ORD-DEMO-002', 'ORD-DEMO-001']
            filtered = await client.get('/api/orders', headers=headers,
                                        params={'search': '演示键盘', 'status': 'shipped',
                                                'payment_status': 'paid', 'page_size': 1})
            assert filtered.status_code == 200 and filtered.json()['total'] == 1, (
                filtered.status_code, filtered.json())
            assert filtered.json()['items'][0]['order_no'] == 'ORD-DEMO-001'
            empty = await client.get('/api/orders', headers=headers, params={'search': '不存在的商品'})
            assert empty.status_code == 200 and empty.json()['total'] == 0 and empty.json()['items'] == []
            order = await client.get('/api/orders/ORD-DEMO-001', headers=headers)
            customer = await client.get('/api/customers/CUST-DEMO-001', headers=headers)
            customer_list = await client.get('/api/customers', headers=headers,
                                             params={'search': '演示客户', 'level': 'vip', 'status': 'active'})
            assert order.status_code == 200 and order.json()['total_amount'] == '299.00'
            assert len(order.json()['order_items']) == 2
            assert customer.status_code == 200 and customer.json()['phone'] == '138****0001'
            assert customer_list.status_code == 200 and customer_list.json()['total'] == 1
            assert customer_list.json()['items'][0]['phone'] == '138****0001'
            assert (await client.get('/api/orders/ORD-MISSING', headers=headers)).status_code == 404
            assert (await client.get('/api/orders/INVALID;SQL', headers=headers)).status_code == 422
            await users.change(username, role='viewer')
            headers = {'Authorization': 'Bearer ' + main.access_response(username, 'viewer', 1)['access_token']}
            assert (await client.get('/api/orders/ORD-DEMO-001', headers=headers)).status_code == 403
            assert (await client.get('/api/orders', headers=headers)).status_code == 403
            assert (await client.get('/api/customers', headers=headers)).status_code == 403
            plugin_token = os.environ['PLUGIN_SERVICE_TOKEN']
            tool_headers = {'X-Plugin-Token': plugin_token}
            assert (await client.post('/business/orders/query', headers=tool_headers,
                                      json={'order_no': 'ORD-DEMO-001'})).status_code == 200
            assert (await client.post('/business/customers/query', headers=tool_headers,
                                      json={'customer_no': 'CUST-DEMO-001'})).status_code == 200
            print('Real business HTTP integration: PASS')
    finally:
        await delete_probe_user(db, username)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
