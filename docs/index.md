---
layout: home

hero:
   name: yutto
   text: 🧊 一个可爱且任性的 B 站视频下载器
   actions:
      - theme: brand
        text: 从零开始
        link: /guide/quick-start.html
      - theme: alt
        text: 从 bilili 迁移
        link: /migration/
      - theme: alt
        text: GitHub
        link: https://github.com/yutto-dev/yutto
   image:
      src: /logo.png
      alt: yutto-logo
features:
   - icon: ⚡️
     title: 快速下载
     details: 协程 + 分块下载，尽可能地利用并行性
   - icon: 📜
     title: 弹幕支持
     details: 默认支持 ASS 弹幕生成
   - icon: 🔁
     title: 断点续传
     details: 即便一次没下完也可以接着下载～
   - icon: 🌈
     title: 支持类型丰富
     details: 支持投稿视频、番剧、视频合集、收藏夹等的下载
---

<style>
:root {
  --vp-home-hero-name-color: transparent;
  --vp-home-hero-name-background: -webkit-linear-gradient(20deg, #34fefe 30%,#47caff 80%);

  --vp-home-hero-image-background-image: linear-gradient(-20deg, #23f0e2 50%, #47caff 30%);
  --vp-home-hero-image-filter: blur(44px);
}

@media (min-width: 640px) {
  :root {
    --vp-home-hero-image-filter: blur(56px);
  }
}

@media (min-width: 960px) {
  :root {
    --vp-home-hero-image-filter: blur(68px);
  }
}
</style>
