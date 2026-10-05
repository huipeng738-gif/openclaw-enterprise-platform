import asyncio
import json
import os

import fakeredis.aioredis
import httpx
import pytest
from fastapi.testclient import TestClient

os.environ['JWT_SECRET'] = 'test-secret-' * 4

from app import main
from app.worker import Gateway
from app.clients.ragflow import RagflowClient


DATASET_ID = 'a' * 32
DOCUMENT_ID = 'b' * 32


def test_knowledge_api_rbac_plugin_and_ragflow(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setenv('PLUGIN_SERVICE_TOKEN', 'test-plugin-token')
    monkeypatch.delenv('RAGFLOW_DATASET_IDS', raising=False)
    for username, role in [('admin', 'admin'), ('operator', 'operator')]:
        asyncio.run(fake.hset(f'user:{username}', mapping={
            'password': main.password_hash('strongpassword123'), 'role': role}))

    calls = []

    def ragflow(request):
        assert request.headers['Authorization'] == 'Bearer test-ragflow-key'
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == '/api/v1/datasets' and request.method == 'POST':
            return httpx.Response(200, json={'code': 0, 'data': {'id': DATASET_ID, 'name': '企业制度'}})
        if request.method == 'DELETE':
            assert json.loads(request.content)['ids'] in ([DATASET_ID], [DOCUMENT_ID])
            return httpx.Response(200, json={'code': 0})
        if path == '/api/v1/datasets':
            return httpx.Response(200, json={'code': 0, 'data': [{'id': DATASET_ID, 'name': '企业制度'}]})
        if path.endswith('/documents') and request.method == 'POST':
            return httpx.Response(200, json={'code': 0, 'data': [{'id': DOCUMENT_ID, 'name': 'policy.txt'}]})
        if path.endswith('/documents'):
            return httpx.Response(200, json={'code': 0, 'data': {'docs': [{'id': DOCUMENT_ID, 'name': 'policy.txt', 'run': 'UNSTART'}], 'total': 1}})
        if path.endswith('/chunks'):
            return httpx.Response(200, json={'code': 0, 'data': None})
        if path == '/api/v1/retrieval':
            body = json.loads(request.content)
            assert body['dataset_ids'] == [DATASET_ID]
            assert body['page_size'] == 5
            assert 'top_k' not in body
            return httpx.Response(200, json={'code': 0, 'data': {'total': 1, 'chunks': [
                {'id': 'c' * 32, 'kb_id': DATASET_ID, 'document_id': DOCUMENT_ID,
                 'document_keyword': 'policy.txt', 'content': '年假规定', 'similarity': 0.9}]}})
        raise AssertionError(f'unexpected RAGFlow call: {request.method} {path}')

    ragflow_client = RagflowClient('http://ragflow.test', 'test-ragflow-key', transport=httpx.MockTransport(ragflow))
    monkeypatch.setattr(RagflowClient, 'from_env', classmethod(lambda cls: ragflow_client))

    with TestClient(main.app) as api:
        def login(username):
            token = api.post('/api/auth/login', json={
                'username': username, 'password': 'strongpassword123'}).json()['access_token']
            return {'Authorization': f'Bearer {token}'}

        admin = login('admin')
        operator = login('operator')
        assert api.get('/api/knowledge/datasets').status_code == 401
        assert api.get('/api/knowledge/datasets/available', headers=operator).status_code == 403
        assert api.get('/api/knowledge/datasets/available', headers=admin).json()[0]['id'] == DATASET_ID
        assert api.post('/api/knowledge/datasets', headers=operator, json={'name': '企业制度'}).status_code == 403
        created = api.post('/api/knowledge/datasets', headers=admin, json={'name': '企业制度'})
        assert created.status_code == 201 and created.json()['id'] == DATASET_ID
        assert api.get('/api/knowledge/datasets/available', headers=admin).json() == []
        assert api.get('/api/knowledge/datasets', headers=operator).json()[0]['id'] == DATASET_ID
        assert api.get(f'/api/knowledge/bases/{DATASET_ID}', headers=operator).json()['id'] == DATASET_ID
        assert api.delete(f'/api/knowledge/bases/{DATASET_ID}', headers=operator).status_code == 403
        uploaded = api.post(f'/api/knowledge/datasets/{DATASET_ID}/documents', headers=admin,
                            files={'file': ('policy.txt', b'Annual leave', 'text/plain')})
        assert uploaded.status_code == 201 and uploaded.json()[0]['id'] == DOCUMENT_ID
        assert api.get(f'/api/knowledge/datasets/{DATASET_ID}/documents', headers=operator).json()['total'] == 1
        assert api.get(f'/api/knowledge/bases/{DATASET_ID}/documents/{DOCUMENT_ID}/status',
                       headers=operator).json()['run'] == 'UNSTART'
        assert api.post(f'/api/knowledge/datasets/{DATASET_ID}/parse', headers=admin,
                        json={'document_ids': [DOCUMENT_ID]}).status_code == 202
        result = api.post('/api/knowledge/search', headers=operator, json={'query': '年假', 'top_k': 5})
        assert result.status_code == 200 and result.json()['chunks'][0]['content'] == '年假规定'
        assert 'test-ragflow-key' not in result.text
        assert result.json()['results'][0]['document_id'] == DOCUMENT_ID
        assert result.json()['results'][0]['knowledge_base_id'] == DATASET_ID
        assert api.post('/api/knowledge/retrieval', headers=operator, json={
            'query': '年假', 'knowledge_base_ids': [DATASET_ID], 'similarity_threshold': 0.4}).status_code == 200
        assert api.post('/api/knowledge/search', headers=operator,
                        json={'query': '年假', 'dataset_ids': ['d' * 32]}).status_code == 403
        assert api.post('/knowledge/search', json={'query': '年假'}).status_code == 401
        assert api.post('/knowledge/search', headers={'X-Plugin-Token': 'test-plugin-token'},
                        json={'query': '年假'}).status_code == 200
        assert api.delete(f'/api/knowledge/bases/{DATASET_ID}',
                          headers={'X-Plugin-Token': 'test-plugin-token'}).status_code == 401
        assert api.delete(f'/api/knowledge/bases/{DATASET_ID}/documents/{DOCUMENT_ID}',
                          headers=admin).status_code == 204
        assert api.delete(f'/api/knowledge/bases/{DATASET_ID}', headers=admin).status_code == 204
        assert api.get('/api/knowledge/bases', headers=admin).json() == []
    assert ('POST', '/api/v1/retrieval') in calls
    audits = asyncio.run(fake.xrange('audit'))
    assert any(values['action'] == 'document.upload' for _, values in audits)
    assert all('年假' not in json.dumps(values, ensure_ascii=False) for _, values in audits)


def test_ragflow_business_error_is_not_exposed():
    async def scenario():
        client = RagflowClient('http://ragflow.test', 'test-key', transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'code': 102, 'message': 'secret upstream detail'})))
        try:
            from app.clients.ragflow import RagflowError
            try:
                await client.retrieve('question', [DATASET_ID], 5)
                assert False, 'expected RAGFlow failure'
            except RagflowError as exc:
                assert exc.status_code == 502
                assert 'secret' not in exc.detail
        finally:
            await client.close()
    asyncio.run(scenario())


