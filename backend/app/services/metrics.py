"""Code-owned metric definitions and range validation."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.repositories.metrics import MetricsRepository


@dataclass(frozen=True)
class MetricDefinition:
    label: str
    unit: str
    table: str
    expression: str
    predicate: str = ''


REGISTRY = {
    'sales_amount': MetricDefinition('已支付订单金额', 'CNY', 'orders',
        "COALESCE(SUM(CASE WHEN payment_status = 'paid' THEN total_amount ELSE 0 END), 0)"),
    'order_count': MetricDefinition('订单数', 'orders', 'orders', 'COUNT(*)'),
    'refund_rate': MetricDefinition('退款订单占比', '%', 'orders',
        "COALESCE(ROUND(100 * SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2), 0)"),
    'active_customer_count': MetricDefinition('区间内新建且当前活跃客户数', 'customers', 'customers',
        'COUNT(*)', "AND status = 'active'"),
}


# 将 Decimal 转为精确文本；数量指标保留整数格式。
def metric_value(value, unit: str) -> str:
    if unit in {'CNY', '%'}:
        return f'{Decimal(value):.2f}'
    return str(int(value))


class MetricsService:
    # 注入只读聚合 Repository。
    def __init__(self, repository: MetricsRepository):
        self.repository = repository

    # 校验指标、分组和最长一年日期范围，再返回真实总值与趋势点。
    async def query(self, metric: str, start_date: date, end_date: date, group_by: str) -> dict:
        definition = REGISTRY.get(metric)
        if definition is None:
            raise HTTPException(422, 'unknown metric')
        if group_by not in {'day', 'week', 'month'}:
            raise HTTPException(422, 'invalid group_by')
        if end_date < start_date or (end_date - start_date).days > 366:
            raise HTTPException(422, 'invalid date range')
        total, points = await self.repository.query(definition, start_date, end_date, group_by)
        return {'metric': metric, 'label': definition.label, 'unit': definition.unit,
                'start_date': start_date.isoformat(), 'end_date': end_date.isoformat(),
                'group_by': group_by, 'total': metric_value(total, definition.unit),
                'points': [{'period': point['bucket'], 'value': metric_value(point['value'], definition.unit)}
                           for point in points]}
