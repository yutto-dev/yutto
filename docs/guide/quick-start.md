# 快速开始

嗨～你好呀～这里是 yutto，一个可爱的命令行驱动的 B 站视频下载工具～

我的工作方式非常简单快捷，你只需要提供给我 B 站的链接，我就可以帮你下载好视频啦～就像这样：

<div class="language-sh">
<pre>
<code>
<span style="color:magenta;">❯</span> yutto https://www.bilibili.com/video/BV1ZEf9YiE2h/
 <span style="color:#0096FF;">INFO</span>  发现配置文件 yutto.toml，加载中……
<span style="color:var(--vp-code-block-bg);background-color:magenta;font-weight:bold"> 大会员 </span> 成功以大会员身份登录～
<span style="color:var(--vp-code-block-bg);background-color:cyan;"> 投稿视频 </span> 植物大战僵尸融合版2.2正式版宣传片
 <span style="color:#0096FF;">INFO</span>  开始处理视频 植物大战僵尸融合版2.2正式版宣传片
 <span style="color:#0096FF;">INFO</span>  共包含以下 15 个视频流：
 <span style="color:#0096FF;">INFO</span>  <span style="color:#0096FF;">* 0 [AVC ] [1920x1080] <1080P 60帧> #3</span>
 <span style="color:#0096FF;">INFO</span>    1 [HEVC] [1920x1080] &lt;1080P 60帧&gt; #3
 <span style="color:#0096FF;">INFO</span>    2 [AV1 ] [1920x1080] &lt;1080P 60帧&gt; #3
 <span style="color:#0096FF;">INFO</span>    3 [AVC ] [1920x1080] &lt;1080P 高清&gt; #3
 <span style="color:#0096FF;">INFO</span>    4 [HEVC] [1920x1080] &lt;1080P 高清&gt; #3
 <span style="color:#0096FF;">INFO</span>    5 [AV1 ] [1920x1080] &lt;1080P 高清&gt; #3
 <span style="color:#0096FF;">INFO</span>    6 [AVC ] [1280x720 ] &lt;720P 高清 &gt; #3
 <span style="color:#0096FF;">INFO</span>    7 [HEVC] [1280x720 ] &lt;720P 高清 &gt; #3
 <span style="color:#0096FF;">INFO</span>    8 [AV1 ] [1280x720 ] &lt;720P 高清 &gt; #3
 <span style="color:#0096FF;">INFO</span>    9 [AVC ] [ 852x480 ] &lt;480P 清晰 &gt; #3
 <span style="color:#0096FF;">INFO</span>   10 [HEVC] [ 852x480 ] &lt;480P 清晰 &gt; #3
 <span style="color:#0096FF;">INFO</span>   11 [AV1 ] [ 852x480 ] &lt;480P 清晰 &gt; #3
 <span style="color:#0096FF;">INFO</span>   12 [AVC ] [ 640x360 ] &lt;360P 流畅 &gt; #3
 <span style="color:#0096FF;">INFO</span>   13 [HEVC] [ 640x360 ] &lt;360P 流畅 &gt; #3
 <span style="color:#0096FF;">INFO</span>   14 [AV1 ] [ 640x360 ] &lt;360P 流畅 &gt; #3
 <span style="color:#0096FF;">INFO</span>  共包含以下 3 个音频流：
 <span style="color:#0096FF;">INFO</span>  <span style="color:magenta;">* 0 [MP4A] <320kbps ></span>
 <span style="color:#0096FF;">INFO</span>    1 [MP4A] &lt; 64kbps &gt;
 <span style="color:#0096FF;">INFO</span>    2 [MP4A] &lt;128kbps &gt;
<span style="color:var(--vp-code-block-bg);background-color:cyan;"> 弹幕 </span> ASS 弹幕已生成
 <span style="color:#0096FF;">INFO</span>  开始下载……
<span style="color:green;">━━━━━━━━━━━━━━━━━━━━━━━━━━━╸</span>━━━━━━━━━━━━━━━━━━━━━━  39.05 MiB/ 72.13 MiB 32.22 MiB/⚡
</code>
</pre>
</div>

下面我将会从安装开始介绍我的使用方式～

## 环境配置

::: tip 注意

如果你使用 Homebrew、yay/paru/pacman、Docker 等可以自动帮助你配置环境的方式来安装，此部分内容可以跳过～

:::

### Python 解释器安装 <Badge type="tip" text="3.10+"/>

你可能会好奇，我是怎么指挥你的设备来帮助你下载想要的视频的，其实这很大程度归功于 Python 前辈的帮忙，有了 <span title="指 Python">TA</span>，我才能和你的设备正常沟通。不过有一点需要注意的就是，必须要 3.10 以上版本的 Python 前辈才可以哦，不然可能 <span title="指 Python">TA</span> 也听不懂我的一些「方言」呢～

