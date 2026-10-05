"""Keep legacy Redis fixtures isolated while production accounts use MySQL."""
import os

import pytest

os.environ.setdefault('JWT_SECRET', 'test-secret-' * 4)
from app import main, worker  # noqa: E402


class FixtureUsers:
    def __init__(self, redis_provider):
        self.redis_provider = redis_provider

    # 旧测试在 Redis 中造账号；通过注入仓库适配其原有认证断言。
    async def get(self, username):
        raw = await self.redis_provider().hgetall(f'user:{username}')
        if not raw:
            return None
        return {'username': username, 'password_hash': raw.get('password', ''),
                'role': raw.get('role'), 'disabled': raw.get('disabled') == '1',
                'session_version': int(raw.get('sessionVersion', 0))}


@pytest.fixture(autouse=True)
def account_store_fixture():
    main.app.state.users = FixtureUsers(lambda: main.r)
    worker.users = FixtureUsers(lambda: worker.r)
    yield
    main.app.state.users = None
    worker.users = None
