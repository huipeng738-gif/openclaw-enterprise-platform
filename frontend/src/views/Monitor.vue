<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { http } from '../api/http'
import PageHeader from '../components/common/PageHeader.vue'
import StatusTag from '../components/common/StatusTag.vue'
import LoadingState from '../components/common/LoadingState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'

interface Task {
  id: string; owner: string; prompt: string; agent: string; status: string; createdAt: string
  traceId?: string | null; threadId?: string | null; model?: string | null
  latencyMs?: number | null; tokenUsage?: number | null; error?: string | null
}
interface TaskEvent {
  id: string; kind: string; at?: number; name?: string; phase?: string; status?: string
  callId?: string; durationMs?: number; resultSummary?: string; resultCount?: number
  rowCount?: number; isError?: boolean; error?: string
}
interface TimelineEvent extends TaskEvent { displayDurationMs?: number }

const route = useRoute()
const router = useRouter()
const tasks = ref<Task[]>([])
const selected = ref<Task | null>(null)
const selectedId = ref('')
const events = ref<TaskEvent[]>([])
const search = ref('')
const statusFilter = ref('')
const agentFilter = ref('')
const listError = ref('')
const detailError = ref('')
const loading = ref(false)
const detailLoading = ref(false)
const eventsLoading = ref(false)
const hasMoreEvents = ref(false)
const refreshing = ref(false)
const terminal = new Set(['completed', 'failed', 'cancelled', 'timed_out'])
const statuses = ['queued', 'running', 'completed', 'failed', 'cancelled', 'timed_out']
let timer: number | undefined
let detailVersion = 0
let disposed = false

// 只统计最近一百条真实任务，并提供状态、Agent 和任务/Trace ID 检索。
const agents = computed(() => [...new Set(tasks.value.map(task => task.agent))].sort())
const visibleTasks = computed(() => tasks.value.filter(task => {
  const keyword = search.value.trim().toLowerCase()
  return (!keyword || `${task.id} ${task.traceId || ''} ${task.prompt} ${task.owner}`.toLowerCase().includes(keyword)) &&
    (!statusFilter.value || task.status === statusFilter.value) &&
    (!agentFilter.value || task.agent === agentFilter.value)
}))
const runningCount = computed(() => tasks.value.filter(task => task.status === 'running' || task.status === 'queued').length)
const failedCount = computed(() => tasks.value.filter(task => task.status === 'failed' || task.status === 'timed_out').length)

// 按真实 Tool 起止事件补算历史调用耗时，保留原始事件顺序与新版本记录的耗时。
const timelineEvents = computed<TimelineEvent[]>(() => {
  const starts = new Map<string, number>()
  return events.value.map(event => {
    if (event.kind !== 'tool') return event
    const key = event.callId || event.name || ''
    if (event.phase === 'start' && key && event.at != null) starts.set(key, event.at)
    let duration = event.durationMs
    if (['result', 'end', 'completed', 'error', 'failed'].includes(event.phase || '') && key) {
      const started = starts.get(key)
      if (duration == null && started != null && event.at != null && event.at >= started)
        duration = Math.round((event.at - started) * 1000)
      starts.delete(key)
    }
    return { ...event, displayDurationMs: duration }
  })
})

// 将任务和 Redis 事件时间统一显示到秒，未知时间保持 N/A。
function timeText(value?: string | number | null) {
  if (value == null) return 'N/A'
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value)
  return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleString('sv-SE', { hour12: false })
}

// 将真实事件类型转换为便于排障的中文标题，不推断不存在的阶段。
function eventTitle(event: TaskEvent) {
  const labels: Record<string, string> = {
    status: '任务状态', accepted: 'Gateway 接收', lifecycle: 'Agent 阶段',
    tool: 'Tool 调用', database_stage: '数据库分析', assistant: 'Agent 消息'
  }
  return labels[event.kind] || event.kind
}

