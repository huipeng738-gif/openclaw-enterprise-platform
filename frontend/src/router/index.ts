import {createRouter, createWebHistory} from 'vue-router'
import {pinia, useAuthStore} from '../stores/auth'
import Dashboard from '../views/Dashboard.vue'
import Chat from '../views/Chat.vue'
import Agents from '../views/Agents.vue'
import Knowledge from '../views/Knowledge.vue'
import Tasks from '../views/Tasks.vue'
import Login from '../views/Login.vue'
import Audit from '../views/Audit.vue'
import Analytics from '../views/Analytics.vue'
import Orders from '../views/Orders.vue'
import Customers from '../views/Customers.vue'
import Approvals from '../views/Approvals.vue'
import Monitor from '../views/Monitor.vue'
import Settings from '../views/Settings.vue'

const router = createRouter({
    history: createWebHistory(), routes: [
        {path: '/login', component: Login},
        {path: '/', alias: '/dashboard', component: Dashboard}, {
            path: '/chat',
            component: Chat,
            meta: {roles: ['operator', 'admin']}
        },
        {path: '/agents', component: Agents}, {
            path: '/knowledge',
            component: Knowledge,
            meta: {roles: ['operator', 'admin']}
        },
        {path: '/analytics', component: Analytics, meta: {roles: ['operator', 'admin']}},
        {path: '/orders', component: Orders, meta: {roles: ['operator', 'admin']}},
        {path: '/customers', component: Customers, meta: {roles: ['operator', 'admin']}},
        {path: '/tasks', component: Tasks}, {
            path: '/approvals',
            component: Approvals,
            meta: {roles: ['operator', 'admin']}
        },
        {path: '/audit', component: Audit, meta: {admin: true}},
        {path: '/monitor', component: Monitor, meta: {admin: true}},
        {path: '/settings', component: Settings, meta: {admin: true}}
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
    if (Array.isArray(to.meta.roles) && !to.meta.roles.includes(auth.role)) return '/'
})
export default router
