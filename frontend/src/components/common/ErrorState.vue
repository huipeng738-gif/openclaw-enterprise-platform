<script setup lang="ts">
defineProps<{ message: string }>()
defineEmits<{ retry: [] }>()
</script>
<template><div class="state-panel" role="alert"><strong>{{ message }}</strong><p><el-button @click="$emit('retry')">重试</el-button></p></div></template>
