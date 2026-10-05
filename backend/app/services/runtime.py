"""Read the worker's expiring Gateway connectivity observation."""
import json


GATEWAY_HEALTH_KEY = 'runtime:gateway'
GATEWAY_HEALTH_TTL = 90


# 仅返回 Worker 最近一次真实 Gateway 握手结果；记录过期时状态为未知。
async def gateway_status(redis):
    raw = await redis.get(GATEWAY_HEALTH_KEY)
    if not raw:
        return {'status': 'unknown', 'checkedAt': None, 'latencyMs': None}
    try:
        record = json.loads(raw)
    except ValueError:
        return {'status': 'unknown', 'checkedAt': None, 'latencyMs': None}
    if not isinstance(record, dict) or record.get('status') not in {'online', 'offline'}:
        return {'status': 'unknown', 'checkedAt': None, 'latencyMs': None}
    return {'status': record['status'], 'checkedAt': record.get('checkedAt'),
            'latencyMs': record.get('latencyMs')}
