<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '../api/http'
const rows = ref<any[]>([])
// 页面挂载时读取最近的操作审计记录。
onMounted(async () => rows.value = (await http.get('/audit')).data)
</script>
<template><h1 class="page-title">操作审计</h1><el-table :data="rows"><el-table-column prop="at" label="时间"/><el-table-column prop="actor" label="操作人"/><el-table-column prop="action" label="动作"/><el-table-column prop="target" label="对象"/><el-table-column prop="outcome" label="结果"/></el-table></template>
