import { defineConfig } from 'vitepress'
import {
  groupIconMdPlugin,
  groupIconVitePlugin,
  localIconLoader,
} from 'vitepress-plugin-group-icons'

export default defineConfig({
  lang: 'zh-CN',
  title: 'yutto',
  description: '🧊 yutto，一个可爱且任性的 B 站下载器（CLI）',
  cleanUrls: true,
  head: [['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo-mini.svg' }]],
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '指南', link: '/guide/quick-start' },
      { text: '迁移', link: '/migration/' },
      {
        text: '支持我',
        items: [
          { text: '赞助', link: '/sponsor' },
          {
            text: '参与贡献',
            link: 'https://github.com/yutto-dev/yutto/blob/main/CONTRIBUTING.md',
          },
        ],
      },
    ],

    sidebar: {
      '/guide': [
        {
          text: '开始',
          items: [
            {
              text: '快速开始',
              link: '/guide/quick-start',
            },
            {
              text: '支持的链接',
              link: '/guide/supported-links',
            },
            {
              text: '命令行参数',
              link: '/guide/cli',
              collapsed: false,
              items: [
                {
                  text: '基础参数',
                  link: '/guide/cli/basic',
                },
                {
                  text: '资源选择参数',
                  link: '/guide/cli/resource',
                },
                {
                  text: '弹幕设置参数',
                  link: '/guide/cli/danmaku',
                },
                {
                  text: '批量下载参数',
                  link: '/guide/cli/batch',
                },
              ],
            },
          ],
        },
        {
          text: '小技巧',
          link: '/guide/tips',
        },
        {
          text: 'FAQ',
          link: '/guide/faq',
        },
        {
          text: '交流和反馈',
          link: '/guide/feedback',
        },
        {
          text: '注意事项',
          link: '/guide/notice',
        },
        {
          text: '特别感谢',
          link: '/guide/thanks',
        },
      ],
    },

    footer: {
      message: 'Released under the GPL3.0 License.',
      copyright: 'Copyright © 2025-present Nyakku Shigure',
    },

    editLink: {
      pattern: 'https://github.com/yutto-dev/yutto/edit/main/docs/:path',
      text: '欸？我刚刚哪里说错了？你可以帮我改正一下哦～',
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/yutto-dev/yutto' },
      { icon: 'discord', link: 'https://discord.gg/5cQGyFwsqC' },
    ],

    search: {
      provider: 'local',
    },
  },

  markdown: {
    image: {
      lazyLoading: true,
    },
    config(md) {
      md.use(groupIconMdPlugin)
    },
  },
  vite: {
    plugins: [
      groupIconVitePlugin({
        customIcon: {
          yutto: localIconLoader(import.meta.url, '../public/logo-mini.svg'),
        },
      }) as any,
    ],
  },
})
