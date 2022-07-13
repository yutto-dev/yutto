# 快速开始

嘿！你好呀～这里是 yutto，一个可爱的命令行驱动的 B 站视频下载工具～

我的工作方式非常简单快捷，你只需要提供给我 B 站的链接，我就可以帮你下载好视频啦～就像这样：

<div class="language-sh">
<pre>
<code>
❯ yutto https://www.bilibili.com/video/BV1Er4y1h7FX
 <span style="color:#0096FF;">INFO</span>  未提供 SESSDATA，无法下载会员专享剧集哟～
<span style="color:var(--vp-code-block-bg);background-color:cyan;"> 投稿视频 </span> 《原神》2.5版本PV：「薄樱初绽时」
 <span style="color:#0096FF;">INFO</span>  开始处理视频 《原神》2.5版本PV：「薄樱初绽时」
 <span style="color:#0096FF;">INFO</span>  共包含以下 12 个视频流：
 <span style="color:#0096FF;">INFO</span>  <span style="color:#0096FF;">* 0 [AVC ] [1920x1080] &lt;1080P 高清&gt; #3</span>
 <span style="color:#0096FF;">INFO</span>    1 [HEVC] [1920x1080] &lt;1080P 高清&gt; #3
 <span style="color:#0096FF;">INFO</span>    2 [AV1 ] [1920x1080] &lt;1080P 高清&gt; #3
 <span style="color:#0096FF;">INFO</span>    3 [AVC ] [1280x720 ] &lt;720P 高清 &gt; #3
 <span style="color:#0096FF;">INFO</span>    4 [HEVC] [1280x720 ] &lt;720P 高清 &gt; #3
 <span style="color:#0096FF;">INFO</span>    5 [AV1 ] [1280x720 ] &lt;720P 高清 &gt; #3
 <span style="color:#0096FF;">INFO</span>    6 [AVC ] [ 852x480 ] &lt;480P 清晰 &gt; #3
 <span style="color:#0096FF;">INFO</span>    7 [HEVC] [ 852x480 ] &lt;480P 清晰 &gt; #3
 <span style="color:#0096FF;">INFO</span>    8 [AV1 ] [ 852x480 ] &lt;480P 清晰 &gt; #3
 <span style="color:#0096FF;">INFO</span>    9 [HEVC] [ 640x360 ] &lt;360P 流畅 &gt; #3
 <span style="color:#0096FF;">INFO</span>   10 [AVC ] [ 640x360 ] &lt;360P 流畅 &gt; #3
 <span style="color:#0096FF;">INFO</span>   11 [AV1 ] [ 640x360 ] &lt;360P 流畅 &gt; #3
 <span style="color:#0096FF;">INFO</span>  共包含以下 3 个音频流：
 <span style="color:#0096FF;">INFO</span>  <span style="color:magenta;">* 0 [MP4A] &lt;320kbps &gt;</span>
 <span style="color:#0096FF;">INFO</span>    1 [MP4A] &lt; 64kbps &gt;
 <span style="color:#0096FF;">INFO</span>    2 [MP4A] &lt;128kbps &gt;
<span style="color:var(--vp-code-block-bg);background-color:cyan;"> 弹幕 </span> ASS 弹幕已生成
 <span style="color:#0096FF;">INFO</span>  开始下载……
<span style="color:green;">━━━━━━━━━━━━━━━━━━━━━━╸</span>━━━━━━━━━  45.98 MiB/ 65.79 MiB 8.79 MiB/⚡
</code>
</pre>
</div>

下面我将会从安装开始介绍我的使用方式～

## 环境配置

如果你使用 homebrew、yay、docker 等可以自动帮助你配置环境的方式来安装，此部分内容可以跳过～

### FFmpeg 下载与配置

### Python 解释器安装

## 从安装开始

我提供了多种安装方式，你可以自行选择其中一种即可～

### 通过包管理器一键安装<sup>测试中</sup>

我目前可以通过一些包管理器直接安装～这是最简单快捷的安装方式～

Homebrew 用户可以尝试下面的命令：

```bash
brew tap siguremo/tap
brew install yutto
```

使用 yay（Arch 上的 AUR 包管理器）的用户可以尝试下这样的命令（感谢 @ouuan）：

```bash
yay -S yutto
```

### 使用 Docker<sup>测试中</sup>

你也可以尝试使用 docker 直接运行（运行时的更多参数需要参考下后面的内容～）

```bash
docker run --rm -it -v /path/to/download:/app siguremo/yutto <url> [options]
```

与直接本机运行不同的是，这里的下载目标路径是通过 `-v <path>:/app` 指定的，也就是说 docker 内的我会将内容下载到 docker 里的 `/app` 目录下，与之相对应的挂载点 `<path>` 就是下载路径。你也可以直接挂载到 `$(pwd)`，此时就和本机运行我的默认行为一致啦，也是下载到当前目录下～

### 使用 pip 安装 <sup>需自行配置环境</sup>

由于我是基于 Python 开发的，因此我当然也是可以通过 pip 安装啦。

```bash
pip install --pre yutto
```

如果你是非 Windows 系统，可以通过 `[uvloop]` 标志安装额外的 `uvloop` 包以获得更好的协程性能。

```bash
pip install --pre "yutto[uvloop]"
```

### 从 GitHub 获取最新源码手动安装 <sup>需自行配置环境</sup>

```bash
git clone https://github.com/yutto-dev/yutto.git
cd yutto/
pip install poetry
poetry build
pip install ./dist/yutto-*.whl
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
