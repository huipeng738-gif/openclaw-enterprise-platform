<script setup lang="ts">
defineProps<{ modelValue: boolean; title: string; message: string; busy?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; confirm: [] }>()
</script>
<template>
  <el-dialog :model-value="modelValue" :title="title" width="min(420px, 90vw)" @update:model-value="emit('update:modelValue', $event)">
    <p>{{ message }}</p>
    <template #footer><el-button @click="emit('update:modelValue', false)">取消</el-button><el-button type="danger" :loading="busy" @click="emit('confirm')">确认</el-button></template>
  </el-dialog>
</template>
