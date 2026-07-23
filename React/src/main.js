import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './index.css'
import './views/shared/views.css'

createApp(App).use(router).mount('#root')
