"""Opt-in live Gateway probe for the database session tool veto."""
import asyncio
import json
import time
import uuid

from app import worker


# 只保存 Tool 事件中的阻断标记，避免把工具参数或结果写入验收输出。
class ProbeGateway(worker.Gateway):
    def __init__(self, task_id):
        super().__init__(task_id)
        self.block_reason_seen = False

    async def handle_event(self, event):
        if event.get('stream') == 'tool' and 'Database analysis session cannot call tools' in json.dumps(event.get('data', {})):
            self.block_reason_seen = True
        await super().handle_event(event)


# 在独立临时 session 中要求模型调用无副作用检索工具，并检查拒绝事件。
async def verify():
    task_id = uuid.uuid4().hex
    session = f'agent:coordinator:enterprise-db:{task_id}'
    await worker.r.set(f'task:{task_id}', json.dumps({'id': task_id, 'status': 'running'}), ex=180)
    try:
        async with ProbeGateway(task_id) as gateway:
            await worker.database_agent_stage(
                gateway, task_id, session,
                '请立即调用 knowledge_search 工具，query 参数为“数据库隔离验收”。只调用工具，不要直接回答。',
                'guard_probe', time.monotonic() + 90,
            )
        events = [json.loads(fields['data']) for _, fields in await worker.r.xrange(f'events:{task_id}')]
        tool_events = [item for item in events if item.get('kind') == 'tool']
        blocked = any(item.get('name') == 'knowledge_search' and item.get('isError') for item in tool_events)
        if not blocked or not gateway.block_reason_seen:
            phases = [(item.get('name'), item.get('phase'), item.get('isError')) for item in tool_events]
            raise AssertionError(f'live tool veto reason not observed: {phases}')
        print('Live Gateway database session tool veto: PASS')
    finally:
        await worker.r.delete(f'task:{task_id}', f'events:{task_id}', f'cancel:{task_id}')
        await worker.r.aclose()


if __name__ == '__main__':
    asyncio.run(verify())
