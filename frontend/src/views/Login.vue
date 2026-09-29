<script setup lang="ts">
import {ref} from 'vue'
import {useRouter} from 'vue-router'
import {pinia, useAuthStore} from '../stores/auth'

const router = useRouter()
const username = ref('');
const password = ref('');
const error = ref('')

// 提交登录信息，保存返回的令牌和角色后进入工作台；失败时显示错误。
async function login() {
  error.value = ''
  try {
    await useAuthStore(pinia).login(username.value, password.value)
    router.push('/')
  } catch {
    error.value = '用户名或密码错误'
  }
}
</script>
<template>
  <div class="login">
    <div class="card"><h2>企业 AI 平台登录</h2>
      <el-input v-model="username" placeholder="用户名"/>
      <el-input v-model="password" type="password" placeholder="密码" show-password @keyup.enter="login"/>
      <el-alert v-if="error" type="error" :title="error"/>
      <el-button type="primary" @click="login">登录</el-button>
    </div>
  </div>
</template>
