import type { ChatTask, TaskEvent, ToolCall } from '../types/chat'

export const terminalStatuses = new Set(['completed', 'failed', 'cancelled', 'timed_out'])
export function isTerminal(task: ChatTask | null) { return !!task && terminalStatuses.has(task.status) }

export function compareEventIds(a: string, b: string): number {
  const [at, sequence] = a.split('-').map(BigInt)
  const [bt, other] = b.split('-').map(BigInt)
  return at === bt ? (sequence < other ? -1 : sequence > other ? 1 : 0) : at < bt ? -1 : 1
}

export function assistantText(task: ChatTask | null, events: TaskEvent[]): string {
  if (task?.status === 'completed' && task.result != null) return task.result
  // Worker assistant events contain cumulative text, not deltas.
  return [...events].reverse().find(event => event.kind === 'assistant' && typeof event.text === 'string')?.text || ''
}

export function toolCalls(events: TaskEvent[], terminal: boolean): ToolCall[] {
  const calls: ToolCall[] = []
  for (const event of events) {
    if (event.kind !== 'tool') continue
    const name = event.name || 'Tool'
    let call = event.callId ? calls.find(item => item.id === event.callId) :
      [...calls].reverse().find(item => item.name === name && item.status === 'running')
    if (!call || (event.phase === 'start' && !event.callId)) {
      call = { id: event.callId || event.id, name, status: 'running', startedAt: event.at }
      calls.push(call)
    }
    // Only consume the server's allowlisted metadata. Never render raw args/output.
    if (typeof event.query === 'string') call.query = event.query
    if (typeof event.resultCount === 'number') call.resultCount = event.resultCount
    if (typeof event.resultSummary === 'string') call.summary = event.resultSummary
    if (event.isError || ['error', 'failed'].includes(event.phase || '')) call.status = 'failed'
    else if (['result', 'end', 'completed'].includes(event.phase || '')) call.status = 'success'
    if (typeof event.durationMs === 'number' && event.durationMs >= 0) call.durationMs = event.durationMs
    else if (call.status !== 'running' && call.startedAt != null && event.at != null)
      call.durationMs = Math.max(0, Math.round((event.at - call.startedAt) * 1000))
  }
  if (terminal) for (const call of calls) if (call.status === 'running') call.status = 'interrupted'
  return calls
}

export function executionStage(task: ChatTask | null, events: TaskEvent[]): string {
  if (!task) return '等待提问'
  const terminal: Record<string, string> = { completed: 'Completed · 已完成', failed: '执行失败', cancelled: '已取消', timed_out: '执行超时' }
  if (terminal[task.status]) return terminal[task.status]
  const latest = events[events.length - 1]
  if (latest?.kind === 'tool') {
    if (latest.isError || ['error', 'failed'].includes(latest.phase || '')) return 'Tool Failed · 工具失败'
    if (['result', 'end', 'completed'].includes(latest.phase || '')) return 'Tool Success · 工具完成'
    return latest.phase === 'start' ? 'Calling Tool · 调用工具' : 'Tool Running · 工具执行中'
  }
  if (latest?.kind === 'database_stage') return ({
    plan: '正在规划查询', plan_retry: '正在重新规划查询', validate: '正在校验查询',
    analyze: '正在分析查询结果', answer: '正在生成分析结论',
  } as Record<string, string>)[latest.phase || ''] || '正在分析数据'
  if (latest?.kind === 'accepted') return 'Gateway 已接收任务'
  if (latest?.kind === 'lifecycle' && latest.phase === 'finishing') return '正在整理结果'
  if (latest?.kind === 'lifecycle' && latest.phase === 'model') return '模型处理中'
  if (latest?.kind === 'assistant') return '正在生成回复'
  return task.status === 'queued' ? '等待执行' : 'Thinking · 思考中'
}

export interface TraceStep {
  id: string
  label: string
  detail?: string
  at?: number
  tone?: 'success' | 'failed'
}

