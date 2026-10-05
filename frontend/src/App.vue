<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { token, role, pinia, useAuthStore } from './stores/auth'
import { ElMessage } from 'element-plus'
import { http } from './api/http'
import { House, ChatDotRound, Avatar, Reading, Tickets, User, DataAnalysis, List, Document, Checked, Monitor, Setting } from '@element-plus/icons-vue'
const auth = useAuthStore(pinia)
const router = useRouter()
const titles: Record<string, string> = { '/': '总览', '/dashboard': '总览', '/chat': 'AI 助手', '/agents': 'Agent 管理', '/knowledge': '知识库', '/orders': '订单管理', '/customers': '客户管理', '/analytics': '数据分析', '/tasks': '任务中心', '/approvals': '人工审批', '/monitor': '运行监控', '/audit': '审计日志', '/settings': '系统设置' }
const pageTitle = computed(() => titles[router.currentRoute.value.path] || '工作空间')
interface GatewayStatus { status: 'online' | 'offline' | 'unknown'; checkedAt: string | null; latencyMs: number | null }
const gateway = ref<GatewayStatus>({ status: 'unknown', checkedAt: null, latencyMs: null })
const gatewayLabel = computed(() => ({ online: '在线', offline: '离线', unknown: '未知' })[gateway.value.status])
let gatewayTimer: number | undefined
let gatewayRequest = 0
// 只读获取 Worker 最近一次真实 Gateway 握手结果，不把 API 健康误认为 Gateway 健康。
async function loadGateway() {
  if (!auth.authenticated) return
  const request = ++gatewayRequest
  try {
    const result = (await http.get<GatewayStatus>('/runtime/gateway')).data
    if (request === gatewayRequest) gateway.value = result
  } catch { if (request === gatewayRequest) gateway.value = { status: 'unknown', checkedAt: null, latencyMs: null } }
}
watch(() => auth.authenticated, authenticated => {
  if (authenticated) void loadGateway()
  else { gatewayRequest++; gateway.value = { status: 'unknown', checkedAt: null, latencyMs: null } }
}, { immediate: true })
onMounted(() => { gatewayTimer = window.setInterval(() => { void loadGateway() }, 30000) })
onUnmounted(() => { if (gatewayTimer != null) window.clearInterval(gatewayTimer); gatewayRequest++ })
// 清空当前登录状态并跳转到登录页。
async function exit() {
  try { await auth.logout(); await router.push('/login') }
  catch { ElMessage.error('退出未完成，请重试以撤销登录会话') }
}
async function retryInitialize() { await auth.initialize(); if (auth.authInitialized) router.replace(location.pathname + location.search) }
</script>
<template>
  <div v-if="auth.logoutError" class="login">
    <div>{{ auth.logoutError }} <el-button @click="exit">重试退出</el-button></div>
  </div>
  <div v-else-if="!auth.authInitialized" class="login">
    <div v-if="auth.initializationError">{{ auth.initializationError }} <el-button @click="retryInitialize">重试</el-button></div>
    <span v-else>正在恢复登录状态…</span>
  </div>
  <router-view v-else-if="!token"/>
  <el-container v-else class="shell chat-shell">
    <el-aside width="240px" class="aside"><div class="brand">企业智能体平台</div>
      <el-menu router :default-active="$route.path === '/dashboard' ? '/' : $route.path" class="menu">
        <div class="menu-group">工作空间</div>
        <el-menu-item index="/"><el-icon><House /></el-icon><span>总览</span></el-menu-item>
        <el-menu-item index="/chat" v-if="role !== 'viewer'"><el-icon><ChatDotRound /></el-icon><span>AI 助手</span></el-menu-item>
        <el-menu-item index="/agents"><el-icon><Avatar /></el-icon><span>Agent 管理</span></el-menu-item>
        <div v-if="role !== 'viewer'" class="menu-group">企业数据</div>
        <el-menu-item index="/knowledge" v-if="role !== 'viewer'"><el-icon><Reading /></el-icon><span>知识库</span></el-menu-item>
        <el-menu-item index="/orders" v-if="role !== 'viewer'"><el-icon><Tickets /></el-icon><span>订单管理</span></el-menu-item>
        <el-menu-item index="/customers" v-if="role !== 'viewer'"><el-icon><User /></el-icon><span>客户管理</span></el-menu-item>
        <el-menu-item index="/analytics" v-if="role !== 'viewer'"><el-icon><DataAnalysis /></el-icon><span>数据分析</span></el-menu-item>
        <div class="menu-group">运营管理</div>
        <el-menu-item index="/tasks"><el-icon><List /></el-icon><span>任务中心</span></el-menu-item>
        <el-menu-item index="/approvals" v-if="role !== 'viewer'"><el-icon><Checked /></el-icon><span>人工审批</span></el-menu-item>
        <el-menu-item index="/monitor" v-if="role === 'admin'"><el-icon><Monitor /></el-icon><span>运行监控</span></el-menu-item>
        <el-menu-item index="/audit" v-if="role === 'admin'"><el-icon><Document /></el-icon><span>审计日志</span></el-menu-item>
        <div v-if="role === 'admin'" class="menu-group">系统</div>
        <el-menu-item v-if="role === 'admin'" index="/settings"><el-icon><Setting /></el-icon><span>系统设置</span></el-menu-item>
      </el-menu></el-aside>
    <el-container><el-header class="header">
      <el-breadcrumb separator="/"><el-breadcrumb-item>工作空间</el-breadcrumb-item><el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item></el-breadcrumb>
      <div class="header-actions"><span class="gateway-state" :title="gateway.checkedAt ? `最近检测：${gateway.checkedAt}` : '暂无有效检测记录'">Gateway {{ gatewayLabel }}</span><span>{{ auth.user?.username }} · {{ role }}</span><el-button @click="exit">退出登录</el-button></div>
    </el-header><el-main><router-view/></el-main></el-container>
  </el-container>
</template>
