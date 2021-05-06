# yutto [WIP]

<p align="center">
   <a href="https://python.org/" target="_blank"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/yutto?logo=python&style=flat-square"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img src="https://img.shields.io/pypi/v/yutto?style=flat-square" alt="pypi"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/yutto?style=flat-square"></a>
   <a href="LICENSE"><img alt="LICENSE" src="https://img.shields.io/github/license/SigureMo/yutto?style=flat-square"></a>
   <a href="https://gitmoji.carloscuesta.me"><img src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67?style=flat-square" alt="Gitmoji"></a>
</p>

yutto，一个可爱且任性的 B 站下载器（CLI）

## 版本号为什么是 2.0

因为 yutto 是 bilili 的後輩呀～

## 名字的由来

终于在 B 站播放[《転スラ日記》](https://www.bilibili.com/bangumi/play/ep395211)这一天将 yutto 基本流程搭建完了，可以稍微休息一下了（

至于名字嘛，开始只是觉得 yutto 很可爱，印象里是萌王说过的，但具体忘记出处是在哪里了，今天“重温”《転スラ日記》第一话时候，居然 00:25 就是～总之，リムル最可爱啦〜

## 可用程度

安装预览版：

```bash
pip install --pre yutto
```

-  单个视频下载支持、批量下载支持
-  投稿视频支持、番剧支持
-  弹幕支持、字幕支持

现在可以通过以下命令来尝试下载《転スラ日記》第一话

```bash
yutto get -q 64 --danmaku=ass https://www.bilibili.com/bangumi/play/ep395211
```

或者通过 batch get 命令也是可以的

```bash
yutto batch get -q 64 --danmaku=ass https://www.bilibili.com/bangumi/play/ep395211 -p 1
```

更多功能请 `yutto -h` 查看～

## TODO List

-  [ ] `info` 子命令、`batch info` 子命令
-  [ ] 完善的信息提示
-  [ ] 完善的下载进度展示
-  [ ] 字幕、弹幕嵌入视频支持
-  [ ] 更多批下载支持（UP 主、收藏夹等）
-  [ ] 等等等等，以及
-  [ ] 更加可爱～

## References

-  基本结构：<https://github.com/SigureMo/bilili>
-  协程下载：<https://github.com/changmenseng/AsyncBilibiliDownloader>
-  弹幕转换：<https://github.com/ShigureLab/biliass>
