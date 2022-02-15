# yutto<sup>2.0.0-beta</sup>

<p align="center">
   <a href="https://python.org/" target="_blank"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/yutto?logo=python&style=flat-square"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img src="https://img.shields.io/pypi/v/yutto?style=flat-square" alt="pypi"></a>
   <a href="https://pypi.org/project/yutto/" target="_blank"><img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/yutto?style=flat-square"></a>
   <a href="LICENSE"><img alt="LICENSE" src="https://img.shields.io/github/license/SigureMo/yutto?style=flat-square"></a>
   <a href="https://github.com/psf/black"><img alt="black" src="https://img.shields.io/badge/code%20style-black-000000?style=flat-square"></a>
   <a href="https://gitmoji.dev"><img src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67?style=flat-square" alt="Gitmoji"></a>
</p>

yutto，一个可爱且任性的 B 站下载器（CLI）

当前 yutto 尚处于 beta 阶段，有任何建议尽管在 [Discussions](https://github.com/SigureMo/yutto/discussions) 提出～～～

## 版本号为什么是 2.0

因为 yutto 是 bilili 的後輩呀～

## 从安装开始～

### 包管理器一键安装啦 <sup>测试中</sup>

目前 yutto 已经可以通过部分包管理器直接安装～

使用 Homebrew 的用户可以尝试下下面的命令：

```bash
brew tap siguremo/tap
brew install yutto
```

使用 yay（Arch 上的 AUR 包管理器）的用户可以尝试下这样的命令（感谢 @ouuan）：

```bash
yay -S yutto
```

### 使用 Docker <sup>测试中</sup>

你也可以尝试使用 docker 直接运行 yutto（具体如何运行需要参考下后面的内容～）

```bash
docker run --rm -it -v /path/to/download:/app siguremo/yutto <url> [options]
```

与直接运行 yutto 不同的是，这里的下载目标路径是通过 `-v <path>:/app` 指定的，也就是说 docker 里的 yutto 会将内容下载到 docker 里的 `/app` 目录下，与之相对应的挂载点 `<path>` 就是下载路径。你也可以直接挂载到 `$(pwd)`，此时就和本机 yutto 的默认行为一致啦，也是下载到当前目录下～

### pip 安装

在此之前请确保安装 Python3.9 及以上版本，并配置好 FFmpeg（参照 [bilili 文档](https://bilili.sigure.xyz/guide/getting-started.html)）

```bash
pip install --pre yutto
```

如果想要尝试 Nightly 版本，可尝试

```bash
pip install git+https://github.com/SigureMo/yutto@main
```

### 从 GitHub 获取最新源码手动安装

这同样要求你自行配置 Python 和 FFmpeg 环境

```bash
git clone https://github.com/SigureMo/yutto.git
cd yutto/
pip install poetry
poetry build
pip install ./dist/yutto-*.whl
```

## 主要功能

### 已支持的下载类型

<!-- prettier-ignore -->
|Type|Batch|Example url|Path template|
|-|-|-|-|
|投稿视频|:x:|`https://www.bilibili.com/video/BV1vZ4y1M7mQ` <br/> `https://www.bilibili.com/video/av371660125` <br/> `https://www.bilibili.com/video/BV1vZ4y1M7mQ?p=1` <br/> `av371660125` <br/> `BV1vZ4y1M7mQ`|`{title}`|
|投稿视频|:white_check_mark:|`https://www.bilibili.com/video/BV1vZ4y1M7mQ` <br/> `https://www.bilibili.com/video/av371660125`  <br/> `av371660125` <br/> `BV1vZ4y1M7mQ`|`{title}/{name}`|
|番剧|:x:|`https://www.bilibili.com/bangumi/play/ep395211` <br/> `ep395211`|`{name}`|
|番剧|:white_check_mark:|`https://www.bilibili.com/bangumi/play/ep395211` <br/> `https://www.bilibili.com/bangumi/play/ss38221` <br/> `https://www.bilibili.com/bangumi/media/md28233903` <br/> `ep395211` <br/> `ss38221` <br/> `md28233903`|`{title}/{name}`|
|用户指定收藏夹|:white_check_mark:|`https://space.bilibili.com/100969474/favlist?fid=1306978874`|`{username}的收藏夹/{series_title}/{title}/{name}`|
|用户全部收藏夹|:white_check_mark:|`https://space.bilibili.com/100969474/favlist`|`{username}的收藏夹/{series_title}/{title}/{name}`|
|UP 主个人空间|:white_check_mark:|`https://space.bilibili.com/100969474/video`|`{username}的全部投稿视频/{title}/{name}`|
|合集和视频列表|:white_check_mark:|`https://space.bilibili.com/361469957/channel/collectiondetail?sid=23195` <br/> `https://space.bilibili.com/100969474/channel/seriesdetail?sid=1947439` <br/> `https://www.bilibili.com/medialist/play/100969474?business=space_series&business_id=1947439`|`{series_title}/{title}/{name}`|

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

> 大部分参数与 bilili 重合，可参考 [bilili 的 cli 文档](https://bilili.nyakku.moe/cli/)

yutto 支持一些基础参数，无论是批量下载还是单视频下载都适用。

<details>
<summary>点击展开详细参数</summary>

#### 最大并行 worker 数量

-  参数 `-n` 或 `--num-workers`
-  默认值 `8`

与 bilili 不同的是，yutto 并不是使用多线程实现并行下载，而是使用协程实现的，本参数限制的是最大的并行 Worker 数量。

#### 指定视频清晰度等级

-  参数 `-q` 或 `--video-quality`
-  可选值 `127 | 126 | 125 | 120 | 116 | 112 | 80 | 74 | 64 | 32 | 16`
-  默认值 `127`

清晰度对应关系如下

<!-- prettier-ignore -->
|code|清晰度|
|:-:|:-:|
|127|8K 超高清|
|126|杜比视界|
|125|HDR 真彩|
|120|4K 超清|
|116|1080P 60帧|
|112|1080P 高码率|
|80|1080P 高清|
|74|720P 60帧|
|64|720P 高清|
|32|480P 清晰|
|16|360P 流畅|

并不是说指定某个清晰度就一定会下载该清晰度的视频，yutto 只会尽可能满足你的要求，如果不存在指定的清晰度，yutto 就会按照默认的清晰度搜索机制进行调节，比如指定清晰度为 `80`，**首先会依次降清晰度搜索** `74`、`64`、`32`、`16`，如果依然找不到合适的则**继续升清晰度搜索** `112`、`116`、`120`、`125`、`126`、`127`。

值得注意的是，目前杜比视界视频只能简单下载音视频流并合并，合并后并不能达到在线观看的效果。

#### 指定音频码率等级

-  参数 `-aq` 或 `--audio-quality`
-  可选值 `30280 | 30232 | 30216`
-  默认值 `30280`

码率对应关系如下

<!-- prettier-ignore -->
|code|码率|
|:-:|:-:|
|30280|320kbps|
|30232|128kbps|
|30216|64kbps|

码率自动调节机制与视频清晰度一致，也采用先降后升的匹配机制。

#### 指定视频编码

-  参数 `--vcodec`
-  下载编码可选值 `"av1" | "hevc" | "avc"`
-  保存编码可选值 FFmpeg 所有可用的视频编码器
-  默认值 `"avc:copy"`

该参数略微复杂，前半部分表示在下载时**优先**选择哪一种编码的视频流，后半部分则表示在合并时如何编码视频流，两者使用 `:` 分隔。

值得注意的是，前半的下载编码只是优先下载的编码而已，如果不存在该编码，则仍会像视频清晰度调节机制一样自动选择其余编码。

而后半部分的参数如果设置成非 `copy` 的值则可以确保在下载完成后对其进行重新编码，而且不止支持 `av1`、`hevc` 与 `avc`，只要你的 FFmpeg 支持的视频编码器，它都可以完成。

#### 指定音频编码

-  参数 `--acodec`
-  下载编码可选值 `"mp4a"`
-  保存编码可选值 FFmpeg 所有可用的音频编码器
-  默认值 `"mp4a:copy"`

详情同视频编码。

#### 仅下载视频流

-  参数 `--video-only`
-  默认值 `False`

#### 仅下载音频流

-  参数 `--audio-only`
-  默认值 `False`

仅下载其中的音频流，保存为 `.aac` 文件。

值得注意的是，在不选择视频流时，嵌入字幕、弹幕功能将无法工作。

#### 弹幕格式选择

-  参数 `-df` 或 `--danmaku-format`
-  可选值 `"ass" | "xml" | "protobuf"`
-  默认值 `"ass"`

B 站提供了 `xml` 与 `protobuf` 两种弹幕数据接口，yutto 会自动下载 `xml` 格式弹幕并转换为 `ass` 格式，如果你不喜欢 yutto 自动转换的效果，可以选择输出格式为 `xml` 或 `protobuf`，手动通过一些工具进行转换，比如 yutto 和 bilili 所使用的 [biliass](https://github.com/ShigureLab/biliass)，或者使用 [us-danmaku](https://tiansh.github.io/us-danmaku/bilibili/) 进行在线转换。

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

#### 存放子路径模板

-  参数 `-tp` 或 `--subpath-template`
-  可选参数变量 `title | id | name | username | series_title | pubdate` （以后可能会有更多）
-  默认值 `"{auto}"`

通过配置子路径模板可以灵活地控制视频存放位置。

默认情况是由 yutto 自动控制存放位置的。比如下载单个视频时默认就是直接存放在设定的根目录，不会创建一层容器目录，此时自动选择了 `{name}` 作为模板；而批量下载时则会根据视频层级生成多级目录，比如番剧会是 `{title}/{name}`，首先会在设定根目录里生成一个番剧名的目录，其内才会存放各个番剧剧集视频，这样方便了多个不同番剧的管理。当然，如果你仍希望将番剧直接存放在设定根目录下的话，可以修改该参数值为 `{name}`即可。

另外，该功能语法由 Python format 函数模板语法提供，所以也支持一些高级的用法，比如 `{id:0>3}{name}`。

值得注意的是，并不是所有变量在各种场合下都会提供，比如 `username` 变量当前仅在 UP 主全部投稿视频/收藏夹才提供，在其它情况下不应使用它。各变量详细作用域描述见下表：

<!-- prettier-ignore -->
|Variable|Description|Scope|
|-|-|-|
|title|系列视频总标题（番剧名/投稿视频标题）|全部|
|id|系列视频单 p 顺序标号|全部|
|name|系列视频单 p 标题|全部|
|username|UP 主用户名|个人空间、收藏夹、合集、视频列表下载|
|series_title|合集标题|收藏夹、视频合集、视频列表下载|
|pubdate|投稿日期|仅投稿视频|

> 未来可能会对路径变量及默认路径模板进行调整

#### url 别名文件路径

-  参数 `-af` 或 `--alias-file`
-  默认值 `None`

指定别名文件路径，别名文件中存放一个别名与其对应的 url，使用空格或者 `=` 分隔，示例如下：

```
rimuru1=https://www.bilibili.com/bangumi/play/ss25739/
rimuru2=https://www.bilibili.com/bangumi/play/ss36170/
rimuru-nikki=https://www.bilibili.com/bangumi/play/ss38221/
```

比如将上述内容存储到 `~/.yutto_alias`，则通过以下命令即可解析该文件：

```bash
yutto rimuru1 --batch --alias-file='~/.yutto_alias'
```

当参数值为 `-` 时，会从标准输入中读取：

```bash
cat ~/.yutto_alias | yutto rimuru-nikki --batch --alias-file -
```

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

#### 不下载弹幕

-  参数 `--no-danmaku`
-  默认值 `False`

#### 不下载字幕

-  参数 `--no-subtitle`
-  默认值 `False`

#### 不显示颜色

-  参数 `--no-color`
-  默认值 `False`

#### 不显示进度条

-  参数 `--no-progress`
-  默认值 `False`

#### 启用 Debug 模式

-  参数 `--debug`
-  默认值 `False`

#### 生成媒体元数据文件

-  参数 `--with-metadata`
-  默认值 `False`

目前媒体元数据生成尚在试验阶段，可能提取出的信息并不完整。

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
4. 个人空间、合集、收藏夹等批量下载暂不支持选集操作

#### 同时下载附加剧集

-  参数 `-s` 或 `--with-section`
-  默认值 `False`

</details>

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

### 使用 uvloop 提升协程效率

听说 uvloop 可以提高协程效率，如果你的系统非 Windows 的话，可以试一下安装 uvloop：

```bash
pip install uvloop
```

现在再运行就会发现不会弹出「没有安装 uvloop 的」 warning 了，至于具体提升多少我也不太清楚啦，没有测过

### 作为 log 输出到文件

虽说 yutto 不像 bilili 那样会全屏刷新，但进度条还是会一直刷新占据多行，可能影响 log 的阅读，另外颜色码也是难以阅读的，因此我们可以通过选项禁用他们：

```bash
yutto --no-color --no-progress > log
```

当然，如果你有

### 使用 url alias

yutto 新增的 url alias 可以让你下载正在追的番剧时不必每次都打开浏览器复制 url，只需要将追番列表存储在一个文件中，并为这些 url 起一个别名即可

```
rimuru-nikki=https://www.bilibili.com/bangumi/play/ss38221/
```

之后下载最新话只需要

```
yutto --batch rimuru-nikki --alias-file=/path/to/alias-file
```

### 使用文件列表

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
rimuru1 --batch -p $ --no-danmaku --vcodec="hevc:copy"
rimuru2 --batch -p $
```

而命令中则使用

```
yutto file:///path/to/list --vcodec="avc:copy"
```

最终下载的 rimuru1 会是 "hevc:copy"，而 rimuru2 则会是 "avc:copy"

另外，文件列表也是支持 alias 的，你完全可以为该列表起一个别名，一个比较特别的用例是将你所有追番的内容放在一个文件里，然后为该文件起一个别名（比如 `subscription`），这样只需要 `yutto subscription --alias-file path/to/alias/file` 就可以达到追番效果啦～

最后，列表也是支持嵌套的哦（虽然没什么用 2333）

## FAQ

### 名字的由来

[《転スラ日記》第一话 00:24](https://www.bilibili.com/bangumi/play/ep395211?t=24)

### yutto 会很快替代 bilili 吗

短期内不会，bilili 并不会消失，在一段时间内 bilili 仍会做纠错性维护，只是不会提供新特性了。

## Roadmap

### 2.0.0-beta

-  [x] feat: 支持 bare name (bare id, bare path)
-  [x] refactor: url 列表能够预线性展开
-  [x] feat: 添加各种 return code
-  [x] test: 编写单元测试

### 2.0.0-rc

-  [x] feat: 投稿视频描述文件支持
-  [x] refactor: 整理路径变量名
-  [ ] docs: 可爱的 logo（呜呜呜，有谁会做 logo 嘛？）
-  [ ] docs: 可爱的静态文档（可能需要 VitePress 到 1.0）

### future

-  [ ] feat: 增加参数 `--reverse` 以允许逆序下载（不清楚是否有必要诶……可能只是我个人的需求）
-  [ ] feat: 字幕、弹幕嵌入视频支持（也许？）
-  [ ] feat: 封面下载支持（也许？）
-  [ ] refactor: 以插件形式支持更多音视频处理方面的功能，比如类似 autosub 的工具（也许？）
-  [ ] feat: 更多批下载支持
-  [ ] feat: 以及更加可爱～

## 参考

-  基本结构：<https://github.com/SigureMo/bilili>
-  协程下载：<https://github.com/changmenseng/AsyncBilibiliDownloader>
-  弹幕转换：<https://github.com/ShigureLab/biliass>
-  样式设计：<https://github.com/willmcgugan/rich>

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)
