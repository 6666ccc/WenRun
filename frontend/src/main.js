import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './index.css'
import './views/shared/views.css'
import './styles/clinic-theme.css'

createApp(App).use(createPinia()).use(router).mount('#root')
