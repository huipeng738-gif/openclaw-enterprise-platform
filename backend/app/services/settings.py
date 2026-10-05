"""Persistent task policy and safe dependency observations for system settings."""
import asyncio
import json
from datetime import datetime, timezone

from redis.exceptions import WatchError

from .runtime import gateway_status


POLICY_KEY = 'settings:task-policy'
DEFAULT_POLICY = {'version': 0, 'defaultTimeoutSeconds': 180, 'submissionsPaused': False}


# 读取版本化策略；尚未配置时返回与历史任务一致的默认值。
async def task_policy(redis):
    raw = await redis.get(POLICY_KEY)
    return json.loads(raw) if raw else DEFAULT_POLICY.copy()


# 基于 Redis WATCH 比较版本，防止两个管理员互相覆盖策略。
async def update_task_policy(redis, expected_version, timeout, paused):
    async with redis.pipeline() as pipe:
        await pipe.watch(POLICY_KEY)
        raw = await pipe.get(POLICY_KEY)
        current = json.loads(raw) if raw else DEFAULT_POLICY
        if current['version'] != expected_version:
            return None
        updated = {'version': expected_version + 1, 'defaultTimeoutSeconds': timeout,
                   'submissionsPaused': paused, 'updatedAt': datetime.now(timezone.utc).isoformat()}
        pipe.multi()
        pipe.set(POLICY_KEY, json.dumps(updated))
        try:
            await pipe.execute()
        except WatchError:
            return None
    return updated


# 将任务落库和入队放入同一事务，并与暂停策略更新建立顺序。
async def admit_task(redis, task_id, task_factory):
    for _ in range(5):
        async with redis.pipeline() as pipe:
            await pipe.watch(POLICY_KEY)
            raw = await pipe.get(POLICY_KEY)
            policy = json.loads(raw) if raw else DEFAULT_POLICY
            if policy['submissionsPaused']:
                return None
            task = task_factory(policy)
            pipe.multi()
            pipe.set(f'task:{task_id}', json.dumps(task, ensure_ascii=False))
            pipe.sadd('tasks:all', task_id)
            pipe.rpush('tasks:queue', task_id)
            try:
                await pipe.execute()
                return task
            except WatchError:
                continue
    raise RuntimeError('task policy changed too frequently')


# 返回真实依赖探测与上次 Worker/Gateway 心跳，不返回连接信息或凭据。
async def dependency_status(redis, business_db, ragflow):
    checked = datetime.now(timezone.utc).isoformat()
    async def probe_redis():
        await redis.ping()
    async def probe_mysql():
        async with asyncio.timeout(3):
            async with business_db.pool.acquire() as conn:
                await conn.ping()
    async def probe_ragflow():
        await asyncio.wait_for(ragflow.list_datasets(page=1, page_size=1), 5)
    async def check(name, probe, configured=True):
        if not configured:
            return {'name': name, 'status': 'unconfigured', 'checkedAt': checked, 'detail': '未配置'}
        try:
            await probe()
            return {'name': name, 'status': 'online', 'checkedAt': checked, 'detail': '连接正常'}
        except Exception:
            return {'name': name, 'status': 'offline', 'checkedAt': checked, 'detail': '连接或请求失败'}
    redis_state, mysql_state, ragflow_state = await asyncio.gather(
        check('Redis', probe_redis), check('MySQL', probe_mysql, business_db is not None),
        check('RAGFlow', probe_ragflow, ragflow is not None))
    gateway = await gateway_status(redis)
    worker_raw = await redis.get('runtime:worker')
    worker = json.loads(worker_raw) if worker_raw else None
    return [
        {'name': 'API', 'status': 'online', 'checkedAt': checked, 'detail': '请求已处理'},
        redis_state,
        {'name': 'Worker', 'status': 'online' if worker else 'unknown',
         'checkedAt': worker.get('checkedAt') if worker else None,
         'detail': '心跳正常' if worker else '未收到有效心跳'},
        {'name': 'Gateway', 'status': gateway['status'], 'checkedAt': gateway['checkedAt'],
         'detail': '握手正常' if gateway['status'] == 'online' else '无有效握手或连接失败'},
        mysql_state, ragflow_state,
    ]
