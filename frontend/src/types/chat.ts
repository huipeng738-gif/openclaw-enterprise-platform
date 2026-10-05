export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'timed_out'
export interface Citation {
  document_name?: string
  document_id: string
  knowledge_base_id?: string
  score?: number
}
export interface ChatTask {
  id: string
  prompt: string
  agent: string
  status: TaskStatus
  createdAt: string
  finishedAt?: string | null
  model?: string | null
  tokenUsage?: number | null
  result?: string | null
  error?: string | null
  sources?: Citation[]
  database?: { sql: string; rowCount: number; truncated: boolean; preview: Record<string, string | number | null>[] }
}
export interface TaskEvent {
  id: string
  kind: string
  at?: number
  text?: string
  name?: string
  phase?: string
  status?: string
  callId?: string
  query?: string
  resultCount?: number
  rowCount?: number
  durationMs?: number
  isError?: boolean
  resultSummary?: string
}
export interface ToolCall {
  id: string
  name: string
  status: 'running' | 'success' | 'failed' | 'interrupted'
  query?: string
  resultCount?: number
  durationMs?: number
  summary?: string
  startedAt?: number
}
