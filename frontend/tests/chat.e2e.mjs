import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const origin = process.env.CHAT_E2E_ORIGIN || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'chrome' })

try {
  const page = await browser.newPage()
  const task = { id: 'chat-e2e', owner: 'tester', prompt: '查询知识库', agent: 'coordinator', status: 'running', createdAt: '2026-09-30T00:00:00Z', result: null }
  let taskReads = 0
  let eventReads = 0

  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (!path.startsWith('/api/')) return route.continue()
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/auth/refresh') return json({ access_token: 'e2e-token', user: { username: 'tester', role: 'operator' } })
    if (path === '/api/runtime/gateway') return json({ status: 'online', checkedAt: '2026-10-01T10:00:00Z', latencyMs: 12 })
    if (path === '/api/agents') return json([{ id: 'coordinator', name: 'Coordinator' }])
    if (path === '/api/tasks') return json([task])
    if (path === '/api/tasks/chat-e2e') return json({ ...task, status: taskReads++ ? 'completed' : 'running', result: '检索完成', model: 'test/model', tokenUsage: 128 })
    if (path === '/api/tasks/chat-e2e/events') {
      return json(eventReads++ ? [
        { id: '1-0', kind: 'tool', phase: 'start', name: 'knowledge_search', callId: 'call-1', at: 1, query: '查询知识库' },
        { id: '2-0', kind: 'tool', phase: 'result', name: 'knowledge_search', callId: 'call-1', at: 2, resultCount: 2, resultSummary: '检索到 2 条来源' }
      ] : [])
    }
    if (path === '/api/tasks/chat-e2e/ws-ticket') return json({ ticket: 'e2e-ticket' })
    return json({ detail: 'unexpected API request' }, 500)
  })

  // Simulate a terminal snapshot whose trailing tool events are lost with an abnormal WebSocket close.
  await page.addInitScript(snapshot => {
    window.WebSocket = class {
      constructor() {
        setTimeout(() => {
          this.onopen?.()
          this.onmessage?.({ data: JSON.stringify({ type: 'snapshot', task: snapshot }) })
          this.onclose?.({ wasClean: false })
        }, 0)
      }
      close() {}
    }
  }, { ...task, status: 'completed', result: '检索完成', model: 'test/model', tokenUsage: 128 })

  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  page.on('requestfailed', request => errors.push(`${request.url()}: ${request.failure()?.errorText}`))
  const navigation = await page.goto(`${origin}/chat?task=chat-e2e`)
  try { await page.getByText('检索完成').waitFor({ timeout: 8000 }) }
  catch (error) {
    console.error('Chat page:', navigation?.status(), (await page.content()).slice(0, 1000), { taskReads, eventReads, errors })
    throw error
  }
  await page.locator('.tool-card summary').click()
  await page.locator('.tool-card').getByText('检索到 2 条来源').waitFor()
  await page.getByText('回放完成').waitFor()
  assert.equal(await page.locator('.trace-meta dd').nth(2).textContent(), 'test/model')
  assert.equal(await page.locator('.trace-meta dd').nth(3).textContent(), '128')
  assert.equal(await page.locator('.trace-events li').filter({ hasText: 'knowledge_search' }).count(), 1)
  if (process.env.CHAT_E2E_SCREENSHOT) await page.screenshot({ path: join(tmpdir(), 'openclaw-chat-phase3.png'), fullPage: true })
  assert.ok(taskReads >= 2, 'abnormal close must refresh the task snapshot')
  assert.ok(eventReads >= 2, 'abnormal close must replay trailing events')
  await page.reload()
  await page.getByText('检索完成').waitFor()
  await page.locator('.tool-card summary').click()
  await page.locator('.tool-card').getByText('检索到 2 条来源').waitFor()
  assert.deepEqual(errors, [])
  console.log('Chat terminal replay E2E: PASS')
} finally {
  await browser.close()
}
