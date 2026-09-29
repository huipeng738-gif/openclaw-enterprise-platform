import { computed, ref } from 'vue'
import { createPinia, defineStore, storeToRefs } from 'pinia'
import axios from 'axios'
import { http } from '../api/http'

interface User { username: string; role: string }
interface AuthResponse { access_token: string; user: User }
export const pinia = createPinia()
export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref('')
  const user = ref<User | null>(null)
  const authenticated = computed(() => !!accessToken.value)
  const role = computed(() => user.value?.role ?? '')
  const authInitialized = ref(false)
  const initializationError = ref('')
  const logoutError = ref('')
  let generation = 0
  let refreshPromise: Promise<void> | null = null
  let initializePromise: Promise<void> | null = null
  let loggingOut = false
  function clear() { generation++; accessToken.value = ''; user.value = null }
  function apply(data: AuthResponse) { accessToken.value = data.access_token; user.value = data.user }
  async function login(username: string, password: string) {
    const current = ++generation
    const { data } = await http.post<AuthResponse>('/auth/login', { username, password })
    if (current === generation) { apply(data); authInitialized.value = true; initializationError.value = '' }
  }
  function refresh(): Promise<void> {
    if (loggingOut) return Promise.reject(new Error('正在退出登录'))
    if (refreshPromise) return refreshPromise
    const current = generation
    refreshPromise = http.post<AuthResponse>('/auth/refresh').then(({ data }) => {
      if (current !== generation) throw new Error('登录状态已变化')
      apply(data)
    }).catch(error => {
      if (current === generation && axios.isAxiosError(error) && error.response?.status === 401) clear()
      throw error
    }).finally(() => { refreshPromise = null })
    return refreshPromise
  }
  function initialize(): Promise<void> {
    if (authInitialized.value) return Promise.resolve()
    if (initializePromise) return initializePromise
    initializationError.value = ''
    initializePromise = refresh().then(() => { authInitialized.value = true }).catch(error => {
      if (axios.isAxiosError(error) && error.response?.status === 401) authInitialized.value = true
      else initializationError.value = '无法恢复登录状态，请检查网络后重试'
    }).finally(() => { initializePromise = null })
    return initializePromise
  }
  async function logout() {
    loggingOut = true
    logoutError.value = ''
    clear()
    try {
      await refreshPromise?.catch(() => {})
      await http.post('/auth/logout')
      authInitialized.value = true
    } catch (error) {
      logoutError.value = '退出未完成，请重试以撤销登录会话'
      throw error
    } finally { loggingOut = false }
  }
  return { accessToken, user, authenticated, role, authInitialized, initializationError, logoutError,
    clear, login, refresh, initialize, logout }
})
export const { accessToken: token, role } = storeToRefs(useAuthStore(pinia))
