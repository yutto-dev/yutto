# 小技巧

## 通过 Agent 使用

如果你有趁手的 Agent，你也可以通过如下命令来安装我的 skill：

```bash
npx skills add https://github.com/yutto-dev/yutto --skill bilibili-video-download
```

之后请直接描述你的需求，agent 就会帮你补齐环境检查、登录状态检查、下载目录和最终命令执行流程啦～例如：

- “帮我下载 BVXXXXXXX 视频到 `/tmp/video`”
- “把番剧 epxxxxxxx 最新一话下载到 `/data/anime`”
- “下载用户 xxxxxx 的收藏夹，只要音频，保存到 `/downloads/music`”
- “下载视频 BVXXXXXXX，4K 超高清，保存到桌面”

## 作为 log 输出到文件

由于进度条会一直刷新占据多行，可能影响 log 的阅读，另外颜色码也是难以阅读的，因此可以通过选项禁用它们：

```bash
yutto --no-color --no-progress <url> > log
```

## 使用配置自定义默认参数

如果你希望修改我的部分参数，那么可能每次运行都需要在后面加上长长一串选项，为了避免这个问题，你可以尝试使用配置文件

```toml
# ~/.config/yutto/yutto.toml
#:schema https://raw.githubusercontent.com/yutto-dev/yutto/refs/heads/main/schemas/config.json
[basic]
dir = "~/Movies/yutto"
num_workers = 16
fetch_workers = 16
vcodec = "av1:copy"

[auth]
auth = "SESSDATA=***************; bili_jct=***************"
```

当然，请手动修改 `auth` 内容为自己的 Cookie 哦～

## 下载流量控制

yutto 的媒体下载由 Haya 核心统一调度。它会把 HTTP Range block 拆成固定 64 KiB page，并通过有界窗口限制尚未连续写入的数据量；如果最前方的块持续失败，调度器会有限重试、切换等价镜像，并把大块逐步拆小，而不是让后方任务无限堆积。

文件始终只按连续前缀顺序写入。下载中断后再次运行时，会从现有临时媒体文件的长度继续；`--overwrite` 仍会从零开始。
