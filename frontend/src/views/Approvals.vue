<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { http } from '../api/http'
import { role, pinia, useAuthStore } from '../stores/auth'
import PageHeader from '../components/common/PageHeader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorState from '../components/common/ErrorState.vue'

interface Approval {
  id: string; action: string; target: string; reason: string; risk: string; requester: string
  status: string; createdAt: string; expiresAt: number; reviewer?: string | null
}
const approvals = ref<Approval[]>([])
const auth = useAuthStore(pinia)
const loading = ref(false)
const error = ref('')
const actionError = ref('')
const tab = ref('pending')
const search = ref('')
const actionFilter = ref('')
const statusLabels: Record<string, string> = { pending: '待审批', approved: '已批准', rejected: '已拒绝', expired: '已过期' }
const editOpen = ref(false)
const editTarget = ref<Approval | null>(null)
const editReason = ref('')
const busy = ref('')
const visible = computed(() => approvals.value.filter(item =>
  item.status === tab.value && (!actionFilter.value || item.action === actionFilter.value) &&
  (!search.value.trim() || `${item.action} ${item.target} ${item.reason} ${item.requester}`.toLowerCase().includes(search.value.trim().toLowerCase()))
))
const counts = computed(() => Object.fromEntries(['pending', 'approved', 'rejected', 'expired'].map(status =>
  [status, approvals.value.filter(item => item.status === status).length])))

// 从真实审批 API 载入当前用户可见的申请，失败时显示可重试提示。
async function load() {
  loading.value = true; error.value = ''
  try { approvals.value = (await http.get<Approval[]>('/approvals')).data }
  catch { error.value = '加载审批记录失败，请重试' }
  finally { loading.value = false }
}

// 管理员批准或拒绝后重新读取权威状态，避免本地重复决定。
async function decide(item: Approval, decision: 'approve' | 'reject') {
  if (busy.value) return
  busy.value = item.id; actionError.value = ''
  try { await http.post(`/approvals/${item.id}/${decision}`); await load() }
  catch { actionError.value = decision === 'approve' ? '批准失败，申请可能已过期或目标任务已结束' : '拒绝失败，申请可能已被处理' }
  finally { busy.value = '' }
}

// 打开原因编辑窗口；目标任务在审批期间保持不可编辑。
function beginEdit(item: Approval) { editTarget.value = item; editReason.value = item.reason; editOpen.value = true }

// 保存待审批原因并刷新记录，保留审批人的最终决定步骤。
async function saveEdit() {
  if (!editTarget.value || editReason.value.trim().length < 3 || busy.value) return
  busy.value = editTarget.value.id; actionError.value = ''
  try { await http.patch(`/approvals/${editTarget.value.id}`, { reason: editReason.value.trim() }); editOpen.value = false; await load() }
  catch { actionError.value = '编辑失败，申请可能已过期或被处理' }
  finally { busy.value = '' }
}

onMounted(load)
</script>

<template>
  <div class="approvals-page">
    <PageHeader title="人工审批" description="处理 Agent 提出的高风险操作" />
    <div class="card approvals-card">
      <el-tabs v-model="tab" class="approval-tabs">
        <el-tab-pane :label="`待审批 (${counts.pending || 0})`" name="pending" />
        <el-tab-pane :label="`已批准 (${counts.approved || 0})`" name="approved" />
        <el-tab-pane :label="`已拒绝 (${counts.rejected || 0})`" name="rejected" />
        <el-tab-pane :label="`已过期 (${counts.expired || 0})`" name="expired" />
      </el-tabs>
      <div class="approvals-toolbar">
        <el-input v-model="search" clearable placeholder="搜索操作、目标、申请人…" aria-label="搜索审批" />
        <el-select v-model="actionFilter" aria-label="操作类型" placeholder="全部操作" style="width: 180px"><el-option label="全部操作" value="" /><el-option label="取消任务" value="task_cancel" /></el-select>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-alert v-if="actionError" :title="actionError" type="error" show-icon />
      <ErrorState v-if="error" :message="error" @retry="load" />
      <EmptyState v-else-if="!loading && !visible.length" title="暂无审批记录" description="新的高风险申请会显示在这里" />
      <el-table v-else :data="visible" v-loading="loading" stripe>
        <el-table-column label="操作内容" min-width="210"><template #default="scope"><strong>{{ scope.row.action === 'task_cancel' ? '取消平台任务' : scope.row.action }}</strong><small class="approval-reason">{{ scope.row.reason }}</small></template></el-table-column>
        <el-table-column label="风险等级" width="100"><template #default><el-tag type="danger" size="small">高风险</el-tag></template></el-table-column>
        <el-table-column label="目标任务" min-width="150"><template #default="scope"><span :title="scope.row.target">{{ scope.row.target.slice(0, 12) }}…</span></template></el-table-column>
        <el-table-column label="申请人" width="150"><template #default="scope"><span class="approval-requester" :title="scope.row.requester">{{ scope.row.requester }}</span></template></el-table-column>
        <el-table-column label="创建时间" width="170"><template #default="scope">{{ new Date(scope.row.createdAt).toLocaleString('zh-CN') }}</template></el-table-column>
        <el-table-column label="操作" width="210"><template #default="scope"><template v-if="scope.row.status === 'pending' && role === 'admin' && scope.row.requester !== auth.user?.username"><el-button link type="primary" :disabled="!!busy" @click="decide(scope.row, 'approve')">批准</el-button><el-button link @click="beginEdit(scope.row)">编辑</el-button><el-button link type="danger" :disabled="!!busy" @click="decide(scope.row, 'reject')">拒绝</el-button></template><span v-else>{{ statusLabels[scope.row.status] || scope.row.status }}</span></template></el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="editOpen" title="编辑申请原因" width="min(500px, 90vw)">
      <p>目标任务：{{ editTarget?.target }}</p>
      <el-input v-model="editReason" type="textarea" :rows="4" maxlength="500" show-word-limit aria-label="审批原因" />
      <template #footer><el-button @click="editOpen = false">取消</el-button><el-button type="primary" :loading="!!busy" :disabled="editReason.trim().length < 3" @click="saveEdit">保存</el-button></template>
    </el-dialog>
  </div>
</template>
