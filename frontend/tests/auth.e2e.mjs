import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })

try {
  const page = await browser.newPage()
  let signedIn = false
  let role = 'operator'
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) return route.continue()
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return signedIn ? json({ access_token: 'e2e-token', user: { username: 'tester', role } }) : json({ detail: 'unauthorized' }, 401)
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (path === '/api/auth/login') { signedIn = true; return json({ access_token: 'e2e-token', user: { username: 'tester', role } }) }
    if (path === '/api/auth/logout') { signedIn = false; return json({ ok: true }) }
    if (path === '/api/dashboard') return json({ agentCount: 1, runningTasks: 0, todayTasks: 0, completedTasks: 0, successRate: null, taskTrend: [], recentTasks: [], failedTasks: [] })
    return json({ detail: 'unexpected API request' }, 500)
  })

  await page.goto(`${origin}/dashboard`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill('tester')
  await page.getByPlaceholder('请输入密码').fill('test-password')
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByText('最近任务 · Agent Activity').waitFor()
  await page.getByText('暂无任务').first().waitFor()
  await page.reload()
  await page.getByText('最近任务 · Agent Activity').waitFor()
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.waitForURL('**/login')

  role = 'viewer'; signedIn = true
  await page.goto(`${origin}/chat`)
  await page.waitForURL(url => url.pathname === '/')
  await page.goto(`${origin}/orders`)
  await page.waitForURL(url => url.pathname === '/')
  assert.equal(await page.getByText('AI 助手', { exact: true }).count(), 0)
  assert.equal(await page.getByText('订单管理', { exact: true }).count(), 0)
  assert.equal(await page.getByText('数据分析', { exact: true }).count(), 0)
  assert.equal(await page.getByText('审计日志', { exact: true }).count(), 0)
  assert.deepEqual(errors, [])
  console.log('Login, refresh, logout and RBAC browser E2E: PASS')
} finally {
  await browser.close()
}
