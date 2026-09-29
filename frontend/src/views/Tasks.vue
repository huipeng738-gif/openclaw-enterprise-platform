<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { http } from '../api/http'
const prompt = ref('总结本周企业经营数据'); const tasks = ref<any[]>([])
const selected = ref<any>(null); const events = ref<any[]>([]); const error = ref('')
let ws: WebSocket | undefined
let watchVersion = 0
const terminal = ['completed', 'failed', 'cancelled', 'timed_out']
// 加载当前用户可见的任务列表，失败时展示后端错误或默认提示。
async function load() {
  try { tasks.value = (await http.get('/tasks')).data }
  catch (e: any) { error.value = e.response?.data?.detail || '加载任务列表失败' }
}
// 读取所选任务历史并订阅实时事件；版本号防止切换任务后旧请求覆盖当前页面。
async function watch(task: any) {
  const version = ++watchVersion
  ws?.close(); ws = undefined
  error.value = ''; selected.value = task; events.value = []
  try {
    const history = (await http.get(`/tasks/${task.id}/events`)).data
    if (version !== watchVersion) return
    events.value = history
    if (terminal.includes(task.status)) return
    const ticket = (await http.post(`/tasks/${task.id}/ws-ticket`)).data.ticket
    if (version !== watchVersion) return
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const socket = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`)
    ws = socket
    // 同步当前任务快照，并按事件 ID 去重；忽略已切换任务的旧连接消息。
    socket.onmessage = e => {
      if (version !== watchVersion) return
      const msg = JSON.parse(e.data)
      if (msg.type === 'snapshot') {
        selected.value = msg.task
        const i = tasks.value.findIndex(t => t.id === msg.task.id)
        if (i >= 0) tasks.value[i] = msg.task
      } else if (msg.type === 'event' && !events.value.some(x => x.id === msg.id)) {
        events.value.push({id: msg.id, ...msg.event})
      }
    }
    // 当前任务未结束就断连时提示重新订阅，并清理对应连接引用。
    socket.onclose = () => {
      if (version === watchVersion && !terminal.includes(selected.value?.status))
        error.value = '实时连接中断，请重新点选任务'
      if (ws === socket) ws = undefined
    }
  } catch (e: any) {
    if (version === watchVersion)
      error.value = e.response?.data?.detail || '读取任务事件或建立实时连接失败'
  }
}
// 创建后台任务，加入列表并立即查看执行事件。
async function create() {
  error.value = ''
  let task: any
  try { task = (await http.post('/tasks', {prompt: prompt.value})).data }
  catch (e: any) { error.value = e.response?.data?.detail || '创建失败'; return }
  tasks.value.unshift(task)
  await watch(task)
}
// 提交任务取消请求并刷新列表，实际取消由 Worker 异步处理。
async function cancel(task:any) {
  try { await http.post(`/tasks/${task.id}/cancel`); await load() }
  catch (e: any) { error.value = e.response?.data?.detail || '取消任务失败' }
}
// 为未成功任务创建新的执行记录，并切换到新任务查看过程。
async function retry(task:any) {
  try {
    const newer = (await http.post(`/tasks/${task.id}/retry`)).data
    tasks.value.unshift(newer)
    await watch(newer)
  } catch (e: any) { error.value = e.response?.data?.detail || '重试任务失败' }
}
// 挂载时加载列表；卸载时使在途订阅失效并关闭实时连接。
onMounted(load); onUnmounted(() => { watchVersion++; ws?.close() })
</script>
<template><h1 class="page-title">任务中心</h1><div class="card"><div class="toolbar"><el-input v-model="prompt" placeholder="输入真实 Agent 任务"/><el-button type="primary" @click="create">创建</el-button></div><el-alert v-if="error" type="error" :title="error"/></div>
<el-table :data="tasks"><el-table-column prop="prompt" label="任务"/><el-table-column prop="status" label="状态" width="130"/><el-table-column prop="agent" label="Agent" width="140"/><el-table-column label="操作" width="230"><template #default="s"><el-button size="small" @click="watch(s.row)">查看</el-button><el-button v-if="['queued','running'].includes(s.row.status)" size="small" @click="cancel(s.row)">取消</el-button><el-button v-if="['failed','cancelled','timed_out'].includes(s.row.status)" size="small" @click="retry(s.row)">重试</el-button></template></el-table-column></el-table>
<div v-if="selected" class="card"><h3>{{selected.id}} · {{selected.status}}</h3><p v-if="selected.error">{{selected.error}}</p><pre v-if="selected.result">{{selected.result}}</pre><h4>Agent / Tool 实时事件</h4><div v-for="event in events" :key="event.id" class="event">{{event.kind}} · {{event.name || event.phase || event.status || ''}} <span v-if="event.kind==='assistant'">{{event.text}}</span></div></div></template>
