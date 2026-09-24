<script setup lang="ts">
import { useRouter } from 'vue-router'
import { token, role, logout } from './stores/auth'
const router = useRouter()
function exit() { logout(); router.push('/login') }
</script>
<template>
  <router-view v-if="!token"/>
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
