<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '../api/http'
import { role } from '../stores/auth'
import PageHeader from '../components/common/PageHeader.vue'
import StatCard from '../components/common/StatCard.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import StatusTag from '../components/common/StatusTag.vue'
import { useRouter } from 'vue-router'

interface TaskSummary { id: string; prompt: string; agent: string; status: string; createdAt: string; latencyMs?: number | null }
interface TrendPoint { date: string; count: number }
interface Observability {
  sampledTasks: number; taskSuccessRate: number | null; toolSuccessRate: number | null
  p50LatencyMs: number | null; p95LatencyMs: number | null; tokenUsage: number | null
  tokenSampledTasks?: number
  errorRate: number | null; topTools: { name: string; count: number }[]
}
interface GatewayStatus { status: 'online' | 'offline' | 'unknown'; checkedAt: string | null; latencyMs: number | null }
interface DashboardData {
  agentCount?: number; runningTasks?: number; completedTasks?: number; todayTasks?: number
  successRate?: number | null; taskTrend?: TrendPoint[]; recentTasks?: TaskSummary[]; failedTasks?: TaskSummary[]
  observability?: Observability
  gateway?: GatewayStatus
}
const data = ref<DashboardData>({})
const loading = ref(false)
const error = ref('')
const router = useRouter()
// 把 Gateway 检测时间转换为可读的本地年月日时分秒。
function gatewayTime(value?: string | null) { return value ? new Date(value).toLocaleString('sv-SE', { hour12: false }) : '暂无检测记录' }
// 从总览失败任务跳转到运行监控中的对应真实 Trace。
function inspectTask(taskId: string) { void router.push({ path: '/monitor', query: { taskId } }) }
// 读取当前用户可见的真实任务指标，后端未提供的观测值保留为未知。
async function load() {
  loading.value = true; error.value = ''
  try { data.value = (await http.get('/dashboard')).data }
  catch { error.value = '加载工作台失败' }
  finally { loading.value = false }
}
onMounted(load)
</script>
<template>
  <PageHeader title="工作台" description="企业 AI Agent 运营与管理平台 · 当前用户可见数据" />
  <LoadingState v-if="loading" />
  <ErrorState v-else-if="error" :message="error" @retry="load" />
  <div v-else class="grid">
    <StatCard label="Agents" :value="data.agentCount" />
    <StatCard label="运行任务" :value="data.runningTasks" />
    <StatCard label="今日任务" :value="data.todayTasks" />
    <StatCard label="成功率" :value="data.successRate == null ? null : `${data.successRate}%`" hint="已结束任务" />
    <StatCard label="P50 耗时" :value="data.observability?.p50LatencyMs == null ? null : `${data.observability.p50LatencyMs}ms`" hint="最近 100 条可见任务" />
  </div>
  <template v-if="!loading && !error">
    <div class="dashboard-panels">
      <section class="card"><h2>近七日任务趋势</h2><div class="trend-chart" v-if="data.taskTrend?.length">
        <div v-for="point in data.taskTrend" :key="point.date" class="trend-day"><strong>{{ point.count }}</strong><div class="trend-track"><div class="trend-bar" :style="{ height: `${Math.max(4, point.count / Math.max(1, ...data.taskTrend.map(day => day.count)) * 100)}%` }" /></div><small>{{ point.date.slice(5) }}</small></div>
      </div><EmptyState v-else title="暂无趋势数据" /></section>
      <section class="card"><div class="gateway-heading"><h2>Gateway 状态</h2><el-button size="small" @click="load">刷新</el-button></div>
        <el-tag v-if="data.gateway?.status === 'online'" type="success">在线</el-tag>
        <el-tag v-else-if="data.gateway?.status === 'offline'" type="danger">离线</el-tag>
        <el-tag v-else type="info">未知</el-tag>
        <p class="gateway-description">Worker 真实连接检测 · {{ gatewayTime(data.gateway?.checkedAt) }}</p>
        <p v-if="data.gateway?.latencyMs != null" class="gateway-description">握手耗时 {{ data.gateway.latencyMs }}ms</p>
        <p v-if="data.gateway?.status === 'unknown'" class="gateway-description">Worker 尚未上报，或最近检测记录已过期。</p>
      </section>
    </div>
    <div class="dashboard-panels">
      <section class="card"><h2>最近任务 · Agent Activity</h2><EmptyState v-if="!data.recentTasks?.length" title="暂无任务" /><el-table v-else :data="data.recentTasks"><el-table-column prop="prompt" label="任务" /><el-table-column prop="agent" label="Agent" width="130" /><el-table-column label="状态" width="125"><template #default="scope"><StatusTag :status="scope.row.status" /></template></el-table-column></el-table></section>
      <section class="card"><h2>失败任务</h2><EmptyState v-if="!data.failedTasks?.length" title="暂无失败任务" /><el-table v-else :data="data.failedTasks"><el-table-column prop="prompt" label="任务" /><el-table-column label="状态" width="125"><template #default="scope"><StatusTag :status="scope.row.status" /></template></el-table-column><el-table-column v-if="role === 'admin'" label="排查" width="76"><template #default="scope"><el-button link type="primary" :aria-label="`排查任务 ${scope.row.id}`" @click="inspectTask(scope.row.id)">查看</el-button></template></el-table-column></el-table></section>
    </div>
    <div class="dashboard-panels">
      <section class="card"><h2>运行观测 · 最近 {{ data.observability?.sampledTasks ?? 0 }} 条可见任务</h2>
        <div class="observability-metrics">
          <div><span>任务成功率</span><strong>{{ data.observability?.taskSuccessRate == null ? 'N/A' : `${data.observability.taskSuccessRate}%` }}</strong></div>
          <div><span>工具成功率</span><strong>{{ data.observability?.toolSuccessRate == null ? 'N/A' : `${data.observability.toolSuccessRate}%` }}</strong></div>
          <div><span>P95 耗时</span><strong>{{ data.observability?.p95LatencyMs == null ? 'N/A' : `${data.observability.p95LatencyMs}ms` }}</strong></div>
          <div><span>错误率</span><strong>{{ data.observability?.errorRate == null ? 'N/A' : `${data.observability.errorRate}%` }}</strong></div>
          <div><span>Token 用量 · 已采集 {{ data.observability?.tokenSampledTasks ?? 0 }} 条</span><strong>{{ data.observability?.tokenUsage ?? '未采集' }}</strong></div>
        </div>
      </section>
      <section class="card"><h2>常用工具</h2><EmptyState v-if="!data.observability?.topTools.length" title="暂无工具调用数据" />
        <el-table v-else :data="data.observability.topTools"><el-table-column prop="name" label="工具" /><el-table-column prop="count" label="调用次数" width="100" /></el-table></section>
    </div>
  </template>
</template>
<style scoped>
.observability-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 18px; }
.observability-metrics > div { display: grid; gap: 6px; padding: 14px; border: 1px solid #e5eaf2; border-radius: 10px; background: #f8faff; }
.observability-metrics span { color: #64748b; font-size: 13px; }
.observability-metrics strong { color: #17233c; font-size: 20px; }
.gateway-heading { display: flex; justify-content: space-between; align-items: start; }
.gateway-description { color: var(--oc-muted); font-size: 13px; margin: 12px 0 0; }
</style>
