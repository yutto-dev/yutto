---
aside: true
---

# 基础参数

我支持一些基础参数，无论是批量下载还是单视频下载都适用。

## 最大并行 worker 数量

- 参数 `-n` 或 `--num-workers`
- 配置项 `basic.num_workers`
- 默认值 `8`

与 bilili 不同的是，我并不是使用多线程实现并行下载，而是使用协程实现的，本参数限制的是最大的并行 Worker 数量。

## 指定视频清晰度等级

- 参数 `-q` 或 `--video-quality`
- 配置项 `basic.video_quality`
- 可选值 `127 | 126 | 125 | 120 | 116 | 112 | 100 | 80 | 74 | 64 | 32 | 16`
- 默认值 `127`

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

并不是说指定某个清晰度就一定会下载该清晰度的视频，我只会尽可能满足你的要求，如果不存在指定的清晰度，我就会按照默认的清晰度搜索机制进行调节，比如指定清晰度为 `80`，**首先会依次降清晰度搜索** `74`、`64`、`32`、`16`，如果依然找不到合适的则**继续升清晰度搜索** `100`、`112`、`116`、`120`、`125`、`126`、`127`。

## 指定音频码率等级

- 参数 `-aq` 或 `--audio-quality`
- 配置项 `basic.audio_quality`
- 可选值 `30251 | 30255 | 30250 | 30280 | 30232 | 30216`
- 默认值 `30251`

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

## 指定视频编码

- 参数 `--vcodec`
- 配置项 `basic.vcodec`
- 下载编码可选值 `"av1" | "hevc" | "avc"`
- 保存编码可选值 FFmpeg 所有可用的视频编码器
- 默认值 `"avc:copy"`

该参数略微复杂，前半部分表示在下载时**优先**选择哪一种编码的视频流，后半部分则表示在合并时如何编码视频流，两者使用 `:` 分隔。

值得注意的是，前半的下载编码只是优先下载的编码而已，如果不存在该编码，则会根据 `--download-vcodec-priority` 自动选择其余编码，如未设置 `--download-vcodec-priority`，则会类似视频清晰度调节机制先降序后升序的方式来选择。

而后半部分的参数如果设置成非 `copy` 的值则可以确保在下载完成后对其进行重新编码，而且不止支持 `av1`、`hevc` 与 `avc`，只要你的 FFmpeg 支持的视频编码器，它都可以完成。

## 指定音频编码

- 参数 `--acodec`
- 配置项 `basic.acodec`
- 下载编码可选值 `"mp4a"`
- 保存编码可选值 FFmpeg 所有可用的音频编码器
- 默认值 `"mp4a:copy"`

详情同视频编码。

## 指定视频下载编码优先级

- 参数 `--download-vcodec-priority`
- 配置项 `basic.download_vcodec_priority`
- 默认值 `"auto"`
- 可选值 `"auto"` 或者使用 `,` 分隔的下载编码列表，如 `"hevc,avc,av1"`

当使用默认值 `"auto"` 时，我会类似视频清晰度调节机制先降序后升序的方式来选择。

当使用自定义下载编码列表时，我会严格按照列表中的顺序进行选择，如果不存在则会认为该视频无视频流。

::: warning

如若设置本参数，请总是将 `--download-vcode-priority` 首选编码作为 `--vcodec` 的前半部分，否则可能会导致下载失败。

另外需要注意的是，作为配置项时，请直接使用列表形式，比如：

```toml [yutto.toml]
[basic]
download_vcodec_priority = ["hevc", "avc", "av1"]
```

:::

## 指定输出格式

- 参数 `--output-format`
- 配置项 `basic.output_format`
- 可选值 `"infer" | "mp4" | "mkv" | "mov"`
- 默认值 `"infer"`

在至少包含视频流时所使用的输出格式，默认选值 `"infer"` 表示自动根据情况进行推导以保证输出的可用，推导规则如下：

- 如果输出包含音频流且音频流编码为 `"fLaC"`，则输出格式为 `"mkv"`，因为 `"mp4"` 尚不支持 `"fLaC"` 编码
- 否则为 `"mp4"`

## 指定在仅包含音频流时的输出格式

- 参数 `--output-format-audio-only`
- 配置项 `basic.output_format_audio_only`
- 可选值 `"infer" | "m4a" | "aac" | "mp3" | "flac" | "mp4" | "mkv" | "mov"`
- 默认值 `"infer"`