def test_ragflow_empty_dataset_returns_empty_retrieval():
    async def scenario():
        client = RagflowClient('http://ragflow.test', 'test-key', transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={
                'code': 102, 'message': 'No chunk found! Check the chunk status please!', 'data': None})))
        try:
            assert await client.retrieve('question', [DATASET_ID], 5) == {'chunks': [], 'total': 0}
        finally:
            await client.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('response_status', [401, 403, 404, 500])
def test_ragflow_http_error_hides_upstream_detail(response_status, caplog):
    async def scenario():
        client = RagflowClient('http://ragflow.test', 'test-key', transport=httpx.MockTransport(
            lambda request: httpx.Response(response_status, text='private upstream detail')))
        try:
            from app.clients.ragflow import RagflowError
            with pytest.raises(RagflowError) as caught:
                await client.list_datasets()
            assert caught.value.status_code == 502
            assert 'private' not in caught.value.detail
        finally:
            await client.close()
    asyncio.run(scenario())
    assert 'test-key' not in caplog.text


@pytest.mark.parametrize('error', [httpx.ConnectError('connection failed'), httpx.ReadTimeout('timed out')])
def test_ragflow_network_error(error):
    async def scenario():
        def fail(request):
            raise error
        client = RagflowClient('http://ragflow.test', 'test-key', transport=httpx.MockTransport(fail))
        try:
            from app.clients.ragflow import RagflowError
            with pytest.raises(RagflowError) as caught:
                await client.list_datasets()
            assert caught.value.status_code == (504 if isinstance(error, httpx.TimeoutException) else 502)
            assert 'test-key' not in caught.value.detail
        finally:
            await client.close()
    asyncio.run(scenario())


def test_gateway_knowledge_tool_event_keeps_only_verified_sources(monkeypatch):
    events = []

    async def capture(_task_id, kind, **data):
        events.append((kind, data))

    monkeypatch.setattr('app.worker.emit', capture)
    gateway = Gateway('task-1')
    result = {'content': [{'type': 'text', 'text': json.dumps({'results': [
        {'document_name': 'policy.txt', 'document_id': DOCUMENT_ID,
         'knowledge_base_id': DATASET_ID, 'score': 0.9, 'content': 'private passage'},
    ]})}]}
    asyncio.run(gateway.handle_event({'seq': 1, 'stream': 'tool', 'data': {
        'name': 'knowledge_search', 'phase': 'result', 'args': {'query': '年假'}, 'result': result}}))
    assert events[0][1]['resultCount'] == 1
    assert events[0][1]['query'] == '年假'
    assert 'private passage' not in json.dumps(events)
    assert gateway.sources == [{'document_name': 'policy.txt', 'document_id': DOCUMENT_ID,
                                'knowledge_base_id': DATASET_ID, 'score': 0.9}]
