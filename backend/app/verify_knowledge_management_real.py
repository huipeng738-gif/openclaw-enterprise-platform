"""Verify real knowledge management without calling an Agent model."""
import asyncio
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user
from app.services.knowledge import MANAGED_DATASETS_KEY


# 用一次性数据集验证创建、发现未关联项、关联与删除的完整链路。
async def verify():
    owner = 'knowledge_manage_probe_' + uuid.uuid4().hex[:10]
    name = '知识库验收_' + uuid.uuid4().hex[:10]
    dataset_id = None
    db, _ = await create_probe_user(owner, 'admin')
    try:
        token = main.access_response(owner, 'admin')['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=30) as api:
            created = await api.post('/api/knowledge/bases', json={'name': name}, headers=headers)
            assert created.status_code == 201, f'create status={created.status_code}'
            dataset_id = created.json()['id']
            listed = await api.get('/api/knowledge/bases', headers=headers)
            assert listed.status_code == 200 and any(item['id'] == dataset_id for item in listed.json())
            await main.r.srem(MANAGED_DATASETS_KEY, dataset_id)
            available = await api.get('/api/knowledge/datasets/available', headers=headers)
            assert available.status_code == 200 and any(item['id'] == dataset_id for item in available.json())
            registered = await api.post(f'/api/knowledge/datasets/{dataset_id}/register', headers=headers)
            assert registered.status_code == 200, f'register status={registered.status_code}'
            listed = await api.get('/api/knowledge/bases', headers=headers)
            assert listed.status_code == 200 and any(item['id'] == dataset_id for item in listed.json())
            print('Real RAGFlow knowledge create, available, register: PASS')
    finally:
        if dataset_id:
            client = getattr(main.app.state, 'ragflow', None)
            if client is None:
                from app.clients.ragflow import RagflowClient
                client = RagflowClient.from_env()
            try:
                await client.delete_dataset(dataset_id)
                print('Temporary dataset cleanup: PASS')
            finally:
                await client.close()
                await main.r.srem(MANAGED_DATASETS_KEY, dataset_id)
        await delete_probe_user(db, owner)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
