"""MySQL source of truth for platform accounts."""
import aiomysql


class UserStore:
    def __init__(self, pool):
        self.pool = pool

    # 只读检查迁移是否已由 MySQL 初始化脚本完成；API 不持有 DDL 权限。
    async def ensure_schema(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute('SELECT username FROM platform_users LIMIT 0')

    # 读取单个账号供认证及 Worker 权限复核，不输出密码字段给前端。
    async def get(self, username):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute('SELECT username, password_hash, role, disabled, session_version '
                                     'FROM platform_users WHERE username=%s', (username,))
                return await cursor.fetchone()

    # 仅列出设置页面需要的非敏感账号字段。
    async def list(self):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute('SELECT username, role, disabled FROM platform_users ORDER BY username')
                return await cursor.fetchall()

    # 使用主键唯一约束防止覆盖现有账号；迁移时可选择忽略已存在账号。
    async def create(self, username, password_hash, role, disabled=False, ignore_existing=False):
        verb = 'INSERT IGNORE' if ignore_existing else 'INSERT'
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f'{verb} INTO platform_users '
                                     '(username,password_hash,role,disabled) VALUES (%s,%s,%s,%s)',
                                     (username, password_hash, role, disabled))
                return cursor.rowcount == 1

    # 事务内锁定管理员行并保护最后一个可用管理员，同时递增会话版本。
    async def change(self, username, *, role=None, disabled=None, password_hash=None):
        async with self.pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("SELECT username FROM platform_users WHERE role='admin' "
                                         'AND disabled=0 FOR UPDATE')
                    admins = await cursor.fetchall()
                    await cursor.execute('SELECT username, role, disabled FROM platform_users '
                                         'WHERE username=%s FOR UPDATE', (username,))
                    current = await cursor.fetchone()
                    if not current:
                        await conn.rollback()
                        return None
                    new_role = role if role is not None else current['role']
                    new_disabled = disabled if disabled is not None else bool(current['disabled'])
                    if (current['role'] == 'admin' and not current['disabled'] and
                            (new_role != 'admin' or new_disabled) and len(admins) <= 1):
                        await conn.rollback()
                        return False
                    await cursor.execute('UPDATE platform_users SET role=%s, disabled=%s, '
                                         'password_hash=COALESCE(%s,password_hash), '
                                         'session_version=session_version+1 WHERE username=%s',
                                         (new_role, new_disabled, password_hash, username))
                await conn.commit()
                return {'username': username, 'role': new_role, 'disabled': new_disabled}
            except Exception:
                await conn.rollback()
                raise


# 将已有 Redis 账号无损导入 MySQL；已存在的 MySQL 行始终优先。
async def migrate_legacy_users(redis, store):
    if await redis.get('settings:users-migrated'):
        return
    async for key in redis.scan_iter(match='user:*'):
        legacy = await redis.hgetall(key)
        username = key[5:]
        if (username.isidentifier() and legacy.get('role') in {'viewer', 'operator', 'admin'}
                and legacy.get('password')):
            if await store.get(username) is None:
                await store.create(username, legacy['password'], legacy['role'],
                                   legacy.get('disabled') == '1', ignore_existing=True)
    await redis.set('settings:users-migrated', '1')
