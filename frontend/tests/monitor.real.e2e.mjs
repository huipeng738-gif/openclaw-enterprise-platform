import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const username = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let browser

// 经 API 容器创建或清理一次性管理员账号，密码仅通过标准输入传递。
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
  await page.goto(`${origin}/monitor`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.getByText('Gateway 在线').waitFor()
  await page.getByText('Worker 真实连接检测').waitFor()
  assert.ok(apiPaths.includes('/api/runtime/gateway'))
  await page.goto(`${origin}/monitor`)
  await page.getByRole('heading', { name: '运行监控' }).waitFor()
  await page.getByText('统计范围：管理员可见的最近 100 条任务').waitFor()
  const firstTask = page.locator('.monitor-task').first()
  if (await firstTask.count()) {
    await firstTask.click()
    await page.getByText('Trace ID').waitFor()
    assert.doesNotMatch((await page.locator('.monitor-details dd').nth(1).innerText()), /未采集/)
    assert.ok(apiPaths.some(path => /^\/api\/tasks\/[^/]+$/.test(path)))
    assert.ok(apiPaths.some(path => /^\/api\/tasks\/[^/]+\/events$/.test(path)))
  }
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  assert.ok(apiPaths.includes('/api/tasks'))
  assert.deepEqual(errors, [])
  assert.deepEqual(failures, [])
  console.log('Real monitor login, API and responsive browser E2E: PASS')
} finally {
  try { if (browser) await browser.close() }
  finally { identity('cleanup') }
}
