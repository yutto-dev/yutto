# Server 模式 <Badge text="Experimental" type="warning" />

`yutto serve` 会启动一个只监听本机回环地址的 WebSocket server，供 WebUI、桌面应用或其他本地前端通过 JSON-RPC 2.0 调用。

## 启动

```bash
yutto serve --token-file ~/.config/yutto/server.token
```

默认监听 `ws://127.0.0.1:11223`。Token 依次从以下位置获取：

1. `YUTTO_SERVER_TOKEN` 环境变量；
2. `--token-file` 指定的文件；
3. 都未提供时，生成仅本次运行有效的随机 Token 并显示在终端。

若 `--token-file` 指向的文件尚不存在，yutto 会在首次启动时生成随机 Token 并以 `0600` 权限创建该文件，后续启动直接复用。在 POSIX 系统上，已有 Token 文件必须是权限不高于 `0600` 的普通文件，符号链接会被拒绝。

server 只接受回环地址。浏览器连接还需要用 `--allow-origin` 显式允许完整 Origin：

```bash
yutto serve \
  --token-file ~/.config/yutto/server.token \
  --allow-origin http://127.0.0.1:3000
```

## 调用流程

连接建立后，第一条消息必须调用 `server.authenticate`。Token 不放在 URL 中。

```json
{ "jsonrpc": "2.0", "id": 1, "method": "server.authenticate", "params": { "token": "YOUR_TOKEN" } }
```

认证成功后，可以提交下载任务：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "download.start",
  "params": {
    "request": {
      "source": { "url": "https://www.bilibili.com/video/BV..." },
      "output": { "directory": "番剧" }
    }
  }
}
```

`request` 使用与 yutto Core 相同的强类型请求模型。未提供的设置继承 server 启动时加载的 yutto 配置；认证 Cookie 不会放入请求，而是由 server 按 `access.auth_profile` 从 `--auth-file` 读取。配置里的 inline Cookie 与旧 `sessdata` 字段不会进入 server 请求边界。

可用方法如下：

| 方法               | 用途                                                         |
| ------------------ | ------------------------------------------------------------ |
| `server.info`      | 查询版本、协议版本和能力列表                                 |
| `download.start`   | 提交下载任务，返回任务快照                                   |
| `resolve.start`    | 提交解析任务，仅列出条目不下载（见「解析任务」一节）         |
| `task.get`         | 查询一个任务                                                 |
| `task.list`        | 分页查询当前进程中的任务摘要（包含 URL，不展开请求 payload） |
| `task.cancel`      | 取消排队中或运行中的任务                                     |
| `task.subscribe`   | 获取事件回放并订阅后续事件                                   |
| `task.unsubscribe` | 取消当前连接上的任务订阅                                     |

订阅后的实时事件以 `task.event` notification 推送。事件包含全局递增的 `seq`（download 与 resolve 任务共享同一序号空间）；从回放切换到实时流时，应按 `seq` 去重。任务快照（`download.start` / `resolve.start` / `task.get` / `task.list` 的返回值）均携带 `kind` 字段（`download` 或 `resolve`）标识任务类别。断开客户端不会自动取消任务。

下载完成后，`task.get` 的 `result` 会列出每个条目的目标路径和最终产物：

```json
{
  "items": [
    {
      "state": "done",
      "output_path": "/downloads/番剧/第 1 话.mp4",
      "skip_reason": null,
      "artifacts": [
        { "kind": "subtitle", "path": "/downloads/番剧/第 1 话.zh-CN.srt" },
        { "kind": "media", "path": "/downloads/番剧/第 1 话.mp4" }
      ]
    }
  ]
}
```

`state` 为 `done` 或 `skipped`；跳过原因目前包括 `already_exists` 和 `no_media_stream`。仅请求字幕、弹幕、描述文件或封面时，只要资源处理完成，条目同样为 `done`。`output_path` 是推导出的媒体目标路径，在未请求媒体或没有可用媒体流时不一定存在。

`artifacts` 包含本次生成或确认已存在的最终文件，不包含下载分片、临时封面或 FFmpeg 章节文件。`kind` 可能为 `media`、`subtitle`、`danmaku`、`metadata` 或 `cover`；客户端应按 `kind` 识别产物，不依赖数组顺序。一个 `skipped` 条目仍可能包含已经写入的 sidecar 产物。

除 runtime 自己产生的 `state` 外，下载事件的 `kind` 包括：

| `kind`             | `data`                                              | 含义                                       |
| ------------------ | --------------------------------------------------- | ------------------------------------------ |
| `stage`            | `{ name, item? }`                                   | 进入解析、资源写入、下载或后处理阶段       |
| `progress`         | `{ phase, current, total, speed_per_second, unit }` | 音视频字节下载进度                         |
| `item_skipped`     | `{ item, reason }`                                  | 条目因媒体已存在或没有请求到可用媒体流跳过 |
| `artifact_created` | `{ item, path }`                                    | 本次任务生成了最终媒体文件                 |

`stage.name` 目前可能为 `resolving`、`preparing`、`writing_resources`、`downloading` 或 `postprocessing`。`artifact_created` 只在本次新生成最终媒体文件时发送；其他 sidecar 产物通过完成结果获取。

## 解析任务

`resolve.start` 把「解析」作为独立任务提交（仅当 `server.info` 能力列表包含它时可用）：在不触发任何下载的前提下列出条目的稳定信息，供前端渲染选择器，选中后再逐条 `download.start`。

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resolve.start",
  "params": {
    "request": {
      "source": { "url": "https://www.bilibili.com/video/BV..." },
      "selection": { "batch": true }
    }
  }
}
```

