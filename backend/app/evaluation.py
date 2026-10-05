"""Offline evaluation for recorded Agent outcomes and explicitly synthetic fixtures."""
import argparse
import json
import math
from pathlib import Path


CATEGORIES = {'Knowledge', 'Order', 'Customer', 'Metrics', 'Database', 'Action', 'HITL'}


# 从平台任务快照和脱敏事件生成可评分观测，缺少的 Tool 参数保持未知。
def observation_from_task(task, events):
    tools = [event for event in events if event.get('kind') == 'tool' and event.get('name')]
    observed = {'status': task['status'], 'tool': tools[0]['name'] if tools else None,
                'latencyMs': task.get('latencyMs'), 'tokenUsage': task.get('tokenUsage'),
                'citations': [source['document_id'] for source in task.get('sources', [])
                              if isinstance(source, dict) and source.get('document_id')]}
    if tools and isinstance(tools[0].get('query'), str):
        observed['parameters'] = {'query': tools[0]['query']}
    if task.get('kind') == 'database':
        observed['tool'] = 'database_agent'
        observed['sqlExecuted'] = isinstance(task.get('database'), dict)
    return observed


# 对单个观测结果执行确定性评分，记录所有不符合期望的维度。
def evaluate_case(case):
    expected = case['expected']
    observed = case['observed']
    checks = {
        'taskSuccess': observed.get('status') == expected['status'],
        'toolSelection': observed.get('tool') == expected['tool'],
    }
    if expected.get('parameters'):
        checks['parameterAccuracy'] = all(observed.get('parameters', {}).get(key) == value
                                          for key, value in expected['parameters'].items())
    if 'sqlExecuted' in expected:
        checks['sqlExecutionSuccess'] = observed.get('sqlExecuted') is expected['sqlExecuted']
    if 'citations' in expected:
        checks['citationAccuracy'] = set(expected['citations']).issubset(set(observed.get('citations', [])))
    for key, value in expected.get('constraints', {}).items():
        checks[key] = observed.get(key) == value
    latency = observed.get('latencyMs')
    tokens = observed.get('tokenUsage')
    cost = observed.get('tokenCostUsd')
    if (not isinstance(latency, (int, float)) or isinstance(latency, bool) or
            not math.isfinite(latency) or latency < 0):
        raise ValueError(f'{case["id"]}: invalid latencyMs')
    if tokens is not None and (not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0):
        raise ValueError(f'{case["id"]}: invalid tokenUsage')
    if cost is not None and (not isinstance(cost, (int, float)) or isinstance(cost, bool) or
                             not math.isfinite(cost) or cost < 0):
        raise ValueError(f'{case["id"]}: invalid tokenCostUsd')
    return {'id': case['id'], 'category': case['category'], 'checks': checks,
            'latencyMs': latency, 'tokenUsage': tokens,
            'tokenCostUsd': cost}


# 汇总七类案例的通过率、耗时与用量；缺失费用保持未知并保留 Bad Case。
def evaluate(dataset):
    if dataset.get('source') not in {'demo_fixture', 'recorded_run'}:
        raise ValueError('evaluation source must be explicit')
    cases = dataset['cases']
    if {case['category'] for case in cases} != CATEGORIES:
        raise ValueError('evaluation dataset must cover all seven categories')
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('evaluation case ids must be unique')
    results = [evaluate_case(case) for case in cases]
    dimensions = sorted({key for row in results for key in row['checks']})
    rates = {}
    for dimension in dimensions:
        values = [row['checks'][dimension] for row in results if dimension in row['checks']]
        rates[dimension] = round(sum(values) / len(values) * 100, 1)
    latencies = sorted(row['latencyMs'] for row in results)
    usage = [row['tokenUsage'] for row in results if row['tokenUsage'] is not None]
    costs = [row['tokenCostUsd'] for row in results if row['tokenCostUsd'] is not None]
    return {
        'source': dataset['source'], 'sampleCount': len(results), 'rates': rates,
        'p50LatencyMs': latencies[math.ceil(len(latencies) * 0.5) - 1],
        'p95LatencyMs': latencies[math.ceil(len(latencies) * 0.95) - 1],
        'totalTokens': sum(usage) if len(usage) == len(results) else None,
        'tokenCostUsd': round(sum(costs), 6) if len(costs) == len(results) else None,
        'badCases': [{'id': row['id'], 'category': row['category'],
                      'failedChecks': [key for key, passed in row['checks'].items() if not passed]}
                     for row in results if not all(row['checks'].values())],
    }


# 从指定数据集生成 JSON 报告，可选落盘供阶段验收与 Bad Case 复盘。
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    arguments = parser.parse_args()
    report = evaluate(json.loads(arguments.dataset.read_text(encoding='utf-8')))
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if arguments.report:
        arguments.report.write_text(output + '\n', encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
