<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { http } from '../api/http'
import { role } from '../stores/auth'
import PageHeader from '../components/common/PageHeader.vue'
import StatusTag from '../components/common/StatusTag.vue'
import EmptyState from '../components/common/EmptyState.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'

interface Task { id: string; prompt: string; agent: string; status: string; createdAt: string; result?: string | null; error?: string | null; traceId?: string; threadId?: string | null; model?: string | null; tokenUsage?: number | null; latencyMs?: number | null }
interface TaskEvent { id: string; kind: string; at?: number; name?: string; phase?: string; status?: string; text?: string; resultSummary?: string; durationMs?: number; isError?: boolean }
interface Followup { id: string; title: string; reason: string; orderNo?: string | null; status: string; createdAt: string; sourceTaskId: string }
const prompt = ref('')
const tasks = ref<Task[]>([])
const followups = ref<Followup[]>([])
const selected = ref<Task | null>(null)
const events = ref<TaskEvent[]>([])
const listError = ref('')
const actionError = ref('')
const detailError = ref('')
const loading = ref(false)
const detailLoading = ref(false)
const drawer = ref(false)
const search = ref('')
const statusFilter = ref('')
const agentFilter = ref('')
const dateRange = ref<string[]>([])
const terminal = ['completed', 'failed', 'cancelled', 'timed_out']
const statuses = ['queued', 'running', 'completed', 'failed', 'cancelled', 'timed_out']
const agents = computed(() => [...new Set(tasks.value.map(task => task.agent))].sort())
const visibleTasks = computed(() => tasks.value.filter(task => {
  const term = search.value.trim().toLowerCase()
  if (term && !`${task.id} ${task.prompt}`.toLowerCase().includes(term)) return false
  if (statusFilter.value && task.status !== statusFilter.value) return false
  if (agentFilter.value && task.agent !== agentFilter.value) return false
  if (dateRange.value.length === 2) {
    const day = task.createdAt.slice(0, 10)
    if (day < dateRange.value[0] || day > dateRange.value[1]) return false
  }
  return true
}))
let ws: WebSocket | undefined
let watchVersion = 0

// 格式化后端时间，不推断尚未提供的任务完成时间或耗时。
function timeText(value?: string | null) { return value ? value.replace('T', ' ').slice(0, 16) : 'N/A' }

// 将 Redis 事件中的 Unix 时间转换为本地轨迹时间。
function eventTime(value?: number) { return value == null ? 'N/A' : new Date(value * 1000).toLocaleTimeString() }

// 读取当前用户可见的最近一百条任务，失败时保留明确错误状态。
async function load() {
  loading.value = true; listError.value = ''
  try {
    tasks.value = (await http.get<Task[]>('/tasks')).data
    if (role.value !== 'viewer') followups.value = (await http.get<Followup[]>('/followups')).data
  }
  catch { listError.value = '加载任务列表失败，请重试' }
  finally { loading.value = false }
}

