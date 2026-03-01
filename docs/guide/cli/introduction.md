# 命令行参数

既然我是基于 CLI（Command Line Interface）的工具，那么自然而然，我支持很多命令行参数来让你更好地调度我。

就比如说，你可以添加 `-d` 参数来指定下载的视频路径，或者使用 `--auth` 参数来设置用于登录状态的 Cookie。

## 参数的使用方式

如果你是第一次接触命令行，那么你可能会对这些参数的使用方式感到困惑。

不过，不用担心，我会在这里为你详细地介绍一下。

### 指定参数值

比如你需要修改下载路径到 `/path/to/videos`，只需要

```bash
yutto <url> --dir /path/to/videos
# 或者使用短参数 -d
yutto <url> -d /path/to/videos
# 你也可以使用 = 将参数 key 和 value 连接在一起
yutto <url> -d=/path/to/videos
yutto <url> --dir=/path/to/videos
```

### 切换 `True` or `False`

对于那些不需要指定具体值，只切换 `True` or `False` 的参数，你也不需要在命令中指定值，比如开启强制覆盖已下载视频选项

```bash
yutto <url> --overwrite
# 或者
yutto <url> -w
```

### 多参数同时使用

当然，同时使用多个参数也是允许的，只需要写在一起即可，而且 `<url>` 和其它参数都不强制要求顺序，比如下面这些命令都是合法的

```bash
yutto <url> --overwrite --dir=/path/to/videos
yutto --overwrite -d /path/to/videos <url>
yutto -w <url> --d=/path/to/videos
```

## 更多参数

当然，这些只是冰山一角啦，我支持的参数远不止这些，你可以通过 `yutto --help` 来查看所有支持的参数。也可以前往以下页面查看具体介绍：

- [基础参数](./basic)
- [个人信息认证参数](./auth)
- [资源选择参数](./resource)
- [弹幕设置参数](./danmaku) <Badge text="Experimental" type="warning"/>
- [批量下载参数](./batch)

## 配置文件 <Badge text="Experimental" type="warning"/>

当你熟悉 CLI 界面后，可能每次下载视频的时候都需要输入一长串的参数，你可能会希望有一种方式来保存常用的参数，下次下载时直接使用，这时候配置文件就派上用场啦～

你可以通过 `--config` 参数来指定配置文件的路径，比如

```bash
yutto --config /path/to/config.toml <url>
```

我还支持配置自动发现，也就是说，如果不指定配置文件路径，我也会自动去以下路径查找配置文件的：

- 当前目录下的 `yutto.toml`
- [`XDG_CONFIG_HOME`](https://specifications.freedesktop.org/basedir-spec/latest/) 下的 `yutto/yutto.toml` 文件
- 非 Windows 系统下的 `~/.config/yutto/yutto.toml`，Windows 系统下的 `~/AppData/Roaming/yutto/yutto.toml`

你可以通过配置文件来设置一些默认参数，整体上与命令行参数基本一致，下面以一些示例来展示配置文件的写法：

```toml [yutto.toml]
#:schema https://raw.githubusercontent.com/yutto-dev/yutto/refs/heads/main/schemas/config.json
[basic]
# 设置下载目录
dir = "/path/to/download"
# 设置临时文件目录
tmp_dir = "/path/to/tmp"
# 设置大会员严格校验
vip_strict = true
# 设置登录严格校验
login_strict = true

[auth]
# 推荐的认证信息写法（inline cookie）
auth = "SESSDATA=***************; bili_jct=***************"

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

如果你使用 VS Code 对配置文件编辑，强烈建议使用 [Even Better TOML](https://marketplace.visualstudio.com/items?itemName=tamasfe.even-better-toml) 扩展，配合我提供的 schema，可以获得最佳的提示体验。
