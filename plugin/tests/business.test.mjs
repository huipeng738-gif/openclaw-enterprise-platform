import assert from 'node:assert/strict'
import test from 'node:test'
import register from '../src/index.ts'

test('business tools register alongside knowledge and call only fixed service endpoints', async () => {
  const tools = new Map()
  const hooks = new Map()
  const calls = []
  const originalFetch = globalThis.fetch
  const originalToken = process.env.PLUGIN_SERVICE_TOKEN
  process.env.PLUGIN_SERVICE_TOKEN = 'test-plugin-token'
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return { ok: true, json: async () => ({ order_no: 'ORD-DEMO-001' }) }
  }
  try {
    register({ pluginConfig: { businessUrl: 'http://business.test/', metricsUrl: 'http://business.test/metrics/query', timeoutMs: 1000 },
      on: (name, handler) => hooks.set(name, handler),
      registerTool: (tool, metadata) => tools.set(tool.name || metadata?.name, tool) })
    const toolGuard = hooks.get('before_tool_call')
    assert.equal(toolGuard({}, { sessionKey: `agent:coordinator:enterprise-db:${'a'.repeat(32)}` }).block, true)
    assert.equal(toolGuard({}, { sessionKey: 'agent:coordinator:enterprise:normal' }), undefined)
    assert.deepEqual([...tools.keys()], ['knowledge_search', 'order_query', 'customer_query', 'metrics_query', 'task_create', 'task_cancel_request'])
    assert.equal(tools.get('task_create')({sessionKey: 'untrusted'}), null)
    const actionSession = `agent:coordinator:enterprise:${'b'.repeat(32)}`
    const followupTool = tools.get('task_create')({sessionKey: actionSession})
    const cancelTool = tools.get('task_cancel_request')({sessionKey: actionSession})
    await followupTool.execute('action-1', {title: '催发货', order_no: 'ORD-DEMO-001'})
    await cancelTool.execute('action-2', {target_task_id: 'c'.repeat(32), reason: '用户要求停止任务'})
    assert.equal(tools.get('order_query').parameters.additionalProperties, false)
    assert.equal(tools.get('customer_query').parameters.additionalProperties, false)
    const order = await tools.get('order_query').execute('call-1', { order_no: 'ORD-DEMO-001' })
    await tools.get('customer_query').execute('call-2', { customer_no: 'CUST-DEMO-001' })
    await tools.get('metrics_query').execute('call-3', {
      metric: 'sales_amount', start_date: '2026-09-01', end_date: '2026-09-30', group_by: 'day'
    })
    assert.equal(JSON.parse(order.content[0].text).order_no, 'ORD-DEMO-001')
    assert.deepEqual(calls.map(call => call.url), [
      'http://business.test/actions/task-create',
      'http://business.test/actions/task-cancel/request',
      'http://business.test/business/orders/query',
      'http://business.test/business/customers/query',
      'http://business.test/metrics/query'
    ])
    assert.deepEqual(calls.map(call => JSON.parse(call.options.body)), [
      {title: '催发货', order_no: 'ORD-DEMO-001', session_key: actionSession, tool_call_id: 'action-1'},
      {target_task_id: 'c'.repeat(32), reason: '用户要求停止任务', session_key: actionSession, tool_call_id: 'action-2'},
      { order_no: 'ORD-DEMO-001' }, { customer_no: 'CUST-DEMO-001' },
      { metric: 'sales_amount', start_date: '2026-09-01', end_date: '2026-09-30', group_by: 'day' }
    ])
    assert.ok(calls.every(call => call.options.headers['X-Plugin-Token'] === 'test-plugin-token'))
  } finally {
    globalThis.fetch = originalFetch
    if (originalToken === undefined) delete process.env.PLUGIN_SERVICE_TOKEN
    else process.env.PLUGIN_SERVICE_TOKEN = originalToken
  }
})
