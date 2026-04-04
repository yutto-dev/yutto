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

虽说我不像 bilili 前辈那样会全屏刷新，但进度条还是会一直刷新占据多行，可能影响 log 的阅读，另外颜色码也是难以阅读的，因此可以通过选项禁用它们：

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
vcodec = "av1:copy"

[auth]
auth = "SESSDATA=***************; bili_jct=***************"
```

当然，请手动修改 `auth` 内容为自己的 Cookie 哦～
