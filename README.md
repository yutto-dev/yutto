# yutto<sup>2.0.0-rc</sup>

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

yutto，一个可爱且任性的 B 站下载器（CLI）

当前 yutto 目前处于 RC 阶段，请通过 [Issues](https://github.com/yutto-dev/yutto/issues) 反馈功能正确性问题和功能请求，其他问题请通过 [Discussions](https://github.com/yutto-dev/yutto/discussions) 反馈～

## 版本号为什么是 2.0

因为 yutto 是 [bilili](https://github.com/yutto-dev/bilili) 的後輩呀～

## 从安装开始～

### 包管理器一键安装啦

目前 yutto 已经可以通过部分包管理器直接安装～

使用 Homebrew 的用户可以尝试下下面的命令：

```bash
brew tap siguremo/tap
brew install yutto
```

使用 [paru](https://github.com/Morganamilo/paru)（Arch 上的 AUR 包管理器）的用户可以尝试下这样的命令（感谢 @ouuan）：

```bash
paru -S yutto
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
pip install --pre yutto
```

当然，你也可以通过 [pipx](https://github.com/pypa/pipx)/[uv](https://github.com/astral-sh/uv) 来安装 yutto（当然，前提是你要自己先安装它）

```bash
pipx install --pre yutto      # 使用 pipx
uv tool install --pre yutto   # 或者使用 uv
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

### 已支持的下载类型

<!-- prettier-ignore -->
| 类型 | 是否支持选集 | 示例链接 | 默认路径模板 |
| - | - | - | - |
| 投稿视频 | - | `https://www.bilibili.com/video/BV1vZ4y1M7mQ` <br/> `https://www.bilibili.com/video/av371660125` <br/> `https://www.bilibili.com/video/BV1vZ4y1M7mQ?p=1` <br/> `av371660125` <br/> `BV1vZ4y1M7mQ` | `{title}` |
| 投稿视频 <sup>批量</sup> | :white_check_mark: | `https://www.bilibili.com/video/BV1vZ4y1M7mQ` <br/> `https://www.bilibili.com/video/av371660125`  <br/> `av371660125` <br/> `BV1vZ4y1M7mQ` | `{title}/{name}` |
| 番剧 | - | `https://www.bilibili.com/bangumi/play/ep395211` <br/> `ep395211` | `{name}` |
| 番剧 <sup>批量</sup> | :white_check_mark: | `https://www.bilibili.com/bangumi/play/ep395211` <br/> `https://www.bilibili.com/bangumi/play/ss38221` <br/> `https://www.bilibili.com/bangumi/media/md28233903` <br/> `ep395211` <br/> `ss38221` <br/> `md28233903` | `{title}/{name}` |
| 课程 | - | `https://www.bilibili.com/cheese/play/ep6902` | `{name}` |
| 课程 <sup>批量</sup> | :white_check_mark: | `https://www.bilibili.com/cheese/play/ep6902` <br/> `https://www.bilibili.com/cheese/play/ss298` | `{title}/{name}` |
| 用户指定收藏夹 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/favlist?fid=1306978874&ftype=create` | `{username}的收藏夹/{series_title}/{title}/{name}` |
| 当前用户稍后再看 <sup>批量</sup> | :x: | `https://www.bilibili.com/watchlater` | `稍后再看/{title}/{name}` |
| 用户全部收藏夹 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/favlist` | `{username}的收藏夹/{series_title}/{title}/{name}` |
| UP 主个人空间 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/video` | `{username}的全部投稿视频/{title}/{name}` |
| 合集 <sup>批量</sup> | :white_check_mark: | `https://space.bilibili.com/361469957/channel/collectiondetail?sid=23195` <br/> `https://www.bilibili.com/medialist/play/361469957?business=space_collection&business_id=23195` | `{series_title}/{title}` |
| 视频列表 <sup>批量</sup> | :x: | `https://space.bilibili.com/100969474/channel/seriesdetail?sid=1947439` <br/> `https://www.bilibili.com/medialist/play/100969474?business=space_series&business_id=1947439` <br/> `https://space.bilibili.com/100969474/favlist?fid=270359&ftype=collect` | `{series_title}/{title}/{name}` |

> [!NOTE]
>
> 标记「批量」的视频都必须通过 `-b/--batch` 参数来下载，否则会按照单个视频来解析下载

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

### 基础参数

yutto 支持一些基础参数，无论是批量下载还是单视频下载都适用。

<details>
<summary>点击展开详细参数</summary>

#### 最大并行 worker 数量

-  参数 `-n` 或 `--num-workers`
-  默认值 `8`

与 bilili 不同的是，yutto 并不是使用多线程实现并行下载，而是使用协程实现的，本参数限制的是最大的并行 Worker 数量。

#### 指定视频清晰度等级

-  参数 `-q` 或 `--video-quality`
-  可选值 `127 | 126 | 125 | 120 | 116 | 112 | 100 | 80 | 74 | 64 | 32 | 16`
-  默认值 `127`

清晰度对应关系如下

<!-- prettier-ignore -->
| code | 清晰度 |
| :-: | :-: |
| 127 | 8K 超高清 |
| 126 | 杜比视界 |
| 125 | HDR 真彩 |
| 120 | 4K 超清 |
| 116 | 1080P 60帧 |
| 112 | 1080P 高码率 |
| 100 | 智能修复 |
| 80 | 1080P 高清 |
| 74 | 720P 60帧 |
| 64 | 720P 高清 |
| 32 | 480P 清晰 |
| 16 | 360P 流畅 |

并不是说指定某个清晰度就一定会下载该清晰度的视频，yutto 只会尽可能满足你的要求，如果不存在指定的清晰度，yutto 就会按照默认的清晰度搜索机制进行调节，比如指定清晰度为 `80`，**首先会依次降清晰度搜索** `74`、`64`、`32`、`16`，如果依然找不到合适的则**继续升清晰度搜索** `100`、`112`、`116`、`120`、`125`、`126`、`127`。

值得注意的是，目前杜比视界视频只能简单下载音视频流并合并，合并后并不能达到在线观看的效果。

#### 指定音频码率等级

-  参数 `-aq` 或 `--audio-quality`
-  可选值 `30251 | 30255 | 30250 | 30280 | 30232 | 30216`
-  默认值 `30251`

码率对应关系如下

<!-- prettier-ignore -->
| code | 码率 |
| :-: | :-: |
| 30251 |  - (Hi-Res)  |
| 30255 |  - (杜比音效)  |
| 30250 |  - (杜比全景声)  |
| 30280 | 320kbps |
| 30232 | 128kbps |
| 30216 | 64kbps |

码率自动调节机制与视频清晰度一致，也采用先降后升的匹配机制。

#### 指定视频编码

-  参数 `--vcodec`
-  下载编码可选值 `"av1" | "hevc" | "avc"`
-  保存编码可选值 FFmpeg 所有可用的视频编码器
-  默认值 `"avc:copy"`

该参数略微复杂，前半部分表示在下载时**优先**选择哪一种编码的视频流，后半部分则表示在合并时如何编码视频流，两者使用 `:` 分隔。

值得注意的是，前半的下载编码只是优先下载的编码而已，如果不存在该编码，则会根据 `--download-vcodec-priority` 自动选择其余编码，如未设置 `--download-vcodec-priority`，则会类似视频清晰度调节机制先降序后升序的方式来选择。

而后半部分的参数如果设置成非 `copy` 的值则可以确保在下载完成后对其进行重新编码，而且不止支持 `av1`、`hevc` 与 `avc`，只要你的 FFmpeg 支持的视频编码器，它都可以完成。

#### 指定音频编码

-  参数 `--acodec`
-  下载编码可选值 `"mp4a"`
-  保存编码可选值 FFmpeg 所有可用的音频编码器
-  默认值 `"mp4a:copy"`

详情同视频编码。

#### 指定视频下载编码优先级

-  参数 `--download-vcodec-priority`
-  默认值 `"auto"`
-  可选值 `"auto"` 或者使用 `,` 分隔的下载编码列表，如 `"hevc,avc,av1"`

当使用默认值 `"auto"` 时，yutto 会类似视频清晰度调节机制先降序后升序的方式来选择。

当使用自定义下载编码列表时，yutto 会严格按照列表中的顺序进行选择，如果不存在则会认为该视频无视频流。

<!--
这里使用 [!Warning] 渲染会出问题，因为 GitHub 尚不支持嵌套在 summary 中，因此暂时回退到 **Warning** 的写法
更多讨论见
https://github.com/orgs/community/discussions/16925#discussioncomment-7571187
-->

> **Warning**
>
> 如若设置本参数，请总是将 `--download-vcode-priority` 首选编码作为 `--vcodec` 的前半部分，否则可能会导致下载失败。

#### 指定输出格式

-  参数 `--output-format`
-  可选值 `"infer" | "mp4" | "mkv" | "mov"`
-  默认值 `"infer"`

在至少包含视频流时所使用的输出格式，默认选值 `"infer"` 表示自动根据情况进行推导以保证输出的可用，推导规则如下：

-  如果输出包含音频流且音频流编码为 `"fLaC"`，则输出格式为 `"mkv"`，因为 `"mp4"` 尚不支持 `"fLaC"` 编码
-  否则为 `"mp4"`

#### 指定在仅包含音频流时的输出格式

-  参数 `--output-format-audio-only`
-  可选值 `"infer" | "aac" | "mp3" | "flac" | "mp4" | "mkv" | "mov"`
-  默认值 `"infer"`

在仅包含音频流时所使用的输出格式，默认选值 `"infer"` 表示自动根据情况进行推导以保证输出的可用，推导规则如下：

-  如果音频流编码为 `"fLaC"`，则输出格式为 `"flac"`
-  否则为 `"aac"`

> **Note**
>
> 并不是仅仅在指定 `--audio-only` 时才会仅仅包含视频流，有些视频是仅包含音频流的，此时即便不指定 `--audio-only` 选项也会按照本选项的格式进行输出。

#### 弹幕格式选择

-  参数 `-df` 或 `--danmaku-format`
-  可选值 `"ass" | "xml" | "protobuf"`
-  默认值 `"ass"`

B 站提供了 `xml` 与 `protobuf` 两种弹幕数据接口，`xml` 接口为旧接口，弹幕数上限较低，`protobuf` 接口相对较高，但不登录情况下只能获取很少的弹幕

为了确保无论是否登录都能获取最多的弹幕，yutto 在登录时会下载 `protobuf` 源数据，在未登录时会下载 `xml` 源数据，并将其转换为主流播放器支持的 `ass` 格式

如果你不喜欢 yutto 自动转换的效果，可以选择输出格式为 `xml` 或 `protobuf`，手动通过一些工具进行转换，比如 yutto 和 bilili 所使用的 [biliass](https://github.com/yutto-dev/yutto/tree/main/packages/biliass)，或者使用 [us-danmaku](https://tiansh.github.io/us-danmaku/bilibili/) 进行在线转换。

如果你不想下载弹幕，只需要使用参数 `--no-danmaku` 即可。

#### 下载块大小

-  参数 `-bs` 或 `--block-size`
-  默认值 `0.5`

以 MiB 为单位，为分块下载时各块大小，不建议更改。

#### 强制覆盖已下载文件

-  参数 `-w` 或 `--overwrite`
-  默认值 `False`

#### 代理设置

-  参数 `-x` 或 `--proxy`
-  可选值 `"auto" | "no" | <https?://url/to/proxy/server>`
-  默认值 `"auto"`

设置代理服务器，默认是从环境变量读取，`no` 则为不设置代理，设置其它 http/https url 则将其作为代理服务器。

#### 存放根目录

-  参数 `-d` 或 `--dir`
-  默认值 `"./"`

#### 临时文件目录

-  参数 `--tmp-dir`
-  默认值是“存放根目录”即 `-d, --dir` 的值

#### Cookies 设置

-  参数 `-c` 或 `--sessdata`
-  默认值 `""`

设置 Cookies 后你才可以下载更高清晰度以及更多的剧集，当你传入你的大会员 `SESSDATA` 时（当然前提是你是大会员），你就可以下载大会员可访问的资源咯。

<details><summary> SESSDATA 获取方式 </summary>

这里用 Chrome 作为示例，其它浏览器请尝试类似方法。

首先，用你的帐号登录 B 站，然后随便打开一个 B 站网页，比如[首页](https://www.bilibili.com/)。

按 F12 打开开发者工具，切换到 Network 栏，刷新页面，此时第一个加载的资源应该就是当前页面的 html，选中该资源，在右侧 「Request Headers」 中找到 「cookie」，在其中找到类似于 `SESSDATA=d8bc7493%2C2843925707%2C08c3e*81;` 的一串字符串，复制这里的 `d8bc7493%2C2843925707%2C08c3e*81`，这就是你需要的 `SESSDATA`。

</details>

另外，由于 SESSDATA 中可能有特殊符号，所以传入时你可能需要使用双引号来包裹

```bash
yutto <url> -c "d8bc7493%2C2843925707%2C08c3e*81"
```

当然，示例里的 SESSDATA 是无效的，请使用自己的 SESSDATA。

#### 存放子路径模板

-  参数 `-tp` 或 `--subpath-template`
-  可选参数变量 `title | id | name | username | series_title | pubdate | download_date | owner_uid` （以后可能会有更多）
-  默认值 `"{auto}"`

通过配置子路径模板可以灵活地控制视频存放位置。

默认情况是由 yutto 自动控制存放位置的。比如下载单个视频时默认就是直接存放在设定的根目录，不会创建一层容器目录，此时自动选择了 `{name}` 作为模板；而批量下载时则会根据视频层级生成多级目录，比如番剧会是 `{title}/{name}`，首先会在设定根目录里生成一个番剧名的目录，其内才会存放各个番剧剧集视频，这样方便了多个不同番剧的管理。当然，如果你仍希望将番剧直接存放在设定根目录下的话，可以修改该参数值为 `{name}`即可。

另外，该功能语法由 Python format 函数模板语法提供，所以也支持一些高级的用法，比如 `{id:0>3}{name}`，此外还专门为时间变量 🕛 增加了自定义时间模板的语法 `{pubdate@%Y-%m-%d %H:%M:%S}`，默认时间模板为 `%Y-%m-%d`。

值得注意的是，并不是所有变量在各种场合下都会提供，比如 `username`, `owner_uid` 变量当前仅在 UP 主全部投稿视频/收藏夹/稍后再看才提供，在其它情况下不应使用它。各变量详细作用域描述见下表：

<!-- prettier-ignore -->
| Variable | Description | Scope |
| - | - | - |
| title | 系列视频总标题（番剧名/投稿视频标题） | 全部 |
| id | 系列视频单 p 顺序标号 | 全部 |
| name | 系列视频单 p 标题 | 全部 |
| username | UP 主用户名 | 个人空间、收藏夹、稍后再看、合集、视频列表下载 |
| series_title | 合集标题 | 收藏夹、视频合集、视频列表下载 |
| pubdate🕛 | 投稿日期 | 仅投稿视频 |
| download_date🕛 | 下载日期 | 全部 |
| owner_uid | UP 主UID | 个人空间、收藏夹、稍后再看、合集、视频列表下载 |

> **Note**
>
> 未来可能会对路径变量及默认路径模板进行调整

#### url 别名文件路径

-  参数 `-af` 或 `--alias-file`
-  默认值 `None`

指定别名文件路径，别名文件中存放一个别名与其对应的 url，使用空格或者 `=` 分隔，示例如下：

```
tensura1=https://www.bilibili.com/bangumi/play/ss25739/
tensura2=https://www.bilibili.com/bangumi/play/ss36170/
tensura-nikki=https://www.bilibili.com/bangumi/play/ss38221/
```

比如将上述内容存储到 `~/.yutto_alias`，则通过以下命令即可解析该文件：

```bash
yutto tensura1 --batch --alias-file='~/.yutto_alias'
```

当参数值为 `-` 时，会从标准输入中读取：

```bash
cat ~/.yutto_alias | yutto tensura-nikki --batch --alias-file -
```

#### 指定媒体元数据值的格式

当前仅支持 `premiered`

-  参数 `--metadata-format-premiered`
-  默认值 `"%Y-%m-%d"`
-  常用值 `"%Y-%m-%d %H:%M:%S"`

#### 严格校验大会员状态有效

-  参数 `--vip-strict`
-  默认值 `False`

#### 严格校验登录状态有效

-  参数 `--login-strict`
-  默认值 `False`

#### 设置下载间隔

-  参数 `--download-interval`
-  默认值 `0`

设置两话之间的下载间隔（单位为秒），避免短时间內下载大量视频导致账号被封禁

#### 禁用下载镜像

-  参数 `--banned-mirrors-pattern`
-  默认值 `None`

使用正则禁用特定镜像，比如 `--banned-mirrors-pattern "mirrorali"` 将禁用 url 中包含 `mirrorali` 的镜像

#### 不显示颜色

-  参数 `--no-color`
-  默认值 `False`

#### 不显示进度条

-  参数 `--no-progress`
-  默认值 `False`

#### 启用 Debug 模式

-  参数 `--debug`
-  默认值 `False`

</details>

### 资源选择参数

此外有一些参数专用于资源选择，比如选择是否下载弹幕、音频、视频等等。

<details>
<summary>点击展开详细参数</summary>

#### 仅下载视频流

-  参数 `--video-only`
-  默认值 `False`

> **Note**
>
> 这里「仅下载视频流」是指视频中音视频流仅选择视频流，而不是仅仅下载视频而不下载弹幕字幕等资源，如果需要取消字幕等资源下载，请额外使用 `--no-danmaku` 等参数。
>
> 「仅下载音频流」也是同样的。

#### 仅下载音频流

-  参数 `--audio-only`
-  默认值 `False`

仅下载其中的音频流，保存为 `.aac` 文件。

#### 不生成弹幕文件

-  参数 `--no-danmaku`
-  默认值 `False`

#### 仅生成弹幕文件

-  参数 `--danmaku-only`
-  默认值 `False`

#### 不生成字幕文件

-  参数 `--no-subtitle`
-  默认值 `False`

#### 仅生成字幕文件

-  参数 `--subtitle-only`
-  默认值 `False`

#### 生成媒体元数据文件

-  参数 `--with-metadata`
-  默认值 `False`

目前媒体元数据生成尚在试验阶段，可能提取出的信息并不完整。

#### 仅生成媒体元数据文件

-  参数 `--metadata-only`
-  默认值 `False`

#### 不生成视频封面

-  参数 `--no-cover`
-  默认值 `False`

> [!NOTE]
>
> 当前仅支持为包含视频流的视频生成封面。

#### 生成视频流封面时单独保存封面

-  参数 `--save-cover`
-  默认值 `False`

#### 仅生成视频封面

-  参数 `--cover-only`
-  默认值 `False`

#### 不生成章节信息

-  参数 `--no-chapter-info`
-  默认值 `False`

不生成章节信息，包含 MetaData 和嵌入视频流的章节信息。

</details>

### 弹幕设置参数<sup>Experimental</sup>

yutto 通过与 biliass 的集成，提供了一些 ASS 弹幕选项，包括字号、字体、速度等～

<details>
<summary>点击展开详细参数</summary>

#### 弹幕字体大小

-  参数 `--danmaku-font-size`
-  默认值 `video_width / 40`

#### 弹幕字体

-  参数 `--danmaku-font`
-  默认值 `"SimHei"`

#### 弹幕不透明度

-  参数 `--danmaku-opacity`
-  默认值 `0.8`

#### 弹幕显示区域与视频高度的比例

-  参数 `--danmaku-display-region-ratio`
-  默认值 `1.0`

#### 弹幕速度

-  参数 `--danmaku-speed`
-  默认值 `1.0`

#### 屏蔽顶部弹幕

-  参数 `--danmaku-block-top`
-  默认值 `False`

#### 屏蔽底部弹幕

-  参数 `--danmaku-block-bottom`
-  默认值 `False`

#### 屏蔽滚动弹幕

-  参数 `--danmaku-block-scroll`
-  默认值 `False`

#### 屏蔽逆向弹幕

-  参数 `--danmaku-block-reverse`
-  默认值 `False`

#### 屏蔽固定弹幕（顶部、底部）

-  参数 `--danmaku-block-fixed`
-  默认值 `False`

#### 屏蔽高级弹幕

-  参数 `--danmaku-block-special`
-  默认值 `False`

#### 屏蔽彩色弹幕

-  参数 `--danmaku-block-colorful`
-  默认值 `False`

#### 屏蔽关键词

-  参数 `"--danmaku-block-keyword-patterns`
-  默认值 `None`

按关键词屏蔽，支持正则，使用 `,` 分隔

</details>

### 批量参数

有些参数是只有批量下载时才可以使用的

<details>
<summary>点击展开详细参数</summary>

#### 启用批量下载

-  参数 `-b` 或 `--batch`
-  默认值 `False`

只需要 `yutto --batch <url>` 即可启用批量下载功能。

#### 选集

-  参数 `-p` 或 `--episodes`
-  默认值 `1~-1`（也即全选）

也就是选集咯，其语法是这样的

-  `<p1>` 单独下某一剧集
   -  支持负数来选择倒数第几话
   -  此外还可以使用 `$` 来代表 `-1`
-  `<p_start>~<p_end>` 使用 `~` 可以连续选取（如果起始为 1，或者终止为 -1 则可以省略）
-  `<p1>,<p2>,<p3>,...,<pn>` 使用 `,` 可以不连续选取

emmm，直接看的话大概并不能知道我在说什么，所以我们通过几个小例子来了解其语法

```bash
# 假设要下载一个具有 24 话的番剧
# 如果我们只想下载第 3 话，只需要这样
yutto <url> -b -p 3
# 那如果我想下载第 5 话到第 7 话呢，使用 `~` 可以连续选中
yutto <url> -b -p 5~7
# 那我想下载第 12 话和第 17 话又要怎么办？此时只需要 `,` 就可以将多个不连续的选集一起选中
yutto <url> -b -p 12,17
# 那我突然又想将刚才那些都选中了呢？还是使用 `,` 呀，将它们连在一起即可
yutto <url> -b -p 3,5~7,12,17
# 嗯，你已经把基本用法都了解过了，很简单吧～
# 下面是一些语法糖，不了解也完全不会影响任何功能哒～
# 那如果我只知道我想下载倒数第 3 话，而不想算倒数第三话是第几话应该怎么办？
# 此时可以用负数哒～不过要注意的是，这种参数以 `-` 开头参数需要使用 `=` 来连接选项和参数
yutto <url> -b -p=-3
# 那么如果想下载最后一话你可能会想到 `-p=-1` 对吧？不过我内置了符号 $ 用于代表最后一话
# 像下面这样就可以直接下载最后一话啦～
yutto <url> -b -p $
# 为了进一步方便表示一个范围选取，在从第一话开始选取或者以最后一话为终止时可以省略它们
# 这样就是前三话啦（这里与以 `-` 开头类似，以 `~` 开头可能被识别为 $HOME，因此最好也用等号，或者使用引号包裹）
yutto <url> -b -p=~3
# 这样就是后四话啦
yutto <url> -b -p=-4~
# 所有语法都了解完啦，我们看一个稍微复杂的例子
yutto <url> -b -p "~3,10,12~14,16,-4~"
# 很明显，上面的例子就是下载前 3 话、第 10 话、第 12 到 14 话、第 16 话以及后 4 话
```

下面是一些要注意的问题

1. 这里使用的序号是视频的顺序序号，而不是番剧所标注的`第 n 话`，因为有可能会出现 `第 x.5 话` 等等的特殊情况，此时一定要按照顺序自行计数。
2. 参数值里一定不要加空格
3. 参数值开头为特殊符号时最好使用 `=` 来连接选项和参数，或者尝试使用引号包裹参数
4. 个人空间、视频列表、收藏夹等批量下载暂不支持选集操作

#### 同时下载附加剧集

-  参数 `-s` 或 `--with-section`
-  默认值 `False`

#### 指定稿件发布时间范围

-  参数 `--batch-filter-start-time` 和 `--batch-filter-end-time` 分别表示`开始`和`结束`时间，该区间**左闭右开**
-  默认 `不限制`
-  支持的格式

   -  `%Y-%m-%d`
   -  `%Y-%m-%d %H:%M:%S`

   例如仅下载 2020 年投稿的视频，可以这样:

   `--batch-filter-start-time=2020-01-01 --batch-filter-end-time=2021-01-01`

</details>

### 配置文件<sup>Experimental</sup>

yutto 自 `2.0.0-rc.3` 起增加了实验性的配置文件功能，你可以通过 `--config` 选项来指定配置文件路径，比如

```bash
yutto --config /path/to/config.toml <url>
```

如果不指定配置文件路径，yutto 也支持配置自动发现，根据优先级，搜索路径如下：

-  当前目录下的 `yutto.toml`
-  搜索 [`XDG_CONFIG_HOME`](https://specifications.freedesktop.org/basedir-spec/latest/) 下的 `yutto/yutto.toml` 文件
-  非 Windows 系统下的 `~/.config/yutto/yutto.toml`，Windows 系统下的 `~/AppData/Roaming/yutto/yutto.toml`

你可以通过配置文件来设置一些默认参数，整体上与命令行参数基本一致，下面以一些示例来展示配置文件的写法：

```toml
# yutto.toml
#:schema https://raw.githubusercontent.com/yutto-dev/yutto/refs/heads/main/schemas/config.json
[basic]
# 设置下载目录
dir = "/path/to/download"
# 设置临时文件目录
tmp_dir = "/path/to/tmp"
# 设置 SESSDATA
sessdata = "***************"
# 设置大会员严格校验
vip_strict = true
# 设置登录严格校验
login_strict = true

[resource]
# 不下载字幕
require_subtitle = false

[danmaku]
# 设置弹幕速度
speed = 2.0
# 设置弹幕屏蔽关键词
block_keyword_patterns = [
   ".*keyword1.*",
   ".*keyword2.*",
]

[batch]
# 下载额外剧集
with_section = true
```

如果你使用 VS Code 对配置文件编辑，强烈建议使用 [Even Better TOML](https://marketplace.visualstudio.com/items?itemName=tamasfe.even-better-toml) 扩展，配合 yutto 提供的 schema，可以获得最佳的提示体验。

## 从 bilili1.x 迁移

### 取消的功能

-  `- bilibili` 目录的生成
-  播放列表生成
-  源格式修改功能（不再支持 flv 源视频下载，如果仍有视频不支持 dash 源，请继续使用 bilili）
-  对 Python3.8 的支持，最低支持 Python3.9
-  下载前询问
-  弃用选集语法糖开始符号 `^`，直接使用明确的剧集号 `1` 即可

### 默认行为的修改

-  使用协程而非多线程进行下载
-  默认生成弹幕为 ASS
-  默认启用从多镜像源下载的特性
-  不仅可以控制是否使用系统代理，还能配置特定的代理服务器

### 新增的特性

-  单视频下载与批量下载命令分离（`bilili` 命令与 `yutto --batch` 相类似）
-  音频/视频编码选择
-  可选仅下载音频/视频
-  存放子路径的自由定制
-  支持 url 别名
-  支持文件列表
-  更多的批下载支持（现已支持 UP 主全部投稿视频、视频合集、收藏夹等）
-  更加完善的 warning 与 error 提示
-  支持仅输入 id 即可下载（aid、bvid、episode_id 等）
-  支持描述文件生成
-  将链接解析延迟到下载前一刻，避免短时间大量请求导致 IP 被封的问题

## 小技巧

### 作为 log 输出到文件

虽说 yutto 不像 bilili 那样会全屏刷新，但进度条还是会一直刷新占据多行，可能影响 log 的阅读，另外颜色码也是难以阅读的，因此我们可以通过选项禁用他们：

```bash
yutto --no-color --no-progress <url> > log
```

### 使用配置自定义默认参数

如果你希望修改 yutto 的部分参数，那么可能每次运行都需要在后面加上长长一串选项，为了避免这个问题，你可以尝试使用配置文件

```toml
# ~/.config/yutto/yutto.toml
#:schema https://raw.githubusercontent.com/yutto-dev/yutto/refs/heads/main/schemas/config.json
[basic]
dir = "~/Movies/yutto"
sessdata = "***************"
num_workers = 16
vcodec = "av1:copy"
```

当然，请手动修改 `sessdata` 内容为自己的 `SESSDATA` 哦～

> [!TIP]
>
> 本方案可替代原有的「自定义命令别名」方式～
>
> <details>
> <summary>原「自定义命令别名」方案</summary>
>
> 在 `~/.zshrc` / `~/.bashrc` 中自定义一条 alias，像这样
>
> ```bash
> alias ytt='yutto -d ~/Movies/yutto/ -c `cat ~/.sessdata` -n 16 --vcodec="av1:copy"'
> ```
>
> 这样我每次只需要 `ytt <url>` 就可以直接使用这些参数进行下载啦～
>
> 由于我提前在 `~/.sessdata` 存储了我的 `SESSDATA`，所以避免每次都要手动输入 cookie 的问题。
>
> </details>

### 使用 url alias

yutto 新增的 url alias 可以让你下载正在追的番剧时不必每次都打开浏览器复制 url，只需要将追番列表存储在一个文件中，并为这些 url 起一个别名即可

```
tensura-nikki=https://www.bilibili.com/bangumi/play/ss38221/
```

之后下载最新话只需要

```
yutto --batch tensura-nikki --alias-file=/path/to/alias-file
```

你同样可以通过配置文件来实现这一点（推荐）

```toml
# ~/.config/yutto/yutto.toml
#:schema https://raw.githubusercontent.com/yutto-dev/yutto/refs/heads/main/schemas/config.json
[basic.aliases]
tensura-nikki = "https://www.bilibili.com/bangumi/play/ss38221/"
```

### 使用任务列表

现在 url 不仅支持 http/https 链接与裸 id，还支持使用文件路径与 file scheme 来用于表示文件列表，文件列表以行分隔，每行写一次命令的参数，该参数会覆盖掉主程序中所使用的参数，示例如下：

首先将下面的文件存储到一个地方

```
https://www.bilibili.com/bangumi/play/ss38221/ --batch -p $
https://www.bilibili.com/bangumi/play/ss38260/ --batch -p $
```

然后运行

```
yutto file:///path/to/list
```

即可分别下载这两个番剧的最新一话

或者直接使用相对或者绝对路径也是可以的

```
yutto ./path/to/list
```

值得注意的是，在文件列表各项里的参数优先级是高于命令里的优先级的，比如文件中使用：

```
tensura1 --batch -p $ --no-danmaku --vcodec="hevc:copy"
tensura2 --batch -p $
```

而命令中则使用

```
yutto file:///path/to/list --vcodec="avc:copy"
```

最终下载的 tensura1 会是 "hevc:copy"，而 tensura2 则会是 "avc:copy"

另外，文件列表也是支持 alias 的，你完全可以为该列表起一个别名，一个比较特别的用例是将你所有追番的内容放在一个文件里，然后为该文件起一个别名（比如 `subscription`），这样只需要 `yutto subscription --alias-file path/to/alias/file` 就可以达到追番效果啦～

最后，列表也是支持嵌套的哦（虽然没什么用 2333）

## FAQ

### 名字的由来

[《転スラ日記》第一话 00:24](https://www.bilibili.com/bangumi/play/ep395211?t=24)

### 何谓「任性」？

yutto 添加任何特性都需要以保证可维护性为前提，因此 yutto 不会添加过于复杂的特性，只需要满足够用即可。

### yutto 会替代 bilili 吗

yutto 自诞生以来已经过去三年多了，功能上基本可以替代 bilili 了，由于 B 站接口的不断变化，bilili 也不再适用于现在的环境，因此请 bilili 用户尽快迁移到 yutto ～

### 正式版什么时候发布

快了……吧？

## 其他应用

你也可以通过这些应用来使用 yutto

-  [KubeSpider](https://github.com/opennaslab/kubespider): 一个多功能全局资源编排下载系统，支持下载、订阅各类资源网站～

## Roadmap

### 2.0.0-rc

-  [x] feat: 投稿视频描述文件支持
-  [x] refactor: 整理路径变量名
-  [x] feat: 视频合集选集支持（合集貌似有取代分 p 的趋势，需要对其进行合适的处理）
-  [x] refactor: 重写 biliass

### 2.0.0

-  [x] feat: 支持弹幕字体、字号、速度等设置
-  [x] feat: 配置文件支持
-  [x] feat: 配置文件功能优化，支持自定义配置路径
-  [ ] docs: issue template 添加配置引导
-  [x] docs: 优化 biliass rust 重构后的贡献指南
-  [ ] feat: 新的基于 toml 的任务列表
-  [ ] refactor: 配置参数复用 pydantic 验证
-  [ ] docs: 可爱的静态文档（WIP in [#86](https://github.com/yutto-dev/yutto/pull/86)）

### future

-  [ ] refactor: 针对视频合集优化路径变量
-  [ ] refactor: 优化杜比视界/音效/全景声选取逻辑（Discussing in [#62](https://github.com/yutto-dev/yutto/discussions/62)）
-  [ ] refactor: 直接使用 rich 替代内置的终端显示模块
-  [ ] feat: 更多批下载支持
-  [ ] feat: 以及更加可爱～

## 参考

-  基本结构：<https://github.com/yutto-dev/bilili>
-  协程下载：<https://github.com/changmenseng/AsyncBilibiliDownloader>
-  弹幕转换：<https://github.com/yutto-dev/yutto/tree/main/packages/biliass>
-  样式设计：<https://github.com/willmcgugan/rich>

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)
