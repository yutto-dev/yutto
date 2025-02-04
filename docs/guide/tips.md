# 小技巧

## 作为 log 输出到文件

虽说我不像 bilili 前辈那样会全屏刷新，但进度条还是会一直刷新占据多行，可能影响 log 的阅读，另外颜色码也是难以阅读的，因此我们可以通过选项禁用他们：

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
sessdata = "***************"
num_workers = 16
vcodec = "av1:copy"
```

当然，请手动修改 `sessdata` 内容为自己的 `SESSDATA` 哦～

:::: tip

本方案可替代原有的「自定义命令别名」方式～

::: details 原「自定义命令别名」方案

在 `~/.zshrc` / `~/.bashrc` 中自定义一条 alias，像这样

```bash
alias ytt='yutto -d ~/Movies/yutto/ -c `cat ~/.sessdata` -n 16 --vcodec="av1:copy"'
```

这样我每次只需要 `ytt <url>` 就可以直接使用这些参数进行下载啦～

由于我提前在 `~/.sessdata` 存储了我的 `SESSDATA`，所以避免每次都要手动输入 cookie 的问题。

:::

::::
