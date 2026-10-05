<script setup lang="ts">
import type { ToolCall } from '../../types/chat'
defineProps<{ call: ToolCall }>()
const labels = { running: 'Tool Running · 执行中', success: 'Tool Success · 已完成', failed: 'Tool Failed · 失败', interrupted: '未返回结果' }
</script>
<template>
  <details class="tool-card" :class="`tool-card--${call.status}`" :open="call.status === 'running'">
    <summary><span class="tool-symbol" aria-hidden="true">⌘</span><strong>{{ call.name }}</strong><span class="tool-status">{{ labels[call.status] }}</span></summary>
    <div class="tool-details">
      <dl><dt>参数</dt><dd>{{ call.query ? `Query: ${call.query}` : '无可展示参数' }}</dd><dt>结果摘要</dt><dd>{{ call.summary || (call.resultCount != null ? `检索到 ${call.resultCount} 条来源` : '等待工具结果') }}</dd><dt>耗时</dt><dd>{{ call.durationMs == null ? '未提供' : `${call.durationMs} ms` }}</dd></dl>
    </div>
  </details>
</template>
