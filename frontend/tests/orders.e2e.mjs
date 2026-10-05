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
    if (url.pathname === '/api/orders') {
      queries.push(Object.fromEntries(url.searchParams))
      if (mode === 'error') return json({ detail: 'unavailable' }, 503)
      return json({ total: mode === 'empty' ? 0 : 1, page: Number(url.searchParams.get('page') || 1), page_size: 20,
        items: mode === 'empty' ? [] : [{ order_no: 'ORD-DEMO-001', status: 'shipped', total_amount: '299.00',
          payment_status: 'paid', created_at: '2026-09-01T09:00:00',
          customer: { customer_no: 'CUST-DEMO-001', name: '演示客户甲' } }] })
    }
    if (url.pathname === '/api/orders/ORD-DEMO-001') return json({ order_no: 'ORD-DEMO-001', status: 'shipped',
      total_amount: '299.00', payment_status: 'paid', created_at: '2026-09-01T09:00:00',
      customer: { customer_no: 'CUST-DEMO-001', name: '演示客户甲' },
      order_items: [{ product_name: '演示键盘', sku: 'DEMO-KEYBOARD', quantity: 1, unit_price: '199.00' }] })
    return json({ detail: 'unexpected API request' }, 500)
  })
  await page.goto(`${origin}/orders`)
  await page.getByText('ORD-DEMO-001').first().waitFor()
  await page.getByText('演示客户甲').first().waitFor()
  assert.equal(await page.locator('.orders-table .el-tag').first().textContent(), '已发货')
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.orders-table .el-tag')).opacity === '1')
  assert.equal(queries[0].page_size, '20')
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-orders-05.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-orders-05-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: '查看订单 ORD-DEMO-001' }).click()
  await page.getByText('DEMO-KEYBOARD').waitFor()
  await page.keyboard.press('Escape')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.getByLabel('搜索订单').fill('演示键盘')
  const filtered = page.waitForResponse(response => response.url().includes('/api/orders?') && response.url().includes('search='))
  await page.getByRole('button', { name: '查询' }).click()
  await filtered
  assert.equal(queries.at(-1).search, '演示键盘')
  await page.getByRole('button', { name: '查看订单 ORD-DEMO-001' }).click()
  await page.getByText('DEMO-KEYBOARD').waitFor()
  await page.keyboard.press('Escape')
  mode = 'empty'
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByText('没有匹配的订单').waitFor()
  mode = 'error'
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByText('加载订单失败，请稍后重试').waitFor()
  assert.deepEqual(errors, [])
  console.log('Orders list, search, detail, empty and error browser E2E: PASS')
} finally {
  await browser.close()
}
