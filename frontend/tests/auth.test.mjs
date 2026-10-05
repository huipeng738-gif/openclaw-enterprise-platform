import assert from 'node:assert/strict'
import { test } from 'node:test'
import axios from 'axios'
import { createPinia } from 'pinia'
import { pinia, useAuthStore } from '../src/stores/auth.ts'
import { http } from '../src/api/http.ts'

const user = { username: 'alice', role: 'operator' }
function response(config, data, status = 200) { return { config, data, status, statusText: '', headers: {} } }
function unauthorized(config) {
  return new axios.AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, null, response(config, {}, 401))
}
function deferred() { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

test('initialize shares refresh, restores identity, and preserves state on network errors', async () => {
  const auth = useAuthStore(createPinia())
  let count = 0
  http.defaults.adapter = async config => { count++; return response(config, { access_token: 'initial', user }) }
  await Promise.all([auth.initialize(), auth.initialize()])
  assert.equal(count, 1)
  assert.equal(auth.authInitialized, true)
  assert.equal(auth.user.username, 'alice')
  http.defaults.adapter = async config => { throw new axios.AxiosError('Offline', 'ERR_NETWORK', config) }
  await assert.rejects(auth.refresh())
  assert.equal(auth.accessToken, 'initial')
  const offline = useAuthStore(createPinia())
  await offline.initialize()
  assert.equal(offline.authInitialized, false)
  assert.ok(offline.initializationError)
})

test('parallel 401s share a refresh and retry with the new token', async () => {
  const auth = useAuthStore(pinia)
  auth.accessToken = 'old'
  const gate = deferred()
  let refreshes = 0
  let retries = 0
  http.defaults.adapter = async config => {
    if (config.url === '/auth/refresh') {
      refreshes++
      await gate.promise
      return response(config, { access_token: 'new', user })
    }
    if (config.headers.Authorization === 'Bearer old') throw unauthorized(config)
    assert.equal(config.headers.Authorization, 'Bearer new')
    assert.equal(config._retry, true)
    retries++
    return response(config, { ok: true })
  }
  const requests = Promise.all([http.get('/tasks'), http.get('/agents'), http.get('/audit')])
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(refreshes, 1)
  gate.resolve()
  await requests
  assert.equal(retries, 3)
})

test('failed refresh redirects once per request without recursive refresh', async () => {
  const auth = useAuthStore(pinia)
  auth.accessToken = 'old'
  let refreshes = 0
  let redirects = 0
  globalThis.location = { pathname: '/tasks', assign() { redirects++ } }
  http.defaults.adapter = async config => { if (config.url === '/auth/refresh') refreshes++; throw unauthorized(config) }
  await assert.rejects(http.get('/tasks'))
  assert.equal(refreshes, 1)
  assert.equal(auth.authenticated, false)
  assert.equal(redirects, 1)
  await assert.rejects(http.post('/auth/login'))
  assert.equal(refreshes, 1)
})

test('logout invalidates in-flight refresh and revokes session afterwards', async () => {
  const auth = useAuthStore(pinia)
  auth.accessToken = 'old'
  const gate = deferred()
  const calls = []
  http.defaults.adapter = async config => {
    calls.push(config.url)
    if (config.url === '/auth/refresh') { await gate.promise; return response(config, { access_token: 'new', user }) }
    return response(config, { status: 'ok' })
  }
  const refresh = auth.refresh()
  const rejected = assert.rejects(refresh)
  const logout = auth.logout()
  gate.resolve()
  await Promise.all([rejected, logout])
  assert.equal(auth.authenticated, false)
  assert.deepEqual(calls, ['/auth/refresh', '/auth/logout'])
})

test('retry is bounded and permission failures never refresh', async () => {
  const auth = useAuthStore(pinia)
  auth.accessToken = 'old'
  let refreshes = 0
  let business = 0
  http.defaults.adapter = async config => {
    if (config.url === '/auth/refresh') { refreshes++; return response(config, { access_token: 'new', user }) }
    business++
    throw unauthorized(config)
  }
  await assert.rejects(http.get('/tasks'))
  assert.equal(refreshes, 1)
  assert.equal(business, 2)
  http.defaults.adapter = async config => {
    throw new axios.AxiosError('Forbidden', 'ERR_BAD_REQUEST', config, null, response(config, {}, 403))
  }
  await assert.rejects(http.get('/audit'))
  assert.equal(refreshes, 1)
})

test('failed logout remains retryable until server revocation succeeds', async () => {
  const auth = useAuthStore(pinia)
  auth.accessToken = 'old'
  http.defaults.adapter = async config => { throw new axios.AxiosError('Offline', 'ERR_NETWORK', config) }
  await assert.rejects(auth.logout())
  assert.equal(auth.authenticated, false)
  assert.ok(auth.logoutError)
  http.defaults.adapter = async config => response(config, { status: 'ok' })
  await auth.logout()
  assert.equal(auth.logoutError, '')
})
