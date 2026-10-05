"""Opt-in smoke check for Database Agent SQL against the isolated Demo MySQL."""
import asyncio

from app.agents.database.query import execute_query
from app.clients.business_db import BusinessDatabase


# 在真实只读账号上核对类别迁移、关联查询和受控结果。
async def verify():
    db = await BusinessDatabase.from_env()
    assert db is not None
    try:
        result = await execute_query(db,
            "SELECT i.product_category AS category, SUM(i.quantity * i.unit_price) AS amount "
            "FROM order_items i JOIN orders o ON o.id = i.order_id "
            "WHERE o.payment_status = 'paid' GROUP BY i.product_category")
        assert result['row_count'] == 2
        assert {row['category'] for row in result['rows']} == {'电脑配件', '数码配件'}
        assert 'LIMIT 100' in result['sql']
        print('Real Database Agent read-only SQL integration: PASS')
    finally:
        await db.close()


if __name__ == '__main__':
    asyncio.run(verify())
