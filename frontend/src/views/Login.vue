<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { pinia, useAuthStore } from '../stores/auth'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

// 提交平台账号密码，认证成功后进入工作空间。
async function login() {
  if (loading.value) return
  error.value = ''
  loading.value = true
  try {
    await useAuthStore(pinia).login(username.value, password.value)
    await router.push('/')
  } catch {
    error.value = '登录失败，请检查账号密码或网络连接'
  } finally { loading.value = false }
}
</script>
<template>
  <main class="login login-page">
    <div class="login-frame">
      <section class="login-hero" aria-label="平台介绍">
        <div class="login-brand"><span class="brand-symbol" aria-hidden="true">企</span><span>企业智能体平台</span></div>
        <div class="hero-content"><span class="hero-eyebrow">ENTERPRISE WORKSPACE</span><h1>让业务协作<br>更高效、更清晰</h1><p>统一管理智能体、业务任务与执行过程，帮助团队稳健推进日常工作。</p><div class="hero-rule" aria-hidden="true"></div><span class="hero-caption">业务协同 · 智能执行 · 过程可追溯</span></div>
        <span class="hero-footer">企业级智能工作空间</span>
      </section>
      <form class="login-panel" @submit.prevent="login">
        <div class="mobile-brand"><span class="brand-symbol" aria-hidden="true">企</span><span>企业智能体平台</span></div>
        <div class="panel-heading"><span class="panel-eyebrow">账号访问</span><h2>欢迎登录</h2><p>使用企业平台账号进入工作空间</p></div>
        <div class="login-fields"><label for="login-username">用户名</label><el-input id="login-username" v-model="username" autocomplete="username" placeholder="请输入用户名" /><label for="login-password">密码</label><el-input id="login-password" v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" show-password /></div>
        <el-alert v-if="error" type="error" :title="error" show-icon />
        <el-button class="login-submit" type="primary" native-type="submit" :loading="loading" :disabled="!username || !password">登录工作空间</el-button>
        <p class="login-assurance">企业内部系统 · 请妥善保管账号信息</p>
      </form>
    </div>
  </main>
</template>

<style scoped>
.login-page { padding: 24px; background: #edf2f7; }
.login-frame { width: min(1020px, 100%); min-height: 610px; display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(390px, .95fr); overflow: hidden; background: #fff; border: 1px solid #dce5ef; border-radius: 20px; box-shadow: 0 24px 70px rgba(19, 43, 71, .11); }
.login-hero { position: relative; display: flex; flex-direction: column; justify-content: space-between; padding: 42px 48px; overflow: hidden; color: #fff; background: linear-gradient(145deg, #102741, #173e63 64%, #24547b); }
.login-hero::before { content: ''; position: absolute; inset: 0; opacity: .15; background: linear-gradient(90deg, transparent 97%, #b8d9ee 98%), linear-gradient(0deg, transparent 97%, #b8d9ee 98%); background-size: 42px 42px; mask-image: linear-gradient(135deg, transparent 15%, #000 100%); }
.login-hero::after { content: ''; position: absolute; width: 350px; height: 350px; right: -115px; bottom: -160px; border: 1px solid rgba(196, 227, 247, .22); border-radius: 50%; box-shadow: 0 0 0 65px rgba(180, 220, 246, .035), 0 0 0 130px rgba(180, 220, 246, .025); }
.login-brand, .hero-content, .hero-footer { position: relative; z-index: 1; }
.login-brand, .mobile-brand { display: flex; align-items: center; gap: 12px; font-size: 18px; font-weight: 700; letter-spacing: .02em; }
.brand-symbol { width: 35px; height: 35px; display: inline-grid; place-items: center; border: 1px solid rgba(255, 255, 255, .45); border-radius: 8px; font-size: 18px; line-height: 1; }
.hero-eyebrow, .panel-eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .19em; }
.hero-eyebrow { color: #9ec6df; }
.hero-content h1 { margin: 18px 0 18px; font-size: clamp(31px, 3.3vw, 44px); line-height: 1.3; letter-spacing: .01em; }
.hero-content p { max-width: 355px; margin: 0; color: #d1e1ed; font-size: 15px; line-height: 1.9; }
.hero-rule { width: 46px; height: 2px; margin: 32px 0 22px; background: #8dc2df; }
.hero-caption, .hero-footer { color: #bad1e2; font-size: 12px; letter-spacing: .06em; }
.login-panel { display: flex; flex-direction: column; justify-content: center; gap: 22px; padding: 64px clamp(32px, 5vw, 76px); }
.mobile-brand { display: none; }
.panel-eyebrow { color: #527ba4; }
.panel-heading h2 { margin: 10px 0; color: #172c42; font-size: 30px; letter-spacing: .02em; }
.panel-heading p { margin: 0; color: #718094; font-size: 14px; }
.login-fields { display: grid; gap: 11px; margin-top: 18px; }
.login-fields label { color: #33495e; font-size: 13px; font-weight: 600; }
.login-fields :deep(.el-input) { margin-bottom: 9px; }
.login-fields :deep(.el-input__wrapper) { min-height: 44px; border-radius: 8px; box-shadow: 0 0 0 1px #dbe4ed inset; }
.login-submit { width: 100%; height: 44px; font-weight: 600; background: #245781; border-color: #245781; }
.login-submit:hover, .login-submit:focus { background: #1b456b; border-color: #1b456b; }
.login-assurance { margin: 0; color: #8a98a8; text-align: center; font-size: 12px; }
@media (max-width: 760px) { .login-page { padding: 16px; } .login-frame { max-width: 460px; min-height: auto; grid-template-columns: 1fr; } .login-hero { display: none; } .login-panel { min-height: 560px; padding: 36px 30px; } .mobile-brand { display: flex; margin-bottom: 20px; color: #173e63; } .mobile-brand .brand-symbol { border-color: #b9cbda; } }
@media (max-width: 420px) { .login-frame { border-radius: 14px; } .login-panel { padding: 32px 23px; } }
</style>
