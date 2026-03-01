# 个人信息认证参数

为了能够解锁更高清晰度以及或者大会员专享的剧集，你需要提供自己的登录信息，不过放心，yutto 只会使用这些信息来访问 B 站，并不会上传或者泄露你的信息～

yutto 支持通过 `yutto login` 命令扫码登录并把认证信息写入 auth 文件，也支持直接通过 `--auth` 选项传入 Cookie 字符串。

对于第一种方式，执行 `yutto login` 后会提示你扫码登录：

```bash
yutto login
 INFO  发现配置文件 yutto.toml，加载中……
 <这里会有一个二维码>
 INFO  请使用哔哩哔哩 App 扫码并确认登录
 INFO  二维码待扫描
 INFO  登录成功，已写入认证文件：~/.config/yutto/auth.toml（profile: default，url: https://www.bilibili.com）
```

登录后，后续直接使用 `yutto` 命令时就会自动加载认证信息了：

```bash
yutto <url>
 INFO  发现配置文件 yutto.toml，加载中……
 大会员  成功以大会员身份登录～
```

对于第二种方式，你可以直接在命令行中使用 `--auth` 选项传入 Cookie 字符串：

```bash
yutto <url> --auth "SESSDATA=xxxxx; bili_jct=yyyyy"
```

::: details `SESSDATA`、`bili_jct` 获取方式

这里用 Chrome 作为示例，其它浏览器请尝试类似方法。

首先，用你的帐号登录 B 站，然后随便打开一个 B 站网页，比如[首页](https://www.bilibili.com/)。

按 F12 打开开发者工具，切换到 Network 栏，刷新页面，此时第一个加载的资源应该就是当前页面的 html，选中该资源，在右侧 「Request Headers」 中找到 「cookie」，在其中找到类似于 `SESSDATA=d8bc7493%2C2843925707%2C08c3e*81;` 的一串字符串，复制这里的 `d8bc7493%2C2843925707%2C08c3e*81`，这就是你需要的 `SESSDATA`，你可以同样的方法找到 `bili_jct`。

:::

## Inline Cookie 字符串

- 参数 `--auth`
- 配置项 `auth.auth`
- 默认值 `""`

推荐直接使用 inline cookie 字符串：

```bash
yutto <url> --auth "SESSDATA=xxxxx; bili_jct=yyyyy"
```

对应配置文件写法：

```toml [yutto.toml]
#:schema https://raw.githubusercontent.com/yutto-dev/yutto/refs/heads/main/schemas/config.json
[auth]
auth = "SESSDATA=xxxxx; bili_jct=yyyyy"
```

## 认证文件

- 参数 `--auth-config`
- 配置项 `auth.auth_file`

用于指定 `auth.toml` 的路径，优先级：

1. `--auth-config`
2. `auth.auth_file`
3. 默认路径（`~/.config/yutto/auth.toml` 或系统等价路径）

## 认证 Profile

- 参数 `--auth-profile`
- 配置项 `auth.auth_profile`
- 默认值 `"default"`

用于在同一个 `auth.toml` 中切换不同认证条目，比如工作号/个人号分离。

## `login` 子命令

`yutto login` 会扫码登录并把认证信息写入 auth 文件（包含 `SESSDATA` 与 `bili_jct`）。

```bash
yutto login
yutto login --auth-profile default
yutto login --auth-config ~/.config/yutto/auth.toml
```

## 已弃用参数

- 参数 `-c` / `--sessdata`：已弃用

目前为了兼容旧脚本，`--sessdata` 仍然可用，但会打印弃用提示，并在前处理阶段自动转换到 `auth`。

推荐尽快迁移到 `--auth`，后续会以 `--auth` 作为唯一推荐入口。
