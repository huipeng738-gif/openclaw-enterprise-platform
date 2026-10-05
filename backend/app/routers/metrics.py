"""JWT and plugin-token entrypoints for registered business metrics."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.repositories.metrics import MetricsRepository
from app.schemas.metrics import MetricQuery
from app.services.metrics import MetricsService


# 注入权限、审计和插件凭证依赖，注册用户与 Tool 查询入口。
def build_metrics_router(permission, plugin_guard, audit):
    router = APIRouter()

    # 从应用的只读 MySQL 连接池创建指标 Service。
    def service(request: Request):
        db = getattr(request.app.state, 'business_db', None)
        if db is None:
            raise HTTPException(503, 'business database is not configured')
        return MetricsService(MetricsRepository(db))

    # 执行指标查询并记录指标名与结果，不记录 SQL 或原始数据行。
    async def audited_query(body: MetricQuery, actor: str, metrics: MetricsService):
        try:
            result = await metrics.query(body.metric, body.start_date, body.end_date, body.group_by)
        except Exception:
            await audit(actor, 'metric.query', body.metric, 'failed')
            raise
        await audit(actor, 'metric.query', body.metric)
        return result

    # JWT 用户按 business:read 权限查询预定义指标。
    @router.post('/api/metrics/query')
    async def user_metrics(body: MetricQuery, response: Response,
                           user=Depends(permission('business:read')), metrics=Depends(service)):
        response.headers['Cache-Control'] = 'no-store'
        return await audited_query(body, user['username'], metrics)

    # 沿用既有插件路径，供 metrics_query Tool 调用同一 Service。
    @router.post('/metrics/query')
    async def tool_metrics(body: MetricQuery, response: Response,
                           _=Depends(plugin_guard), metrics=Depends(service)):
        response.headers['Cache-Control'] = 'no-store'
        return await audited_query(body, 'enterprise-data-tools', metrics)

    return router
