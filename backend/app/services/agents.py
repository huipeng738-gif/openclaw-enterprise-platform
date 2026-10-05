"""Gateway-backed Agent roster and platform availability."""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.worker import Gateway


MANAGED_KEY = 'agents:managed'  # Hash: agent ID -> display metadata; no TTL.
DISABLED_KEY = 'agents:disabled'  # Set: platform-disabled legacy/managed IDs; no TTL.
CREATE_LOCK_PREFIX = 'agents:create:'  # Short-lived String; prevents duplicate create requests.
READ_ONLY_TOOLS = ['knowledge_search', 'order_query', 'customer_query', 'metrics_query']


# 只返回 Gateway 非敏感字段；Gateway 无法访问时不虚构 Agent 清单。
async def gateway_agents():
    try:
        async with Gateway('agent-management') as gateway:
            payload = await gateway.rpc('agents.list', {}, timeout=15)
        return [entry for entry in payload.get('agents', []) if isinstance(entry, dict) and entry.get('id')]
    except Exception as exc:
        raise HTTPException(503, 'OpenClaw Gateway 暂时不可用') from exc


# 将历史环境白名单与平台新增记录合并，并排除平台停用的 Agent。
async def enabled_ids(redis):
    legacy = {item.strip() for item in os.getenv('ALLOWED_AGENTS', 'coordinator,researcher,writer,reviewer').split(',') if item.strip()}
    managed = set(await redis.hkeys(MANAGED_KEY))
    disabled = await redis.smembers(DISABLED_KEY)
    return (legacy | managed) - disabled - {'database'}


# 从已有任务记录统计近 30 天真实执行数据，成功率仅以完成/失败/超时为分母。
async def task_stats(redis):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    counts = Counter()
    outcomes = defaultdict(Counter)
    tools = defaultdict(Counter)
    for task_id in await redis.smembers('tasks:all'):
        raw = await redis.get(f'task:{task_id}')
        if not raw:
            continue
        task = json.loads(raw)
        if task.get('createdAt', '') < cutoff:
            continue
        agent_id = task.get('agent')
        if not agent_id or task.get('kind') == 'database':
            continue
        counts[agent_id] += 1
        outcomes[agent_id][task.get('status')] += 1
        for _, fields in await redis.xrevrange(f'events:{task_id}', count=200):
            event = json.loads(fields['data'])
            if event.get('kind') == 'tool' and event.get('phase') == 'start' and event.get('name'):
                tools[agent_id][event['name']] += 1
    return counts, outcomes, tools


# 合并 Gateway 配置、平台启用状态和可追溯的任务统计。
async def agent_roster(redis, include_unavailable=False):
    entries = await gateway_agents()
    allowed = await enabled_ids(redis)
    metadata = {key: json.loads(value) for key, value in (await redis.hgetall(MANAGED_KEY)).items()}
    if include_unavailable:
        counts, outcomes, tools = await task_stats(redis)
        policies = await gateway_tool_policies()
    else:
        counts, outcomes, tools = Counter(), defaultdict(Counter), defaultdict(Counter)
        policies = {}
    rows = []
    for entry in entries:
        agent_id = entry['id']
        if entry.get('kind') == 'system' or (not include_unavailable and agent_id not in allowed):
            continue
        info = metadata.get(agent_id, {})
        policy = policies.get(agent_id, {})
        configured_tools = set(policy.get('alsoAllow') or [])
        actual_policy = ('business_readonly' if policy.get('profile') == 'minimal' and configured_tools == set(READ_ONLY_TOOLS)
                         else 'minimal' if policy.get('profile') == 'minimal' and not configured_tools else 'gateway')
        terminal = sum(outcomes[agent_id][status] for status in ('completed', 'failed', 'timed_out'))
        rows.append({
            'id': agent_id, 'name': info.get('name') or (entry.get('identity') or {}).get('name') or entry.get('name') or agent_id,
            'description': info.get('description', ''), 'enabled': agent_id in allowed,
            'model': (entry.get('model') or {}).get('primary'),
            'toolPolicy': actual_policy if include_unavailable else 'gateway',
            'tools': [{'name': name, 'count': count} for name, count in tools[agent_id].most_common(8)],
            'taskCount': counts[agent_id], 'successRate': round(outcomes[agent_id]['completed'] / terminal * 100, 1) if terminal else None,
            'sampleSize': terminal, 'createdAt': entry.get('createdAt'),
            'source': 'platform' if agent_id in metadata else 'gateway',
        })
    return rows


