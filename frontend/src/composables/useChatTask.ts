import { ref } from 'vue'
import axios from 'axios'
import { http } from '../api/http'
import type { ChatTask, TaskEvent } from '../types/chat'
import { compareEventIds, isTerminal } from '../utils/chat'

export function useChatTask() {
  const task = ref<ChatTask | null>(null)
  const events = ref<TaskEvent[]>([])
  const loading = ref(false)
  const error = ref('')
  const connection = ref<'idle' | 'connecting' | 'live' | 'reconnecting' | 'offline' | 'finished'>('idle')
  const cancelling = ref(false)
  let generation = 0
  let selectedId = ''
  let cursor = '0-0'
  let retries = 0
  let socket: WebSocket | undefined
  let controller: AbortController | undefined
  let timer: ReturnType<typeof setTimeout> | undefined
  const seen = new Set<string>()

  function closeSocket() {
    if (!socket) return
    socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null
    socket.close()
    socket = undefined
  }
  function stop() {
    generation++
    controller?.abort()
    if (timer) clearTimeout(timer)
    timer = undefined
    closeSocket()
  }
  function append(batch: TaskEvent[]) {
    for (const event of batch) {
      if (!/^\d+-\d+$/.test(event.id) || seen.has(event.id)) continue
      seen.add(event.id)
      events.value.push(event)
      if (compareEventIds(event.id, cursor) > 0) cursor = event.id
    }
    events.value.sort((a, b) => compareEventIds(a.id, b.id))
  }
  function schedule(version: number) {
    if (version !== generation) return
    closeSocket()
    if (retries >= 3) {
      connection.value = 'offline'
      error.value = '实时连接不可用，任务仍在后台执行。请重试连接以查看结果。'
      return
    }
    connection.value = 'reconnecting'
    retries++
    error.value = `连接中断，正在重连（${retries}/3）`
    // Bounded network reconnect backoff; never enqueue/re-execute the task.
    timer = setTimeout(() => { timer = undefined; void recover(version) }, 500 * 2 ** (retries - 1))
  }
  async function recover(version: number) {
    const signal = controller!.signal
    try {
      const snapshot = (await http.get<ChatTask>(`/tasks/${selectedId}`, { signal })).data
      if (version !== generation) return
      task.value = snapshot
      for (let page = 0; page < 20; page++) {
        const batch = (await http.get<TaskEvent[]>(`/tasks/${selectedId}/events`, { params: { after: cursor, limit: 200 }, signal })).data
        if (version !== generation) return
        const previous = cursor
        append(batch)
        if (batch.length < 200 || previous === cursor) break
      }
      if (isTerminal(task.value)) {
        connection.value = 'finished'; error.value = ''; cancelling.value = false
        return
      }
      const { ticket } = (await http.post<{ ticket: string }>(`/tasks/${selectedId}/ws-ticket`, {}, { signal })).data
      if (version !== generation) return
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      const active = new WebSocket(`${protocol}://${location.host}/ws/tasks/${selectedId}?ticket=${encodeURIComponent(ticket)}&after=${cursor}`)
      socket = active
      active.onopen = () => { if (version === generation) connection.value = 'live' }
      active.onmessage = event => {
        if (version !== generation) return
        try {
          const frame = JSON.parse(event.data)
          if (frame.type === 'snapshot' && frame.task?.id === selectedId) {
            task.value = frame.task as ChatTask
            retries = 0; error.value = ''
            if (isTerminal(task.value)) cancelling.value = false
            // Keep receiving: the server drains Tool/assistant events after a terminal snapshot.
          } else if (frame.type === 'event' && typeof frame.id === 'string' && frame.event?.kind) {
            append([{ ...frame.event, id: frame.id }])
          }
        } catch {
          error.value = '收到无法解析的事件，正在恢复连接'
          schedule(version)
        }
      }
      active.onerror = () => { if (version === generation) error.value = '实时连接异常' }
      active.onclose = event => {
        if (version !== generation) return
        // An abnormal close can happen after the terminal snapshot but before its last events arrive.
        if (isTerminal(task.value) && event.wasClean) { connection.value = 'finished'; error.value = ''; socket = undefined }
        else schedule(version)
      }
    } catch (failure) {
      if (version !== generation || axios.isCancel(failure)) return
      if (axios.isAxiosError(failure) && [401, 403, 404].includes(failure.response?.status || 0)) {
        connection.value = 'offline'
        error.value = '对话不存在或当前账号无权访问'
      } else schedule(version)
    } finally { if (version === generation) loading.value = false }
  }
  async function open(id: string) {
    stop()
    selectedId = id; cursor = '0-0'; retries = 0; seen.clear()
    task.value = null; events.value = []; error.value = ''; cancelling.value = false
    loading.value = !!id
    connection.value = id ? 'connecting' : 'idle'
    controller = new AbortController()
    if (id) await recover(generation)
  }
  async function reconnect() {
    if (!selectedId) return
    stop(); controller = new AbortController(); retries = 0
    connection.value = 'connecting'; loading.value = true; error.value = ''
    await recover(generation)
  }
  async function cancel() {
    if (!task.value || isTerminal(task.value) || cancelling.value) return
    const version = generation
    cancelling.value = true
    try { await http.post(`/tasks/${task.value.id}/cancel`) }
    catch {
      if (version === generation) { cancelling.value = false; error.value = '取消请求失败，请重试' }
    }
  }
  return { task, events, loading, error, connection, cancelling, open, reconnect, cancel, dispose: stop }
}
