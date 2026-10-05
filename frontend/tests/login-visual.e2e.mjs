import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/auth/refresh', route => route.fulfill({ status: 401, contentType: 'application/json', body: '{}' }))
  await page.goto(`${origin}/login`)
  await page.getByRole('heading', { name: '欢迎登录' }).waitFor()
  assert.equal(await page.getByText('OpenClaw Enterprise').count(), 0)
  assert.equal(await page.locator('.login-brand:visible').count(), 1)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  await page.screenshot({ path: join(tmpdir(), 'openclaw-login-business-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.locator('.mobile-brand:visible').count(), 1)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  await page.screenshot({ path: join(tmpdir(), 'openclaw-login-business-mobile.png'), fullPage: true })
  assert.deepEqual(errors, [])
  console.log('Business login desktop/mobile visual E2E: PASS')
} finally { await browser.close() }
