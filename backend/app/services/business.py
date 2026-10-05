"""Validation and safe response shaping for deterministic business lookups."""
import re
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException

from app.repositories.business import CustomerRepository, OrderRepository

BUSINESS_NO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$')


# 校验受控业务编号，拒绝空值、超长值和 SQL 元字符。
def validate_number(value: str) -> None:
    if not BUSINESS_NO.fullmatch(value):
        raise HTTPException(422, 'invalid business number')


# 将 MySQL 日期转换为 ISO 文本，空值保持 None。
def timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


# 将金额保留为两位小数字符串，避免浮点精度丢失。
def amount(value: Decimal) -> str:
    return f'{value:.2f}'


# 仅保留手机号前三位与后四位，避免 Tool 与前端暴露完整号码。
def masked_phone(value: str) -> str:
    return value[:3] + '****' + value[-4:] if len(value) >= 7 else '****'


class OrderService:
    # 注入固定查询 Repository。
    def __init__(self, repository: OrderRepository):
        self.repository = repository

    # 查询单个订单并组合客户、明细信息；不存在时返回 404。
    async def query(self, order_no: str) -> dict:
        validate_number(order_no)
        row = await self.repository.get(order_no)
        if row is None:
            raise HTTPException(404, 'order not found')
        items = await self.repository.items(row['id'])
        return {'order_no': row['order_no'], 'status': row['status'],
                'total_amount': amount(row['total_amount']), 'payment_status': row['payment_status'],
                'created_at': timestamp(row['created_at']),
                'customer': {'customer_no': row['customer_no'], 'name': row['customer_name']},
                'order_items': [{'product_name': item['product_name'], 'sku': item['sku'],
                                 'quantity': item['quantity'], 'unit_price': amount(item['unit_price'])}
                                for item in items]}

    # 查询有限分页订单，保留金额精度并只暴露页面所需的客户字段。
    async def list_page(self, search: str | None, status: str | None, payment_status: str | None,
                        page: int, page_size: int) -> dict:
        normalized = search.strip() if search else None
        total = await self.repository.count(normalized, status, payment_status)
        rows = await self.repository.list_page(normalized, status, payment_status,
                                               page_size, (page - 1) * page_size)
        return {'items': [{'order_no': row['order_no'], 'status': row['status'],
                           'total_amount': amount(row['total_amount']),
                           'payment_status': row['payment_status'],
                           'created_at': timestamp(row['created_at']),
                           'customer': {'customer_no': row['customer_no'], 'name': row['customer_name']}}
                          for row in rows],
                'total': total, 'page': page, 'page_size': page_size}


class CustomerService:
    # 注入固定查询 Repository。
    def __init__(self, repository: CustomerRepository):
        self.repository = repository

    # 查询客户、聚合数据和最近五笔订单，手机号在返回前脱敏。
    async def query(self, customer_no: str) -> dict:
        validate_number(customer_no)
        row = await self.repository.get(customer_no)
        if row is None:
            raise HTTPException(404, 'customer not found')
        totals = await self.repository.totals(row['id'])
        recent = await self.repository.recent_orders(row['id'])
        return {'customer_no': row['customer_no'], 'name': row['name'],
                'phone': masked_phone(row['phone']), 'level': row['level'], 'status': row['status'],
                'created_at': timestamp(row['created_at']), 'order_count': totals['order_count'],
                'total_amount': amount(totals['total_amount']),
                'last_order_time': timestamp(totals['last_order_time']),
                'recent_orders': [{'order_no': order['order_no'], 'status': order['status'],
                                   'total_amount': amount(order['total_amount']),
                                   'payment_status': order['payment_status'],
                                   'created_at': timestamp(order['created_at'])} for order in recent]}

    # 读取客户分页概览，手机号在离开 Service 前统一脱敏。
    async def list_page(self, search: str | None, level: str | None, status: str | None,
                        page: int, page_size: int) -> dict:
        normalized = search.strip() if search else None
        total = await self.repository.count(normalized, level, status)
        rows = await self.repository.list_page(normalized, level, status,
                                               page_size, (page - 1) * page_size)
        return {'items': [{'customer_no': row['customer_no'], 'name': row['name'],
                           'phone': masked_phone(row['phone']), 'level': row['level'],
                           'status': row['status'], 'created_at': timestamp(row['created_at']),
                           'order_count': int(row['order_count']),
                           'last_order_time': timestamp(row['last_order_time'])}
                          for row in rows],
                'total': total, 'page': page, 'page_size': page_size}
