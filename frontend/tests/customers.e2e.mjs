import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  const queries = []
  let mode = 'data'
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url())
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (url.pathname === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'tester', role: 'operator' } })
    if (url.pathname === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (url.pathname === '/api/customers') {
      queries.push(Object.fromEntries(url.searchParams))
      if (mode === 'error') return json({ detail: 'unavailable' }, 503)
      return json({ total: mode === 'empty' ? 0 : 1, page: 1, page_size: 20,
        items: mode === 'empty' ? [] : [{ customer_no: 'CUST-DEMO-001', name: '演示客户甲',
          phone: '138****0001', level: 'vip', status: 'active', created_at: '2026-08-01T09:00:00',
          order_count: 2, last_order_time: '2026-09-10T09:00:00' }] })
    }
    if (url.pathname === '/api/customers/CUST-DEMO-001') return json({
      customer_no: 'CUST-DEMO-001', name: '演示客户甲', phone: '138****0001', level: 'vip', status: 'active',
      created_at: '2026-08-01T09:00:00', order_count: 2, total_amount: '299.00',
      last_order_time: '2026-09-10T09:00:00',
      recent_orders: [{ order_no: 'ORD-DEMO-001', status: 'shipped', total_amount: '299.00', created_at: '2026-09-10T09:00:00' }]
    })
    return json({ detail: 'unexpected API request' }, 500)
  })
  await page.goto(`${origin}/customers`)
  await page.getByText('CUST-DEMO-001').first().waitFor()
  assert.equal(await page.getByText('138****0001').count(), 1)
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.customers-table .el-tag')).opacity === '1')
  assert.equal(queries[0].page_size, '20')
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-customers-06.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-customers-06-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: '查看客户 CUST-DEMO-001' }).click()
  await page.getByRole('heading', { name: '最近订单' }).waitFor()
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByLabel('搜索客户').fill('演示客户')
  const filtered = page.waitForResponse(response => response.url().includes('/api/customers?') && response.url().includes('search='))
  await page.getByRole('button', { name: '查询' }).click()
  await filtered
  assert.equal(queries.at(-1).search, '演示客户')
  await page.getByRole('button', { name: '查看客户 CUST-DEMO-001' }).click()
  await page.getByText('ORD-DEMO-001').waitFor()
  await page.keyboard.press('Escape')
  mode = 'empty'
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByText('没有匹配的客户').waitFor()
  mode = 'error'
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByText('加载客户失败，请稍后重试').waitFor()
  assert.deepEqual(errors, [])
  console.log('Customers list, search, detail, empty and error browser E2E: PASS')
} finally {
  await browser.close()
}
