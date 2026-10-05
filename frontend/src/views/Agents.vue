<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { http } from '../api/http'
import { pinia, useAuthStore } from '../stores/auth'
import PageHeader from '../components/common/PageHeader.vue'
import LoadingState from '../components/common/LoadingState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'

interface Agent {
  id: string; name: string; description: string; enabled: boolean; model: string | null
  toolPolicy: string; tools: Array<{ name: string; count: number }>
  taskCount: number; successRate: number | null; sampleSize: number
  source: string; createdAt: number | null
}
const auth = useAuthStore(pinia)
const isAdmin = computed(() => auth.role === 'admin')
const rows = ref<Agent[]>([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const tab = ref('all')
const selected = ref<Agent | null>(null)
const drawer = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const saving = ref(false)
const formError = ref('')
const models = ref<string[]>([])
const form = ref({ id: '', name: '', description: '', model: '', tool_policy: 'minimal' })
const filtered = computed(() => rows.value.filter(agent => {
  const matchTab = tab.value === 'all' || (tab.value === 'enabled' ? agent.enabled : !agent.enabled)
  const term = search.value.trim().toLowerCase()
  return matchTab && (!term || `${agent.name} ${agent.id} ${agent.description}`.toLowerCase().includes(term))
}))
const enabledCount = computed(() => rows.value.filter(agent => agent.enabled).length)

// 从 Gateway 与平台统计读取 Agent 管理清单，并保留真实加载错误。
async function load() {
  loading.value = true; error.value = ''
  try { rows.value = (await http.get<Agent[]>('/agents/manage')).data }
  catch { error.value = '加载 Agent 管理数据失败，请检查 Gateway 连接后重试' }
  finally { loading.value = false }
}

// 打开详情时使用当前卡片数据，保存后再刷新详情。
function showDetail(agent: Agent) { selected.value = agent; drawer.value = true }

// 读取 Gateway 当前可用模型，并打开新增 Agent 表单。
async function openCreate() {
  form.value = { id: '', name: '', description: '', model: '', tool_policy: 'minimal' }
  formError.value = ''; createVisible.value = true
  try { models.value = (await http.get<string[]>('/agents/models')).data }
  catch { formError.value = '无法读取 Gateway 模型列表，请稍后重试' }
}

// 校验表单后创建真实 Gateway Agent，成功时刷新列表。
async function createAgent() {
  formError.value = ''
  if (!/^[a-z][a-z0-9_-]{1,47}$/.test(form.value.id)) { formError.value = 'ID 必须以小写字母开头，长度为 2–48 位'; return }
  if (!form.value.name.trim() || !form.value.model) { formError.value = '请填写名称并选择模型'; return }
  creating.value = true
  try {
    await http.post('/agents', { ...form.value, name: form.value.name.trim(), description: form.value.description.trim() })
    createVisible.value = false
    await load()
  } catch { formError.value = '创建失败；如 Gateway 已创建该 ID，请先刷新列表检查状态' }
  finally { creating.value = false }
}

// 切换平台可用状态，不修改 Gateway 中的 Agent 本体。
async function setEnabled(agent: Agent, enabled: boolean) {
  saving.value = true
  try {
    await http.post(`/agents/${encodeURIComponent(agent.id)}/availability`, null, { params: { enabled } })
    await load()
    selected.value = rows.value.find(item => item.id === agent.id) || null
  } catch { error.value = '更新 Agent 可用状态失败，请重试' }
  finally { saving.value = false }
}

onMounted(load)
</script>

<template>
  <div class="agents-page">
    <PageHeader title="Agent 管理" description="管理 Gateway 中的智能体，查看近 30 天平台任务数据">
      <template #actions><el-button v-if="isAdmin" type="primary" @click="openCreate">＋ 新建 Agent</el-button></template>
    </PageHeader>
    <div class="agent-toolbar">
      <el-tabs v-model="tab" class="agent-tabs">
        <el-tab-pane :label="`全部 (${rows.length})`" name="all" />
        <el-tab-pane :label="`已启用 (${enabledCount})`" name="enabled" />
        <el-tab-pane :label="`未启用 (${rows.length - enabledCount})`" name="disabled" />
      </el-tabs>
      <el-input v-model="search" clearable placeholder="搜索 Agent 名称或 ID" aria-label="搜索 Agent" />
    </div>
    <LoadingState v-if="loading" title="正在加载 Agent…" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState v-else-if="!filtered.length" title="没有符合条件的 Agent" description="可调整搜索或筛选条件" />
    <div v-else class="agent-grid">
      <button v-for="agent in filtered" :key="agent.id" class="card agent-card" type="button" @click="showDetail(agent)">
        <span class="agent-card-heading"><span class="agent-card-icon">{{ agent.name.slice(0, 1).toUpperCase() }}</span><span><strong class="agent-card-title">{{ agent.name }}</strong><small class="agent-card-id">{{ agent.id }}</small></span></span>
        <span class="agent-card-status" :class="agent.enabled ? 'is-enabled' : 'is-disabled'">{{ agent.enabled ? '已启用' : '未启用' }}</span>
        <span class="agent-card-description">{{ agent.description || '暂无用途说明' }}</span>
        <span class="agent-card-meta">模型 <strong :title="agent.model || ''">{{ agent.model || '未采集' }}</strong></span>
        <span class="agent-card-meta">近 30 天任务 <strong>{{ agent.taskCount }}</strong></span>
        <span class="agent-card-meta">成功率 <strong>{{ agent.successRate === null ? '未采集' : `${agent.successRate}%` }}</strong></span>
      </button>
    </div>
    <p v-if="rows.length && !loading" class="agent-note">任务统计来自平台近 30 天记录；成功率只统计完成、失败及超时任务。Tool 列表为历史调用记录。</p>
    <el-drawer v-model="drawer" title="Agent 详情" size="min(480px, 100vw)">
      <template v-if="selected">
        <dl class="agent-detail">
          <dt>名称</dt><dd>{{ selected.name }}</dd>
          <dt>ID</dt><dd>{{ selected.id }}</dd>
          <dt>用途</dt><dd>{{ selected.description || '未填写' }}</dd>
          <dt>平台状态</dt><dd>{{ selected.enabled ? '已启用' : '未启用' }}</dd>
          <dt>有效模型</dt><dd>{{ selected.model || '未采集' }}</dd>
          <dt>Tool 策略</dt><dd>{{ selected.toolPolicy === 'minimal' ? '最小权限' : selected.toolPolicy === 'business_readonly' ? '只读业务工具' : '沿用 Gateway 配置' }}</dd>
          <dt>历史 Tool</dt><dd>{{ selected.tools.length ? selected.tools.map(tool => `${tool.name} (${tool.count})`).join('、') : '暂无调用记录' }}</dd>
          <dt>近 30 天任务</dt><dd>{{ selected.taskCount }}</dd>
          <dt>成功率</dt><dd>{{ selected.successRate === null ? '未采集' : `${selected.successRate}%（${selected.sampleSize} 条终态任务）` }}</dd>
        </dl>
        <el-button v-if="isAdmin && selected.id !== 'database' && (selected.source === 'platform' || ['coordinator', 'researcher', 'writer', 'reviewer'].includes(selected.id))" :loading="saving" @click="setEnabled(selected, !selected.enabled)">{{ selected.enabled ? '停用平台调用' : '启用平台调用' }}</el-button>
      </template>
    </el-drawer>
    <el-dialog v-model="createVisible" title="新建 Agent" width="min(520px, 96vw)">
      <el-form label-position="top">
        <el-form-item label="Agent ID"><el-input v-model="form.id" maxlength="48" placeholder="例如 sales-assistant" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" maxlength="80" placeholder="例如 销售助手" /></el-form-item>
        <el-form-item label="用途说明"><el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" placeholder="说明这个 Agent 的职责" /></el-form-item>
        <el-form-item label="模型"><el-select v-model="form.model" filterable placeholder="选择 Gateway 可用模型" style="width: 100%"><el-option v-for="model in models" :key="model" :label="model" :value="model" /></el-select></el-form-item>
        <el-form-item label="Tool 策略"><el-select v-model="form.tool_policy" style="width: 100%"><el-option label="最小权限（默认）" value="minimal" /><el-option label="只读业务工具" value="business_readonly" /></el-select></el-form-item>
        <p class="agent-form-note">创建后会在 Gateway 建立独立 Workspace；仅管理员可以修改平台可用状态。</p>
        <p v-if="formError" class="chat-error" role="alert">{{ formError }}</p>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="creating" :disabled="!models.length" @click="createAgent">创建 Agent</el-button></template>
    </el-dialog>
  </div>
</template>