// 读取任务详情与历史事件，并通过原有 WebSocket 接收实时更新。
async function openTask(task: Task) {
  const version = ++watchVersion
  ws?.close(); ws = undefined
  drawer.value = true; selected.value = task; events.value = []; detailError.value = ''; detailLoading.value = true
  try {
    const current = (await http.get<Task>(`/tasks/${task.id}`)).data
    const history = (await http.get<TaskEvent[]>(`/tasks/${task.id}/events`)).data
    if (version !== watchVersion) return
    selected.value = current; events.value = history
    if (terminal.includes(current.status)) return
    const ticket = (await http.post<{ ticket: string }>(`/tasks/${task.id}/ws-ticket`)).data.ticket
    if (version !== watchVersion) return
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`)
    ws = socket
    socket.onmessage = message => {
      if (version !== watchVersion) return
      const frame = JSON.parse(message.data)
      if (frame.type === 'snapshot') {
        selected.value = frame.task
        const index = tasks.value.findIndex(item => item.id === frame.task.id)
        if (index >= 0) tasks.value[index] = frame.task
      } else if (frame.type === 'event' && !events.value.some(item => item.id === frame.id)) {
        events.value.push({ id: frame.id, ...frame.event })
      }
    }
    socket.onclose = () => {
      if (version === watchVersion && !terminal.includes(selected.value?.status || ''))
        detailError.value = '实时连接中断，请重新打开任务详情'
      if (ws === socket) ws = undefined
    }
  } catch {
    if (version === watchVersion) detailError.value = '读取任务详情或事件失败，请重试'
  } finally { if (version === watchVersion) detailLoading.value = false }
}

// 关闭详情时释放 WebSocket，并忽略在途的旧请求和事件。
function closeTask() { watchVersion++; ws?.close(); ws = undefined }

// 创建真实后台任务并展示执行详情。
async function create() {
  if (!prompt.value.trim()) return
  actionError.value = ''
  try {
    const task = (await http.post<Task>('/tasks', { prompt: prompt.value.trim() })).data
    prompt.value = ''; tasks.value.unshift(task); await openTask(task)
  } catch { actionError.value = '创建任务失败，请重试' }
}

// 向后端提交取消标记，由 Worker 异步完成取消。
async function cancel(task: Task) {
  try { await http.post(`/tasks/${task.id}/cancel`); await load() }
  catch { actionError.value = '取消任务失败，请重试' }
}

// 为未成功的任务创建重试记录，不覆盖原任务。
async function retry(task: Task) {
  try {
    const newer = (await http.post<Task>(`/tasks/${task.id}/retry`)).data
    tasks.value.unshift(newer); await openTask(newer)
  } catch { actionError.value = '重试任务失败，请重试' }
}

onMounted(load)
onUnmounted(closeTask)
</script>

<template>
  <div class="tasks-page">
    <PageHeader title="任务中心" description="管理您发起的任务与执行记录" />
    <div v-if="role !== 'viewer'" class="card task-create">
      <el-input v-model="prompt" placeholder="输入真实 Agent 任务" aria-label="新任务内容" maxlength="4000" @keyup.enter="create" />
      <el-button type="primary" :disabled="!prompt.trim()" @click="create">创建任务</el-button>
    </div>
    <el-alert v-if="actionError" :title="actionError" type="error" show-icon class="task-action-error" />
    <div class="card tasks-card">
      <div class="tasks-filters">
        <el-input v-model="search" clearable placeholder="搜索任务内容或 ID…" aria-label="搜索任务" />
        <el-select v-model="statusFilter" aria-label="任务状态" placeholder="全部状态"><el-option label="全部状态" value="" /><el-option v-for="item in statuses" :key="item" :label="item" :value="item" /></el-select>
        <el-select v-model="agentFilter" aria-label="Agent 筛选" placeholder="全部 Agent"><el-option label="全部 Agent" value="" /><el-option v-for="item in agents" :key="item" :label="item" :value="item" /></el-select>
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始时间" end-placeholder="结束时间" aria-label="创建时间范围" />
        <el-button @click="load">刷新</el-button>
      </div>
      <LoadingState v-if="loading && !tasks.length" title="正在加载任务…" />
      <ErrorState v-else-if="listError" :message="listError" @retry="load" />
      <EmptyState v-else-if="!visibleTasks.length" title="暂无匹配任务" description="可调整筛选条件或创建任务" />
      <el-table v-else :data="visibleTasks" v-loading="loading" stripe>
        <el-table-column label="任务" min-width="230"><template #default="scope"><div class="task-name" :title="scope.row.prompt">{{ scope.row.prompt }}</div></template></el-table-column>
        <el-table-column prop="agent" label="Agent" min-width="130" />
        <el-table-column label="状态" width="125"><template #default="scope"><StatusTag :status="scope.row.status" /></template></el-table-column>
        <el-table-column label="耗时" width="90"><template #default="scope">{{ scope.row.latencyMs == null ? 'N/A' : `${scope.row.latencyMs}ms` }}</template></el-table-column>
        <el-table-column label="创建时间" min-width="150"><template #default="scope">{{ timeText(scope.row.createdAt) }}</template></el-table-column>
        <el-table-column label="操作" width="200"><template #default="scope"><el-button link type="primary" @click="openTask(scope.row)">查看</el-button><el-button v-if="role !== 'viewer' && ['queued', 'running'].includes(scope.row.status)" link @click="cancel(scope.row)">取消</el-button><el-button v-if="role !== 'viewer' && ['failed', 'cancelled', 'timed_out'].includes(scope.row.status)" link @click="retry(scope.row)">重试</el-button></template></el-table-column>
      </el-table>
      <p class="task-list-note">仅显示当前账号可见的最近 100 条任务；历史任务可能没有耗时记录。</p>
    </div>
    <div v-if="role !== 'viewer'" class="card tasks-card">
      <h2>Agent 创建的催办任务</h2>
      <EmptyState v-if="!followups.length" title="暂无催办任务" description="Agent 创建的后续工作会显示在这里" />
      <el-table v-else :data="followups" stripe>
        <el-table-column prop="title" label="任务" min-width="200" />
        <el-table-column prop="orderNo" label="订单" width="150" />
        <el-table-column prop="reason" label="原因" min-width="220" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="创建时间" width="160"><template #default="scope">{{ timeText(scope.row.createdAt) }}</template></el-table-column>
      </el-table>
    </div>
    <el-drawer v-model="drawer" title="任务详情" size="min(560px, 100vw)" @close="closeTask">
      <LoadingState v-if="detailLoading" title="正在加载任务详情…" />
      <ErrorState v-else-if="detailError" :message="detailError" @retry="selected && openTask(selected)" />
      <div v-else-if="selected" class="task-detail">
        <dl><dt>任务 ID</dt><dd>{{ selected.id }}</dd><dt>Trace ID</dt><dd>{{ selected.traceId || '未采集' }}<small v-if="selected.traceId && selected.traceId === selected.id">（历史任务沿用 Task ID）</small></dd><dt>Thread ID</dt><dd>{{ selected.threadId || '未采集' }}</dd><dt>Agent</dt><dd>{{ selected.agent }}</dd><dt>Model</dt><dd>{{ selected.model || '未采集' }}</dd><dt>状态</dt><dd><StatusTag :status="selected.status" /></dd><dt>耗时</dt><dd>{{ selected.latencyMs == null ? '未采集' : `${selected.latencyMs}ms` }}</dd><dt>Token 用量</dt><dd>{{ selected.tokenUsage ?? '未采集' }}</dd><dt>创建时间</dt><dd>{{ timeText(selected.createdAt) }}</dd></dl>
        <h3>任务内容</h3><p class="task-full-prompt">{{ selected.prompt }}</p>
        <el-alert v-if="selected.error" :title="selected.error" type="error" show-icon />
        <template v-if="selected.result"><h3>执行结果</h3><p class="task-result">{{ selected.result }}</p></template>
        <h3>Agent / Tool 执行轨迹</h3>
        <EmptyState v-if="!events.length" title="暂无执行事件" />
        <div v-for="event in events" :key="event.id" class="task-event"><strong>{{ event.kind }}</strong><span>{{ eventTime(event.at) }} · {{ event.name || event.phase || event.status || '' }}<template v-if="event.durationMs != null"> · {{ event.durationMs }}ms</template></span><p v-if="event.resultSummary">{{ event.resultSummary }}</p><p v-if="event.kind === 'assistant' && event.text">{{ event.text }}</p></div>
      </div>
    </el-drawer>
  </div>
</template>
