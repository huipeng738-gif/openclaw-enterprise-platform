<script setup lang="ts">
import type { Citation } from '../../types/chat'
defineProps<{ source: Citation; index: number }>()
</script>
<template><div class="citation-card"><span aria-hidden="true">▤</span><div><strong>[{{ index + 1 }}] {{ source.document_name || '未命名文档' }}</strong><small>文档 {{ source.document_id }}<template v-if="source.score != null"> · 相似度 {{ source.score.toFixed(2) }}</template></small></div></div></template>
