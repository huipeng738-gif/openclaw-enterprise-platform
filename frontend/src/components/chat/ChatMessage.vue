<script setup lang="ts">
defineProps<{ role: 'user' | 'assistant'; content: string; agent?: string }>()
</script>
<template>
  <article class="chat-message" :class="`chat-message--${role}`" :aria-label="role === 'user' ? '我的提问' : 'Agent 回复'">
    <div class="message-avatar" aria-hidden="true">{{ role === 'user' ? '我' : 'AI' }}</div>
    <div class="message-body"><strong class="message-author">{{ role === 'user' ? '你' : agent || 'Agent' }}</strong><div class="message-content">{{ content }}</div><slot /></div>
  </article>
</template>
