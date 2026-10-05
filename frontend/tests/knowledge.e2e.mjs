import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
try {
  const page = await browser.newPage()
  const errors = []
  const createdId = 'a'.repeat(32)
  const existingId = 'b'.repeat(32)
  const datasets = [{ id: 'kb-1', name: '企业文档', description: '员工规范', document_count: 2, status: '1', update_date: '2026-09-29T10:20:30' }]
  const available = [{ id: existingId, name: '已有制度库' }]
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    const method = route.request().method()
    if (!path.startsWith('/api/')) return route.continue()
    const json = value => route.fulfill({ contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'tester', role: 'admin' } })
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (path === '/api/knowledge/datasets/available' && method === 'GET') return json(available)
    if (path === '/api/knowledge/bases' && method === 'POST') {
      const name = JSON.parse(route.request().postData()).name
      datasets.push({ id: createdId, name, document_count: 0 })
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: createdId, name }) })
    }
    if (path === `/api/knowledge/datasets/${existingId}/register` && method === 'POST') {
      datasets.push(available.shift())
      return json({ id: existingId })
    }
    if (path === '/api/knowledge/bases') return json(datasets)
    if (path === '/api/knowledge/bases/kb-1/documents') return json({ docs: [
      { id: 'doc-1', name: '员工手册.pdf', run: 'DONE', chunk_count: 4, update_date: '2026-09-29T10:20:30' },
      { id: 'doc-2', name: '接口说明.docx', run: 'FAIL', chunk_count: 0, update_date: '2026-09-28T08:09:10' }
    ] })
    if (path === `/api/knowledge/bases/${createdId}/documents` || path === `/api/knowledge/bases/${existingId}/documents`) return json({ docs: [] })
    return route.fulfill({ status: 500, body: 'unexpected API request' })
  })
  await page.goto(`${origin}/knowledge`)
  try { await page.getByText('员工手册.pdf').waitFor({ timeout: 8000 }) }
  catch (error) { console.error((await page.locator('body').innerText()).slice(0, 1000), errors); throw error }
  await page.getByRole('radiogroup', { name: '文档类型' }).getByText('PDF').click()
  assert.equal(await page.getByText('接口说明.docx').count(), 0)
  await page.getByRole('radiogroup', { name: '文档类型' }).getByText('全部').click()
  await page.getByRole('textbox', { name: '搜索文档' }).fill('接口')
  await page.getByText('接口说明.docx').waitFor()
  assert.equal(await page.getByText('员工手册.pdf').count(), 0)
  assert.equal(await page.getByText('2026-09-28 08:09:10').count(), 1)
  await page.getByRole('textbox', { name: '搜索文档' }).clear()
  await page.getByRole('spinbutton', { name: '最少 Chunk 数' }).fill('1')
  await page.getByText('员工手册.pdf').waitFor()
  assert.equal(await page.getByText('接口说明.docx').count(), 0)
  await page.getByRole('button', { name: '重置筛选' }).first().click()
  const documentDate = page.locator('.knowledge-list-filters').first().locator('.el-date-editor input')
  await documentDate.fill('2026-09-29')
  await documentDate.press('Enter')
  assert.equal(await page.getByText('接口说明.docx').count(), 0)
  await page.getByRole('button', { name: '重置筛选' }).first().click()
  await page.getByRole('textbox', { name: '搜索知识库' }).fill('不存在')
  assert.equal(await page.getByRole('cell', { name: '企业文档' }).count(), 0)
  await page.getByRole('button', { name: '重置筛选' }).last().click()
  assert.equal(await page.getByText('2026-09-29 10:20:30').count(), 2)
  await page.getByRole('button', { name: '管理知识库' }).click()
  await page.getByPlaceholder('例如：企业制度库').fill('新建政策库')
  await page.getByRole('dialog').getByRole('button', { name: '创建' }).click()
  await page.getByText('新建政策库').first().waitFor()
  await page.getByRole('button', { name: '管理知识库' }).click()
  await page.getByRole('dialog').locator('.el-select').click()
  await page.getByText('已有制度库', { exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: '关联' }).click()
  await page.getByText('已有制度库').first().waitFor()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  await page.setViewportSize({ width: 390, height: 844 })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
  await page.getByRole('button', { name: '管理知识库' }).click()
  const dialogBounds = await page.getByRole('dialog').boundingBox()
  assert.ok(dialogBounds && dialogBounds.x >= 0 && dialogBounds.x + dialogBounds.width <= 390)
  await page.keyboard.press('Escape')
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-knowledge-phase4.png'), fullPage: true })
  assert.deepEqual(errors, [])
  console.log('Knowledge filters and management browser E2E: PASS')
} finally {
  await browser.close()
}
