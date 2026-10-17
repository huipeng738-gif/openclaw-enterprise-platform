import axios, {type InternalAxiosRequestConfig} from 'axios'
import {pinia, useAuthStore} from '../stores/auth'

// 所有 REST 请求共用同一个客户端：相对路径由 Nginx（生产）或 Vite（开发）转发到 FastAPI。

interface AuthRequestConfig extends InternalAxiosRequestConfig {
    _retry?: boolean
}

export const http = axios.create({baseURL: '/api', timeout: 30000, withCredentials: true})
// 请求发出前自动附带登录令牌；页面组件只需描述业务路径和数据。

http.interceptors.request.use(config => {
    const auth = useAuthStore(pinia)
    if (auth.accessToken) config.headers.Authorization = `Bearer ${auth.accessToken}`;
    else delete config.headers.Authorization
    return config
})
// 统一处理失效登录态，并把错误继续交给调用页面的 catch 展示。

http.interceptors.response.use(r => r, async e => {
    const config = e.config as AuthRequestConfig | undefined
    if (e.response?.status !== 401 || !config || /^\/auth\/(login|refresh|logout)(?:$|\?)/.test(config.url ?? '')) return Promise.reject(e)
    const auth = useAuthStore(pinia)
    const redirect = () => {
        if (location.pathname !== '/login') location.assign('/login')
    }
    if (config._retry) {
        auth.clear();
        redirect();
        return Promise.reject(e)
    }
    config._retry = true
    try {
        // Late responses for an old token reuse an already refreshed token.
        if (!auth.accessToken || config.headers.Authorization === `Bearer ${auth.accessToken}`) await auth.refresh()
    } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 401) redirect()
        return Promise.reject(error)
    }
    config.headers.Authorization = `Bearer ${auth.accessToken}`
    return http.request(config)
})
