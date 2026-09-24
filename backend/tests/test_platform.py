import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path

import fakeredis.aioredis
from fastapi.testclient import TestClient
import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import base64

os.environ['JWT_SECRET'] = 'test-secret-' * 4
from app import main, worker  # noqa: E402


def test_login_rbac_owner_retry_and_audit(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    asyncio.run(fake.hset('user:alice', mapping={'password': main.password_hash('strongpassword123'), 'role': 'operator'}))
    asyncio.run(fake.hset('user:bob', mapping={'password': main.password_hash('strongpassword123'), 'role': 'viewer'}))
    with TestClient(main.app) as client:
        assert client.get('/api/tasks').status_code == 401
        a = client.post('/api/auth/login', json={'username': 'alice', 'password': 'strongpassword123'})
        assert a.status_code == 200
        headers = {'Authorization': 'Bearer ' + a.json()['access_token']}
        created = client.post('/api/tasks', headers=headers, json={'prompt': 'hello'})
        assert created.status_code == 202
        task_id = created.json()['id']
        assert client.get(f'/api/tasks/{task_id}', headers=headers).status_code == 200
        assert client.post(f'/api/tasks/{task_id}/retry', headers=headers).status_code == 409
        assert client.post(f'/api/tasks/{task_id}/cancel', headers=headers).status_code == 200
        assert client.get('/api/audit', headers=headers).status_code == 403
        b = client.post('/api/auth/login', json={'username': 'bob', 'password': 'strongpassword123'})
        bh = {'Authorization': 'Bearer ' + b.json()['access_token']}
        assert client.get(f'/api/tasks/{task_id}', headers=bh).status_code == 403
        assert client.post('/api/tasks', headers=bh, json={'prompt': 'hello'}).status_code == 403
        ticket = client.post(f'/api/tasks/{task_id}/ws-ticket', headers=headers).json()['ticket']
        with client.websocket_connect(f'/ws/tasks/{task_id}?ticket={ticket}') as ws:
            assert ws.receive_json()['task']['id'] == task_id
        assert asyncio.run(fake.get(f'ws-ticket:{ticket}')) is None


async def mock_gateway(socket):
    await socket.send(json.dumps({'type': 'event', 'event': 'connect.challenge', 'payload': {'nonce': 'abc123', 'ts': 1234567890}}))
    handshake = json.loads(await socket.recv())
    assert handshake['method'] == 'connect'
    assert handshake['params']['caps'] == ['tool-events']
    assert handshake['params']['device']['nonce'] == 'abc123'
    params = handshake['params']
    d = params['device']
    pub = base64.urlsafe_b64decode(d['publicKey'] + '==')
    assert hashlib.sha256(pub).hexdigest() == d['id']
    signed = '|'.join(['v3', d['id'], 'gateway-client', 'operator', 'operator', ','.join(params['scopes']), str(d['signedAt']), 'test-gateway-token', d['nonce'], 'linux', ''])
    Ed25519PublicKey.from_public_bytes(pub).verify(base64.urlsafe_b64decode(d['signature'] + '=='), signed.encode())
    await socket.send(json.dumps({'type': 'res', 'id': 'connect', 'ok': True, 'payload': {'type': 'hello-ok'}}))
    while True:
        try:
            frame = json.loads(await socket.recv())
        except websockets.exceptions.ConnectionClosed:
            return
        if frame['method'] == 'agent':
            await socket.send(json.dumps({'type': 'res', 'id': frame['id'], 'ok': True, 'payload': {'runId': 'run-1'}}))
            await socket.send(json.dumps({'type': 'event', 'event': 'agent', 'payload': {'runId': 'run-1', 'seq': 1, 'stream': 'tool', 'data': {'phase': 'start', 'name': 'knowledge_search', 'args': {'secret': 'must-not-leak'}}}}))
            await socket.send(json.dumps({'type': 'event', 'event': 'agent', 'payload': {'runId': 'run-1', 'seq': 2, 'stream': 'assistant', 'data': {'text': '真实答复'}}}))
        elif frame['method'] == 'agent.wait':
            await socket.send(json.dumps({'type': 'res', 'id': frame['id'], 'ok': True, 'payload': {'status': 'ok'}}))
        elif frame['method'] == 'chat.abort':
            await socket.send(json.dumps({'type': 'res', 'id': frame['id'], 'ok': True, 'payload': {'ok': True}}))


def test_gateway_handshake_run_and_tool_event(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(worker, 'r', fake)
    monkeypatch.setattr(worker, 'TOKEN', 'test-gateway-token')
    async def scenario():
        with tempfile.TemporaryDirectory() as directory:
            monkeypatch.setattr(worker, 'IDENTITY', Path(directory) / 'device.pem')
            async with websockets.serve(mock_gateway, '127.0.0.1', 0) as server:
                monkeypatch.setattr(worker, 'GATEWAY', f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}')
                task = {'id': 'task-1', 'owner': 'alice', 'prompt': 'hello', 'agent': 'coordinator', 'timeoutSeconds': 10, 'status': 'queued'}
                await fake.set('task:task-1', json.dumps(task))
                await worker.run('task-1')
                stored = json.loads(await fake.get('task:task-1'))
                events = [json.loads(v['data']) for _, v in await fake.xrange('events:task-1')]
                assert stored['status'] == 'completed'
                assert stored['result'] == '真实答复'
                assert any(e.get('name') == 'knowledge_search' for e in events)
                assert all('secret' not in json.dumps(e) for e in events)
                assert len(worker.IDENTITY.read_bytes()) > 50
    asyncio.run(scenario())
