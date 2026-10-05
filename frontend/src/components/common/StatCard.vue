<script setup lang="ts">
defineProps<{ label: string; value: string | number | null | undefined; hint?: string }>()
</script>
<template>
  <div class="card"><div class="muted">{{ label }}</div><div class="metric">{{ value ?? '—' }}</div><small v-if="hint" class="muted">{{ hint }}</small></div>
</template>
