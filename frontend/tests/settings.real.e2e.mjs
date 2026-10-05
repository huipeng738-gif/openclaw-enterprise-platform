import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const admin = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const member = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let browser

// 经标准输入在 MySQL 中创建和清理一次性账号，不把密码写入命令行。
function identity(action, username, role = 'admin') {
  const result = spawnSync('docker', ['compose', 'exec', '-T', 'api', 'uv', 'run', 'python', '-m', 'app.verify_browser_identity'], {
    cwd: new URL('../..', import.meta.url),
    input: JSON.stringify({ action, username, ...(action === 'create' ? { password, role } : {}) }),
    encoding: 'utf8',
  })
  if (result.status !== 0) throw new Error(`temporary identity ${action} failed: ${result.stderr}`)
}

identity('create', admin)
try {
  browser = await chromium.launch({ headless: true, channel: 'chrome' })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  const failures = []
  const paths = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('response', response => {
    if (!response.url().includes('/api/')) return
    paths.push(new URL(response.url()).pathname)
    if (response.status() >= 500) failures.push(response.status())
  })
  await page.goto(`${origin}/settings`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill(admin)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.goto(`${origin}/settings`)
  await page.getByRole('heading', { name: '系统设置' }).waitFor()
  await page.getByText('RAGFlow').waitFor()
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-settings-desktop.png'), fullPage: true })
  assert.ok(paths.includes('/api/users'))
  assert.ok(paths.includes('/api/settings/task-policy'))
  assert.ok(paths.includes('/api/settings/dependencies'))
  await page.getByRole('button', { name: '新建账号' }).click()
  await page.locator('.el-dialog').getByLabel('用户名').fill(member)
  await page.locator('.el-dialog').getByLabel('密码').fill(password)
  await page.locator('.el-dialog').getByRole('button', { name: '创建' }).click()
  await page.getByText(member).waitFor()
  const row = page.locator('.el-table__row').filter({ hasText: member })
  await row.getByRole('button', { name: '停用' }).click()
  await page.getByRole('button', { name: 'OK' }).click()
  await row.getByText('已停用').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-settings-mobile.png'), fullPage: true })
  assert.deepEqual(errors, [])
  assert.deepEqual(failures, [])
  console.log('Real MySQL settings browser E2E: PASS')
} finally {
  try { if (browser) await browser.close() }
  finally { identity('cleanup', member); identity('cleanup', admin) }
}
