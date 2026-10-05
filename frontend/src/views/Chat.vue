<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { http } from '../api/http'
import type { ChatTask } from '../types/chat'
import { assistantText, executionStage, isTerminal, toolCalls } from '../utils/chat'
import { useChatTask } from '../composables/useChatTask'
import ChatMessage from '../components/chat/ChatMessage.vue'
import ToolCallCard from '../components/chat/ToolCallCard.vue'
import ThinkingState from '../components/chat/ThinkingState.vue'
import CitationCard from '../components/chat/CitationCard.vue'
import AgentTrace from '../components/chat/AgentTrace.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import LoadingState from '../components/common/LoadingState.vue'
import EmptyState from '../components/common/EmptyState.vue'
import StatusTag from '../components/common/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const session = useChatTask()
const { task, events, loading, error, connection, cancelling } = session
const input = ref('')
const search = ref('')
const sessions = ref<ChatTask[]>([])
const agents = ref<Array<{ id: string; name: string }>>([])
const selectedAgent = ref('')
const submitting = ref(false)
const listLoading = ref(false)
const pageError = ref('')
const listError = ref('')
const messages = ref<HTMLElement>()
const followOutput = ref(true)
const requests = new AbortController()
let mounted = true
const active = computed(() => !!task.value && !isTerminal(task.value))
const reply = computed(() => assistantText(task.value, events.value))
const calls = computed(() => toolCalls(events.value, isTerminal(task.value)))
const filteredSessions = computed(() => sessions.value.filter(item => item.prompt.toLowerCase().includes(search.value.toLowerCase())))
const stage = computed(() => executionStage(task.value, events.value))

