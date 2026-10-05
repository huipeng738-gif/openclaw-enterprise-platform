import asyncio
import os
from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
import jwt
from fastapi.testclient import TestClient

os.environ['JWT_SECRET'] = 'test-secret-' * 4
from app import main  # noqa: E402


def test_refresh_session_cookie_rbac_and_logout(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setattr(main, 'REFRESH_COOKIE_SECURE', False)
    asyncio.run(fake.hset('user:alice', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'operator'}))
    with TestClient(main.app) as client:
        assert client.post('/api/auth/refresh').status_code == 401
        login = client.post('/api/auth/login', json={'username': 'alice', 'password': 'strongpassword123'})
        assert login.status_code == 200
        assert 'refresh_token' not in login.json()
        cookie_header = login.headers['set-cookie'].lower()
        assert 'httponly' in cookie_header and 'samesite=lax' in cookie_header
        assert 'path=/api/auth' in cookie_header
        cookie = client.cookies.get(main.REFRESH_COOKIE)
        claims = main.refresh_claims(cookie)
        key = f'auth:refresh:{claims["jti"]}'
        ttl = asyncio.run(fake.ttl(key))
        assert main.REFRESH_TOKEN_EXPIRE_DAYS * 86400 - 5 <= ttl <= main.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {cookie}'}).status_code == 401
        refreshed = client.post('/api/auth/refresh')
        assert refreshed.status_code == 200
        access = refreshed.json()['access_token']
        payload = jwt.decode(access, main.SECRET, algorithms=['HS256'], issuer='enterprise-bff')
        assert payload['type'] == 'access'
        assert payload['exp'] - payload['iat'] == main.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert client.get('/api/audit', headers={'Authorization': f'Bearer {access}'}).status_code == 403
        expired = jwt.encode({'sub': 'alice', 'iss': 'enterprise-bff', 'type': 'access',
                              'exp': datetime.now(timezone.utc) - timedelta(seconds=1)}, main.SECRET, algorithm='HS256')
        assert client.get('/api/auth/me', headers={'Authorization': f'Bearer {expired}'}).status_code == 401
        assert client.post('/api/auth/refresh').status_code == 200
        assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/auth/logout').status_code == 200
        assert asyncio.run(fake.get(key)) is None
        client.cookies.set(main.REFRESH_COOKIE, cookie, path=main.REFRESH_COOKIE_PATH)
        assert client.post('/api/auth/refresh').status_code == 401


def test_refresh_expired_disabled_and_missing_session(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setattr(main, 'REFRESH_COOKIE_SECURE', False)
    asyncio.run(fake.hset('user:alice', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'operator'}))
    with TestClient(main.app) as client:
        client.post('/api/auth/login', json={'username': 'alice', 'password': 'strongpassword123'})
        claims = main.refresh_claims(client.cookies.get(main.REFRESH_COOKIE))
        asyncio.run(fake.hset('user:alice', 'disabled', '1'))
        assert client.post('/api/auth/refresh').status_code == 401
        asyncio.run(fake.hset('user:alice', 'disabled', '0'))
        asyncio.run(fake.delete(f'auth:refresh:{claims["jti"]}'))
        assert client.post('/api/auth/refresh').status_code == 401
        claims['exp'] = datetime.now(timezone.utc) - timedelta(seconds=1)
        client.cookies.clear()
        client.cookies.set(main.REFRESH_COOKIE, jwt.encode(claims, main.SECRET, algorithm='HS256'), path=main.REFRESH_COOKIE_PATH)
        assert client.post('/api/auth/refresh').status_code == 401


def test_secure_cookie(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(main, 'r', fake)
    monkeypatch.setattr(main, 'REFRESH_COOKIE_SECURE', True)
    asyncio.run(fake.hset('user:alice', mapping={
        'password': main.password_hash('strongpassword123'), 'role': 'operator'}))
    with TestClient(main.app, base_url='https://testserver') as client:
        response = client.post('/api/auth/login', json={'username': 'alice', 'password': 'strongpassword123'})
        assert 'Secure' in response.headers['set-cookie']
        assert client.post('/api/auth/refresh').status_code == 200
