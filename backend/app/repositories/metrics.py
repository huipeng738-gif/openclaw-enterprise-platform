"""Read-only metric aggregation using only registry-controlled SQL fragments."""
from datetime import date, datetime, time, timedelta

from app.clients.business_db import BusinessDatabase

GROUP_FORMATS = {'day': '%Y-%m-%d', 'week': '%x-W%v', 'month': '%Y-%m'}


class MetricsRepository:
    # 注入只读 MySQL 边界。
    def __init__(self, db: BusinessDatabase):
        self.db = db

    # 以半开日期区间聚合总值与趋势，SQL 片段仅来自 Metric Registry。
    async def query(self, definition, start: date, end: date, group_by: str):
        lower = datetime.combine(start, time.min)
        upper = datetime.combine(end + timedelta(days=1), time.min)
        source = f'FROM {definition.table} WHERE created_at >= %s AND created_at < %s {definition.predicate}'
        total = await self.db.fetchone(f'SELECT {definition.expression} AS value {source}', (lower, upper))
        points = await self.db.fetchall(
            f'SELECT DATE_FORMAT(created_at, %s) AS bucket, {definition.expression} AS value '
            f'{source} GROUP BY bucket ORDER BY bucket LIMIT 400',
            (GROUP_FORMATS[group_by], lower, upper))
        return total['value'], points
