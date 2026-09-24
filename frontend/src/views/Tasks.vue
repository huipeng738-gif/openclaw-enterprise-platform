<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { http } from '../api/http'
const prompt = ref('总结本周企业经营数据'); const tasks = ref<any[]>([])
const selected = ref<any>(null); const events = ref<any[]>([]); const error = ref('')
let ws: WebSocket | undefined
async function load() { tasks.value = (await http.get('/tasks')).data }
async function watch(task: any) {
  ws?.close(); selected.value = task; events.value = (await http.get(`/tasks/${task.id}/events`)).data
  if (['completed','failed','cancelled','timed_out'].includes(task.status)) return
  const ticket = (await http.post(`/tasks/${task.id}/ws-ticket`)).data.ticket
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${protocol}://${location.host}/ws/tasks/${task.id}?ticket=${encodeURIComponent(ticket)}`)
  ws.onmessage = e => { const msg = JSON.parse(e.data); if (msg.type === 'snapshot') { selected.value = msg.task; const i=tasks.value.findIndex(t=>t.id===msg.task.id); if(i>=0) tasks.value[i]=msg.task } else if (msg.type === 'event' && !events.value.some(x=>x.id===msg.id)) events.value.push({id:msg.id,...msg.event}) }
  ws.onerror = () => error.value = '实时连接中断，请重新点选任务'
}
async function create() { error.value=''; try { const task=(await http.post('/tasks',{prompt:prompt.value})).data; tasks.value.unshift(task); await watch(task) } catch(e:any) {error.value=e.response?.data?.detail || '创建失败'} }
async function cancel(task:any) { await http.post(`/tasks/${task.id}/cancel`); await load() }
async function retry(task:any) { const newer=(await http.post(`/tasks/${task.id}/retry`)).data; tasks.value.unshift(newer); await watch(newer) }
onMounted(load); onUnmounted(()=>ws?.close())
</script>
<template><h1 class="page-title">任务中心</h1><div class="card"><div class="toolbar"><el-input v-model="prompt" placeholder="输入真实 Agent 任务"/><el-button type="primary" @click="create">创建</el-button></div><el-alert v-if="error" type="error" :title="error"/></div>
<el-table :data="tasks"><el-table-column prop="prompt" label="任务"/><el-table-column prop="status" label="状态" width="130"/><el-table-column prop="agent" label="Agent" width="140"/><el-table-column label="操作" width="230"><template #default="s"><el-button size="small" @click="watch(s.row)">查看</el-button><el-button v-if="['queued','running'].includes(s.row.status)" size="small" @click="cancel(s.row)">取消</el-button><el-button v-if="['failed','cancelled','timed_out'].includes(s.row.status)" size="small" @click="retry(s.row)">重试</el-button></template></el-table-column></el-table>
<div v-if="selected" class="card"><h3>{{selected.id}} · {{selected.status}}</h3><p v-if="selected.error">{{selected.error}}</p><pre v-if="selected.result">{{selected.result}}</pre><h4>Agent / Tool 实时事件</h4><div v-for="event in events" :key="event.id" class="event">{{event.kind}} · {{event.name || event.phase || event.status || ''}} <span v-if="event.kind==='assistant'">{{event.text}}</span></div></div></template>
