import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  let role = 'admin'
  let users = [{ username: 'admin', role: 'admin', disabled: false }]
  let policy = { version: 0, defaultTimeoutSeconds: 180, submissionsPaused: false }
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'admin', role } })
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-02T01:00:00Z', latencyMs: 10 })
    if (path === '/api/users' && route.request().method() === 'GET') return json(users)
    if (path === '/api/users' && route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      users.push({ username: body.username, role: body.role, disabled: false })
      return json({ username: body.username, role: body.role }, 201)
    }
    if (path.endsWith('/role')) { users[1].role = route.request().postDataJSON().role; return json(users[1]) }
    if (path.endsWith('/availability')) { users[1].disabled = route.request().postDataJSON().disabled; return json(users[1]) }
    if (path.endsWith('/password')) return json({ reset: true })
    if (path === '/api/settings/task-policy' && route.request().method() === 'GET') return json(policy)
    if (path === '/api/settings/task-policy' && route.request().method() === 'PUT') {
      policy = { ...route.request().postDataJSON(), version: policy.version + 1 }
      return json(policy)
    }
    if (path === '/api/settings/dependencies') return json(['API', 'Redis', 'Worker', 'Gateway', 'MySQL', 'RAGFlow'].map(name => ({ name, status: 'online', checkedAt: '2026-10-02T01:00:00Z', detail: '连接正常' })))
    return json({ detail: 'unexpected request' }, 500)
  })
  await page.goto(`${origin}/settings`)
  await page.getByRole('heading', { name: '系统设置' }).waitFor()
  await page.getByText('RAGFlow').waitFor()
  await page.getByRole('button', { name: '新建账号' }).click()
  await page.locator('.el-dialog').getByLabel('用户名').fill('alice')
  await page.locator('.el-dialog').getByLabel('密码').fill('strongpassword123')
  await page.locator('.el-dialog').getByRole('button', { name: '创建' }).click()
  await page.getByText('alice').waitFor()
  await page.getByRole('button', { name: '保存策略' }).click()
  assert.equal(policy.version, 1)
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  role = 'viewer'
  await page.reload()
  await page.goto(`${origin}/settings`)
  await page.waitForURL(url => url.pathname === '/')
  assert.deepEqual(errors, [])
  console.log('Settings UI, policy, responsive layout and RBAC browser E2E: PASS')
} finally { await browser.close() }
