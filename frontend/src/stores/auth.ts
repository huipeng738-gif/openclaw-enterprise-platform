import {computed, ref} from 'vue'
import {createPinia, defineStore, storeToRefs} from 'pinia'
import axios from 'axios'
import {http} from '../api/http'

interface User {
    username: string;
    role: string
}

interface AuthResponse {
    access_token: string;
    user: User
}

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

    // 清除内存中的登录信息，并使此前发起的认证请求结果失效。
    function clear() {
        generation++;
        accessToken.value = '';
        user.value = null
    }

    // 将登录或刷新接口返回的令牌和用户信息写入当前状态。
    function apply(data: AuthResponse) {
        accessToken.value = data.access_token;
        user.value = data.user
    }

    // 使用账号密码登录；仅接受当前这次登录请求的结果
    async function login(username: string, password: string) {

        // 1. 登录请求编号加 1，记录当前请求的编号
        const current = ++generation

        // 2. 调用 FastAPI 登录接口，等待后端响应
        // <AuthResponse> 指定预期响应数据的 TypeScript 类型
        // {data} 从 Axios 响应对象中提取 data 属性
        const {data} = await http.post<AuthResponse>(
            '/auth/login',
            {username, password}
        )

        // 3. 判断这次登录请求是否仍然有效
        if (current === generation) {

            // 4. 保存后端返回的 Access Token 和用户信息
            apply(data)

            // 5. 标记认证初始化完成
            authInitialized.value = true

            // 6. 清除之前的登录初始化错误
            initializationError.value = ''
        }
    }

    // 刷新访问令牌，并复用正在进行的刷新请求以避免并发重复调用。
    function refresh(): Promise<void> {
        if (loggingOut) return Promise.reject(new Error('正在退出登录'))
        if (refreshPromise) return refreshPromise
        const current = generation
        refreshPromise = http.post<AuthResponse>('/auth/refresh').then(({data}) => {
            if (current !== generation) throw new Error('登录状态已变化')
            apply(data)
        }).catch(error => {
            if (current === generation && axios.isAxiosError(error) && error.response?.status === 401) clear()
            throw error
        }).finally(() => {
            refreshPromise = null
        })
        return refreshPromise
    }

    // 页面启动时尝试恢复登录状态，并区分会话失效与网络错误。
    function initialize(): Promise<void> {
        if (authInitialized.value) return Promise.resolve()
        if (initializePromise) return initializePromise
        initializationError.value = ''
        initializePromise = refresh().then(() => {
            authInitialized.value = true
        }).catch(error => {
            if (axios.isAxiosError(error) && error.response?.status === 401) authInitialized.value = true
            else initializationError.value = '无法恢复登录状态，请检查网络后重试'
        }).finally(() => {
            initializePromise = null
        })
        return initializePromise
    }

    // 清除本地登录状态并通知服务端撤销刷新会话。
    async function logout() {
        loggingOut = true
        logoutError.value = ''
        clear()
        try {
            await refreshPromise?.catch(() => {
            })
            await http.post('/auth/logout')
            authInitialized.value = true
        } catch (error) {
            logoutError.value = '退出未完成，请重试以撤销登录会话'
            throw error
        } finally {
            loggingOut = false
        }
    }

    return {
        accessToken, user, authenticated, role, authInitialized, initializationError, logoutError,
        clear, login, refresh, initialize, logout
    }
})
export const {accessToken: token, role} = storeToRefs(useAuthStore(pinia))
