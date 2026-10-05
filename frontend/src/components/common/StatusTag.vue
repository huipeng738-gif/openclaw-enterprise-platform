<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status: string }>()
const types: Record<string, 'success' | 'primary' | 'danger' | 'info' | 'warning'> = {
  completed: 'success', DONE: 'success', running: 'primary', RUNNING: 'primary',
  failed: 'danger', FAIL: 'danger', timed_out: 'danger', cancelled: 'info',
  queued: 'warning', pending: 'warning'
}
const type = computed(() => types[props.status] || 'info')
</script>
<template><el-tag :type="type" effect="light">{{ status }}</el-tag></template>
