import { EnhanceAppContext } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import Layout from './Layout.vue'
import 'virtual:group-icons.css'
import './index.css'

export default {
  ...DefaultTheme,
  Layout,
  enhanceApp(ctx: EnhanceAppContext) {
    // extend default theme custom behaviour.
    DefaultTheme.enhanceApp(ctx)
  },
}
