import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const username = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let browser

// 通过现有验证脚本创建和清理一次性管理员账号，密码只经标准输入传递。
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
  const failures = []
  const apiPaths = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('response', response => {
    if (!response.url().includes('/api/')) return
    apiPaths.push(new URL(response.url()).pathname)
    if (response.status() >= 500) failures.push(response.status())
  })
  await page.goto(`${origin}/agents`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.goto(`${origin}/agents`)
  await page.getByRole('heading', { name: 'Agent 管理' }).waitFor()
  await page.locator('.agent-card').first().waitFor()
  assert.ok((await page.locator('.agent-card').count()) >= 4)
  assert.ok(apiPaths.includes('/api/agents/manage'))
  const modelResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/agents/models')
  await page.getByRole('button', { name: '＋ 新建 Agent' }).click()
  await modelResponse
  await page.locator('.el-dialog').getByText('模型', { exact: true }).waitFor()
  assert.ok(apiPaths.includes('/api/agents/models'))
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  assert.deepEqual(errors, [])
  assert.deepEqual(failures, [])
  console.log('Real Agent list, model catalog and responsive browser E2E: PASS')
} finally {
  try { if (browser) await browser.close() }
  finally { identity('cleanup') }
}
