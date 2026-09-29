import { createApp } from 'vue'
import { pinia } from './stores/auth'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './style.css'

createApp(App).use(pinia).use(router).use(ElementPlus).mount('#app')