// 用事件自身的类型、阶段与安全元数据说明实际执行动作，不推断工具参数或返回内容。
function eventDescription(event: TimelineEvent) {
  if (event.kind === 'status') return ({
    queued: '任务已进入 Redis 队列，等待 Worker 领取。',
    running: 'Worker 已领取任务，开始执行。', completed: '任务已完成，执行结果已保存。',
    failed: '任务执行失败，请结合上方错误信息排查。',
    cancelled: '任务已取消。', timed_out: '任务执行超时。'
  } as Record<string, string>)[event.status || ''] || `任务状态变更为 ${event.status || '未知'}。`
  if (event.kind === 'accepted') return 'OpenClaw Gateway 已接受执行请求。'
  if (event.kind === 'lifecycle') return ({
    start: 'Agent 开始执行。', model: 'Agent 进入模型处理阶段。',
    finishing: 'Agent 正在整理本轮结果。', end: 'Agent 本轮执行结束。',
    error: 'Agent 执行阶段报告错误。'
  } as Record<string, string>)[event.phase || ''] || `Agent 阶段：${event.phase || '未知'}。`
  if (event.kind === 'database_stage') return ({
    plan: '数据库 Agent 正在生成只读查询计划。',
    plan_retry: '此前计划未通过校验，正在重新生成。',
    validate: '正在校验 SQL 的表列权限及安全规则。',
    analyze: `只读 SQL 已执行，返回${event.rowCount == null ? '记录' : ` ${event.rowCount} 行记录`}，正在分析结果。`,
    answer: '数据库 Agent 正根据查询结果生成回答。'
  } as Record<string, string>)[event.phase || ''] || `数据库分析阶段：${event.phase || '未知'}。`
  if (event.kind === 'tool') {
    const actions: Record<string, string> = {
      knowledge_search: '检索知识库', order_query: '查询订单信息', customer_query: '查询客户信息',
      metrics_query: '查询业务指标', task_create: '创建催办任务', task_cancel_request: '提交任务取消审批'
    }
    const action = actions[event.name || ''] || `调用 ${event.name || '未知工具'}`
    if (event.phase === 'start') return `${action}：已发起调用。`
    if (event.phase === 'update') return `${action}：正在执行。`
    if (event.isError || ['error', 'failed'].includes(event.phase || '')) return `${action}：工具报告执行失败。`
    if (['result', 'end', 'completed'].includes(event.phase || '')) {
      if (event.name === 'knowledge_search')
        return `知识库检索已返回${event.resultCount == null ? '结果' : ` ${event.resultCount} 条来源`}，供 Agent 生成回答。`
      if (event.name === 'order_query' || event.name === 'customer_query' || event.name === 'metrics_query')
        return `${action}已返回结果，供 Agent 分析。`
      return `${action}：工具已返回结果。`
    }
    return `${action}：阶段 ${event.phase || '未知'}。`
  }
  if (event.kind === 'assistant') return 'Agent 已生成回复；监控页不展示对话内容。'
  return `收到 ${event.kind} 事件。`
}

// 读取管理员可见的最近一百条任务，保持后端归属与权限边界。
async function loadTasks() {
  loading.value = true
  listError.value = ''
  try {
    const rows = (await http.get<Task[]>('/tasks')).data
    if (!disposed) tasks.value = rows
  } catch { if (!disposed) listError.value = '加载监控任务失败，请重试' }
  finally { if (!disposed) loading.value = false }
}

// 分页读取最多两百条原始事件，保留 Redis Stream 的先后顺序。
async function loadMoreEvents() {
  if (!selectedId.value || eventsLoading.value) return
  const version = detailVersion
  eventsLoading.value = true
  try {
    const after = events.value[events.value.length - 1]?.id || '0-0'
    const rows = (await http.get<TaskEvent[]>(`/tasks/${selectedId.value}/events`, { params: { after, limit: 200 } })).data
    if (version !== detailVersion) return
    events.value.push(...rows)
    hasMoreEvents.value = rows.length === 200
  } catch { if (version === detailVersion) detailError.value = '读取执行事件失败，请重试' }
  finally { if (version === detailVersion) eventsLoading.value = false }
}

// 打开指定任务详情与首批事件，并同步可分享的监控页地址。
async function openTask(taskId: string) {
  const version = ++detailVersion
  selectedId.value = taskId
  selected.value = null
  events.value = []
  hasMoreEvents.value = false
  detailError.value = ''
  detailLoading.value = true
  void router.replace({ path: '/monitor', query: { taskId } })
  try {
    const task = (await http.get<Task>(`/tasks/${taskId}`)).data
    if (version !== detailVersion) return
    selected.value = task
    await loadMoreEvents()
  } catch { if (version === detailVersion) detailError.value = '读取任务详情失败，请重试' }
  finally { if (version === detailVersion) detailLoading.value = false }
}

// 每十五秒更新任务；选中任务仍在执行时同步拉取新增事件。
async function refresh() {
  if (refreshing.value || disposed) return
  refreshing.value = true
  try {
    await loadTasks()
    if (!disposed && selectedId.value && selected.value && !terminal.has(selected.value.status)) {
      const version = detailVersion
      try {
        const task = (await http.get<Task>(`/tasks/${selectedId.value}`)).data
        if (version === detailVersion) { selected.value = task; await loadMoreEvents() }
      } catch { if (version === detailVersion) detailError.value = '刷新任务轨迹失败，请重试' }
    }
  } finally { refreshing.value = false }
}

