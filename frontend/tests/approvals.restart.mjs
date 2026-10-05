import { randomBytes } from 'node:crypto'
import { spawnSync } from 'node:child_process'

const owner = `phase7_browser_probe_${randomBytes(5).toString('hex')}`
const password = randomBytes(24).toString('hex')
let fixture

// 运行项目容器命令，所有一次性身份数据都经标准输入传递。
function docker(args, payload) {
  const result = spawnSync('docker', ['compose', ...args], {
    cwd: new URL('../..', import.meta.url), input: payload === undefined ? undefined : JSON.stringify(payload),
    encoding: 'utf8', timeout: 120_000,
  })
  if (result.status !== 0) throw new Error(`compose command failed: ${result.stderr}`)
  return result.stdout.trim()
}
function helper(module, payload) { return docker(['exec', '-T', 'api', 'uv', 'run', 'python', '-m', module], payload) }

helper('app.verify_browser_identity', { action: 'create', username: owner, password, role: 'operator' })
try {
  fixture = JSON.parse(helper('app.verify_hitl_fixture', { action: 'create', owner }))
  docker(['restart', 'worker'])
  docker(['restart', 'redis'])
  docker(['up', '-d', 'api', 'worker'])
  const result = helper('app.verify_hitl_fixture', { action: 'check', owner, ...fixture })
  if (!result.includes('PASS')) throw new Error('restart persistence check failed')
  console.log('Pending HITL state survives Worker and Redis restart: PASS')
} finally {
  if (fixture) helper('app.verify_hitl_fixture', { action: 'cleanup', owner, ...fixture })
  helper('app.verify_browser_identity', { action: 'cleanup', username: owner })
}
