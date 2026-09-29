<script setup lang="ts">
import {ref, onUnmounted} from 'vue'
import {http} from '../api/http'

const input = ref('');
const messages = ref<any[]>([]);
const tools = ref<any[]>([]);
const sources = ref<Array<{document_name: string; document_id: string; knowledge_base_id: string; score: number}>>([])
const loading = ref(false);
const error = ref('')
let ws: WebSocket | undefined

async function send() {
  if (!input.value.trim() || loading.value) return
  const q = input.value;
  input.value = '';
  messages.value.push({role: 'user', text: q});
  tools.value = [];
  sources.value = [];
  loading.value = true;
  error.value = ''
  try {
    // 第一步：POST /api/chat 只创建后台任务，202 响应中含 task.id，不会等待 Agent 跑完。

    const task = (await http.post('/chat', {prompt: q})).data
    // 第二步：用短时、一次性的 ticket 换取 WebSocket 连接资格，避免把长期 JWT 放进 URL。

    const ticket = (await http.post(`/tasks/${task.id}/ws-ticket`)).data.ticket
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    // 第三步：任务事件和最终状态通过 WebSocket 异步回传；HTTP 已经完成了“受理”响应。

    ws = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`)
    ws.onmessage = e => {
      const msg = JSON.parse(e.data);
      // Worker 写入的 Tool 事件用于过程展示；终态 snapshot 携带结果或错误。

      if (msg.type === 'event' && msg.event.kind === 'tool') tools.value.push(msg.event);

      if (msg.type === 'snapshot' && ['completed', 'failed', 'cancelled', 'timed_out'].includes(msg.task.status)) {
        messages.value.push({role: 'assistant', text: msg.task.result || msg.task.error || msg.task.status});
        sources.value = msg.task.sources || []
        loading.value = false;
        ws?.close()
      }
    }
    ws.onerror = () => {
      error.value = '实时连接中断，请在任务中心查看结果';
      loading.value = false
    }
    } catch (e: any) {
    error.value = e.response?.data?.detail || '请求失败';
    loading.value = false
  }
}

onUnmounted(() => ws?.close())
</script>
<template><h1 class="page-title">AI 助手</h1>
  <div class="chat-box">
    <div v-for="(m,i) in messages" :key="i" class="msg" :class="m.role"><span class="bubble">{{ m.text }}</span></div>
  </div>
  <div v-if="tools.length" class="card"><b>Tool 调用</b>
    <div v-for="(t,i) in tools" :key="i">{{ t.name }} · {{ t.phase }}<span v-if="t.query"> · {{ t.query }}</span><span v-if="t.resultCount !== undefined"> · {{ t.resultCount }} 条</span></div>
  </div>
  <div v-if="sources.length" class="card"><b>引用来源</b>
    <div v-for="(source,i) in sources" :key="`${source.document_id}-${i}`">[{{ i + 1 }}] {{ source.document_name }} · {{ source.score?.toFixed(2) }}</div>
  </div>
  <el-alert v-if="error" type="error" :title="error"/>
  <div class="toolbar">
    <el-input v-model="input" @keyup.enter="send"/>
    <el-button type="primary" :loading="loading" @click="send">发送</el-button>
  </div>
</template>
