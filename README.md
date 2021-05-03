# yutto [WIP]

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

现在只能简单地下载视频，字幕弹幕等功能还没有做。

由于 yutto 的弹幕支持方式可能需要考虑一段时间，暂时我不太想用 danmaku2ass，所以关于弹幕的支持会延后一段时间。

现在可以通过以下命令来尝试下载《転スラ日記》第一话

```bash
yutto -q 64 get https://www.bilibili.com/bangumi/play/ep395211
```

或者通过 batch get 命令也是可以的

```bash
yutto -q 64 batch get https://www.bilibili.com/bangumi/play/ep395211 -p 1
```

## TODO List

-  [ ] 好多，不知道该写些啥，等剩余任务较少时候再来写吧……

## References

-  基本结构：<https://github.com/SigureMo/bilili>
-  协程下载：<https://github.com/changmenseng/AsyncBilibiliDownloader>
