import {createRouter, createWebHistory} from 'vue-router'
import {pinia, useAuthStore} from '../stores/auth'
import Dashboard from '../views/Dashboard.vue'
import Chat from '../views/Chat.vue'
import Agents from '../views/Agents.vue'
import Knowledge from '../views/Knowledge.vue'
import Tasks from '../views/Tasks.vue'
import Login from '../views/Login.vue'
import Audit from '../views/Audit.vue'

const router = createRouter({
    history: createWebHistory(), routes: [
        {path: '/login', component: Login},
        {path: '/', component: Dashboard}, {path: '/chat', component: Chat},
        {path: '/agents', component: Agents}, {path: '/knowledge', component: Knowledge},
        {path: '/tasks', component: Tasks}, {path: '/audit', component: Audit, meta: {admin: true}}
    ]
})
//全局路由守卫
router.beforeEach(async to => {
    const auth = useAuthStore(pinia)
    await auth.initialize()
    if (!auth.authInitialized) return false
    if (to.path !== '/login' && !auth.authenticated) return '/login';
    if (to.path === '/login' && auth.authenticated) return '/'
    if (to.meta.admin && auth.role !== 'admin') return '/'
})
export default router
