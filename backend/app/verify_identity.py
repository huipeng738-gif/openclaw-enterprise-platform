"""Temporary MySQL identities used only by opt-in verification scripts."""
import secrets
import re

from app.clients.business_db import BusinessDatabase
from app.main import password_hash
from app.services.users import UserStore


# 创建独立一次性账号；随机密码不输出也不复用业务凭据。
async def create_probe_user(username, role):
    db = await BusinessDatabase.from_env()
    if db is None:
        raise RuntimeError('MySQL account store is required')
    store = UserStore(db.pool)
    await store.create(username, password_hash(secrets.token_urlsafe(24)), role)
    return db, store


# 仅删除本次创建的 probe 账号并释放连接池。
async def delete_probe_user(db, username):
    if not re.fullmatch(r'[a-z_]+_probe_[0-9a-f]{8,12}', username):
        raise ValueError('probe username required')
    try:
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('DELETE FROM platform_users WHERE username=%s', (username,))
    finally:
        await db.close()
