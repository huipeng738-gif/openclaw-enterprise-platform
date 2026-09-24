<script setup lang="ts">
import {ref, onUnmounted} from 'vue'
import {http} from '../api/http'

const input = ref('');
const messages = ref<any[]>([]);
const tools = ref<any[]>([]);
const loading = ref(false);
const error = ref('')
let ws: WebSocket | undefined

async function send() {
  if (!input.value.trim() || loading.value) return
  const q = input.value;
  input.value = '';
  messages.value.push({role: 'user', text: q});
  tools.value = [];
  loading.value = true;
  error.value = ''
  try {
    const task = (await http.post('/chat', {prompt: q})).data
    const ticket = (await http.post(`/tasks/${task.id}/ws-ticket`)).data.ticket
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`)
    ws.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'event' && msg.event.kind === 'tool') tools.value.push(msg.event);
      if (msg.type === 'snapshot' && ['completed', 'failed', 'cancelled', 'timed_out'].includes(msg.task.status)) {
        messages.value.push({role: 'assistant', text: msg.task.result || msg.task.error || msg.task.status});
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
    <div v-for="(t,i) in tools" :key="i">{{ t.name }} · {{ t.phase }}</div>
  </div>
  <el-alert v-if="error" type="error" :title="error"/>
  <div class="toolbar">
    <el-input v-model="input" @keyup.enter="send"/>
    <el-button type="primary" :loading="loading" @click="send">发送</el-button>
  </div>
</template>
