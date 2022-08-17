import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'yutto',
  description: 'yutto docs',
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '指引', link: '/guide/quick-start.html' },
      { text: '迁移', link: '/migration/' },
    ],

    sidebar: {
      '/guide': [
        {
          text: '',
          items: [
            {
              text: '快速开始',
              link: '/guide/quick-start.html',
            },
            {
              text: '支持的链接',
              link: '/guide/supported-links.html',
            },
            {
              text: '命令行参数',
              link: '/guide/cli.html',
            },
          ],
        },
      ],
    },

    footer: {
      message: 'Released under the GPL3.0 License.',
      copyright: 'Copyright © 2022-present Nyakku Shigure',
    },

    editLink: {
      pattern: 'https://github.com/yutto-dev/yutto/edit/main/docs/:path',
      text: '为此页提供修改建议',
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/yutto-dev/yutto' },
      { icon: 'discord', link: 'https://discord.gg/5cQGyFwsqC' },
    ],
  },
})
