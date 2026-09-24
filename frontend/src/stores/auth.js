import { ref } from 'vue';
// In-memory token; a page reload requires login again.
export const token = ref('');
export const role = ref('');
export function logout() { token.value = ''; role.value = ''; }
