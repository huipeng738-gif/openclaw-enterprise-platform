import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const username = `database_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let taskId = ''

// 通过 API 容器创建/清理一次性真实账号，敏感值仅经子进程标准输入传递。
function identity(action) {
  const result = spawnSync('docker', ['compose', 'exec', '-T', 'api', 'uv', 'run', 'python', '-m', 'app.verify_browser_identity'], {
    cwd: new URL('../..', import.meta.url),
    input: JSON.stringify({ action, username, ...(action === 'create' ? { password } : { task_id: taskId }) }),
    encoding: 'utf8',
  })
  if (result.status !== 0) throw new Error(`temporary identity ${action} failed: ${result.stderr}`)
}

identity('create')
let browser
try {
  browser = await chromium.launch({ headless: true, channel: 'chrome' })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  const failures = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 500) failures.push(`${response.status()} ${new URL(response.url()).pathname}`)
  })
  await page.goto(`${origin}/analytics`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.goto(`${origin}/analytics`)
  await page.getByLabel('数据库分析问题').fill('查询 Demo 数据中已支付订单的数量，仅根据数据库结果回答。')
  await page.getByRole('button', { name: '开始分析' }).click()
  await page.waitForURL(/\/chat\?task=[a-f0-9]{32}$/)
  taskId = new URL(page.url()).searchParams.get('task') || ''
  assert.match(taskId, /^[a-f0-9]{32}$/)
  try {
    await page.locator('.database-evidence summary').waitFor({ timeout: 120_000 })
  } catch (error) {
    console.error('Database browser terminal UI:', await page.locator('.chat-error, .thinking-state, .status-tag').allTextContents())
    throw error
  }
  await page.locator('.chat-messages .chat-message').last().waitFor()
  await page.locator('.database-evidence summary').click()
  await page.locator('.database-evidence code').waitFor()
  assert.match(await page.locator('.database-evidence code').textContent(), /^SELECT /i)
  await page.reload()
  await page.locator('.database-evidence summary').waitFor()
  await page.locator('.database-evidence summary').click()
  await page.locator('.database-preview .el-table__body').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: 'tests/database-real-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1440, height: 900 })
  if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: 'tests/database-real-desktop.png', fullPage: true })
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.waitForURL('**/login')
  assert.deepEqual(errors, [])
  assert.deepEqual(failures, [])
  console.log('Real database browser login, submit, result, refresh, logout: PASS')
} finally {
  try { if (browser) await browser.close() }
  finally { identity('cleanup') }
}
