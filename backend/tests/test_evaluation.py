import json
from pathlib import Path

import pytest

from app.evaluation import evaluate, observation_from_task


DATASET = Path(__file__).parents[2] / 'evaluation' / 'demo_cases.json'


# 七类模拟案例必须产生可复核的维度得分与两条明确 Bad Case。
def test_demo_evaluation_reports_bad_cases():
    report = evaluate(json.loads(DATASET.read_text(encoding='utf-8')))
    assert report['source'] == 'demo_fixture'
    assert report['sampleCount'] == 7
    assert report['rates']['taskSuccess'] == 100
    assert report['rates']['toolSelection'] == 100
    assert report['rates']['parameterAccuracy'] == 83.3
    assert report['rates']['citationAccuracy'] == 0
    assert report['rates']['sqlExecutionSuccess'] == 100
    assert report['totalTokens'] == 159
    assert report['tokenCostUsd'] is None
    assert report['badCases'] == [
        {'id': 'knowledge-citation', 'category': 'Knowledge', 'failedChecks': ['citationAccuracy']},
        {'id': 'customer-number', 'category': 'Customer', 'failedChecks': ['parameterAccuracy']},
    ]


# 缺类和非法计量必须被拒绝，避免用不完整数据伪造阶段通过率。
def test_evaluation_rejects_incomplete_or_invalid_input():
    dataset = json.loads(DATASET.read_text(encoding='utf-8'))
    with pytest.raises(ValueError, match='seven categories'):
        evaluate({**dataset, 'cases': dataset['cases'][:-1]})
    dataset['cases'][0]['observed']['tokenUsage'] = -1
    with pytest.raises(ValueError, match='invalid tokenUsage'):
        evaluate(dataset)


# 真实任务适配器只提取已持久化的脱敏事件，不推断不存在的业务参数。
def test_recorded_task_observation_keeps_unknown_parameters_unknown():
    observed = observation_from_task(
        {'status': 'completed', 'latencyMs': 125, 'tokenUsage': 42,
         'sources': [{'document_id': 'doc-demo-1'}]},
        [{'kind': 'tool', 'phase': 'result', 'name': 'order_query'}],
    )
    assert observed['tool'] == 'order_query'
    assert observed['citations'] == ['doc-demo-1']
    assert 'parameters' not in observed


# 有可信费用输入时汇总 Token Cost；缺失费用时报告保持未知。
def test_evaluation_sums_supplied_token_cost():
    dataset = json.loads(DATASET.read_text(encoding='utf-8'))
    for case in dataset['cases']:
        case['observed']['tokenCostUsd'] = 0.001
    assert evaluate(dataset)['tokenCostUsd'] == 0.007
