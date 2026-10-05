<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { http } from '../api/http'
import PageHeader from '../components/common/PageHeader.vue'
import LoadingState from '../components/common/LoadingState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'

interface AuditEntry { id: string; at: string; actor: string; action: string; target: string; outcome: string }
const rows = ref<AuditEntry[]>([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const actionFilter = ref('')
const outcomeFilter = ref('')
const dateRange = ref<string[]>([])
const page = ref(1)
const pageSize = 20
const selected = ref<AuditEntry | null>(null)
const drawer = ref(false)
const actions = computed(() => [...new Set(rows.value.map(row => row.action))].sort())
const filtered = computed(() => rows.value.filter(row => {
  const term = search.value.trim().toLowerCase()
  if (term && !`${row.actor} ${row.action} ${row.target}`.toLowerCase().includes(term)) return false
  if (actionFilter.value && row.action !== actionFilter.value) return false
  if (outcomeFilter.value && row.outcome !== outcomeFilter.value) return false
  if (dateRange.value.length === 2) {
    const day = row.at.slice(0, 10)
    if (day < dateRange.value[0] || day > dateRange.value[1]) return false
  }
  return true
}))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
watch([search, actionFilter, outcomeFilter, dateRange], () => { page.value = 1 })

// 将审计时间转为本地可读文本，原始时间仍保留在详情中。
function timeText(value: string) { return value ? value.replace('T', ' ').slice(0, 19) : 'N/A' }

// 根据后端真实结果展示审计状态，不推断未知结果。
function outcomeType(value: string): 'success' | 'danger' | 'info' {
  if (value === 'ok') return 'success'
  if (value === 'failed' || value === 'denied') return 'danger'
  return 'info'
}

// 读取后端最近一百条审计流记录；筛选和分页仅作用于已返回记录。
async function load() {
  loading.value = true; error.value = ''
  try { rows.value = (await http.get<AuditEntry[]>('/audit')).data }
  catch { error.value = '加载审计记录失败，请重试' }
  finally { loading.value = false }
}

// 展示选中记录的原始字段，便于核对时间、目标和结果。
function showDetail(row: AuditEntry) { selected.value = row; drawer.value = true }

// 切换当前客户端分页页码。
function changePage(value: number) { page.value = value }

onMounted(load)
</script>

<template>
  <div class="audit-page">
    <PageHeader title="审计日志" description="查看最近的系统操作记录与执行结果" />
    <div class="card audit-card">
      <div class="audit-filters">
        <el-input v-model="search" clearable placeholder="搜索操作人、动作或对象…" aria-label="搜索审计记录" />
        <el-select v-model="actionFilter" placeholder="全部动作" aria-label="审计动作"><el-option label="全部动作" value="" /><el-option v-for="action in actions" :key="action" :label="action" :value="action" /></el-select>
        <el-select v-model="outcomeFilter" placeholder="全部结果" aria-label="审计结果"><el-option label="全部结果" value="" /><el-option label="成功" value="ok" /><el-option label="失败" value="failed" /><el-option label="拒绝" value="denied" /></el-select>
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始时间" end-placeholder="结束时间" aria-label="审计时间范围" />
        <el-button @click="load">刷新</el-button>
      </div>
      <LoadingState v-if="loading && !rows.length" title="正在加载审计记录…" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState v-else-if="!filtered.length" title="暂无匹配的审计记录" description="可调整筛选条件" />
      <template v-else>
        <el-table :data="visible" v-loading="loading" stripe>
          <el-table-column label="时间" min-width="165"><template #default="scope">{{ timeText(scope.row.at) }}</template></el-table-column>
          <el-table-column prop="actor" label="操作人" min-width="135" />
          <el-table-column prop="action" label="动作" min-width="155" />
          <el-table-column prop="target" label="对象" min-width="180" show-overflow-tooltip />
          <el-table-column label="结果" width="100"><template #default="scope"><el-tag :type="outcomeType(scope.row.outcome)" effect="light">{{ scope.row.outcome }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="90"><template #default="scope"><el-button link type="primary" @click="showDetail(scope.row)">详情</el-button></template></el-table-column>
        </el-table>
        <el-pagination class="audit-pagination" background layout="total, prev, pager, next" :total="filtered.length" :page-size="pageSize" :current-page="page" @current-change="changePage" />
      </template>
      <p class="audit-note">仅包含后端返回的最近 100 条记录；搜索与筛选范围也仅限于这些记录。</p>
    </div>
    <el-drawer v-model="drawer" title="审计详情" size="min(460px, 100vw)">
      <dl v-if="selected" class="audit-detail">
        <dt>记录 ID</dt><dd>{{ selected.id }}</dd>
        <dt>时间</dt><dd>{{ selected.at }}</dd>
        <dt>操作人</dt><dd>{{ selected.actor }}</dd>
        <dt>动作</dt><dd>{{ selected.action }}</dd>
        <dt>对象</dt><dd>{{ selected.target }}</dd>
        <dt>结果</dt><dd><el-tag :type="outcomeType(selected.outcome)">{{ selected.outcome }}</el-tag></dd>
      </dl>
    </el-drawer>
  </div>
</template>
