<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { http } from '../api/http'
const data=ref<any>({});const error=ref('')
// 页面挂载时加载 Agent 与任务统计，失败时显示加载提示。
onMounted(async()=>{try{data.value=(await http.get('/dashboard')).data}catch{error.value='加载失败'}})
</script>
<template><h1 class="page-title">工作台</h1><el-alert v-if="error" type="error" :title="error"/><div class="grid"><div class="card">Agents <div class="metric">{{data.agentCount ?? '-'}}</div></div><div class="card">运行任务 <div class="metric">{{data.runningTasks ?? '-'}}</div></div><div class="card">完成任务 <div class="metric">{{data.completedTasks ?? '-'}}</div></div></div></template>