// 初次加载列表后处理总览带来的任务定位，再启动有限频率轮询。
async function initialize() {
  await loadTasks()
  if (disposed) return
  const taskId = route.query.taskId
  if (typeof taskId === 'string' && taskId) await openTask(taskId)
}

onMounted(() => {
  void initialize().then(() => {
    if (!disposed) timer = window.setInterval(() => { void refresh() }, 15000)
  })
})
onUnmounted(() => { disposed = true; if (timer != null) window.clearInterval(timer); detailVersion++ })
</script>

<template>
  <div class="monitor-page">
    <PageHeader title="运行监控" description="检索真实任务并按事件顺序排查 Agent 与 Tool 执行过程；每 15 秒刷新运行中任务。">
      <template #actions><el-button :loading="refreshing" @click="refresh">立即刷新</el-button></template>
    </PageHeader>
    <div class="monitor-summary">
      <div><span>最近任务</span><strong>{{ tasks.length }}</strong></div>
      <div><span>排队 / 运行</span><strong>{{ runningCount }}</strong></div>
      <div><span>失败 / 超时</span><strong>{{ failedCount }}</strong></div>
      <p>统计范围：管理员可见的最近 100 条任务。完整成功率与趋势请查看总览。</p>
    </div>
    <div class="monitor-layout">
      <section class="card monitor-list">
        <div class="monitor-heading"><h2>任务检索</h2><span>{{ visibleTasks.length }} 条匹配</span></div>
        <div class="monitor-filters">
          <el-input v-model="search" clearable placeholder="任务内容、任务 ID、Trace ID 或用户" aria-label="搜索监控任务" />
          <el-select v-model="statusFilter" aria-label="监控任务状态" placeholder="全部状态"><el-option label="全部状态" value="" /><el-option v-for="status in statuses" :key="status" :label="status" :value="status" /></el-select>
          <el-select v-model="agentFilter" aria-label="监控 Agent" placeholder="全部 Agent"><el-option label="全部 Agent" value="" /><el-option v-for="agent in agents" :key="agent" :label="agent" :value="agent" /></el-select>
        </div>
        <LoadingState v-if="loading && !tasks.length" title="正在加载任务…" />
        <ErrorState v-else-if="listError" :message="listError" @retry="loadTasks" />
        <EmptyState v-else-if="!visibleTasks.length" title="暂无匹配任务" description="调整筛选条件后重试。" />
        <div v-else class="monitor-task-list" v-loading="loading">
          <button v-for="task in visibleTasks" :key="task.id" type="button" class="monitor-task" :class="{ active: selectedId === task.id }" :aria-label="`查看任务 ${task.id}`" @click="openTask(task.id)">
            <span class="monitor-task-main"><strong>{{ task.prompt }}</strong><StatusTag :status="task.status" /></span>
            <span class="monitor-task-meta">{{ task.agent }} · {{ task.owner }} · {{ timeText(task.createdAt) }}</span>
            <span class="monitor-task-id">{{ task.id }}</span>
          </button>
        </div>
      </section>
      <section class="card monitor-trace">
        <div class="monitor-heading"><h2>执行轨迹</h2><span v-if="selected">{{ events.length }} 条事件</span></div>
        <EmptyState v-if="!selectedId" title="选择任务查看 Trace" description="从左侧任务列表选择，或从总览失败任务直接跳转。" />
        <LoadingState v-else-if="detailLoading" title="正在读取执行轨迹…" />
        <ErrorState v-else-if="detailError" :message="detailError" @retry="openTask(selectedId)" />
        <template v-else-if="selected">
          <div class="monitor-trace-head"><StatusTag :status="selected.status" /><span>{{ selected.agent }}</span><span>{{ selected.latencyMs == null ? '耗时未采集' : `耗时 ${selected.latencyMs}ms` }}</span></div>
          <dl class="monitor-details">
            <dt>任务 ID</dt><dd>{{ selected.id }}</dd><dt>Trace ID</dt><dd>{{ selected.traceId || '未采集' }}<small v-if="selected.traceId && selected.traceId === selected.id" class="monitor-legacy-trace">历史任务沿用 Task ID</small></dd>
            <dt>用户</dt><dd>{{ selected.owner }}</dd><dt>Thread ID</dt><dd>{{ selected.threadId || '未采集' }}</dd>
            <dt>模型</dt><dd>{{ selected.model || '未采集' }}</dd><dt>Token 用量</dt><dd>{{ selected.tokenUsage ?? '未采集' }}</dd>
            <dt>创建时间</dt><dd>{{ timeText(selected.createdAt) }}</dd>
          </dl>
          <div class="monitor-task-goal"><strong>任务目标</strong><p>{{ selected.prompt }}</p></div>
          <el-alert v-if="selected.error" type="error" :title="selected.error" show-icon class="monitor-error" />
          <h3>事件时间线</h3>
          <EmptyState v-if="!events.length" title="暂无执行事件" />
          <ol v-else class="monitor-timeline">
            <li v-for="event in timelineEvents" :key="event.id" :class="{ failed: event.isError || event.phase === 'failed' || event.phase === 'error' || event.status === 'failed' || event.status === 'timed_out' }">
              <span class="monitor-event-time">{{ timeText(event.at) }}</span>
              <div><strong>{{ eventTitle(event) }}</strong><span v-if="event.name || event.phase || event.status"> · {{ event.name || event.phase || event.status }}</span><p>{{ eventDescription(event) }}</p><small v-if="event.displayDurationMs != null">Tool 耗时 {{ event.displayDurationMs }}ms</small></div>
            </li>
          </ol>
          <el-button v-if="hasMoreEvents" :loading="eventsLoading" @click="loadMoreEvents">加载更多事件</el-button>
          <p class="monitor-note">按 Redis 事件顺序展示，每次最多加载 200 条；不展示原始 Tool 参数或输出。</p>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.monitor-summary { display: flex; flex-wrap: wrap; gap: 12px; align-items: stretch; margin-bottom: 16px; }
