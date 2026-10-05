"""Fixed, parameterized business queries. No model-generated SQL enters this layer."""
from app.clients.business_db import BusinessDatabase


class OrderRepository:
    # 保存数据库边界，以订单编号读取订单、所属客户和有限明细。
    def __init__(self, db: BusinessDatabase):
        self.db = db

    # 用唯一订单编号查询单个订单及客户标识。
    async def get(self, order_no: str) -> dict | None:
        return await self.db.fetchone(
            'SELECT o.id, o.order_no, o.status, o.total_amount, o.payment_status, o.created_at, '
            'c.customer_no, c.name AS customer_name FROM orders o '
            'JOIN customers c ON c.id = o.customer_id WHERE o.order_no = %s LIMIT 1', (order_no,))

    # 按订单内部 ID 读取最多五十条明细，避免无限结果。
    async def items(self, order_id: int) -> list[dict]:
        return await self.db.fetchall(
            'SELECT product_name, sku, quantity, unit_price FROM order_items '
            'WHERE order_id = %s ORDER BY id LIMIT 50', (order_id,))

    # 仅组合固定 SQL 片段，搜索值、筛选值及分页边界始终作为参数传入。
    @staticmethod
    def list_filter(search: str | None, status: str | None, payment_status: str | None) -> tuple[str, tuple]:
        clauses = []
        params = []
        if search:
            escaped = search.replace('!', '!!').replace('%', '!%').replace('_', '!_')
            pattern = f'%{escaped}%'
            clauses.append("(o.order_no LIKE %s ESCAPE '!' OR c.name LIKE %s ESCAPE '!' "
                           "OR EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.id "
                           "AND i.product_name LIKE %s ESCAPE '!'))")
            params.extend((pattern, pattern, pattern))
        if status:
            clauses.append('o.status = %s')
            params.append(status)
        if payment_status:
            clauses.append('o.payment_status = %s')
            params.append(payment_status)
        return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), tuple(params)

    # 查询筛选后的订单总数，供前端分页使用。
    async def count(self, search: str | None, status: str | None, payment_status: str | None) -> int:
        where, params = self.list_filter(search, status, payment_status)
        row = await self.db.fetchone('SELECT COUNT(*) AS total FROM orders o '
                                     'JOIN customers c ON c.id = o.customer_id' + where, params)
        return int(row['total'])

    # 按创建时间倒序读取一页订单及所属客户，避免一次返回全表。
    async def list_page(self, search: str | None, status: str | None, payment_status: str | None,
                        limit: int, offset: int) -> list[dict]:
        where, params = self.list_filter(search, status, payment_status)
        return await self.db.fetchall(
            'SELECT o.order_no, o.status, o.total_amount, o.payment_status, o.created_at, '
            'c.customer_no, c.name AS customer_name FROM orders o '
            'JOIN customers c ON c.id = o.customer_id' + where +
            ' ORDER BY o.created_at DESC, o.id DESC LIMIT %s OFFSET %s', params + (limit, offset))


class CustomerRepository:
    # 保存数据库边界，以客户编号读取客户及其订单概览。
    def __init__(self, db: BusinessDatabase):
        self.db = db

    # 用唯一客户编号查询单个客户。
    async def get(self, customer_no: str) -> dict | None:
        return await self.db.fetchone(
            'SELECT id, customer_no, name, phone, level, status, created_at '
            'FROM customers WHERE customer_no = %s LIMIT 1', (customer_no,))

    # 将客户搜索与等级、状态筛选限制在固定列，所有输入均作为 SQL 参数。
    @staticmethod
    def list_filter(search: str | None, level: str | None, status: str | None) -> tuple[str, tuple]:
        clauses = []
        params = []
        if search:
            escaped = search.replace('!', '!!').replace('%', '!%').replace('_', '!_')
            pattern = f'%{escaped}%'
            clauses.append("(c.customer_no LIKE %s ESCAPE '!' OR c.name LIKE %s ESCAPE '!')")
            params.extend((pattern, pattern))
        if level:
            clauses.append('c.level = %s')
            params.append(level)
        if status:
            clauses.append('c.status = %s')
            params.append(status)
        return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), tuple(params)

    # 统计筛选后的客户数量，供受限分页使用。
    async def count(self, search: str | None, level: str | None, status: str | None) -> int:
        where, params = self.list_filter(search, level, status)
        row = await self.db.fetchone('SELECT COUNT(*) AS total FROM customers c' + where, params)
        return int(row['total'])

    # 返回一页客户及订单汇总；不读取完整手机号之外的额外敏感字段。
    async def list_page(self, search: str | None, level: str | None, status: str | None,
                        limit: int, offset: int) -> list[dict]:
        where, params = self.list_filter(search, level, status)
        return await self.db.fetchall(
            'SELECT c.customer_no, c.name, c.phone, c.level, c.status, c.created_at, '
            'COUNT(o.id) AS order_count, MAX(o.created_at) AS last_order_time '
            'FROM customers c LEFT JOIN orders o ON o.customer_id = c.id' + where +
            ' GROUP BY c.id, c.customer_no, c.name, c.phone, c.level, c.status, c.created_at '
            'ORDER BY c.created_at DESC, c.id DESC LIMIT %s OFFSET %s', params + (limit, offset))

    # 统计客户订单数、已支付金额和最近下单时间。
    async def totals(self, customer_id: int) -> dict | None:
        return await self.db.fetchone(
            "SELECT COUNT(*) AS order_count, COALESCE(SUM(CASE WHEN payment_status = 'paid' "
            'THEN total_amount ELSE 0 END), 0) AS total_amount, MAX(created_at) AS last_order_time '
            'FROM orders WHERE customer_id = %s', (customer_id,))

    # 读取最近五笔订单，供客户查询结果展示。
    async def recent_orders(self, customer_id: int) -> list[dict]:
        return await self.db.fetchall(
            'SELECT order_no, status, total_amount, payment_status, created_at FROM orders '
            'WHERE customer_id = %s ORDER BY created_at DESC, id DESC LIMIT 5', (customer_id,))
