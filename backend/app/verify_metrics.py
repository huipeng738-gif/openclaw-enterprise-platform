"""Opt-in real HTTP and MySQL smoke check for code-defined metrics."""
import asyncio
import os
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 用固定 Demo Seed 核对四个指标和权限，结束后删除临时 MySQL 身份。
async def verify():
    username = 'metrics_probe_' + uuid.uuid4().hex[:8]
    db, users = await create_probe_user(username, 'operator')
    try:
        token = main.access_response(username, 'operator')['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        body = {'start_date': '2026-08-01', 'end_date': '2026-09-30', 'group_by': 'day'}
        expected = {'sales_amount': '428.00', 'order_count': '3',
                    'refund_rate': '0.00', 'active_customer_count': '2'}
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10) as client:
            for metric, total in expected.items():
                response = await client.post('/api/metrics/query', headers=headers,
                                             json={**body, 'metric': metric})
                assert response.status_code == 200, response.status_code
                assert response.json()['total'] == total, metric
            for grouping, periods in [('day', 3), ('week', 2), ('month', 1)]:
                grouped = await client.post('/api/metrics/query', headers=headers,
                    json={**body, 'metric': 'order_count', 'group_by': grouping})
                assert grouped.status_code == 200 and len(grouped.json()['points']) == periods
            empty = await client.post('/api/metrics/query', headers=headers, json={
                **body, 'metric': 'sales_amount', 'start_date': '2025-01-01', 'end_date': '2025-01-31'})
            assert empty.status_code == 200 and empty.json()['points'] == []
            assert (await client.post('/api/metrics/query', headers=headers,
                                      json={**body, 'metric': 'unknown'})).status_code == 422
            await users.change(username, role='viewer')
            headers = {'Authorization': 'Bearer ' + main.access_response(username, 'viewer', 1)['access_token']}
            assert (await client.post('/api/metrics/query', headers=headers,
                                      json={**body, 'metric': 'order_count'})).status_code == 403
            plugin = {'X-Plugin-Token': os.environ['PLUGIN_SERVICE_TOKEN']}
            assert (await client.post('/metrics/query', headers=plugin,
                                      json={**body, 'metric': 'order_count'})).status_code == 200
            print('Real metrics HTTP integration: PASS')
    finally:
        await delete_probe_user(db, username)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