如果你是 Windows，请自行去 [Python 官网](https://www.python.org/)下载并安装，安装时记得要勾选「Add to PATH」选项，不然可能需要你手动添加到环境变量。

macOS 及 Linux 发行版一般都自带 Python 环境，但要注意版本。

安装完成后可以通过 `python --version` 来确定是否正确安装，当然这里仍然需要再次注意一下版本号～

### FFmpeg 下载与配置

由于 B 站视频是需要混流合并的，因此我的正常运作离不开 FFmpeg 前辈的帮助，因此你需要事先将 <span title="指 FFmpeg">TA</span> 正确安装在你的设备上～

如果你所使用的操作系统是 Windows，操作有些些麻烦，你需要[手动下载](https://ffmpeg.org/download.html)后，并将可执行文件所在路径设置到到你的环境变量中～

::: details 详细操作

打开下载链接后，在 「Get packages & executable files」 部分选择 Windows 徽标，在 「Windows EXE Files」 下找到 「Windows builds by BtbN」 并点击，会跳转到一个 GitHub Releases 页面，在 「Latest release」 里就能看到最新的构建版本了～

下载后解压，并随便放到一个安全的地方，然后在文件夹中找到 `ffmpeg.exe`，复制其所在文件夹路径。

右击「此电脑」，选择属性，在其中找到「高级系统设置」 → 「环境变量」，双击 PATH，在其中添加刚刚复制的路径（非 Win10 系统操作略有差异，请自行查阅「环境变量设置」的方法）。

保存保存，完事啦～～～

:::

当然，如果你使用的是 macOS 或者 Linux 发行版的话，直接使用自己的包管理器就能一键完成该过程。

:::: details 示例

这里给出一些示例，不会一一列举，其它的大家可以自行搜索下～

::: code-group

```bash [macOS]
brew install ffmpeg
```

```bash [Ubuntu]
apt install ffmpeg
```

```bash [Arch]
pacman -S ffmpeg
```

:::

::::

此时，你可以尝试在终端上使用 `ffmpeg -version` 命令来测试下安装是否正确，只要显示的不是 `Command not found` 之类的提示就说明成功啦～

## 召唤 yutto

当当当，是时候主角登场啦～不过在此之前仍然需要学习一点小小的咒语～

你可以通过以下几种方式中的任意一种来召唤（安装）我，我随叫随到～

### 包管理器一键安装啦

我目前可以通过一些包管理器直接安装～这是最简单快捷的安装方式～

使用 Homebrew 的小伙伴可以尝试下下面的命令：

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

你也可以尝试使用 docker 直接运行（运行时的更多参数需要参考下后面的内容～）

```bash
docker run --rm -it -v /path/to/download:/app siguremo/yutto <url> [options]
```

与直接本机运行不同的是，这里的下载目标路径是通过 `-v <path>:/app` 指定的，也就是说 docker 内的我会将内容下载到 docker 里的 `/app` 目录下，与之相对应的挂载点 `<path>` 就是下载路径。你也可以直接挂载到 `$(pwd)`，此时就和本机运行我的默认行为一致啦，也是下载到当前目录下～

### pip/pipx/uv 安装 <sup>需自行配置环境</sup>

我的所有版本均已上传到 PyPI，因此你当然可以通过 pip 来安装啦～

```bash
pip install yutto
```

当然，你也可以通过 [pipx](https://github.com/pypa/pipx)/[uv](https://github.com/astral-sh/uv) 来安装（当然，前提是你要自己先安装 TA 们）

```bash
pipx install yutto      # 使用 pipx
uv tool install yutto   # 或者使用 uv
```

pipx/uv 会类似 Homebrew 无感地为我创建一个独立的虚拟环境，与其余环境隔离开，避免污染 pip 的环境，因此相对于 pip，pipx/uv 是更推荐的安装方式（uv 会比 pipx 更快些～）。

### 体验 main 分支最新特性 <sup>需自行配置环境</sup>

有些时候有一些在 main 分支还没有发布的新特性或者 bugfix，你可以尝试直接安装 main 分支的代码，最快的方式仍然是通过 pip 安装，只不过需要使用 git 描述符

```bash
pip install git+https://github.com/yutto-dev/yutto@main                 # 通过 pip
pipx install git+https://github.com/yutto-dev/yutto@main                # 或者通过 pipx
uv tool install git+https://github.com/yutto-dev/yutto.git@main         # 或者通过 uv
```

## yutto 一下～

嗯，跟随上面的指引后我应当可以正常工作啦，那么现在，请为我分配任务吧～

```bash
yutto <url>
```

没错，为我分配任务的方式就是这么简单～

不过值得注意的是这样只可以下载单个视频，如果有批量下载需求的话请添加 `-b/--batch` 参数：

```bash
yutto --batch <url>
# 或者使用其短参数
yutto -b <url>
```

此时我会认为该 url 是一个批量下载链接，会从其中解析出多个视频链接出来进行下载。

下面举例说明一下：

这里的 `<url>` 是 [《転スラ日記》](https://www.bilibili.com/bangumi/play/ep395211) 第一话链接，那么如果你只想下载该话的话只需要运行：

```bash
yutto https://www.bilibili.com/bangumi/play/ep395211
```

或者如果你想要该番剧全集，请运行：

```bash
yutto -b https://www.bilibili.com/bangumi/play/ep395211
```

## 下一步

很好，到此为止你已经了解如何让我来帮你下载视频啦～

不过你可能会有一些问题，比如：

- 为什么下载的视频不够清晰？我在线看的视频明明至少都有 1080P 的呀
- 为什么需要这么冗长的 url 才能下载视频？是否有更简洁的方式？

这里先简单卖个关子，因为这些答案你都可以在后续内容中找到，这才刚刚开始呢～

这里给出一些推荐内容，你可以尝试：

- 如果你希望了解我具体都支持哪些链接，可以尝试前往 [支持的链接](./supported-links) 查看
- 如果你希望了解我的进阶用法，可以尝试前往 [命令行参数](./cli/introduction) 查看
