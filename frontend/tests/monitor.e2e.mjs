import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  let currentRole = 'admin'
  let listReads = 0
  let listMode = 'normal'
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    const json = value => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'tester', role: currentRole } })
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (path === '/api/dashboard') return json({ failedTasks: [{ id: 'task-failed', prompt: '订单查询失败', agent: 'coordinator', status: 'failed', createdAt: '2026-10-01T10:00:00' }], taskTrend: [], recentTasks: [] })
    if (path === '/api/tasks') {
      listReads++
      if (listMode === 'empty') return json([])
      if (listMode === 'error') return route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
      return json([
        { id: 'task-failed', traceId: 'trace-123', owner: 'tester', prompt: '订单查询失败', agent: 'coordinator', status: 'failed', createdAt: '2026-10-01T10:00:00', latencyMs: 340 },
        { id: 'task-running', traceId: 'trace-456', owner: 'operator', prompt: '分析客户趋势', agent: 'researcher', status: 'running', createdAt: '2026-10-01T10:01:00' }
      ])
    }
    if (path === '/api/tasks/task-failed') return json({ id: 'task-failed', traceId: 'trace-123', owner: 'tester', prompt: '订单查询失败', agent: 'coordinator', status: 'failed', createdAt: '2026-10-01T10:00:00', latencyMs: 340, error: 'Tool 调用失败', model: 'test-model', tokenUsage: 12 })
    if (path === '/api/tasks/task-running') return json({ id: 'task-running', traceId: 'trace-456', owner: 'operator', prompt: '分析客户趋势', agent: 'researcher', status: 'running', createdAt: '2026-10-01T10:01:00' })
    if (path === '/api/tasks/task-failed/events') return json([
      { id: '1-0', kind: 'status', at: 1790820000, status: 'running' },
      { id: '2-0', kind: 'tool', at: 1790820001, name: 'order_query', phase: 'failed', durationMs: 88, isError: true, resultSummary: '工具执行失败', args: { token: 'must-not-appear' } },
      { id: '3-0', kind: 'status', at: 1790820002, status: 'failed' }
    ])
    if (path === '/api/tasks/task-running/events') return json([
      { id: '1-0', kind: 'tool', at: 1790820000, name: 'customer_query', callId: 'call-1', phase: 'start' },
      { id: '2-0', kind: 'tool', at: 1790820001, name: 'customer_query', callId: 'call-1', phase: 'result' },
      { id: '3-0', kind: 'tool', at: 1790820002, name: 'knowledge_search', callId: 'call-2', phase: 'result', resultCount: 2 },
      { id: '4-0', kind: 'database_stage', at: 1790820003, phase: 'analyze', rowCount: 3 }
    ])
    return route.fulfill({ status: 500, body: 'unexpected API request' })
  })
  await page.goto(`${origin}/`)
  await page.getByRole('button', { name: '排查任务 task-failed' }).click()
  await page.getByRole('heading', { name: '运行监控' }).waitFor()
  await page.getByText('trace-123').waitFor()
  await page.getByText('Tool 耗时 88ms').waitFor()
  await page.getByText('查询订单信息：工具报告执行失败。').waitFor()
  await page.getByText('Tool 调用失败').first().waitFor()
  assert.equal(new URL(page.url()).searchParams.get('taskId'), 'task-failed')
  assert.equal(await page.getByText('order_query').count(), 1)
  assert.equal(await page.getByText('must-not-appear').count(), 0)
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.monitor-task .el-tag')).opacity === '1')
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-monitor-desktop.png'), fullPage: true })
  await page.getByRole('textbox', { name: '搜索监控任务' }).fill('trace-456')
  assert.equal(await page.getByRole('button', { name: '查看任务 task-failed' }).count(), 0)
  await page.getByRole('button', { name: '查看任务 task-running' }).click()
  await page.getByText('trace-456').waitFor()
  await page.getByText('查询客户信息已返回结果，供 Agent 分析。').waitFor()
  await page.getByText('知识库检索已返回 2 条来源，供 Agent 生成回答。').waitFor()
  await page.getByText('只读 SQL 已执行，返回 3 行记录，正在分析结果。').waitFor()
  await page.getByText('Tool 耗时 1000ms').waitFor()
  await page.getByRole('button', { name: '立即刷新' }).click()
  assert.ok(listReads >= 2)
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-monitor-mobile.png'), fullPage: true })

  listMode = 'empty'
  await page.getByRole('button', { name: '立即刷新' }).click()
  await page.getByText('暂无匹配任务').waitFor()
  listMode = 'error'
  await page.getByRole('button', { name: '立即刷新' }).click()
  await page.getByText('加载监控任务失败，请重试').waitFor()

  currentRole = 'viewer'
  await page.context().clearCookies()
  await page.reload()
  await page.goto(`${origin}/monitor`)
  await page.waitForURL(`${origin}/`)
  assert.equal(await page.getByText('运行监控', { exact: true }).count(), 0)
  assert.deepEqual(errors, [])
  console.log('Monitor trace, refresh and RBAC browser E2E: PASS')
} finally {
  await browser.close()
}
