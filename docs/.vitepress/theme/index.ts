import { App } from 'vue'
import DefaultTheme from 'vitepress/theme'
import Layout from './Layout.vue'
import Badge from './components/Badge.vue'
import './index.css'

export default {
  ...DefaultTheme,
  Layout,
  enhanceApp({ app }: { app: App }) {
    app.component('Badge', Badge)
  },
}
