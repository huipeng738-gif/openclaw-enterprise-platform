import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const operator = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const admin = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let fixture
let browser

// 将一次性账号和审批数据写入真实服务；密码只经过子进程标准输入。
function helper(module, payload) {
  const result = spawnSync('docker', ['compose', 'exec', '-T', 'api', 'uv', 'run', 'python', '-m', module], {
    cwd: new URL('../..', import.meta.url), input: JSON.stringify(payload), encoding: 'utf8',
  })
  if (result.status !== 0) throw new Error(`${module} failed: ${result.stderr}`)
  return result.stdout.trim()
}

// 用真实登录表单进入指定角色的审批页。
async function login(page, username) {
  await page.goto(`${origin}/approvals`)
  await page.waitForURL('**/login')
  await page.getByPlaceholder('请输入用户名').fill(username)
  await page.getByPlaceholder('请输入密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(url => url.pathname === '/')
  await page.goto(`${origin}/approvals`)
  await page.getByText('人工审批', { exact: true }).last().waitFor()
}

helper('app.verify_browser_identity', { action: 'create', username: operator, password, role: 'operator' })
try {
  helper('app.verify_browser_identity', { action: 'create', username: admin, password, role: 'admin' })
  fixture = JSON.parse(helper('app.verify_hitl_fixture', { action: 'create', owner: operator }))
  browser = await chromium.launch({ headless: true, channel: 'chrome' })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  const failures = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 500) failures.push(response.status())
  })
  await login(page, operator)
  await page.getByText('演示审批申请 1').waitFor()
  assert.equal(await page.getByRole('button', { name: '批准' }).count(), 0)
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.waitForURL('**/login')

  await login(page, admin)
  const first = page.getByRole('row').filter({ hasText: '演示审批申请 1' })
  await first.getByRole('button', { name: '编辑' }).click()
  await page.getByLabel('审批原因').fill('管理员修订后的取消原因')
  await page.getByRole('button', { name: '保存' }).click()
  await page.getByText('管理员修订后的取消原因').waitFor()
  await page.getByRole('row').filter({ hasText: '管理员修订后的取消原因' }).getByRole('button', { name: '拒绝' }).click()
  await page.getByRole('tab', { name: /已拒绝/ }).click()
  await page.getByText('管理员修订后的取消原因').waitFor()
  await page.getByRole('tab', { name: /待审批/ }).click()
  await page.getByRole('row').filter({ hasText: '演示审批申请 2' }).getByRole('button', { name: '批准' }).click()
  await page.getByRole('tab', { name: /已批准/ }).click()
  await page.getByText('演示审批申请 2').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: 'tests/approvals-real-mobile.png', fullPage: true })
  await page.setViewportSize({ width: 1440, height: 900 })
  if (process.env.E2E_SCREENSHOTS) await page.screenshot({ path: 'tests/approvals-real-desktop.png', fullPage: true })
  assert.deepEqual(errors, [])
  assert.deepEqual(failures, [])
  console.log('Real HITL browser operator view, admin edit/reject/approve: PASS')
} finally {
  try { if (browser) await browser.close() }
  finally {
    if (fixture) helper('app.verify_hitl_fixture', { action: 'cleanup', owner: operator, ...fixture })
    helper('app.verify_browser_identity', { action: 'cleanup', username: operator })
    helper('app.verify_browser_identity', { action: 'cleanup', username: admin })
  }
}
