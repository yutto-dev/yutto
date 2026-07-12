# server 模式 <Badge text="Experimental" type="warning" />

`yutto serve` 会启动一个只监听本机回环地址的 WebSocket server，供 WebUI、桌面应用或其他本地前端通过 JSON-RPC 2.0 调用。原有下载命令及终端输出不受影响；server 模式也不内置 WebUI。

## 启动

```bash
yutto serve --token-file ~/.config/yutto/server.token
```

默认监听 `ws://127.0.0.1:11223`。Token 依次从以下位置获取：

1. `YUTTO_SERVER_TOKEN` 环境变量；
2. `--token-file` 指定的文件；
3. 都未提供时，生成仅本次运行有效的随机 Token 并显示在终端。

在 POSIX 系统上，已有 Token 文件必须是权限不高于 `0600` 的普通文件，符号链接会被拒绝。

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

| 方法               | 用途                                               |
| ------------------ | -------------------------------------------------- |
| `server.info`      | 查询版本、协议版本和能力列表                       |
| `download.start`   | 提交下载任务，返回任务快照                         |
| `task.get`         | 查询一个任务                                       |
| `task.list`        | 分页查询当前进程中的任务摘要（不展开请求 payload） |
| `task.cancel`      | 取消排队中或运行中的任务                           |
| `task.subscribe`   | 获取事件回放并订阅后续事件                         |
| `task.unsubscribe` | 取消当前连接上的任务订阅                           |

订阅后的实时事件以 `task.event` notification 推送。事件包含全局递增的 `seq`；从回放切换到实时流时，应按 `seq` 去重。断开客户端不会自动取消任务。

## 本地资源边界

- 同一 server 进程默认一次只运行一个下载任务，其余任务排队。
- 请求中的 `output.directory` 和 `output.temporary_directory` 必须是相对路径，并分别限制在 `--download-root` 与 `--tmp-root` 内。
- `output.subpath_template` 不能使用绝对路径或 `..` 逃逸根目录。
- `--max-fetch-workers` 与 `--max-download-workers` 限制单任务并发数。
- 分块大小限制在 64 KiB 至 64 MiB，避免单任务创建过量分块。
- `--task-limit` 限制排队任务与近期任务记录的总量；达到上限时优先淘汰最早的已结束任务。
- 任务事件仅保留有界的近期回放；`truncated: true` 表示更早的事件已经被丢弃。

完整启动选项可通过 `yutto serve -h` 查看。
