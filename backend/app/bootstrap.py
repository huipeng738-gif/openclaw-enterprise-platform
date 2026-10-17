import asyncio
import os
from .main import password_hash, r
from .clients.business_db import BusinessDatabase
from .services.users import UserStore, migrate_legacy_users


# 从环境配置初始化 MySQL 管理员；先导入旧 Redis 账号且不覆盖已有密码。
async def main():
    username = os.environ['BOOTSTRAP_ADMIN_USER']
    password = os.environ['BOOTSTRAP_ADMIN_PASSWORD']
    if not username.isidentifier() or len(password) < 12:
        raise ValueError('admin username or password invalid')
    db = await BusinessDatabase.from_env()
    if db is None:
        raise RuntimeError('MySQL account store is required')
    store = UserStore(db.pool)
    await store.ensure_schema()
    await migrate_legacy_users(r, store)
    created = await store.create(username, password_hash(password), 'admin', ignore_existing=True)
    print('Admin created' if created else 'Admin already exists; password unchanged')
    await db.close()
    await r.aclose()


if __name__ == '__main__':
    asyncio.run(main())
