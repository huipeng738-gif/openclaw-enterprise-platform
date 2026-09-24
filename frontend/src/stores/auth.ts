import { ref } from 'vue'
// In-memory token; a page reload requires login again.
// 前端统一保存当前登录状态
export const token = ref('')
export const role = ref('')
export function logout() { token.value = ''; role.value = '' }
