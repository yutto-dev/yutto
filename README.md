# yutto [WIP]

<p align="center">
   <a href="https://python.org/" target="_blank"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/yutto?logo=python&style=flat-square"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img src="https://img.shields.io/pypi/v/yutto?style=flat-square" alt="pypi"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/yutto?style=flat-square"></a>
   <a href="LICENSE"><img alt="LICENSE" src="https://img.shields.io/github/license/SigureMo/yutto?style=flat-square"></a>
   <a href="https://gitmoji.dev"><img src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67?style=flat-square" alt="Gitmoji"></a>
</p>

yutto，一个可爱且任性的 B 站下载器（CLI）

## 版本号为什么是 2.0

因为 yutto 是 bilili 的後輩呀～

## 名字的由来

终于在 B 站播放[《転スラ日記》](https://www.bilibili.com/bangumi/play/ep395211)这一天将 yutto 基本流程搭建完了，可以稍微休息一下了（

至于名字嘛，开始只是觉得 yutto 很可爱，印象里是萌王说过的，但具体忘记出处是在哪里了，今天“重温”《転スラ日記》第一话时候，居然 00:25 就是～总之，リムル最可爱啦〜

## 安装预览版

在此之前请确保安装 Python3.9（不支持 3.8 及以下，3.10 尚处于 beta，没有测试）与 FFmpeg（参照 [bilili 文档](https://bilili.sigure.xyz/guide/getting-started.html)）

### pip 安装

```bash
pip install --pre yutto
```

### git clone

```bash
git clone https://github.com/SigureMo/yutto.git
python setup.py build
python setup.py install
```

## 功能预览

### 基本命令

你可以通过 get 子命令来下载**一个**视频。它支持 av/BV 号以及相应带 p=n 参数的投稿视频页面，也支持 ep 号（episode_id）的番剧页面。

比如只需要这样你就可以下载《転スラ日記》第一话：

```bash
yutto get https://www.bilibili.com/bangumi/play/ep395211
```

不过有时你可能想要批量下载很多剧集，因此 yutto 提供了用于批量下载的子命令 `batch get`，它不仅支持前面所说的单个视频所在页面地址（会解析该单个视频所在的系列视频），还支持一些明确用于表示系列视频的地址，比如 md 页面（media_id）、ss 页面（season_id）。

比如像下面这样就可以下载《転スラ日記》所有已更新的剧集：

```bash
yutto batch get https://www.bilibili.com/bangumi/play/ep395211
```

### 基础参数

> 大部分参数与 bilili 重合，可参考 [bilili 的 cli 文档](https://bilili.nyakku.moe/cli/)

yutto 支持一些基础参数，是在 `get` 与 `batch get` 子命令中都可以使用的。

<details>
<summary>点击展开详细参数</summary>

#### 最大并行 worker 数量

-  参数 `-n` 或 `--num-workers`
-  默认值 `8`

与 bilili 不同的是，yutto 并不是使用多线程实现并行下载，而是使用协程实现的，本参数限制的是最大的并行 Worker 数量。

#### 视频质量

-  参数 `-q` 或 `--video-quality`
-  可选值 `125 | 120 | 116 | 112 | 80 | 74 | 64 | 32 | 16`
-  默认值 `125`

用于调节视频清晰度（详情可参考 bilili 文档）。

#### 音频质量

-  参数 `-aq` 或 `--audio-quality`
-  可选值 `30280 | 30232 | 30216`
-  默认值 `30280`

用于调节音频码率（详情可参考 bilili 文档）。

#### 视频编码

-  参数 `--vcodec`
-  下载编码可选值 `hevc | avc`
-  保存编码可选值 FFmpeg 所有可用的视频编码器
-  默认值 `avc:copy`

该参数略微复杂，前半部分表示在下载时**优先**选择哪一种编码的视频流，后半部分则表示在合并时如何编码视频流，两者使用 `:` 分隔。

值得注意的是，前半的下载编码只是优先下载的编码而已，如果不存在该编码，则仍会像视频清晰度调节机制一样自动选择其余编码。

而后半部分的参数如果设置成非 `copy` 的值则可以确保在下载完成后对其进行重新编码，而且不止支持 `hevc` 与 `avc`，只要你的 FFmpeg 支持的视频编码器，它都可以完成。

#### 音频编码

-  参数 `--acodec`
-  下载编码可选值 `mp4a`
-  保存编码可选值 FFmpeg 所有可用的音频编码器
-  默认值 `mp4a:copy`

详情同视频编码。

#### 仅下载视频流

-  参数 `--only-video`
-  默认值 `False`

#### 仅下载音频流

-  参数 `--only-audio`
-  默认值 `False`

仅下载其中的音频流，保存为 `.aac` 文件。

值得注意的是，在不选择视频流时，嵌入字幕、弹幕功能将无法工作。

#### 弹幕格式选择

-  参数 `-df` 或 `--danmaku-format`
-  可选值 `ass | xml | protobuf`
-  默认值 `ass`

#### 下载块大小

-  参数 `-b` 或 `--block-size`
-  默认值 `0.5`

以 MiB 为单位，为分块下载时各块大小，不建议更改。

#### 强制覆盖已下载文件

-  参数 `-w` 或 `--overwrite`
-  默认值 `False`

#### 代理设置

-  参数 `-x` 或 `--proxy`
-  可选值 `auto | no | <https?://url/to/proxy/server>`
-  默认值 `auto`

设置代理服务器，默认是从环境变量读取，`no` 则为不设置代理，设置其它 http/https url 则将其作为代理服务器。

#### 存放根目录

-  参数 `-d` 或 `--dir`
-  默认值 `./`

#### 存放子路径模板

-  参数 `-tp` 或 `--subpath-template`
-  可选参数变量 `title | id | name` （以后可能会有更多）
-  默认值 `{auto}`

通过配置子路径模板可以灵活地控制视频存放位置。

默认情况是由 yutto 自动控制存放位置的。比如下载单个视频时默认就是直接存放在设定的根目录，不会创建一层容器目录，此时自动选择了 `{name}` 作为模板；而批量下载时则会根据视频层级生成多级目录，比如番剧会是 `{title}/{name}`，首先会在设定根目录里生成一个番剧名的目录，其内才会存放各个番剧剧集视频，这样方便了多个不同番剧的管理。当然，如果你仍希望将番剧直接存放在设定根目录下的话，可以修改该参数值为 `{name}`即可。

另外，该功能语法由 Python format 语法提供，所以也支持一些高级的用法，比如 `{id:0>3}{name}`。

#### Cookies 设置

-  参数 `-c` 或 `--sessdata`
-  默认值 ``

详情参考 bilili 文档。

#### 不下载弹幕

-  参数 `--no-danmaku`
-  默认值 `False`

#### 不下载字幕

-  参数 `--no-subtitle`
-  默认值 `False`

#### 不显示颜色

-  参数 `--no-color`
-  默认值 `False`

#### 启用 Debug 模式

-  参数 `--debug`
-  默认值 `False`

</details>

### 批量参数

有些参数是只有 `batch` 子命令才可以使用的

<details>
<summary>点击展开详细参数</summary>

#### 选集

-  参数 `-p` 或 `--episodes`
-  默认值 `^~$`

详情参考 bilili 文档。

#### 同时下载附加剧集

-  参数 `-s` 或 `--with-section`
-  默认值 `False`

</details>

## 从 bilili1.x 迁移

### 取消的功能

-  `- bilibili` 目录的生成
-  播放列表生成
-  源格式修改功能（不再支持 flv 源视频下载，如果仍有视频不支持 dash 源，请继续使用 bilili）

### 默认行为的修改

-  使用协程而非多线程进行下载，同时也不是批量解析批量下载，而是边解析边下载
-  默认生成弹幕为 ASS
-  默认启用从多镜像源下载的特性
-  不仅可以控制是否使用系统代理，还能配置特定的代理服务器

### 新增的特性

-  单视频下载与批量下载命令分离（`bilili` 命令与 `yutto batch get` 相类似）
-  音频/视频编码选择
-  仅下载音频/视频
-  存放子路径的自由定制

## TODO List

-  [ ] `info` 子命令、`batch info` 子命令
-  [ ] 完善的信息提示
-  [ ] 字幕、弹幕嵌入视频支持
-  [ ] 更多批下载支持（UP 主、收藏夹等）
-  [ ] 编写测试
-  [ ] 等等等等，以及
-  [ ] 更加可爱～

## 参考

-  基本结构：<https://github.com/SigureMo/bilili>
-  协程下载：<https://github.com/changmenseng/AsyncBilibiliDownloader>
-  弹幕转换：<https://github.com/ShigureLab/biliass>
-  样式设计：<https://github.com/willmcgugan/rich>

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)
