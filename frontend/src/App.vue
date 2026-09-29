<script setup lang="ts">
import { useRouter } from 'vue-router'
import { token, role, pinia, useAuthStore } from './stores/auth'
import { ElMessage } from 'element-plus'
const auth = useAuthStore(pinia)
const router = useRouter()
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
  <el-container v-else class="shell">
    <el-aside width="230px" class="aside"><div class="brand">OpenClaw Enterprise</div>
      <el-menu router :default-active="$route.path" class="menu">
        <el-menu-item index="/">工作台</el-menu-item><el-menu-item index="/chat" v-if="role !== 'viewer'">AI 助手</el-menu-item>
        <el-menu-item index="/agents">Agent 列表</el-menu-item><el-menu-item index="/knowledge" v-if="role !== 'viewer'">知识库</el-menu-item>
        <el-menu-item index="/tasks">任务中心</el-menu-item><el-menu-item index="/audit" v-if="role === 'admin'">审计日志</el-menu-item>
      </el-menu></el-aside>
    <el-container><el-header class="header">企业 AI Agent 管理与应用平台 <el-button @click="exit">退出登录</el-button></el-header><el-main><router-view/></el-main></el-container>
  </el-container>
</template>
