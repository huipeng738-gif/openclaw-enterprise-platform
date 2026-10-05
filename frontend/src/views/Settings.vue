<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '../api/http'
import PageHeader from '../components/common/PageHeader.vue'

interface Account { username: string; role: string; disabled: boolean }
interface Policy { version: number; defaultTimeoutSeconds: number; submissionsPaused: boolean; updatedAt?: string }
interface Dependency { name: string; status: string; checkedAt: string | null; detail: string }
const users = ref<Account[]>([])
const policy = ref<Policy>({ version: 0, defaultTimeoutSeconds: 180, submissionsPaused: false })
const dependencies = ref<Dependency[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const createOpen = ref(false)
const createForm = ref({ username: '', password: '', role: 'operator' })
const formError = ref('')

// 同时读取 MySQL 账号、有效任务策略及真实依赖探测。
async function load() {
  loading.value = true; error.value = ''
  try {
    const [accounts, currentPolicy, health] = await Promise.all([
      http.get<Account[]>('/users'), http.get<Policy>('/settings/task-policy'),
      http.get<Dependency[]>('/settings/dependencies')
    ])
    users.value = accounts.data; policy.value = currentPolicy.data; dependencies.value = health.data
  } catch { error.value = '系统设置加载失败，请重试' }
  finally { loading.value = false }
}

// 提交新账号并刷新列表；密码仅用于本次请求。
async function createUser() {
  formError.value = ''
  if (!/^[A-Za-z_][A-Za-z0-9_]{0,79}$/.test(createForm.value.username) || createForm.value.password.length < 12) {
    formError.value = '用户名需为字母、数字或下划线，密码至少 12 位'; return
  }
  saving.value = true
  try {
    await http.post('/users', createForm.value)
    createOpen.value = false; createForm.value = { username: '', password: '', role: 'operator' }
    users.value = (await http.get<Account[]>('/users')).data
    ElMessage.success('账号已创建')
  } catch { formError.value = '创建失败，请检查用户名是否已存在' }
  finally { saving.value = false }
}

// 经管理员确认后变更角色，立即刷新 MySQL 中的生效值。
async function changeRole(account: Account, role: string) {
  try { await ElMessageBox.confirm(`将 ${account.username} 的角色改为 ${role}？旧登录会话会失效。`, '修改角色') }
  catch { return }
  try {
    await http.put(`/users/${encodeURIComponent(account.username)}/role`, { role })
    users.value = (await http.get<Account[]>('/users')).data
    ElMessage.success('角色已更新')
  } catch { ElMessage.error('角色更新失败；最后一个可用管理员不能降权'); await load() }
}

// 停用或恢复账号；停用会撤销旧会话，恢复后需重新登录。
async function toggleUser(account: Account) {
  try { await ElMessageBox.confirm(`${account.disabled ? '恢复' : '停用'}账号 ${account.username}？`, '账号状态') }
  catch { return }
  try {
    await http.put(`/users/${encodeURIComponent(account.username)}/availability`, { disabled: !account.disabled })
    users.value = (await http.get<Account[]>('/users')).data
    ElMessage.success('账号状态已更新')
  } catch { ElMessage.error('状态更新失败；最后一个可用管理员不能停用'); await load() }
}

// 输入新密码后提交重置；旧 Access/Refresh Token 随会话版本递增失效。
async function resetPassword(account: Account) {
  let password: string
  try {
    const result = await ElMessageBox.prompt(`为 ${account.username} 设置新密码（至少 12 位）`, '重置密码', {
      inputType: 'password', inputValidator: value => value.length >= 12 || '密码至少 12 位'
    })
    password = result.value
  } catch { return }
  try {
    await http.put(`/users/${encodeURIComponent(account.username)}/password`, { password })
    ElMessage.success('密码已重置，旧会话已失效')
  } catch { ElMessage.error('密码重置失败，请重试') }
}

// 使用版本号保存策略；冲突时刷新，避免覆盖另一位管理员的修改。
async function savePolicy() {
  saving.value = true
  try {
    policy.value = (await http.put<Policy>('/settings/task-policy', policy.value)).data
    ElMessage.success('策略已生效，新任务将使用当前设置')
  } catch {
    ElMessage.error('保存失败或策略已被其他管理员修改，已重新加载')
    policy.value = (await http.get<Policy>('/settings/task-policy')).data
  } finally { saving.value = false }
}

// 将探测时间显示到秒，缺失时保持未知。
function timeText(value: string | null) { return value ? new Date(value).toLocaleString('sv-SE') : '未检测' }
onMounted(load)
</script>

<template>
  <div class="settings-page">
    <PageHeader title="系统设置" description="管理账号权限、任务策略与依赖状态">
      <template #actions><el-button :loading="loading" @click="load">刷新状态</el-button></template>
    </PageHeader>
    <el-alert v-if="error" :title="error" type="error" show-icon class="settings-alert" />
    <section class="card">
      <div class="settings-section-head"><div><h2>账号与权限</h2><p>账号保存在 MySQL。角色或密码变更后，旧登录会话立即失效。</p></div><el-button type="primary" @click="createOpen = true">新建账号</el-button></div>
      <el-table :data="users" v-loading="loading" empty-text="暂无账号" class="settings-table">
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column label="角色" min-width="145"><template #default="{ row }"><el-select :model-value="row.role" :aria-label="`角色 ${row.username}`" @change="(value: string) => changeRole(row, value)"><el-option label="查看者" value="viewer" /><el-option label="操作员" value="operator" /><el-option label="管理员" value="admin" /></el-select></template></el-table-column>
        <el-table-column label="状态" min-width="90"><template #default="{ row }"><el-tag :type="row.disabled ? 'info' : 'success'">{{ row.disabled ? '已停用' : '正常' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" min-width="190"><template #default="{ row }"><el-button link @click="resetPassword(row)">重置密码</el-button><el-button link :type="row.disabled ? 'primary' : 'danger'" @click="toggleUser(row)">{{ row.disabled ? '恢复' : '停用' }}</el-button></template></el-table-column>
      </el-table>
    </section>
    <section class="card"><div class="settings-section-head"><div><h2>任务策略</h2><p>默认超时用于未指定超时的新任务；暂停只影响新提交与重试，已运行任务继续执行。</p></div></div>
      <div class="settings-policy"><label>默认超时（秒）<el-input-number v-model="policy.defaultTimeoutSeconds" :min="10" :max="1800" /></label><label>暂停新任务提交 <el-switch v-model="policy.submissionsPaused" /></label><el-button type="primary" :loading="saving" @click="savePolicy">保存策略</el-button></div>
      <p class="settings-note">当前版本 {{ policy.version }} · 最近更新 {{ timeText(policy.updatedAt || null) }}</p>
    </section>
    <section class="card"><div class="settings-section-head"><div><h2>依赖诊断</h2><p>来自实际连接探测和带有效期的 Worker/Gateway 心跳。</p></div><el-button @click="load">重新检测</el-button></div>
      <div class="settings-dependencies"><div v-for="item in dependencies" :key="item.name" class="settings-dependency"><strong>{{ item.name }}</strong><el-tag :type="item.status === 'online' ? 'success' : item.status === 'offline' ? 'danger' : 'info'">{{ item.status === 'online' ? '在线' : item.status === 'offline' ? '离线' : item.status === 'unconfigured' ? '未配置' : '未知' }}</el-tag><small>{{ item.detail }}</small><small>{{ timeText(item.checkedAt) }}</small></div></div>
      <div class="settings-links"><router-link to="/monitor">查看运行监控</router-link><router-link to="/audit">查看审计日志</router-link></div>
      <p class="settings-note">密钥、Gateway Token 与连接密码由部署配置管理；此页仅展示服务状态。</p>
    </section>
    <el-dialog v-model="createOpen" title="新建账号" width="min(480px, 96vw)"><el-form label-position="top"><el-form-item label="用户名"><el-input v-model="createForm.username" maxlength="80" autocomplete="off" /></el-form-item><el-form-item label="密码"><el-input v-model="createForm.password" type="password" show-password autocomplete="new-password" /></el-form-item><el-form-item label="角色"><el-select v-model="createForm.role" style="width:100%"><el-option label="查看者" value="viewer" /><el-option label="操作员" value="operator" /><el-option label="管理员" value="admin" /></el-select></el-form-item><el-alert v-if="formError" :title="formError" type="error" :closable="false" /></el-form><template #footer><el-button @click="createOpen = false">取消</el-button><el-button type="primary" :loading="saving" @click="createUser">创建</el-button></template></el-dialog>
  </div>
</template>

<style scoped>
.settings-page { max-width: 1200px; margin: 0 auto; }
.settings-alert { margin-bottom: 16px; }
.settings-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.settings-section-head h2 { margin: 0; font-size: 18px; }
.settings-section-head p, .settings-note { color: var(--oc-muted); font-size: 13px; margin: 7px 0 0; }
.settings-table { width: 100%; }
.settings-policy { display: flex; flex-wrap: wrap; align-items: end; gap: 24px; }
.settings-policy label { display: flex; flex-direction: column; align-items: flex-start; gap: 9px; font-size: 13px; }
.settings-dependencies { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: 12px; }
.settings-dependency { border: 1px solid var(--oc-border); border-radius: var(--oc-radius); padding: 15px; display: flex; flex-direction: column; align-items: flex-start; gap: 7px; }
.settings-dependency small { color: var(--oc-muted); }
.settings-links { display: flex; gap: 20px; margin-top: 18px; }
@media (max-width: 600px) { .settings-section-head { flex-wrap: wrap; } .settings-table { overflow-x: auto; } }
</style>
