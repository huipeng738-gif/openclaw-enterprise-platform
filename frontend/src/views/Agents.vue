<script setup lang="ts">
import {onMounted,ref} from 'vue';import {http} from '../api/http'
const rows=ref<any[]>([]);onMounted(async()=>rows.value=(await http.get('/agents')).data)
</script>
<template><h1 class="page-title">可选 Agent</h1><el-table :data="rows"><el-table-column prop="id" label="ID"/><el-table-column prop="name" label="名称"/></el-table></template>
