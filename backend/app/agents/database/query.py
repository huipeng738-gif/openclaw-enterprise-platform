"""Validate untrusted MySQL SELECT plans before they reach the read-only pool."""
import json
import re
from datetime import date, datetime
from decimal import Decimal

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify

from app.clients.business_db import BusinessDatabase

MAX_ROWS = 100
MAX_SQL_LENGTH = 4000
SCHEMA = {
    'customers': {'id': 'BIGINT', 'customer_no': 'VARCHAR', 'name': 'VARCHAR',
                  'level': 'VARCHAR', 'status': 'VARCHAR', 'created_at': 'DATETIME'},
    'orders': {'id': 'BIGINT', 'order_no': 'VARCHAR', 'customer_id': 'BIGINT',
               'status': 'VARCHAR', 'total_amount': 'DECIMAL', 'payment_status': 'VARCHAR',
               'created_at': 'DATETIME', 'updated_at': 'DATETIME'},
    'order_items': {'id': 'BIGINT', 'order_id': 'BIGINT', 'product_name': 'VARCHAR',
                    'product_category': 'VARCHAR', 'sku': 'VARCHAR', 'quantity': 'INT',
                    'unit_price': 'DECIMAL'},
}
FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'ROUND', 'DATE',
             'TS_OR_DS_TO_DATE', 'YEAR', 'MONTH', 'DAY', 'NULLIF', 'IFNULL', 'ABS'}
PROHIBITED = (exp.Command, exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
              exp.Alter, exp.TruncateTable, exp.Into, exp.Lock, exp.Parameter,
              exp.SessionParameter)


class UnsafeQuery(ValueError):
    """The proposed query exceeds the Database Agent's read boundary."""


# 提供不包含手机号等敏感列的固定目录，供 Gateway 生成候选查询。
def schema_prompt() -> str:
    columns = '\n'.join(f'{table}: {", ".join(names)}' for table, names in SCHEMA.items())
    return (columns + '\n关联：orders.customer_id = customers.id；'
            'order_items.order_id = orders.id。已支付销售额只统计 payment_status = paid。'
            'product_category 为 NULL 表示未知类别；没有足够月份时不能判断下降。')


# 只接受独立 JSON 对象，避免从模型的自由文本中猜测 SQL。
def parse_plan(text: str) -> str:
    try:
        plan = json.loads(text.strip())
    except (ValueError, TypeError) as exc:
        raise UnsafeQuery('database plan is not valid JSON') from exc
    if not isinstance(plan, dict) or set(plan) != {'sql'} or not isinstance(plan['sql'], str):
        raise UnsafeQuery('database plan must contain only sql')
    return plan['sql']


# 校验完整 AST、表列和函数范围，并将所有字面量改为驱动参数。
def prepare_query(sql: str) -> tuple[str, tuple]:
    if not isinstance(sql, str) or not 1 <= len(sql) <= MAX_SQL_LENGTH:
        raise UnsafeQuery('invalid SQL length')
    if re.search(r'--|/\*|\*/|#', sql):
        raise UnsafeQuery('SQL comments are forbidden')
    try:
        statements = sqlglot.parse(sql, read='mysql')
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise UnsafeQuery('one SELECT statement is required')
        query = statements[0]
        if (query.args.get('with_') and query.args['with_'].args.get('recursive')) or query.find(*PROHIBITED):
            raise UnsafeQuery('unsafe SQL construct')
        if any(not isinstance(node, exp.Select) for node in query.find_all(exp.Query)):
            raise UnsafeQuery('unsupported query construct')
        if query.args.get('offset') or len(list(query.find_all(exp.Select))) > 4:
            raise UnsafeQuery('query shape exceeds limits')
        if any(join.args.get('kind') == 'CROSS' for join in query.find_all(exp.Join)):
            raise UnsafeQuery('cross joins are forbidden')
        if any(isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count)
               for node in query.find_all(exp.Star)):
            raise UnsafeQuery('SELECT * is forbidden')
        cte_names = {cte.alias for cte in query.find_all(exp.CTE)}
        tables = list(query.find_all(exp.Table))
        allowed_tables = set(SCHEMA) | cte_names
        if not tables or len(tables) > 4 or any(table.name not in allowed_tables
                                                  or table.db or table.catalog for table in tables):
            raise UnsafeQuery('table is not allowed')
        if any((node.sql_name().upper() not in FUNCTIONS) for node in query.find_all(exp.Func)):
            raise UnsafeQuery('function is not allowed')
        query = qualify(query, schema=SCHEMA, dialect='mysql',
                        validate_qualify_columns=True, expand_stars=False, identify=False)
        # 保证最终行数上限由服务器控制，原 SQL 的 LIMIT 不能扩大结果。
        query.set('limit', exp.Limit(expression=exp.Literal.number(MAX_ROWS)))
        values = {}
        for index, literal in enumerate(list(query.find_all(exp.Literal))):
            if isinstance(literal.parent, exp.Limit):
                continue
            value = literal.this if literal.is_string else (float(literal.this) if '.' in literal.this else int(literal.this))
            marker = f'agent_param_{index}'
            values[marker] = value
            literal.replace(exp.Placeholder(this=marker))
        rendered = query.sql(dialect='mysql')
        ordered = []
        def bind(match):
            ordered.append(values[match.group(1)])
            return '%s'
        rendered = re.sub(r':(agent_param_\d+)', bind, rendered)
        if len(ordered) != len(values):
            raise UnsafeQuery('query parameterization failed')
        return rendered, tuple(ordered)
    except (ParseError, OptimizeError, ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, UnsafeQuery):
            raise
        raise UnsafeQuery('SQL validation failed') from exc


# 执行通过校验的查询并将数据库数值转换为可序列化文本。
async def execute_query(db: BusinessDatabase, sql: str) -> dict:
    statement, params = prepare_query(sql)
    rows = await db.fetchall(statement, params)
    def clean(value):
        if isinstance(value, (Decimal, date, datetime)):
            return str(value)
        return value
    safe_rows = [{key: clean(value) for key, value in row.items()} for row in rows]
    return {'sql': statement, 'row_count': len(safe_rows), 'rows': safe_rows,
            'truncated': len(safe_rows) == MAX_ROWS}
