import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const username = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let browser

// 创建并清理一次性管理员账号，不在命令行或输出中传递密码。
function identity(action) {
  const result = spawnSync('docker', ['compose', 'exec', '-T', 'api', 'uv', 'run', 'python', '-m', 'app.verify_browser_identity'], {
    cwd: new URL('../..', import.meta.url),
    input: JSON.stringify({ action, username, ...(action === 'create' ? { password, role: 'admin' } : {}) }),
    encoding: 'utf8',
  })
  if (result.status !== 0) throw new Error(`temporary identity ${action} failed: ${result.stderr}`)
}

identity('create')
try {
  browser = await chromium.launch({ headless: true, channel: 'chrome' })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${origin}/chat`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.goto(`${origin}/chat`)
  const first = page.locator('.conversation-item').first()
  await first.waitFor()
  const taskResponse = page.waitForResponse(response => /\/api\/tasks\/[a-f0-9]{32}$/.test(new URL(response.url()).pathname))
  await first.click()
  const task = await (await taskResponse).json()
  await page.getByText('回放完成').waitFor()
  const metadata = page.locator('.trace-meta dd')
  assert.equal(await metadata.nth(2).textContent(), task.model || '未采集')
  assert.equal(await metadata.nth(3).textContent(), typeof task.tokenUsage === 'number' ? task.tokenUsage.toLocaleString('zh-CN') : '未采集')
  assert.ok((await page.locator('.trace-events li').filter({ hasText: 'Worker 开始执行' }).count()) <= 1)
  assert.deepEqual(errors, [])
  console.log('Real Chat trace replay and telemetry browser E2E: PASS')
} finally {
  try { if (browser) await browser.close() }
  finally { identity('cleanup') }
}