const statusLabels: Record<string, string> = {
  queued: '任务排队', running: 'Worker 开始执行', completed: '任务完成',
  failed: '任务失败', cancelled: '任务已取消', timed_out: '任务超时',
}
const databaseLabels: Record<string, string> = {
  plan: '规划只读查询', plan_retry: '重新规划只读查询', validate: '校验查询安全性',
  analyze: '分析查询结果', answer: '生成分析结论',
}

// 把持久化事件整理为可回放的执行步骤，合并 Tool 起止和重复状态事件。
export function agentTraceSteps(task: ChatTask | null, events: TaskEvent[]): TraceStep[] {
  if (!task) return []
  const createdAt = Date.parse(task.createdAt)
  const steps: TraceStep[] = [{ id: 'request', label: '用户提交任务', at: Number.isNaN(createdAt) ? undefined : createdAt / 1000 }]
  const seenStatuses = new Set<string>()
  const tools = new Map<string, TraceStep>()
  let responseShown = false
  for (const event of events) {
    if (event.kind === 'status') {
      const status = event.status || ''
      if (!statusLabels[status] || seenStatuses.has(status)) continue
      seenStatuses.add(status)
      steps.push({ id: event.id, label: statusLabels[status], at: event.at,
        tone: status === 'completed' ? 'success' : ['failed', 'cancelled', 'timed_out'].includes(status) ? 'failed' : undefined })
    } else if (event.kind === 'accepted') {
      steps.push({ id: event.id, label: 'Gateway 已接受任务', at: event.at })
    } else if (event.kind === 'lifecycle' && event.phase === 'start') {
      steps.push({ id: event.id, label: 'Agent 开始执行', at: event.at })
    } else if (event.kind === 'database_stage') {
      const label = databaseLabels[event.phase || '']
      if (label) steps.push({ id: event.id, label, at: event.at,
        detail: event.phase === 'analyze' && typeof event.rowCount === 'number' ? `查询返回 ${event.rowCount} 行` : undefined })
    } else if (event.kind === 'tool') {
      const name = event.name || 'Tool'
      const key = event.callId || `${name}:${event.phase === 'start' ? event.id : ''}`
      let step = event.callId ? tools.get(key) : event.phase === 'start' ? undefined :
        [...tools.values()].reverse().find(item => item.label === `调用 Tool · ${name}` && item.detail === '执行中')
      if (!step) {
        step = { id: event.id, label: `调用 Tool · ${name}`, at: event.at, detail: '执行中' }
        tools.set(key, step)
        steps.push(step)
      }
      if (event.isError || ['error', 'failed'].includes(event.phase || '')) {
        step.detail = '执行失败'; step.tone = 'failed'
      } else if (['result', 'end', 'completed'].includes(event.phase || '')) {
        const duration = typeof event.durationMs === 'number' && event.durationMs >= 0 ? ` · ${event.durationMs} ms` : ''
        const summary = event.resultSummary || (typeof event.resultCount === 'number' ? `检索到 ${event.resultCount} 条来源` : '执行完成')
        step.detail = `${summary}${duration}`; step.tone = 'success'
      }
    } else if (event.kind === 'assistant' && !responseShown) {
      steps.push({ id: event.id, label: 'Agent 生成回复', at: event.at })
      responseShown = true
    }
  }
  if (terminalStatuses.has(task.status) && !seenStatuses.has(task.status)) {
    const finishedAt = task.finishedAt ? Date.parse(task.finishedAt) : NaN
    steps.push({ id: 'terminal', label: statusLabels[task.status], at: Number.isNaN(finishedAt) ? undefined : finishedAt / 1000,
      tone: task.status === 'completed' ? 'success' : 'failed' })
  }
  if (terminalStatuses.has(task.status)) for (const step of tools.values()) {
    if (step.detail === '执行中') step.detail = '未收到执行结果'
  }
  return steps
}
