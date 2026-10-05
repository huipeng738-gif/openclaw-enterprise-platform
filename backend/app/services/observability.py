"""Bounded observability summary derived from persisted task and tool events."""
import json
import math
from collections import Counter


# 从最近可见任务及有限事件中计算真实指标，缺失的耗时与 token 数据保持未知。
async def summarize(redis, tasks):
    sample = tasks[:100]
    terminal = [task for task in sample if task['status'] in {'completed', 'failed', 'cancelled', 'timed_out'}]
    latencies = sorted(task['latencyMs'] for task in terminal
                       if isinstance(task.get('latencyMs'), (int, float)) and task['latencyMs'] >= 0)
    tool_counts = Counter()
    tool_success = 0
    tool_total = 0
    for task in sample:
        events = await redis.xrevrange(f'events:{task["id"]}', count=200)
        seen = set()
        for _, fields in events:
            event = json.loads(fields['data'])
            if event.get('kind') != 'tool' or event.get('phase') not in {'result', 'end', 'completed', 'error', 'failed'}:
                continue
            name = event.get('name')
            if not name:
                continue
            call_id = event.get('callId') or event.get('id')
            identity = (name, call_id) if call_id else None
            if identity and identity in seen:
                continue
            if identity:
                seen.add(identity)
            tool_counts[name] += 1
            tool_total += 1
            tool_success += not event.get('isError', False)
    usage = [task['tokenUsage'] for task in sample if isinstance(task.get('tokenUsage'), (int, float))]
    return {
        'sampledTasks': len(sample),
        'taskSuccessRate': round(sum(task['status'] == 'completed' for task in terminal) / len(terminal) * 100, 1)
        if terminal else None,
        'errorRate': round(sum(task['status'] in {'failed', 'timed_out'} for task in terminal) /
                           len(terminal) * 100, 1) if terminal else None,
        'toolSuccessRate': round(tool_success / tool_total * 100, 1) if tool_total else None,
        'p50LatencyMs': latencies[math.ceil(len(latencies) * 0.5) - 1] if latencies else None,
        'p95LatencyMs': latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None,
        'tokenUsage': sum(usage) if usage else None,
        'tokenSampledTasks': len(usage),
        'topTools': [{'name': name, 'count': count} for name, count in tool_counts.most_common(5)],
    }
