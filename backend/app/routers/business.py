"""JWT and plugin-token entrypoints for the same deterministic business services."""
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.repositories.business import CustomerRepository, OrderRepository
from app.services.business import CustomerService, OrderService


class OrderQuery(BaseModel):
    order_no: str = Field(min_length=2, max_length=32, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$')


class CustomerQuery(BaseModel):
    customer_no: str = Field(min_length=2, max_length=32, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$')


# 将业务编号转为固定长度审计标识，避免审计流包含原始客户编号。
def audit_target(number: str):
    return hashlib.sha256(number.encode()).hexdigest()[:16]


# 组装用户 API 与 OpenClaw Tool 共用的业务查询 Router。
def build_business_router(permission, plugin_guard, audit):
    router = APIRouter()

    # 从应用生命周期创建的连接池组装 Service；未配置时返回 503。
    def services(request: Request):
        db = getattr(request.app.state, 'business_db', None)
        if db is None:
            raise HTTPException(503, 'business database is not configured')
        return OrderService(OrderRepository(db)), CustomerService(CustomerRepository(db))

    # 调用确定性查询并记录成功或失败，不把结果和原始编号写入审计流。
    async def audited_query(service, number, actor, action):
        target = audit_target(number)
        try:
            result = await service.query(number)
        except Exception:
            await audit(actor, action, target, 'failed')
            raise
        await audit(actor, action, target)
        return result

    # 提供 JWT 保护的订单分页列表；不将搜索词或订单数据写入审计。
    @router.get('/api/orders')
    async def orders(response: Response,
                     search: str | None = Query(default=None, max_length=100),
                     status: str | None = Query(default=None, pattern=r'^[a-z_]{1,24}$'),
                     payment_status: str | None = Query(default=None, pattern=r'^[a-z_]{1,24}$'),
                     page: int = Query(default=1, ge=1, le=1000),
                     page_size: int = Query(default=20, ge=1, le=100),
                     user=Depends(permission('business:read')), pair=Depends(services)):
        response.headers['Cache-Control'] = 'no-store'
        try:
            result = await pair[0].list_page(search, status, payment_status, page, page_size)
        except Exception:
            await audit(user['username'], 'order.list', '-', 'failed')
            raise
        await audit(user['username'], 'order.list', '-')
        return result

    # JWT 用户按业务读取权限查询订单。
    @router.get('/api/orders/{order_no}')
    async def order(order_no: str, response: Response,
                    user=Depends(permission('business:read')), pair=Depends(services)):
        response.headers['Cache-Control'] = 'no-store'
        return await audited_query(pair[0], order_no, user['username'], 'order.query')

    # 提供 JWT 保护的客户分页列表；仅允许数据库已有的等级与状态。
    @router.get('/api/customers')
    async def customers(response: Response,
                        search: str | None = Query(default=None, max_length=100),
                        level: str | None = Query(default=None, pattern=r'^(regular|vip)$'),
                        status: str | None = Query(default=None, pattern=r'^(active|inactive)$'),
                        page: int = Query(default=1, ge=1, le=1000),
                        page_size: int = Query(default=20, ge=1, le=100),
                        user=Depends(permission('business:read')), pair=Depends(services)):
        response.headers['Cache-Control'] = 'no-store'
        try:
            result = await pair[1].list_page(search, level, status, page, page_size)
        except Exception:
            await audit(user['username'], 'customer.list', '-', 'failed')
            raise
        await audit(user['username'], 'customer.list', '-')
        return result

    # JWT 用户按业务读取权限查询客户，手机号由 Service 脱敏。
    @router.get('/api/customers/{customer_no}')
    async def customer(customer_no: str, response: Response,
                       user=Depends(permission('business:read')), pair=Depends(services)):
        response.headers['Cache-Control'] = 'no-store'
        return await audited_query(pair[1], customer_no, user['username'], 'customer.query')

    # OpenClaw 插件凭证调用同一个订单 Service。
    @router.post('/business/orders/query')
    async def tool_order(body: OrderQuery, response: Response, _=Depends(plugin_guard), pair=Depends(services)):
        response.headers['Cache-Control'] = 'no-store'
        return await audited_query(pair[0], body.order_no, 'enterprise-data-tools', 'order.query')

    # OpenClaw 插件凭证调用同一个客户 Service。
    @router.post('/business/customers/query')
    async def tool_customer(body: CustomerQuery, response: Response, _=Depends(plugin_guard), pair=Depends(services)):
        response.headers['Cache-Control'] = 'no-store'
        return await audited_query(pair[1], body.customer_no, 'enterprise-data-tools', 'customer.query')

    return router
