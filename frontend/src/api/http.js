import axios from 'axios';
import { token } from '../stores/auth';
// 所有 REST 请求共用同一个客户端：相对路径由 Nginx（生产）或 Vite（开发）转发到 FastAPI。
export const http = axios.create({ baseURL: '/api', timeout: 30000 });
// 请求发出前自动附带登录令牌；页面组件只需描述业务路径和数据。
http.interceptors.request.use(config => {
    if (token.value)
        config.headers.Authorization = `Bearer ${token.value}`;
    return config;
});
// 统一处理失效登录态，并把错误继续交给调用页面的 catch 展示。
http.interceptors.response.use(r => r, e => {
    if (e.response?.status === 401) {
        token.value = '';
        if (location.pathname !== '/login')
            location.assign('/login');
    }
    return Promise.reject(e);
});
