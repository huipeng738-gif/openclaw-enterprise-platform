import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage()
  const errors = []
  const queries = []
  let mode = 'data'
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) return route.continue()
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'tester', role: 'operator' } })
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (path === '/api/metrics/query') {
      queries.push(route.request().postDataJSON())
      if (mode === 'error') return json({ detail: 'unavailable' }, 503)
      return json({ metric: 'sales_amount', label: '已支付订单金额', unit: 'CNY', total: mode === 'empty' ? '0.00' : '299.00',
        points: mode === 'empty' ? [] : [{ period: '2026-09-01', value: '299.00' }] })
    }
    return json({ detail: 'unexpected API request' }, 500)
  })
  await page.goto(`${origin}/analytics`)
  await page.getByText('指标趋势').waitFor()
  await page.getByText('299.00 CNY').waitFor()
  assert.equal(queries[0].metric, 'sales_amount')
  assert.equal(queries[0].group_by, 'day')
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-analytics-phase5.png'), fullPage: true })
  mode = 'empty'
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByText('所选时间范围暂无数据').waitFor()
  mode = 'error'
  await page.getByRole('button', { name: '查询' }).click()
  await page.getByText('指标查询失败，请检查时间范围或稍后重试').waitFor()
  assert.deepEqual(errors, [])
  console.log('Analytics data, empty and error browser E2E: PASS')
} finally {
  await browser.close()
}
