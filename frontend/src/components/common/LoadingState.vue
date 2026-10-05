<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'
withDefaults(defineProps<{ title?: string }>(), { title: '正在加载…' })
</script>
<template><div class="state-panel" role="status" aria-live="polite"><el-icon class="is-loading"><Loading /></el-icon><p>{{ title }}</p></div></template>