在仅包含音频流时所使用的输出格式，默认选值 `"infer"` 表示自动根据情况进行推导以保证输出的可用，推导规则如下：

- 如果音频流编码为 `"fLaC"`，则输出格式为 `"flac"`
- 否则为 `"m4a"`

::: tip

并不是仅仅在指定 `--audio-only` 时才会仅仅包含视频流，有些视频是仅包含音频流的，此时即便不指定 `--audio-only` 选项也会按照本选项的格式进行输出。

:::

## 弹幕格式选择

- 参数 `-df` 或 `--danmaku-format`
- 配置项 `basic.danmaku_format`
- 可选值 `"ass" | "xml" | "protobuf"`
- 默认值 `"ass"`

B 站提供了 `xml` 与 `protobuf` 两种弹幕数据接口，`xml` 接口为旧接口，弹幕数上限较低，`protobuf` 接口相对较高，但不登录情况下只能获取很少的弹幕

为了确保无论是否登录都能获取最多的弹幕，我在登录时会下载 `protobuf` 源数据，在未登录时会下载 `xml` 源数据，并将其转换为主流播放器支持的 `ass` 格式

如果你不喜欢我自动转换的效果，可以选择输出格式为 `xml` 或 `protobuf`，手动通过一些工具进行转换，比如我和 bilili 所使用的 [biliass](https://github.com/yutto-dev/yutto/tree/main/packages/biliass)，或者使用 [us-danmaku](https://tiansh.github.io/us-danmaku/bilibili/) 进行在线转换。

如果你不想下载弹幕，只需要使用参数 `--no-danmaku` 即可。

## 下载块大小

- 参数 `-bs` 或 `--block-size`
- 配置项 `basic.block_size`
- 默认值 `0.5`

以 MiB 为单位，为分块下载时各块大小，不建议更改。

## 强制覆盖已下载文件

- 参数 `-w` 或 `--overwrite`
- 配置项 `basic.overwrite`
- 默认值 `False`

## 代理设置

- 参数 `-x` 或 `--proxy`
- 配置项 `basic.proxy`
- 可选值 `"auto" | "no" | <https?://url/to/proxy/server>`
- 默认值 `"auto"`

设置代理服务器，默认是从环境变量读取，`no` 则为不设置代理，设置其它 http/https url 则将其作为代理服务器。

## 存放根目录

- 参数 `-d` 或 `--dir`
- 配置项 `basic.dir`
- 默认值 `"./"`

## 临时文件目录

- 参数 `--tmp-dir`
- 配置项 `basic.tmp_dir`
- 默认值是“存放根目录”即 `-d, --dir` 的值

## Cookies 设置

- 参数 `-c` 或 `--sessdata`
- 配置项 `basic.sessdata`
- 默认值 `""`

设置 Cookies 后你才可以下载更高清晰度以及更多的剧集，当你传入你的大会员 `SESSDATA` 时（当然前提是你是大会员），你就可以下载大会员可访问的资源咯。

::: details `SESSDATA` 获取方式

这里用 Chrome 作为示例，其它浏览器请尝试类似方法。

首先，用你的帐号登录 B 站，然后随便打开一个 B 站网页，比如[首页](https://www.bilibili.com/)。

按 F12 打开开发者工具，切换到 Network 栏，刷新页面，此时第一个加载的资源应该就是当前页面的 html，选中该资源，在右侧 「Request Headers」 中找到 「cookie」，在其中找到类似于 `SESSDATA=d8bc7493%2C2843925707%2C08c3e*81;` 的一串字符串，复制这里的 `d8bc7493%2C2843925707%2C08c3e*81`，这就是你需要的 `SESSDATA`。

:::

另外，由于 `SESSDATA` 中可能有特殊符号，所以传入时你可能需要使用双引号来包裹

```bash
yutto <url> -c "d8bc7493%2C2843925707%2C08c3e*81"
```

当然，示例里的 `SESSDATA` 是无效的，请使用自己的 `SESSDATA`。

## 存放子路径模板

- 参数 `-tp` 或 `--subpath-template`
- 配置项 `basic.subpath_template`
- 可选参数变量 `title | id | name | username | series_title | pubdate | download_date | owner_uid` （以后可能会有更多）
- 默认值 `"{auto}"`

通过配置子路径模板可以灵活地控制视频存放位置。

默认情况是由我自动控制存放位置的。比如下载单个视频时默认就是直接存放在设定的根目录，不会创建一层容器目录，此时自动选择了 `{name}` 作为模板；而批量下载时则会根据视频层级生成多级目录，比如番剧会是 `{title}/{name}`，首先会在设定根目录里生成一个番剧名的目录，其内才会存放各个番剧剧集视频，这样方便了多个不同番剧的管理。当然，如果你仍希望将番剧直接存放在设定根目录下的话，可以修改该参数值为 `{name}`即可。

另外，该功能语法由 Python format 函数模板语法提供，所以也支持一些高级的用法，比如 `{id:0>3}{name}`，此外还专门为时间变量 🕛 增加了自定义时间模板的语法 `{pubdate@%Y-%m-%d %H:%M:%S}`，默认时间模板为 `%Y-%m-%d`。

值得注意的是，并不是所有变量在各种场合下都会提供，比如 `username`, `owner_uid` 变量当前仅在 UP 主全部投稿视频/收藏夹/稍后再看才提供，在其它情况下不应使用它。各变量详细作用域描述见下表：

<!-- prettier-ignore -->
| Variable | Description | Scope |
| - | - | - |
| title | 系列视频总标题（番剧名/投稿视频标题） | 全部 |
| id | 系列视频单 p 顺序标号 | 全部 |
| aid | 视频 AV 号，早期使用的视频 ID，不建议使用，详见 [AV 号全面升级公告](https://www.bilibili.com/blackboard/activity-BV-PC.html) | 全部 |
| bvid | 视频 BV 号，即视频 ID | 全部 |
| name | 系列视频单 p 标题 | 全部 |
| username | UP 主用户名 | 个人空间、收藏夹、稍后再看、合集、视频列表下载 |
| series_title | 合集标题 | 收藏夹、视频合集、视频列表下载 |
| pubdate🕛 | 投稿日期 | 仅投稿视频 |
| download_date🕛 | 下载日期 | 全部 |
| owner_uid | UP 主 UID | 个人空间、收藏夹、稍后再看、合集、视频列表下载 |

::: tip

未来可能会对路径变量及默认路径模板进行调整

:::

## url 别名设置

- 参数 `-af` 或 `--alias-file`
- 配置项 `basic.aliases`
- 默认值 `None`

由于 CLI 和配置文件两种界面是不一致的，别名的配置方式有着较大的区别，下面分别介绍两者。

### 别名文件路径设置（CLI）

在 CLI，你需要通过 `-af`/`--alias-file` 来指定别名文件路径，并在该文件中写明别名的映射关系，使用空格或者 `=` 分隔，示例如下：

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

### 别名配置设置（配置文件）

因为配置文件本身就是外部文件，因此可以直接通过结构化数据来表明别名映射关系，示例如下：

```toml
[basic.aliases]
tensura1 = "https://www.bilibili.com/bangumi/play/ss25739/"
tensura2 = "https://www.bilibili.com/bangumi/play/ss36170/"
tensura-nikki = "https://www.bilibili.com/bangumi/play/ss38221/"
```

## 指定媒体元数据值的格式

当前仅支持 `premiered`

- 参数 `--metadata-format-premiered`
- 配置项 `basic.metadata_format_premiered`
- 默认值 `"%Y-%m-%d"`
- 常用值 `"%Y-%m-%d %H:%M:%S"`

## 设置下载间隔

- 参数 `--download-interval`
- 配置项 `basic.download_interval`
- 默认值 `0`

设置两话之间的下载间隔（单位为秒），避免短时间內下载大量视频导致账号被封禁

## 禁用下载镜像

- 参数 `--banned-mirrors-pattern`
- 配置项 `basic.banned_mirrors_pattern`
- 默认值 `None`

使用正则禁用特定镜像，比如 `--banned-mirrors-pattern "mirrorali"` 将禁用 url 中包含 `mirrorali` 的镜像

## 严格校验大会员状态有效

- 参数 `--vip-strict`
- 配置项 `basic.vip_strict`
- 默认值 `False`

## 严格校验登录状态有效

- 参数 `--login-strict`
- 配置项 `basic.login_strict`
- 默认值 `False`

## 不显示颜色

- 参数 `--no-color`
- 配置项 `basic.no_color`
- 默认值 `False`

## 不显示进度条

- 参数 `--no-progress`
- 配置项 `basic.no_progress`
- 默认值 `False`

## 启用 Debug 模式

- 参数 `--debug`
- 配置项 `basic.debug`
- 默认值 `False`
