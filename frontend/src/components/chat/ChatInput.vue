<script setup lang="ts">
defineProps<{ modelValue: string; disabled?: boolean; busy?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; send: [] }>()
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); emit('send') }
}
</script>
<template>
  <form class="chat-composer" @submit.prevent="emit('send')">
    <label class="sr-only" for="chat-prompt">输入问题</label>
    <textarea id="chat-prompt" :value="modelValue" :disabled="disabled" maxlength="4000" rows="3" placeholder="向你的 AI 助手提问…" @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)" @keydown="keydown" />
    <div class="composer-footer"><small>Enter 发送 · Shift + Enter 换行</small><el-button type="primary" native-type="submit" :disabled="disabled || !modelValue.trim()" :loading="busy">发送问题</el-button></div>
  </form>
</template>
