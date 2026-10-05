import assert from 'node:assert/strict'
import { test } from 'node:test'
import { agentTraceSteps, executionStage } from '../src/utils/chat.ts'

test('trace merges duplicate status and tool lifecycle while preserving real progress', () => {
  const task = { id: 'task-1', agent: 'coordinator', prompt: '查询订单', status: 'completed',
    createdAt: '2026-10-02T08:00:00Z', finishedAt: '2026-10-02T08:00:05Z' }
  const events = [
    { id: '1-0', kind: 'status', status: 'running', at: 1 },
    { id: '2-0', kind: 'status', status: 'running', at: 2 },
    { id: '3-0', kind: 'accepted', at: 3 },
    { id: '4-0', kind: 'lifecycle', phase: 'start', at: 4 },
    { id: '5-0', kind: 'lifecycle', phase: 'model', at: 5 },
    { id: '6-0', kind: 'tool', phase: 'start', name: 'order_query', callId: 'call-1', at: 6 },
    { id: '7-0', kind: 'tool', phase: 'result', name: 'order_query', callId: 'call-1', resultSummary: '工具执行完成', durationMs: 88, at: 7 },
    { id: '8-0', kind: 'assistant', text: '答复', at: 8 },
    { id: '9-0', kind: 'status', status: 'completed', at: 9 },
  ]
  const steps = agentTraceSteps(task, events)
  assert.equal(steps.filter(step => step.label === 'Worker 开始执行').length, 1)
  assert.equal(steps.filter(step => step.label.includes('order_query')).length, 1)
  assert.equal(steps.find(step => step.label.includes('order_query')).detail, '工具执行完成 · 88 ms')
  assert.equal(steps.at(-1).label, '任务完成')
  assert.ok(!steps.some(step => step.label.includes('model')))
})

test('database progress and terminal snapshot are shown without fabricated event data', () => {
  const task = { id: 'task-db', agent: 'database', prompt: '分析数据', status: 'completed', createdAt: '2026-10-02T08:00:00Z' }
  const events = [{ id: '1-0', kind: 'database_stage', phase: 'analyze', rowCount: 3, at: 1 }]
  const steps = agentTraceSteps(task, events)
  assert.equal(steps.find(step => step.label === '分析查询结果').detail, '查询返回 3 行')
  assert.equal(steps.at(-1).label, '任务完成')
  assert.equal(steps.at(-1).at, undefined)
  assert.equal(executionStage({ ...task, status: 'running' }, events), '正在分析查询结果')
})
