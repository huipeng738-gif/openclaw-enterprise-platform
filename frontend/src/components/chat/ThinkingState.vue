<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'
defineProps<{ label: string }>()
</script>
<template><div class="thinking-state" role="status" aria-live="polite"><el-icon class="is-loading"><Loading /></el-icon><span>{{ label }}</span></div></template>