async function loadSessions() {
  listLoading.value = true; listError.value = ''
  try { sessions.value = (await http.get<ChatTask[]>('/tasks', { signal: requests.signal })).data }
  catch { if (mounted) listError.value = '加载最近对话失败' }
  finally { if (mounted) listLoading.value = false }
}
async function loadAgents() {
  try {
    agents.value = (await http.get<Array<{ id: string; name: string }>>('/agents', { signal: requests.signal })).data
    selectedAgent.value = agents.value[0]?.id || ''
  } catch { if (mounted) pageError.value = '加载 Agent 列表失败，请刷新页面重试' }
}
function remember(updated: ChatTask) {
  const index = sessions.value.findIndex(item => item.id === updated.id)
  if (index < 0) sessions.value.unshift(updated)
  else sessions.value[index] = updated
}
async function select(id = '') {
  pageError.value = ''; followOutput.value = true
  await router.replace({ path: '/chat', query: id ? { task: id } : {} })
}
async function send() {
  if (!input.value.trim() || submitting.value || active.value || loading.value || !selectedAgent.value) return
  submitting.value = true; pageError.value = ''
  try {
    const created = (await http.post<ChatTask>('/chat', { prompt: input.value.trim(), agent: selectedAgent.value }, { signal: requests.signal })).data
    if (!mounted) return
    input.value = ''; remember(created)
    await select(created.id)
  } catch { if (mounted) pageError.value = '提交失败，请检查网络；若请求已受理，可刷新最近对话查找任务。' }
  finally { if (mounted) submitting.value = false }
}
function onScroll() {
  const panel = messages.value
  if (panel) followOutput.value = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 80
}
watch(() => route.query.task, id => { void session.open(typeof id === 'string' ? id : '') }, { immediate: true })
watch(task, updated => { if (updated) remember(updated) })
watch([reply, () => events.value.length], async () => {
  if (!followOutput.value) return
  await nextTick()
  if (messages.value) messages.value.scrollTop = messages.value.scrollHeight
})
onMounted(() => { void loadSessions(); void loadAgents() })
onUnmounted(() => { mounted = false; requests.abort(); session.dispose() })
</script>
<template>
  <div class="chat-page">
    <header class="chat-page-header"><h1>AI 对话</h1><p>与你的 AI 助手协作，查看每一步执行过程。</p></header>
    <div class="chat-workspace">
      <aside class="conversation-panel" aria-label="最近对话">
        <el-button class="full new-conversation" type="primary" :disabled="submitting" @click="select()">＋ 新建对话</el-button>
        <el-input v-model="search" placeholder="搜索对话…" aria-label="搜索对话" clearable />
        <div class="conversation-heading"><h2>最近对话</h2><el-button text size="small" :loading="listLoading" @click="loadSessions">刷新</el-button></div>
        <p v-if="listError" role="alert" class="chat-error">{{ listError }}</p>
        <LoadingState v-if="listLoading && !sessions.length" />
        <EmptyState v-else-if="!filteredSessions.length && !listError" title="暂无对话" description="从一个问题开始" />
        <nav class="conversation-list"><button v-for="item in filteredSessions" :key="item.id" class="conversation-item" :class="{ selected: route.query.task === item.id }" :aria-current="route.query.task === item.id ? 'true' : undefined" :disabled="submitting" @click="select(item.id)"><span aria-hidden="true">▤</span><span><strong>{{ item.prompt }}</strong><small>{{ item.agent }} · {{ new Date(item.createdAt).toLocaleDateString('zh-CN') }}</small></span></button></nav>
        <p class="conversation-note">最近 100 条任务对话</p>
      </aside>
      <section class="chat-main" aria-label="对话内容">
        <header class="chat-agent-header"><div class="agent-identity"><span class="agent-avatar" aria-hidden="true">AI</span><div><strong>{{ task?.agent || selectedAgent || '选择 Agent' }}</strong><small>企业智能助手</small></div></div><StatusTag v-if="task" :status="task.status" /><el-select v-else v-model="selectedAgent" aria-label="选择 Agent" :disabled="submitting" style="width: 150px"><el-option v-for="agent in agents" :key="agent.id" :label="agent.name" :value="agent.id" /></el-select></header>
        <div ref="messages" class="chat-messages" @scroll="onScroll">
          <LoadingState v-if="loading && !task" title="正在恢复对话…" />
          <EmptyState v-else-if="!task" title="今天想了解什么？" description="检索企业知识、梳理问题，或让 Agent 帮你完成工作。" />
          <template v-if="task">
            <ChatMessage role="user" :content="task.prompt" />
            <div v-if="calls.length" class="chat-tools" aria-label="工具调用"><ToolCallCard v-for="call in calls" :key="call.id" :call="call" /></div>
            <ChatMessage v-if="reply" role="assistant" :content="reply" :agent="task.agent" />
            <details v-if="task.database" class="database-evidence">
              <summary>查询依据 · {{ task.database.rowCount }} 行<template v-if="task.database.truncated">（已达上限）</template></summary>
              <code>{{ task.database.sql }}</code>
              <div v-if="task.database.preview?.length" class="database-preview">
                <el-table :data="task.database.preview" size="small">
                  <el-table-column v-for="column in Object.keys(task.database.preview[0])" :key="column" :prop="column" :label="column" min-width="120" />
                </el-table>
              </div>
            </details>
            <ThinkingState v-if="active" :label="stage" />
            <p v-else-if="task.status !== 'completed'" class="chat-error" role="alert">{{ stage }}<template v-if="task.error">：{{ task.error }}</template></p>
            <EmptyState v-else-if="!reply" title="任务已完成，未返回文本" />
            <div v-if="task.sources?.length" class="chat-citations" aria-label="引用来源"><h3>引用来源</h3><CitationCard v-for="(source, index) in task.sources" :key="source.document_id + '-' + index" :source="source" :index="index" /></div>
          </template>
        </div>
        <div class="chat-feedback"><p v-if="pageError || error" role="alert" class="chat-error">{{ pageError || error }}</p><el-button v-if="connection === 'offline'" size="small" @click="session.reconnect">重试连接</el-button><el-button v-if="active" size="small" :loading="cancelling" @click="session.cancel">取消任务</el-button><span v-if="task && !active" class="muted">新问题将开启独立对话</span></div>
        <ChatInput v-model="input" :disabled="active || loading || submitting || !selectedAgent" :busy="submitting" @send="send" />
      </section>
      <AgentTrace :task="task" :events="events" :connection="connection" />
    </div>
  </div>
</template>
