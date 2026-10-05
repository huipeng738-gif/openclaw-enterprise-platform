<script setup lang="ts">
import { computed } from 'vue'
import type { ChatTask, TaskEvent } from '../../types/chat'
import { agentTraceSteps, executionStage } from '../../utils/chat'
const props = defineProps<{ task: ChatTask | null; events: TaskEvent[]; connection: string }>()
const labels: Record<string, string> = { idle: '未连接', connecting: '连接中', live: '实时连接', reconnecting: '正在重连', offline: '已断开', finished: '回放完成' }
const trace = computed(() => agentTraceSteps(props.task, props.events))

// 将 Unix 秒时间戳格式化为本地时分秒，缺失时间不显示。
function timeLabel(at?: number): string {
  return typeof at === 'number' && Number.isFinite(at) ? new Date(at * 1000).toLocaleTimeString('zh-CN') : ''
}
</script>
<template>
  <aside class="agent-trace" aria-label="Agent Trace">
    <h2>执行过程 <span>Agent Trace</span></h2>
    <p class="trace-connection" role="status">{{ labels[connection] || connection }}</p>
    <div class="trace-current">{{ executionStage(task, events) }}</div>
    <dl class="trace-meta"><dt>Agent</dt><dd>{{ task?.agent || '未选择' }}</dd><dt>Task ID</dt><dd>{{ task?.id || '—' }}</dd><dt>模型</dt><dd>{{ task?.model || '未采集' }}</dd><dt>Token</dt><dd>{{ typeof task?.tokenUsage === 'number' ? task.tokenUsage.toLocaleString('zh-CN') : '未采集' }}</dd></dl>
    <ol v-if="trace.length" class="trace-events"><li v-for="step in trace" :key="step.id" :class="step.tone ? `trace-${step.tone}` : ''"><strong>{{ step.label }}</strong><span v-if="step.detail" class="trace-detail">{{ step.detail }}</span><small v-if="timeLabel(step.at)">{{ timeLabel(step.at) }}</small></li></ol>
    <p v-else class="muted">开始对话后，这里将展示真实执行事件。</p>
  </aside>
</template>
