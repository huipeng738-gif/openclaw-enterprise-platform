import asyncio
import os
from .main import password_hash, r

async def main():
    username = os.environ['BOOTSTRAP_ADMIN_USER']
    password = os.environ['BOOTSTRAP_ADMIN_PASSWORD']
    if not username.isidentifier() or len(password) < 12:
        raise ValueError('admin username or password invalid')
    created = await r.hsetnx(f'user:{username}', 'password', password_hash(password))
    if created:
        await r.hset(f'user:{username}', mapping={'role': 'admin', 'disabled': '0'})
    print('Admin created' if created else 'Admin already exists; password unchanged')
    await r.aclose()

if __name__ == '__main__':
    asyncio.run(main())
