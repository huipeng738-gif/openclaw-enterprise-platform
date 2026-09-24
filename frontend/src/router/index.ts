import { createRouter, createWebHistory } from 'vue-router'
import { token, role } from '../stores/auth'
import Dashboard from '../views/Dashboard.vue'
import Chat from '../views/Chat.vue'
import Agents from '../views/Agents.vue'
import Knowledge from '../views/Knowledge.vue'
import Tasks from '../views/Tasks.vue'
import Login from '../views/Login.vue'
import Audit from '../views/Audit.vue'
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/login', component: Login },
  { path: '/', component: Dashboard }, { path: '/chat', component: Chat },
  { path: '/agents', component: Agents }, { path: '/knowledge', component: Knowledge },
  { path: '/tasks', component: Tasks }, { path: '/audit', component: Audit, meta: {admin: true} }
] })
router.beforeEach(to => { if (to.path !== '/login' && !token.value) return '/login'; if (to.meta.admin && role.value !== 'admin') return '/' })
export default router
