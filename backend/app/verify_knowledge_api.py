"""Read-only RAGFlow and plugin search probe without an Agent model run."""
import asyncio
import os
import uuid

import httpx

from app import main
from app.verify_identity import create_probe_user, delete_probe_user


# 用一次性平台账号验证知识库列表和已有托管数据集的插件检索入口。
async def verify():
    owner = 'knowledge_probe_' + uuid.uuid4().hex[:10]
    db, _ = await create_probe_user(owner, 'operator')
    try:
        token = main.access_response(owner, 'operator')['access_token']
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=20) as api:
            listing = await api.get('/api/knowledge/bases', headers={'Authorization': f'Bearer {token}'})
            assert listing.status_code == 200, listing.status_code
            datasets = listing.json()
            assert isinstance(datasets, list)
            if not datasets:
                print('RAGFlow list PASS; knowledge_search PARTIAL: no managed dataset')
                return
            search = await api.post('/knowledge/search',
                                    headers={'X-Plugin-Token': os.environ['PLUGIN_SERVICE_TOKEN']},
                                    json={'query': '测试', 'top_k': 1, 'dataset_ids': [datasets[0]['id']]})
            assert search.status_code == 200, search.status_code
            assert isinstance(search.json()['results'], list)
            print('RAGFlow list and plugin knowledge_search: PASS')
    finally:
        await delete_probe_user(db, owner)
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
