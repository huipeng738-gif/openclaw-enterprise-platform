<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '../api/http'
import PageHeader from '../components/common/PageHeader.vue'
import StatCard from '../components/common/StatCard.vue'
import LoadingState from '../components/common/LoadingState.vue'
import ErrorState from '../components/common/ErrorState.vue'
import EmptyState from '../components/common/EmptyState.vue'

interface MetricPoint { period: string; value: string }
interface MetricResult { metric: string; label: string; unit: string; total: string; points: MetricPoint[] }

const choices = [
  { value: 'sales_amount', label: '已支付订单金额' },
  { value: 'order_count', label: '订单数' },
  { value: 'refund_rate', label: '退款订单占比' },
  { value: 'active_customer_count', label: '区间内新建且当前活跃客户数' },
]
const today = new Date()
const start = new Date(today)
start.setDate(start.getDate() - 29)
// 将浏览器本地日期格式化为 API 接受的 YYYY-MM-DD。
const dateText = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
const range = ref<string[]>([dateText(start), dateText(today)])
const metric = ref('sales_amount')
const groupBy = ref('day')
const result = ref<MetricResult | null>(null)
const loading = ref(false)
const error = ref('')
const router = useRouter()
const question = ref('')
const asking = ref(false)
const questionError = ref('')
const maxValue = computed(() => Math.max(1, ...(result.value?.points || []).map(point => Number(point.value))))

// 根据当前筛选调用真实指标 API，并在失败时保留明确错误状态。
async function load() {
  if (range.value.length !== 2) { error.value = '请选择完整时间范围'; return }
  loading.value = true; error.value = ''; result.value = null
  try {
    result.value = (await http.post<MetricResult>('/metrics/query', {
      metric: metric.value, start_date: range.value[0], end_date: range.value[1], group_by: groupBy.value
    })).data
  } catch { error.value = '指标查询失败，请检查时间范围或稍后重试' }
  finally { loading.value = false }
}

// 将开放式问题提交为后台数据库任务，并复用聊天页的事件与结果展示。
async function askDatabase() {
  if (!question.value.trim() || asking.value) return
  asking.value = true; questionError.value = ''
  try {
    const task = (await http.post<{ id: string }>('/database/questions', { prompt: question.value.trim() })).data
    await router.push({ path: '/chat', query: { task: task.id } })
  } catch { questionError.value = '提交数据库分析失败，请稍后重试' }
  finally { asking.value = false }
}

onMounted(load)
</script>

<template>
  <div class="analytics-page">
    <PageHeader title="数据分析" description="基于 Demo 业务数据库的预定义指标，结果来自真实查询。" />
    <div class="card analytics-filter">
      <el-select v-model="metric" aria-label="选择指标" style="width: 260px"><el-option v-for="item in choices" :key="item.value" :value="item.value" :label="item.label" /></el-select>
      <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" aria-label="时间范围" />
      <el-select v-model="groupBy" aria-label="分组方式" style="width: 120px"><el-option label="按天" value="day" /><el-option label="按周" value="week" /><el-option label="按月" value="month" /></el-select>
      <el-button type="primary" :loading="loading" @click="load">查询</el-button>
    </div>
    <div class="card analytics-question">
      <h2>开放式数据库分析</h2>
      <p>使用只读业务数据回答问题；数据不足时会明确说明。</p>
      <el-input v-model="question" type="textarea" :rows="2" maxlength="1000" show-word-limit
                placeholder="例如：最近三个月 VIP 客户的购买趋势如何？" aria-label="数据库分析问题" />
      <el-button type="primary" :loading="asking" :disabled="!question.trim()" @click="askDatabase">开始分析</el-button>
      <el-alert v-if="questionError" :title="questionError" type="error" show-icon />
    </div>
    <LoadingState v-if="loading" title="正在查询指标…" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <template v-else-if="result">
      <StatCard :label="result.label" :value="`${result.total} ${result.unit}`" hint="所选时间范围" />
      <div class="card analytics-results">
        <h2>指标趋势</h2>
        <EmptyState v-if="!result.points.length" title="所选时间范围暂无数据" />
        <div v-else class="analytics-chart" role="img" :aria-label="`${result.label}趋势图`">
          <div v-for="point in result.points" :key="point.period" class="analytics-bar">
            <span>{{ point.value }}</span><div class="analytics-track"><div :style="{ height: `${Math.max(3, Number(point.value) / maxValue * 100)}%` }" /></div><small>{{ point.period }}</small>
          </div>
        </div>
      </div>
      <div class="card analytics-results"><h2>数据明细</h2><el-table :data="result.points" empty-text="暂无数据"><el-table-column prop="period" label="时间" /><el-table-column prop="value" :label="`${result.label}（${result.unit}）`" /></el-table></div>
    </template>
  </div>
</template>
