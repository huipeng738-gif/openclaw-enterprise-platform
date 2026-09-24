<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '../api/http'
import { token, role } from '../stores/auth'
const router = useRouter()
const username = ref(''); const password = ref(''); const error = ref('')
async function login() {
  error.value = ''
  try { const {data} = await http.post('/auth/login', {username: username.value, password: password.value}); token.value = data.access_token; role.value = data.role; router.push('/') }
  catch { error.value = '用户名或密码错误' }
}
</script>
<template><div class="login"><div class="card"><h2>企业 AI 平台登录</h2><el-input v-model="username" placeholder="用户名"/><el-input v-model="password" type="password" placeholder="密码" show-password @keyup.enter="login"/><el-alert v-if="error" type="error" :title="error"/><el-button type="primary" @click="login">登录</el-button></div></div></template>
