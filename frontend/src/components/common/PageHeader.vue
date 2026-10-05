<script setup lang="ts">
defineProps<{ title: string; description?: string }>()
</script>
<template>
  <header class="page-header">
    <div><h1 class="page-title">{{ title }}</h1><p v-if="description">{{ description }}</p></div>
    <div v-if="$slots.actions"><slot name="actions" /></div>
  </header>
</template>
