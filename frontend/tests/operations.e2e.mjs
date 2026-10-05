import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  const paths = []
  const agentRows = [
    { id: 'coordinator', name: 'Chief of Staff', description: '协调任务', enabled: true, model: 'test/model', toolPolicy: 'gateway', tools: [{ name: 'metrics_query', count: 2 }], taskCount: 3, successRate: 66.7, sampleSize: 3, source: 'gateway' },
    { id: 'database', name: 'Database', description: '', enabled: false, model: 'test/model', toolPolicy: 'gateway', tools: [], taskCount: 0, successRate: null, sampleSize: 0, source: 'gateway' }
  ]
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    paths.push(path)
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'admin', role: 'admin' } })
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (path === '/api/dashboard') return json({ agentCount: 2, runningTasks: 0, todayTasks: 1, completedTasks: 1,
      successRate: 100, taskTrend: [{ date: '2026-09-30', count: 1 }], recentTasks: [], failedTasks: [],
      observability: { sampledTasks: 2, taskSuccessRate: 50, toolSuccessRate: 100, p50LatencyMs: 120,
        p95LatencyMs: 350, tokenUsage: null, tokenSampledTasks: 0, errorRate: 50, topTools: [{ name: 'metrics_query', count: 1 }] },
      gateway: { status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 } })
    if (path === '/api/tasks') return json([
      { id: 'task-1', owner: 'admin', prompt: '分析本周的业务订单趋势并解释异常', agent: 'coordinator', status: 'completed', createdAt: '2026-09-30T09:00:00', latencyMs: 120, result: '分析完成' },
      { id: 'task-2', owner: 'admin', prompt: '检查系统告警', agent: 'researcher', status: 'failed', createdAt: '2026-09-29T09:00:00', error: 'Gateway unavailable' }
    ])
    if (path === '/api/followups') return json([])
    if (path === '/api/tasks/task-1') return json({ id: 'task-1', traceId: 'trace-1', owner: 'admin', prompt: '分析本周的业务订单趋势并解释异常', agent: 'coordinator', status: 'completed', createdAt: '2026-09-30T09:00:00', latencyMs: 120, result: '分析完成' })
    if (path === '/api/tasks/task-1/events') return json([{ id: '1-0', kind: 'tool', at: 1789990000, name: 'metrics_query', phase: 'completed', durationMs: 48, resultSummary: '工具执行完成' }])
    if (path === '/api/audit') return json([
      { id: '1-0', at: '2026-09-30T09:05:00Z', actor: 'admin', action: 'task.create', target: 'task-1', outcome: 'ok' },
      { id: '2-0', at: '2026-09-29T09:05:00Z', actor: 'operator', action: 'order.query', target: 'hash-1', outcome: 'failed' }
    ])
    if (path === '/api/agents/manage') return json(agentRows)
    if (path === '/api/agents/models') return json(['test/model'])
    if (path === '/api/agents' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      agentRows.push({ id: body.id, name: body.name, description: body.description, enabled: true,
        model: body.model, toolPolicy: body.tool_policy, tools: [], taskCount: 0, successRate: null, sampleSize: 0, source: 'platform' })
      return json({ id: body.id }, 201)
    }
    if (path === '/api/agents') return json([{ id: 'coordinator', name: 'coordinator' }, { id: 'researcher', name: 'researcher' }])
    return json({ detail: 'unexpected API request' }, 500)
  })

  await page.goto(`${origin}/`)
  await page.getByText('近七日任务趋势').waitFor()
  await page.getByText('工具成功率').waitFor()
  await page.getByText('350ms').waitFor()
  await page.getByText('Worker 真实连接检测').waitFor()
  await page.getByText('Gateway 在线').waitFor()
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.gateway-heading + .el-tag')).opacity === '1')
  await page.getByText('企业智能体平台').waitFor()
  const shellColor = await page.locator('.aside').evaluate(el => getComputedStyle(el).backgroundColor)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-dashboard-01.png'), fullPage: true })

  await page.goto(`${origin}/tasks`)
  await page.getByText('分析本周的业务订单趋势并解释异常').first().waitFor()
  assert.equal(await page.locator('.aside').evaluate(el => getComputedStyle(el).backgroundColor), shellColor)
  await page.getByText('completed', { exact: true }).first().waitFor()
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-tasks-07.png'), fullPage: true })
  await page.getByLabel('搜索任务').fill('异常')
  assert.equal(await page.getByText('检查系统告警').count(), 0)
  await page.getByRole('button', { name: '查看' }).click()
  await page.getByText('metrics_query').waitFor()
  await page.getByText('trace-1').waitFor()
  await page.keyboard.press('Escape')

  await page.goto(`${origin}/audit`)
  await page.locator('.el-table').getByText('task.create').waitFor()
  assert.equal(await page.locator('.aside').evaluate(el => getComputedStyle(el).backgroundColor), shellColor)
  assert.equal(await page.locator('.audit-card .el-tag').first().textContent(), 'ok')
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-audit.png'), fullPage: true })
  await page.getByLabel('搜索审计记录').fill('admin')
  assert.equal(await page.locator('.el-table').getByText('order.query').count(), 0)
  await page.getByRole('button', { name: '详情' }).click()
  await page.getByText('task-1').last().waitFor()
  await page.keyboard.press('Escape')

  await page.goto(`${origin}/agents`)
  await page.getByText('任务统计来自平台近 30 天记录').waitFor()
  assert.equal(await page.locator('.aside').evaluate(el => getComputedStyle(el).backgroundColor), shellColor)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-agents-03.png'), fullPage: true })
  await page.getByRole('button', { name: /Chief of Staff/ }).click()
  await page.getByText('Agent 详情').waitFor()
  await page.getByText('metrics_query (2)').waitFor()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '＋ 新建 Agent' }).click()
  await page.getByPlaceholder('例如 sales-assistant').fill('sales-assistant')
  await page.getByPlaceholder('例如 销售助手').fill('销售助手')
  await page.getByPlaceholder('说明这个 Agent 的职责').fill('处理销售咨询')
  await page.locator('.el-dialog').getByRole('combobox').first().click()
  await page.getByText('test/model').last().click()
  await page.getByRole('button', { name: '创建 Agent' }).click()
  await page.getByRole('button', { name: /销售助手/ }).waitFor()
  await page.getByLabel('搜索 Agent').fill('sales-assistant')
  assert.equal(await page.locator('.agent-card').count(), 1)
  assert.ok(paths.includes('/api/tasks') && paths.includes('/api/audit') && paths.includes('/api/agents/manage'))
  assert.deepEqual(errors, [])
  console.log('Tasks, audit and Agent browser E2E: PASS')
} finally {
  await browser.close()
}
