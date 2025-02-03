import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'yutto',
  description: '🧊 yutto，一个可爱且任性的 B 站下载器（CLI）',
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '指南', link: '/guide/quick-start' },
      { text: '参考', link: '/reference/cli' },
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
          ],
          collapsed: false,
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
      '/reference': [
        {
          text: '参考',
          items: [
            {
              text: '命令行参数',
              link: '/reference/cli',
            },
            {
              text: '配置',
              link: '/reference/config',
            },
            {
              text: '详细参数',
              items: [
                {
                  text: '基础参数',
                  link: '/reference/arguments-basic',
                },
                {
                  text: '批量参数',
                  link: '/reference/arguments-batch',
                },
                {
                  text: '弹幕参数',
                  link: '/reference/arguments-danmaku',
                },
              ],
            },
          ],
        },
      ],
    },

    footer: {
      message: 'Released under the GPL3.0 License.',
      copyright: 'Copyright © 2025-present Nyakku Shigure',
    },

    editLink: {
      pattern: 'https://github.com/yutto-dev/yutto/edit/main/docs/:path',
      text: '为此页提供修改建议',
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/yutto-dev/yutto' },
      { icon: 'discord', link: 'https://discord.gg/5cQGyFwsqC' },
    ],

    search: {
      provider: 'local',
    },
  },
})