.monitor-summary > div { display: grid; gap: 5px; min-width: 130px; padding: 13px 18px; background: var(--oc-surface); border: 1px solid var(--oc-border); border-radius: var(--oc-radius); }
.monitor-summary span, .monitor-heading span, .monitor-summary p, .monitor-note { color: var(--oc-muted); font-size: 12px; }
.monitor-summary strong { font-size: 21px; }
.monitor-summary p { align-self: center; margin: 0 0 0 auto; }
.monitor-layout { display: grid; grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.4fr); gap: 16px; align-items: start; }
.monitor-layout .card { min-width: 0; }
.monitor-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.monitor-heading h2, .monitor-trace h3 { margin: 0; font-size: 17px; }
.monitor-filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-bottom: 16px; }
.monitor-filters .el-input { grid-column: 1 / -1; }
.monitor-task-list { display: grid; gap: 8px; max-height: 660px; overflow-y: auto; }
.monitor-task { width: 100%; min-width: 0; display: grid; gap: 7px; padding: 13px; text-align: left; border: 1px solid var(--oc-border); border-radius: 10px; background: var(--oc-surface); color: var(--oc-text); font: inherit; cursor: pointer; }
.monitor-task:hover, .monitor-task.active { border-color: var(--oc-primary); background: var(--oc-bg); }
.monitor-task:focus-visible { outline: 2px solid var(--oc-primary); outline-offset: 2px; }
.monitor-task-main { display: flex; justify-content: space-between; gap: 10px; align-items: start; }
.monitor-task-main strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
.monitor-task-meta, .monitor-task-id { color: var(--oc-muted); font-size: 12px; overflow-wrap: anywhere; }
.monitor-trace-head { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 18px; font-size: 13px; }
.monitor-details { display: grid; grid-template-columns: 88px minmax(0, 1fr); gap: 10px 12px; font-size: 13px; margin: 0 0 22px; }
.monitor-details dt { color: var(--oc-muted); }
.monitor-details dd { margin: 0; overflow-wrap: anywhere; }
.monitor-legacy-trace { display: block; color: var(--oc-muted); margin-top: 3px; }
.monitor-error { margin-bottom: 16px; }
.monitor-task-goal { border-top: 1px solid var(--oc-border); padding: 14px 0; margin-bottom: 12px; font-size: 13px; }
.monitor-task-goal p { margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.5; }
.monitor-timeline { list-style: none; padding: 0 0 0 11px; margin: 16px 0; border-left: 2px solid var(--oc-border); }
.monitor-timeline li { position: relative; display: grid; grid-template-columns: 160px minmax(0, 1fr); gap: 14px; padding: 0 0 20px 20px; font-size: 13px; }
.monitor-timeline li::before { content: ''; position: absolute; left: -7px; top: 4px; width: 11px; height: 11px; border-radius: 50%; background: var(--oc-primary); }
.monitor-timeline li.failed::before { background: var(--oc-danger); }
.monitor-event-time, .monitor-timeline li span, .monitor-timeline small { color: var(--oc-muted); }
.monitor-timeline p { margin: 5px 0; overflow-wrap: anywhere; }
.monitor-note { margin: 14px 0 0; }
@media (max-width: 1050px) { .monitor-layout { grid-template-columns: minmax(0, 1fr); } .monitor-summary p { width: 100%; margin: 0; } }
@media (max-width: 620px) { .monitor-filters { grid-template-columns: minmax(0, 1fr); } .monitor-timeline li { grid-template-columns: minmax(0, 1fr); gap: 3px; } }
</style>
