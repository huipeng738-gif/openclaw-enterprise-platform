import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage()
  const errors = []
  const questions = []
  const task = { id: 'db-e2e-task', owner: 'tester', agent: 'database', kind: 'database',
    prompt: '分析 VIP 客户购买趋势', status: 'completed', createdAt: '2026-09-30T09:00:00',
    result: '当前数据不足以判断三个月趋势。',
    database: { sql: 'SELECT COUNT(*) AS count FROM orders LIMIT 100', rowCount: 1,
      truncated: false, preview: [{ count: 3 }] } }
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'tester', role: 'operator' } })
    if (url.pathname === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (url.pathname === '/api/metrics/query') return json({ metric: 'sales_amount', label: '销售额', unit: 'CNY', total: '0.00', points: [] })
    if (url.pathname === '/api/database/questions') {
      questions.push(route.request().postDataJSON())
      return json(task, 202)
    }
    if (url.pathname === '/api/tasks') return json([task])
    if (url.pathname === '/api/tasks/db-e2e-task') return json(task)
    if (url.pathname === '/api/tasks/db-e2e-task/events') return json([])
    if (url.pathname === '/api/agents') return json([{ id: 'coordinator', name: 'Coordinator' }])
    return json({ detail: 'unexpected API request' }, 500)
  })
  await page.goto(`${origin}/analytics`)
  await page.getByLabel('数据库分析问题').fill(task.prompt)
  await page.getByRole('button', { name: '开始分析' }).click()
  await page.waitForURL('**/chat?task=db-e2e-task')
  await page.getByText('当前数据不足以判断三个月趋势。').waitFor()
  await page.getByText('查询依据 · 1 行').click()
  await page.getByText('SELECT COUNT(*) AS count FROM orders LIMIT 100').waitFor()
  assert.equal(questions.length, 1)
  assert.equal(questions[0].prompt, task.prompt)
  assert.deepEqual(errors, [])
  console.log('Database question submission and task recovery browser E2E: PASS')
} finally {
  await browser.close()
}
