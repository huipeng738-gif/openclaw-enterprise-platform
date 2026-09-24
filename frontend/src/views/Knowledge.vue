<script setup lang="ts">
import { ref } from 'vue'; import { http } from '../api/http'
const q=ref('年假制度'); const result=ref<any>(null);const error=ref('')
async function search(){try{result.value=(await http.post('/knowledge/search',{query:q.value,top_k:5})).data}catch(e:any){error.value=e.response?.data?.detail||'检索失败'}}
</script>
<template><h1 class="page-title">知识库检索</h1><div class="card"><div class="toolbar"><el-input v-model="q"/><el-button @click="search">检索</el-button></div><el-alert v-if="error" type="warning" :title="error"/><pre v-if="result">{{JSON.stringify(result,null,2)}}</pre></div></template>
