# yutto 贡献快速指南

很高兴你对参与 yutto 的贡献感兴趣，在提交你的贡献之前，请花一点点时间阅读本指南

## 开发工具链

为了获得最佳的开发体验，希望你能够安装一些开发工具

这些工具都是可选的，都有一定的替代方案，不过可能会稍微麻烦些……

### 项目管理工具 uv

[uv](https://docs.astral.sh/uv/) 是 yutto 用来进行项目管理的工具，你可以从[安装指南](https://docs.astral.sh/uv/getting-started/installation/)找到合适的安装方式～

### 命令执行工具 just

[just](https://github.com/casey/just) 是一款用 rust 编写的简单易用的命令执行工具，通过它可以方便地执行一些开发时常用的命令。安装方法请参考[它的文档](https://github.com/casey/just#installation)

> 替代方案（不方便安装或者 Windows 上无法运行这些命令时建议使用）：自行查看 justfile 中对应的详细命令。

### 编辑器 Visual Studio Code

[VS Code](https://github.com/microsoft/vscode) 是一款功能强大的编辑器，由于 yutto 全面使用了 [Type Hints](https://docs.python.org/3/library/typing.html)，所以这里建议使用 VS Code + 扩展 pylance 来保证类型提示的准确性，同时配置 Format/Lint 工具 [Ruff](https://github.com/astral-sh/ruff) 以保证代码格式的一致性。

当然，如果你有更熟悉的编辑器或 IDE 的话，也是完全可以的。

### Rust 开发工具链

yutto 虽然是一个 Python 项目，但是为了获得更好的性能，yutto 的部分功能模块是使用 Rust 编写的，这包含了当前 monorepo 中的 package biliass 以及 yutto 中的部分核心模块（下载器模块 haya 等）。因此如需开发 yutto，安装 Rust 开发工具链是必要的，安装方法请参考 [Rust 官方文档](https://www.rust-lang.org/tools/install)

## 本地调试

如果你想要本地调试，最佳实践是从 GitHub 上下载最新的源码来运行

```bash
git clone git@github.com:yutto-dev/yutto.git
cd yutto/
uv sync
uv run yutto -v
```

注意本地调试请不要直接使用 `yutto` 命令，那只会运行从 pip 安装的 yutto，而不是本地调试的 yutto。

另外请注意如果你确定想为 yutto 做贡献请 fork 之后 clone 自己的 repo 再修改，以便发起 PR。

## 架构设计

这部分内容带你了解下 yutto 的主要模块结构与工作流程。

> 本部分内容可能略有滞后，这里列出的是 2026-08-22 时 [487aab0f6764bd40a072d5969d4019bc390d2912](https://github.com/yutto-dev/yutto/tree/487aab0f6764bd40a072d5969d4019bc390d2912) 的模块结构。

### 模块结构

```text
.
├── .github
│   └── workflows                         # CI、构建与发布工作流
├── docs                                  # VitePress 文档站点
├── packages
│   └── biliass                           # 独立发布的 biliass package
│       ├── rust                          # biliass Rust 扩展
│       └── src
│           └── biliass                   # biliass Python package
├── rust                                  # yutto Rust workspace
│   └── crates
│       ├── haya                          # 异步 Range 下载核心
│       ├── haya-http                     # haya 的 HTTP 适配层
│       └── yutto                         # 原生会话、下载后端与 PyO3 绑定
├── schemas                               # 生成的配置 Schema
├── scripts                               # 版本读取、Schema 生成等维护脚本
├── skills                                # 随仓库分发的使用说明
├── src
│   └── yutto                             # yutto Python package
│       ├── api                           # Bilibili API 封装
│       │   ├── __init__.py
│       │   ├── bangumi.py                # 番剧相关
│       │   ├── cheese.py                 # 课程相关
│       │   ├── collection.py             # 合集相关
│       │   ├── danmaku.py                # 弹幕相关
│       │   ├── space.py                  # 个人空间相关
│       │   ├── ugc_video.py              # 投稿视频相关
│       │   └── user_info.py              # 用户信息相关
│       ├── cli                           # 命令行界面
│       │   ├── __init__.py
│       │   ├── cli.py                    # 参数解析
│       │   ├── event_renderer.py         # CLI 事件渲染
│       │   ├── request_adapter.py        # CLI 参数到请求模型的转换
│       │   └── settings.py               # 配置文件模型与加载
│       ├── core                          # 与前端无关的应用层
│       │   ├── __init__.py
│       │   ├── application.py            # 应用编排
│       │   ├── events.py                 # 下载事件
│       │   ├── execution.py              # 请求级执行上下文
│       │   ├── operation.py              # 事件与日志绑定
│       │   ├── request.py                # 下载请求模型
│       │   ├── result.py                 # 下载与解析结果模型
│       │   ├── serialization.py          # 结果序列化
│       │   └── task_service.py           # server 任务服务
│       ├── downloader                    # 下载处理模块
│       │   ├── __init__.py
│       │   ├── artifact_writer.py        # 字幕、弹幕等附加资源写入
│       │   ├── downloader.py             # 单条目下载入口
│       │   ├── executor.py               # 下载计划执行
│       │   ├── media_muxer.py            # FFmpeg 音视频封装
│       │   ├── path_leases.py            # 输出路径租约
│       │   ├── planner.py                # 下载计划生成
│       │   ├── progressbar.py            # 下载进度显示
│       │   ├── selector.py               # 音视频流选择
│       │   └── transfer.py               # 原生媒体传输
│       ├── extractor                     # 页面提取器
│       │   ├── utils
│       │   │   ├── __init__.py
│       │   │   ├── batch.py              # 批量提取辅助方法
│       │   │   └── favourite.py          # 收藏夹辅助方法
│       │   ├── __init__.py
│       │   ├── _abc.py                   # 提取器抽象类
│       │   ├── bangumi.py                # 番剧单话
│       │   ├── bangumi_batch.py          # 番剧全集
│       │   ├── cheese.py                 # 课程单话
│       │   ├── cheese_batch.py           # 课程全集
│       │   ├── collection.py             # 合集
│       │   ├── common.py                 # 低阶提取器（投稿视频、番剧、课程），每种视频类型对应一个低阶提取器
│       │   ├── favourites.py             # 收藏夹
│       │   ├── outcome.py                # 提取结果模型
│       │   ├── series.py                 # 视频列表
│       │   ├── ugc_video.py              # 投稿视频单集
│       │   ├── ugc_video_batch.py        # 投稿视频批量
│       │   ├── user_all_favourites.py    # 全部收藏夹
│       │   ├── user_all_ugc_videos.py    # 个人空间全部投稿
│       │   └── user_watch_later.py       # 稍后再看
│       ├── media                         # 编码与清晰度定义
│       │   ├── __init__.py
│       │   ├── codec.py
│       │   └── quality.py
│       ├── runtime                       # 长生命周期任务运行时
│       │   ├── __init__.py
│       │   └── tasks.py
│       ├── server                        # 本地 WebSocket JSON-RPC server
│       │   ├── __init__.py
│       │   ├── command.py                # server 命令入口
│       │   ├── rpc.py                    # JSON-RPC 分发
│       │   ├── service.py                # server 策略与数据转换
│       │   └── websocket.py              # WebSocket server
│       ├── utils                         # 网络、FFmpeg 与通用工具
│       │   ├── console                   # 命令行输出
│       │   │   ├── __init__.py
│       │   │   ├── attributes.py
│       │   │   ├── colorful.py
│       │   │   ├── formatter.py
│       │   │   ├── logger.py
│       │   │   └── status_bar.py
│       │   ├── functional                # 通用函数
│       │   │   ├── __init__.py
│       │   │   ├── async_to_sync.py
│       │   │   ├── data_access.py
│       │   │   ├── filter_none_values.py
│       │   │   ├── functional.py
│       │   │   ├── singleton.py
│       │   │   └── xmerge.py
│       │   ├── __init__.py
│       │   ├── asynclib.py               # 异步辅助方法
│       │   ├── danmaku.py                # 弹幕资源处理
│       │   ├── fetcher.py                # 网络请求封装
│       │   ├── ffmpeg.py                 # FFmpeg 驱动
│       │   ├── filter.py                 # 发布时间过滤
│       │   ├── metadata.py               # 描述文件处理
│       │   ├── priority.py               # 编码与清晰度优先级
│       │   ├── subtitle.py               # 字幕资源处理
│       │   └── time.py                   # 时间处理
│       ├── __init__.py
│       ├── __main__.py                   # CLI 总入口
│       ├── __version__.py                # 版本号
│       ├── _core.pyi                     # 原生扩展类型声明
│       ├── _native.py                    # 原生扩展适配
│       ├── auth.py                       # 认证信息
│       ├── download_manager.py           # 请求解析与下载调度
│       ├── exceptions.py                 # 异常类型
│       ├── input_parser.py               # alias 与任务列表解析
│       ├── login.py                      # 登录流程
│       ├── path_templates.py             # 下载路径模板
│       ├── py.typed
│       ├── types.py                      # 主要类型声明
│       └── validator.py                  # 命令参数验证
├── tests                                 # 测试目录
│   ├── helpers                           # 测试辅助设施
│   ├── test_api                          # API 测试
│   ├── test_biliass                      # biliass 测试
│   ├── test_core                         # 应用层与执行上下文测试
│   ├── test_processor                    # 提取与下载处理测试
│   ├── test_runtime                      # 任务运行时测试
│   ├── test_server                       # server 测试
│   └── test_utils                        # 通用工具测试
├── CONTRIBUTING.md                       # 贡献指南
├── Dockerfile                            # yutto Docker 镜像
├── LICENSE                               # GPL-3.0 License
├── README.md                             # 项目说明
├── _typos.toml                           # typos 配置
├── justfile                              # 开发与 CI 命令入口
├── pyproject.toml                        # Python package 与 uv workspace 配置
└── uv.lock                               # Python 依赖锁文件
```

### 工作流程

切入代码的最好方式自然是从入口开始啦～ yutto 的命令行入口是 [`src/yutto/__main__.py`](./src/yutto/__main__.py)，这里列出了 yutto 整个的工作流程：

1. 使用 [`src/yutto/cli/cli.py`](./src/yutto/cli/cli.py) 解析参数，并利用 [`src/yutto/validator.py`](./src/yutto/validator.py) 进一步验证参数。
2. 利用 [`src/yutto/input_parser.py`](./src/yutto/input_parser.py) 解析 alias 和任务列表。
3. 利用 [`src/yutto/cli/request_adapter.py`](./src/yutto/cli/request_adapter.py) 将展开后的每组参数转换为下载请求。
4. 处理任务列表中的下载请求：
   1. 根据单话或批量模式初始化对应的 [`extractor`](./src/yutto/extractor/)。
   2. 利用 extractor 将裸 ID 转换为可识别的 URL。
   3. 重定向入口 URL，并选择能够处理该 URL 的 extractor。
   4. 从入口 URL 提取信息，构造解析任务：
      1. 如果是单话下载（继承 `yutto.extractor._abc.SingleExtractor`）：
         1. 解析标题、路径等基本信息。
         2. 构造用于获取音视频流和附加资源的解析任务。
      2. 如果是批量下载（继承 `yutto.extractor._abc.BatchExtractor`）：
         1. 解析并展平列表。
         2. 根据选集、发布时间、分区和预告等条件过滤列表。
         3. 为列表中的每一项构造解析任务。
   5. [`src/yutto/download_manager.py`](./src/yutto/download_manager.py) 根据 `--jobs` 设置并发调度各项，并将解析结果传入 [`src/yutto/downloader/downloader.py`](./src/yutto/downloader/downloader.py) 下载：
      1. 选择音视频清晰度和编码。
      2. 生成字幕、弹幕、描述文件等附加资源。
      3. 下载音频和视频。
      4. 使用 FFmpeg 合并音频和视频。

## 改动

嗯，你现在已经基本了解 yutto 的结构了，可以尝试去修改部分源码了。

## 测试

yutto 已经编写好了一些测试，请确保在改动后仍能通过测试

```bash
just test
```

当然，如果你修改的内容需要对测试用例进行修改和增加，请尽管修改。

## 文档更新

如果你的改动是需要用户感知的，请务必更新文档，文档位于 [docs](./docs) 目录下，你可以在本地启动文档服务来查看你的修改

在此之前，请确保自行安装 Node.js 24 或以上版本

```bash
# 启用 corepack，确保 pnpm 可用
corepack enable
# 安装依赖项
just docs-setup
# 启动文档开发服务器
just docs-dev
```

之后你可以在浏览器中访问 `http://localhost:5173` 来查看你的修改

## 代码格式化

yutto 使用 Ruff 对代码进行格式化，如果你的编辑器或 IDE 没有自动使用 Ruff 进行格式化，请使用下面的命令对代码进行格式化

```bash
just fmt
```

## 提交 PR

提交 PR 的最佳实践是 fork 一个新的 repo 到你的账户下，并创建一个新的分支，在该分支下进行改动后提交到 GitHub 上，并发起 PR（请注意在发起 PR 时不要取消掉默认已经勾选的 `Allow edits from maintainers` 选项）

```bash
# 首先在 GitHub 上 fork
git clone git@github.com:<YOUR_USER_NAME>/yutto.git         # 将你的 repo clone 到本地
cd yutto/                                                   # cd 到该目录
git remote add upstream git@github.com:yutto-dev/yutto.git  # 将原分支绑定在 upstream
git checkout -b <NEW_BRANCH>                                # 新建一个分支，名称随意，最好含有你本次改动的语义
git push origin <NEW_BRANCH>                                # 将该分支推送到 origin （也就是你 fork 后的 repo）
# 对源码进行修改、并通过测试
# 此时可以在 GitHub 发起 PR
```

如果你的贡献需要继续修改，直接继续向该分支提交新的 commit 即可，并推送到 GitHub，PR 也会随之更新

如果你的 PR 已经被合并，就可以放心地删除这个分支了

```bash
git checkout main                                           # 切换到 main
git fetch upstream                                          # 将原作者分支下载到本地
git merge upstream/main                                     # 将原作者 main 分支最新内容合并到本地 main
git branch -d <NEW_BRANCH>                                  # 删除本地分支
git push origin --delete <NEW_BRANCH>                       # 同时删除远程分支
```

## PR 规范

### 标题

表明你所作的更改即可，没有太过苛刻的格式（合并时会重命名）

如果可能，可以按照 `<gitmoji> <type>: <subject>` 来进行命名

这里的 `<type>` 采取和 vite 一样的可选值

> Vite Git Commit Message Convention 参考：<https://github.com/vitejs/vite/blob/main/.github/commit-convention.md>
>
> Gitmoji 参考：<https://gitmoji.dev/>

### 内容

尽可能按照模板书写

## 版本发布

> 本章节内容仅针对有发布权限的维护者

### 更新版本号

现阶段书写版本号的代码包括以下几个文件，发布版本前需要全部更改：

-  [`Dockerfile`](./Dockerfile)
-  [`pyproject.toml`](./pyproject.toml)
-  [`yutto/__version__.py`](./src/yutto/__version__.py)

### 发布到 PyPI

我们优先使用 GitHub Actions 构建并发布到 PyPI，这可以通过如下命令触发

```bash
just release
```

简单来说就是创建一个 tag 并 push，此时便会触发 GitHub Actions 中的 [Release](.github/workflows/yutto-build-and-release.yml) 构建

如果你想要手动发布到 PyPI，可以使用下面的命令

```bash
just publish
```

### 构建镜像并发布到 DockerHub

⚠️ 必须在发布到 PyPI 之后

> 需预先自行安装 [Docker](https://docs.docker.com/get-docker/)

```bash
just docker-publish
```

### 发布到 Homebrew Tap

⚠️ 必须在发布到 PyPI 之后

修改 <https://github.com/SigureMo/homebrew-tap/blob/main/Formula/yutto.rb>，按照提示构建新版本 Formula。

**因为有你，yutto 才会更加完善，感谢你的贡献 (・ω< )★**
