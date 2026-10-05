"""Agent actions and human approval for platform task cancellation."""
import hashlib
import json
import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from redis.exceptions import WatchError

SESSION = re.compile(r'^agent:([A-Za-z0-9_-]{1,48}):enterprise:([a-f0-9]{32})$')
TASK_ID = r'^[a-f0-9]{32}$'
ACTIVE = {'queued', 'running'}
APPROVAL_SECONDS = 24 * 3600


class ToolContext(BaseModel):
    session_key: str = Field(max_length=120)
    tool_call_id: str = Field(min_length=1, max_length=120)


class FollowupCreate(ToolContext):
    title: str = Field(min_length=3, max_length=160)
    reason: str = Field(default='', max_length=500)
    order_no: str | None = Field(default=None, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$')


class CancelRequest(ToolContext):
    target_task_id: str = Field(pattern=TASK_ID)
    reason: str = Field(min_length=3, max_length=500)


class ApprovalEdit(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


# 从 Gateway 的宿主 session 映射回当前运行的任务及有效操作人；模型输入不能指定用户。
async def tool_actor(redis, session_key, users):
    match = SESSION.fullmatch(session_key)
    if not match:
        raise HTTPException(403, 'platform task session required')
    agent, task_id = match.groups()
    raw = await redis.get(f'task:{task_id}')
    if not raw:
        raise HTTPException(403, 'source task unavailable')
    task = json.loads(raw)
    if (task.get('kind', 'chat') != 'chat' or task.get('agent') != agent or
            task.get('sessionKey') != session_key or task.get('status') != 'running'):
        raise HTTPException(403, 'source task inactive')
    user = await users.get(task['owner'])
    if not user or user['role'] not in {'operator', 'admin'} or user['disabled']:
        raise HTTPException(403, 'action permission denied')
    return task, task['owner']


# 为同一 Agent Tool 调用生成稳定标识，Gateway 重放时不重复创建业务记录。
def action_id(task_id, tool_call_id, action):
    return hashlib.sha256(f'{task_id}:{tool_call_id}:{action}'.encode()).hexdigest()[:32]


# 返回审批的当前可见状态，超时记录在读取时呈现为 expired。
def visible_approval(item):
    if item['status'] == 'pending' and item['expiresAt'] <= time.time():
        return {**item, 'status': 'expired'}
    return item


# 组装工具入口及 JWT 保护的审批入口；Redis 事务保证决定与取消标记一起提交。
def build_action_router(permission, plugin_guard, audit, redis_provider, users_provider):
    router = APIRouter()

    # Agent 创建持久化催办任务；仅保留源任务、业务编号和有限描述。
    @router.post('/actions/task-create', status_code=201)
    async def tool_task_create(body: FollowupCreate, _=Depends(plugin_guard)):
        redis = redis_provider()
        source, owner = await tool_actor(redis, body.session_key, users_provider())
        item_id = action_id(source['id'], body.tool_call_id, 'task_create')
        item = {'id': item_id, 'owner': owner, 'sourceTaskId': source['id'], 'title': body.title,
                'reason': body.reason, 'orderNo': body.order_no, 'status': 'open',
                'createdAt': datetime.now(timezone.utc).isoformat()}
        created = await redis.set(f'followup:{item_id}', json.dumps(item, ensure_ascii=False), nx=True)
        if created:
            await redis.zadd('followups:index', {item_id: time.time()})
            await audit(owner, 'followup.create', item_id)
        else:
            item = json.loads(await redis.get(f'followup:{item_id}'))
        return item

    # 返回当前账号可见的催办事项，供任务中心展示 Agent 创建的真实记录。
    @router.get('/api/followups')
    async def followups(response: Response, user=Depends(permission('tasks:read'))):
        response.headers['Cache-Control'] = 'no-store'
        if user['role'] == 'viewer':
            raise HTTPException(403, 'permission denied')
        redis = redis_provider()
        ids = await redis.zrevrange('followups:index', 0, 199)
        rows = [json.loads(raw) for item_id in ids if (raw := await redis.get(f'followup:{item_id}'))]
        return [item for item in rows if user['role'] == 'admin' or item['owner'] == user['username']][:100]

    # 对取消平台任务发起高风险审批；Agent 不能直接设置取消标记。
    @router.post('/actions/task-cancel/request', status_code=202)
    async def tool_cancel_request(body: CancelRequest, _=Depends(plugin_guard)):
        redis = redis_provider()
        source, owner = await tool_actor(redis, body.session_key, users_provider())
        target_raw = await redis.get(f'task:{body.target_task_id}')
        if not target_raw:
            raise HTTPException(404, 'target task not found')
        target = json.loads(target_raw)
        if target.get('owner') != owner or target.get('status') not in ACTIVE:
            raise HTTPException(403, 'target task not cancellable')
        approval_id = action_id(source['id'], body.tool_call_id, 'task_cancel')
        now = time.time()
        item = {'id': approval_id, 'action': 'task_cancel', 'target': body.target_task_id,
                'reason': body.reason, 'risk': 'high', 'requester': owner, 'sourceTaskId': source['id'],
                'status': 'pending', 'createdAt': datetime.fromtimestamp(now, timezone.utc).isoformat(),
                'expiresAt': now + APPROVAL_SECONDS, 'reviewer': None, 'reviewedAt': None}
        created = await redis.set(f'approval:{approval_id}', json.dumps(item, ensure_ascii=False), nx=True)
        if created:
            await redis.zadd('approvals:index', {approval_id: now})
            await audit(owner, 'approval.request', approval_id)
        else:
            item = json.loads(await redis.get(f'approval:{approval_id}'))
        return visible_approval(item)

    # 只返回当前用户有权查看的审批记录；管理员可以查看全部。
    @router.get('/api/approvals')
    async def approvals(response: Response, user=Depends(permission('tasks:read'))):
        response.headers['Cache-Control'] = 'no-store'
        if user['role'] == 'viewer':
            raise HTTPException(403, 'permission denied')
        redis = redis_provider()
        ids = await redis.zrevrange('approvals:index', 0, 199)
        rows = [json.loads(raw) for item_id in ids if (raw := await redis.get(f'approval:{item_id}'))]
        return [visible_approval(item) for item in rows if user['role'] == 'admin' or item['requester'] == user['username']][:100]

    # 管理员可编辑待审批原因，但目标任务和申请人不可改变。
    @router.patch('/api/approvals/{approval_id}')
    async def edit_approval(approval_id: str, body: ApprovalEdit, user=Depends(permission('users:write'))):
        return await decide(approval_id, user['username'], 'edit', body.reason)

    # 管理员审批时原子设置取消标记；重复审批不会重复执行。
    @router.post('/api/approvals/{approval_id}/approve')
    async def approve(approval_id: str, user=Depends(permission('users:write'))):
        return await decide(approval_id, user['username'], 'approved')

    # 管理员拒绝后请求终止；不会修改目标任务。
    @router.post('/api/approvals/{approval_id}/reject')
    async def reject(approval_id: str, user=Depends(permission('users:write'))):
        return await decide(approval_id, user['username'], 'rejected')

    # 使用 WATCH/MULTI 保证状态判断、记录修改与取消标记不可被并发审批拆开。
    async def decide(approval_id, reviewer, decision, reason=None):
        if not re.fullmatch(TASK_ID, approval_id):
            raise HTTPException(404, 'approval not found')
        redis = redis_provider()
        key = f'approval:{approval_id}'
        for _ in range(5):
            async with redis.pipeline() as pipe:
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    if not raw:
                        raise HTTPException(404, 'approval not found')
                    item = json.loads(raw)
                    if item['requester'] == reviewer:
                        raise HTTPException(403, 'requester cannot review own action')
                    if item['status'] != 'pending':
                        raise HTTPException(409, 'approval already decided')
                    if item['expiresAt'] <= time.time():
                        pipe.multi()
                        item['status'] = 'expired'
                        pipe.set(key, json.dumps(item, ensure_ascii=False))
                        await pipe.execute()
                        raise HTTPException(409, 'approval expired')
                    if decision == 'approved':
                        target_key = f'task:{item["target"]}'
                        await pipe.watch(target_key)
                        target_raw = await pipe.get(target_key)
                        target = json.loads(target_raw) if target_raw else {}
                        if target.get('owner') != item['requester'] or target.get('status') not in ACTIVE:
                            raise HTTPException(409, 'target task no longer cancellable')
                    if decision == 'edit':
                        item['reason'] = reason
                    else:
                        item['status'] = decision
                        item['reviewer'] = reviewer
                        item['reviewedAt'] = datetime.now(timezone.utc).isoformat()
                    pipe.multi()
                    pipe.set(key, json.dumps(item, ensure_ascii=False))
                    if decision == 'approved':
                        pipe.set(f'cancel:{item["target"]}', '1', ex=3600)
                    await pipe.execute()
                    await audit(reviewer, f'approval.{decision}', approval_id)
                    return item
                except WatchError:
                    continue
        raise HTTPException(409, 'approval changed concurrently')

    return router