# 校验所选模型确实出现在当前 Gateway 可用模型目录中。
async def available_models():
    try:
        async with Gateway('agent-models') as gateway:
            payload = await gateway.rpc('models.list', {}, timeout=15)
        return sorted({f"{item['provider']}/{item['id']}" for item in payload.get('models', [])
                       if isinstance(item, dict) and item.get('provider') and item.get('id')})
    except Exception as exc:
        raise HTTPException(503, '无法读取 Gateway 模型列表') from exc


# 只提取 Gateway 配置中的非敏感 Tool 策略，避免平台元数据与实际权限漂移。
async def gateway_tool_policies():
    try:
        async with Gateway('agent-tool-policy') as gateway:
            snapshot = await gateway.rpc('config.get', {}, timeout=15)
        entries = (snapshot.get('config') or {}).get('agents', {}).get('entries', {})
        return {agent_id: value.get('tools', {}) for agent_id, value in entries.items() if isinstance(value, dict)}
    except Exception as exc:
        raise HTTPException(503, '无法读取 Gateway Tool 策略') from exc


# 在 Gateway 创建 Agent 并设置受限 Tool 策略，全部完成后才开放给平台任务。
async def create_agent(redis, body):
    lock_key = CREATE_LOCK_PREFIX + body.id
    if not await redis.set(lock_key, '1', nx=True, ex=45):
        raise HTTPException(409, '该 Agent 正在创建中')
    created_in_gateway = False
    try:
        if body.id == 'database' or body.id in {entry['id'] for entry in await gateway_agents()}:
            raise HTTPException(409, 'Agent ID 已存在')
        if body.model not in await available_models():
            raise HTTPException(422, '模型不在 Gateway 可用列表中')
        await redis.sadd(DISABLED_KEY, body.id)
        async with Gateway('agent-create', scopes=['operator.read', 'operator.admin']) as gateway:
            created = await gateway.rpc('agents.create', {
                'name': body.id, 'workspace': f'~/.openclaw/workspace/{body.id}', 'model': body.model,
            }, timeout=30)
            created_in_gateway = True
            if created.get('agentId') != body.id:
                raise HTTPException(502, 'Gateway 返回的 Agent ID 与请求不一致')
            snapshot = await gateway.rpc('config.get', {}, timeout=15)
            policy = {'profile': 'minimal'}
            if body.tool_policy == 'business_readonly':
                policy['alsoAllow'] = READ_ONLY_TOOLS
            patch = {'agents': {'entries': {body.id: {'tools': policy}}}}
            await gateway.rpc('config.patch', {
                'raw': json.dumps(patch), 'baseHash': snapshot['hash'],
                'note': 'Enterprise platform Agent tool policy',
            }, timeout=45)
        await redis.hset(MANAGED_KEY, body.id, json.dumps({
            'name': body.name, 'description': body.description, 'toolPolicy': body.tool_policy,
        }, ensure_ascii=False))
        await redis.srem(DISABLED_KEY, body.id)
        return created['agentId']
    except HTTPException:
        raise
    except Exception as exc:
        message = ('Gateway 已创建 Agent，但 Tool 策略或平台登记未完成；该 Agent 尚不可用于聊天'
                   if created_in_gateway else 'Gateway 创建 Agent 失败')
        raise HTTPException(502, message) from exc
    finally:
        await redis.delete(lock_key)


# 仅允许管理员切换已存在的普通 Agent，保留专用 Database Agent 的隔离。
async def set_agent_enabled(redis, agent_id, enabled):
    legacy = {item.strip() for item in os.getenv('ALLOWED_AGENTS', 'coordinator,researcher,writer,reviewer').split(',')}
    managed = await redis.hexists(MANAGED_KEY, agent_id)
    if (agent_id == 'database' or not (agent_id in legacy or managed)
            or agent_id not in {entry['id'] for entry in await gateway_agents()}):
        raise HTTPException(404, 'Agent 不存在或不可用于聊天')
    if enabled:
        if managed:
            info = json.loads(await redis.hget(MANAGED_KEY, agent_id))
            policy = (await gateway_tool_policies()).get(agent_id, {})
            expected = {'profile': 'minimal'}
            if info.get('toolPolicy') == 'business_readonly':
                expected['alsoAllow'] = READ_ONLY_TOOLS
            if any(policy.get(key) != value for key, value in expected.items()):
                raise HTTPException(409, 'Gateway Tool 策略与平台记录不一致，不能启用')
        await redis.srem(DISABLED_KEY, agent_id)
    else:
        await redis.sadd(DISABLED_KEY, agent_id)
