# yutto

<p align="center">
   <img src="./docs/public/logo.png" width="400px">
</p>

<p align="center">
   <a href="https://python.org/" target="_blank"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/yutto?logo=python&style=flat-square"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img src="https://img.shields.io/pypi/v/yutto?style=flat-square" alt="pypi"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/yutto?style=flat-square"></a>
   <a href="LICENSE"><img alt="LICENSE" src="https://img.shields.io/github/license/yutto-dev/yutto?style=flat-square"></a>
   <br/>
   <a href="https://github.com/astral-sh/uv"><img alt="uv" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=flat-square"></a>
   <a href="https://github.com/astral-sh/ruff"><img alt="ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square"></a>
   <a href="https://gitmoji.dev"><img alt="Gitmoji" src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67?style=flat-square"></a>
   <a href="https://discord.gg/5cQGyFwsqC"><img src="https://img.shields.io/badge/chat-discord-5d24a3?logo=discord&style=flat-square" alt="discord chat"></a>
</p>

<p align="center"><strong>🧊 yutto，一个可爱且任性的 B 站视频下载器（CLI）</strong></p>

**完整静态文档在这里喔 → [yutto](https://yutto.nyakku.moe/)**

> [!TIP]
>
> 如果在使用过程中遇到问题，请通过 [Issues](https://github.com/yutto-dev/yutto/issues) 反馈功能正确性问题和功能请求，其他问题请通过 [Discussions](https://github.com/yutto-dev/yutto/discussions) 反馈～

## 什么是 yutto？

yutto 是一个 B 站视频下载器，它可以帮助你下载 B 站上的投稿视频、番剧、课程等资源，支持单个视频下载、批量下载等功能，就像这样：

```bash
❯ yutto https://www.bilibili.com/video/BV1ZEf9YiE2h/
 INFO  发现配置文件 yutto.toml，加载中……
 大会员  成功以大会员身份登录～
 投稿视频  植物大战僵尸融合版2.2正式版宣传片
 INFO  开始处理视频 植物大战僵尸融合版2.2正式版宣传片
 INFO  共包含以下 15 个视频流：
 INFO  * 0 [AVC ] [1920x1080] <1080P 60帧> #3
 INFO    1 [HEVC] [1920x1080] <1080P 60帧> #3
 INFO    2 [AV1 ] [1920x1080] <1080P 60帧> #3
 INFO    3 [AVC ] [1920x1080] <1080P 高清> #3
 INFO    4 [HEVC] [1920x1080] <1080P 高清> #3
 INFO    5 [AV1 ] [1920x1080] <1080P 高清> #3
 INFO    6 [AVC ] [1280x720 ] <720P 高清 > #3
 INFO    7 [HEVC] [1280x720 ] <720P 高清 > #3
 INFO    8 [AV1 ] [1280x720 ] <720P 高清 > #3
 INFO    9 [AVC ] [ 852x480 ] <480P 清晰 > #3
 INFO   10 [HEVC] [ 852x480 ] <480P 清晰 > #3
 INFO   11 [AV1 ] [ 852x480 ] <480P 清晰 > #3
 INFO   12 [AVC ] [ 640x360 ] <360P 流畅 > #3
 INFO   13 [HEVC] [ 640x360 ] <360P 流畅 > #3
 INFO   14 [AV1 ] [ 640x360 ] <360P 流畅 > #3
 INFO  共包含以下 3 个音频流：
 INFO  * 0 [MP4A] <320kbps >
 INFO    1 [MP4A] < 64kbps >
 INFO    2 [MP4A] <128kbps >
 弹幕  ASS 弹幕已生成
 INFO  开始下载……
━━━━━━━━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━━━━━━━━  39.05 MiB/ 72.13 MiB 32.22 MiB/⚡
```

## 从安装开始～

### 包管理器一键安装啦

目前 yutto 已经可以通过部分包管理器直接安装～

使用 Homebrew 的用户可以尝试下下面的命令：

```bash
brew tap siguremo/tap
brew install yutto
```

Arch Linux 用户可以从 [AUR](https://aur.archlinux.org/packages/yutto)（感谢 @ouuan）或 [archlinuxcn](https://github.com/archlinuxcn/repo) 安装：

```bash
# 从 AUR 安装
yay -S yutto      # 适用于 yay 用户
paru -S yutto     # 适用于 paru 用户
# 或者从 archlinuxcn 安装
sudo pacman -S yutto
```

### 使用 Docker

你也可以尝试使用 docker 直接运行 yutto（具体如何运行需要参考下后面的内容～）

```bash
docker run --rm -it -v /path/to/download:/app siguremo/yutto <url> [options]
```

与直接运行 yutto 不同的是，这里的下载目标路径是通过 `-v <path>:/app` 指定的，也就是说 docker 里的 yutto 会将内容下载到 docker 里的 `/app` 目录下，与之相对应的挂载点 `<path>` 就是下载路径。你也可以直接挂载到 `$(pwd)`，此时就和本机 yutto 的默认行为一致啦，也是下载到当前目录下～

### pip/pipx/uv 安装

> [!TIP]
>
> 在此之前请确保安装 Python3.9 及以上版本，并配置好 FFmpeg（参照 [bilili 文档](https://bilili.nyakku.moe/guide/getting-started.html)）

```bash
pip install yutto
```

当然，你也可以通过 [pipx](https://github.com/pypa/pipx)/[uv](https://github.com/astral-sh/uv) 来安装 yutto（当然，前提是你要自己先安装它）

```bash
pipx install yutto      # 使用 pipx
uv tool install yutto   # 或者使用 uv
```

pipx/uv 会类似 Homebrew 无感地为 yutto 创建一个虚拟环境，与其余环境隔离开，避免污染 pip 的环境，因此相对于 pip，pipx/uv 是更推荐的安装方式（uv 会比 pipx 更快些～）。

### 体验 main 分支最新特性

> [!TIP]
>
> 这同样要求你自行配置 Python 和 FFmpeg 环境

有些时候有一些在 main 分支还没有发布的新特性或者 bugfix，你可以尝试直接安装 main 分支的代码，最快的方式仍然是通过 pip 安装，只不过需要使用 git 描述符

```bash
pip install git+https://github.com/yutto-dev/yutto@main                 # 通过 pip
pipx install git+https://github.com/yutto-dev/yutto@main                # 通过 pipx
uv tool install git+https://github.com/yutto-dev/yutto.git@main         # 通过 uv
```

## 主要功能

### 基本命令

yutto 的基本命令如下：

```bash
yutto <url>
```

你可以通过 `yutto -h` 查看详细命令参数。

如果你需要下载**单个**视频，只需要使用 yutto 加上这个视频的地址即可。它支持 av/BV 号以及相应带 p=n 参数的投稿视频页面，也支持 ep 号（episode_id）的番剧页面。

比如只需要这样你就可以下载[《転スラ日記》](https://www.bilibili.com/bangumi/play/ep395211)第一话：

```bash
yutto https://www.bilibili.com/bangumi/play/ep395211
```

yutto 还支持直接使用能够唯一定位资源的 id 来作为 `<url>`，刚刚的功能与下面的简化后的命令功能是完全一样的

```bash
yutto ep395211
```

不过有时你可能想要批量下载很多剧集，因此 yutto 提供了用于批量下载的参数 `-b/--batch`，它不仅支持前面所说的单个视频所在页面地址（会解析该单个视频所在的系列视频），还支持一些明确用于表示系列视频的地址，比如 md 页面（media_id）、ss 页面（season_id）。

比如像下面这样就可以下载《転スラ日記》所有已更新的剧集：

```bash
yutto --batch https://www.bilibili.com/bangumi/play/ep395211
```

### 更多功能

yutto 还支持很多功能，限于篇幅不在 `README` 中展示，你可以前往 [yutto 文档](https://yutto.nyakku.moe/) 查看更多详细内容～

## 其他应用

你也可以通过这些应用来使用 yutto

-  [KubeSpider](https://github.com/opennaslab/kubespider): 一个多功能全局资源编排下载系统，支持下载、订阅各类资源网站～

## Roadmap

### 2.0.0

-  [x] feat: 支持弹幕字体、字号、速度等设置
-  [x] feat: 配置文件支持
-  [x] feat: 配置文件功能优化，支持自定义配置路径
-  [x] docs: issue template 添加配置引导
-  [x] docs: 优化 biliass rust 重构后的贡献指南

### future

-  [x] docs: 可爱的静态文档（WIP in [#86](https://github.com/yutto-dev/yutto/pull/86)）
-  [ ] feat: 新的基于 toml 的任务列表
-  [ ] refactor: 配置参数复用 pydantic 验证
-  [ ] refactor: 针对视频合集优化路径变量
-  [ ] refactor: 优化杜比视界/音效/全景声选取逻辑（Discussing in [#62](https://github.com/yutto-dev/yutto/discussions/62)）
-  [ ] refactor: 直接使用 rich 替代内置的终端显示模块
-  [ ] feat: 更多批下载支持
-  [ ] feat: 以及更加可爱～

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)
