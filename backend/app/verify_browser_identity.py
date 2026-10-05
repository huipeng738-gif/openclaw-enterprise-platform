"""Create and remove a temporary real-login identity for browser acceptance."""
import asyncio
import json
import sys

from app import main
from app.clients.business_db import BusinessDatabase
from app.services.users import UserStore


# 仅接收标准输入中的一次性账号信息，避免在命令行或日志暴露密码。
async def run():
    payload = json.load(sys.stdin)
    username = payload['username']
    if not username.startswith(('database_browser_probe_', 'phase7_browser_probe_')):
        raise ValueError('temporary probe username required')
    db = await BusinessDatabase.from_env()
    if db is None:
        raise RuntimeError('MySQL account store is required')
    store = UserStore(db.pool)
    try:
        if payload['action'] == 'create':
            role = payload.get('role', 'operator')
            if role not in {'operator', 'admin'}:
                raise ValueError('temporary probe role required')
            await store.create(username, main.password_hash(payload['password']), role)
        elif payload['action'] == 'cleanup':
            task_id = payload.get('task_id')
            if task_id:
                await main.r.delete(f'task:{task_id}', f'events:{task_id}', f'cancel:{task_id}')
                await main.r.srem('tasks:all', task_id)
            async with db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute('DELETE FROM platform_users WHERE username=%s', (username,))
            await main.r.delete(f'login-attempts:{username}')
        else:
            raise ValueError('invalid probe action')
    finally:
        await db.close()
        await main.r.aclose()


if __name__ == '__main__':
    asyncio.run(run())
