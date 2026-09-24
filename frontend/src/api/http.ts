import axios from 'axios'
import { token } from '../stores/auth'
export const http = axios.create({ baseURL: '/api', timeout: 30000 })
http.interceptors.request.use(config => { if (token.value) config.headers.Authorization = `Bearer ${token.value}`; return config })
http.interceptors.response.use(r => r, e => { if (e.response?.status === 401) { token.value = ''; if (location.pathname !== '/login') location.assign('/login') } return Promise.reject(e) })