`request` 与 `download.start` 使用完全相同的请求模型。解析任务运行在独立的单 worker runtime 中，轻量的列表解析不会排在长下载任务之后；`task.get` / `task.list` / `task.cancel` / `task.subscribe` 对两类任务统一路由。

解析过程中每列出一个条目会推送一条 `item_listed` 事件，任务完成后 `result.items` 包含全部条目。条目与 `item_listed` 事件的 `data` 携带相同字段：

- `avid` / `cid`：条目标识；
- `url`：单集原子 URL，可直接用于后续 `download.start`；
- `name` / `title`：分集名与视频标题；
- `uploader` / `description` / `tags`：UP 主、简介与标签，listing 元数据缺失时为空；
- `cover_url`：封面 URL；
- `planned_path`：按模板推导的计划路径（POSIX 风格），实际下载时可能因去重而调整；
- `display_group`：批量解析时的分组名，无分组时为 `null`。

错误语义：来源存在条目但全部解析失败或被过滤时，任务以 `failed` 结束，不会伪装成一次成功的空结果；真正的空来源（如空收藏夹）以 `completed` 返回空 `items`；部分条目失败时任务仍为 `completed` 并返回成功条目，逐项失败原因的结构化上报将在后续版本补充。

## 本地资源边界

- 同一 server 进程默认一次只运行一个下载任务，其余任务排队。
- 解析任务运行在独立的单 worker runtime 中，一次只运行一个解析，但不会排在下载任务之后。
- 请求中的 `output.directory` 和 `output.temporary_directory` 必须是相对路径，并分别限制在 `--download-root` 与 `--tmp-root` 内。
- `output.subpath_template` 不能使用绝对路径或 `..` 逃逸根目录。
- `--max-fetch-workers` 与 `--max-download-workers` 限制单任务并发数。
- 分块大小限制在 64 KiB 至 64 MiB，避免单任务创建过量分块。
- `--task-limit` 限制排队任务与近期任务记录的总量（download 与 resolve 任务合并计算）；达到上限时优先淘汰全局最早的已结束任务。
- 任务事件仅保留有界的近期回放；`truncated: true` 表示更早的事件已经被丢弃。

完整启动选项可通过 `yutto serve -h` 查看。
