"""Async read boundary for the isolated business Demo MySQL database."""
import asyncio
import logging
import os
from typing import Any

import aiomysql

log = logging.getLogger(__name__)


class BusinessDatabaseError(Exception):
    pass


class BusinessDatabaseTimeout(BusinessDatabaseError):
    pass


class BusinessDatabase:
    # 保存连接池和单次查询超时；SQL 由 Repository 固定提供。
    def __init__(self, pool: Any, timeout: float):
        self.pool = pool
        self.timeout = timeout

    # 从环境配置创建连接池；未设置 host 时保留非 Compose 的现有启动方式。
    @classmethod
    async def from_env(cls) -> 'BusinessDatabase | None':
        host = os.getenv('BUSINESS_DB_HOST')
        if not host:
            return None
        required = ('BUSINESS_DB_NAME', 'BUSINESS_DB_USER', 'BUSINESS_DB_PASSWORD')
        if any(not os.getenv(key) for key in required):
            raise RuntimeError('Business database configuration is incomplete')
        timeout = float(os.getenv('BUSINESS_DB_TIMEOUT_SECONDS', '5'))
        if timeout <= 0:
            raise RuntimeError('Business database timeout must be positive')
        pool = await aiomysql.create_pool(
            host=host, port=int(os.getenv('BUSINESS_DB_PORT', '3306')),
            user=os.environ['BUSINESS_DB_USER'], password=os.environ['BUSINESS_DB_PASSWORD'],
            db=os.environ['BUSINESS_DB_NAME'], minsize=1, maxsize=5,
            connect_timeout=timeout, autocommit=True, cursorclass=aiomysql.DictCursor)
        return cls(pool, timeout)

    # 在指定超时内执行固定的参数化 SELECT，返回一条记录或 None。
    async def fetchone(self, sql: str, params: tuple) -> dict | None:
        return await self._fetch(sql, params, many=False)

    # 在指定超时内执行固定的参数化 SELECT，返回有限记录列表。
    async def fetchall(self, sql: str, params: tuple) -> list[dict]:
        return await self._fetch(sql, params, many=True)

    # 统一管理游标、超时和数据库错误，不在日志中写 SQL 参数或凭证。
    async def _fetch(self, sql: str, params: tuple, many: bool) -> dict | list[dict] | None:
        try:
            async with asyncio.timeout(self.timeout):
                async with self.pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute(sql, params)
                        return await (cursor.fetchall() if many else cursor.fetchone())
        except TimeoutError as exc:
            log.warning('Business database query timed out')
            raise BusinessDatabaseTimeout('business database query timed out') from exc
        except Exception as exc:
            log.warning('Business database query failed: %s', type(exc).__name__)
            raise BusinessDatabaseError('business database unavailable') from exc

    # 关闭连接池并等待现有连接释放。
    async def close(self) -> None:
        self.pool.close()
        await self.pool.wait_closed()
