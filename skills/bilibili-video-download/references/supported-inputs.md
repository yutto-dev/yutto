# Supported Inputs

这些是回答“这个链接能不能下”“这里要不要加 `-b`”“能不能直接用 ID”时的快速参考。

## 单个下载

投稿视频：

```text
https://www.bilibili.com/video/BV...
https://www.bilibili.com/video/av...
BV...
av...
```

说明：

- 不带 `?p=` 时默认按第一话处理
- 也支持带 `?p=n` 的投稿视频页面

番剧单话：

```text
https://www.bilibili.com/bangumi/play/ep...
ep...
```

说明：

- 单话下载只支持 `ep`
- `ss` 和 `md` 不能唯一定位到某一话

课程单集：

```text
https://www.bilibili.com/cheese/play/ep...
```

说明：

- 课程单集不支持直接写 `ep...`，会和番剧混淆

## 批量下载

这些场景一般都要加 `-b`：

- 投稿视频全集
- 番剧全集
- 课程全集
- 用户指定收藏夹
- 当前用户稍后再看
- 用户全部收藏夹
- UP 主个人空间
- 合集
- 视频列表

常见入口：

```text
https://www.bilibili.com/video/BV...
https://www.bilibili.com/video/av...
https://www.bilibili.com/bangumi/play/ep...
https://www.bilibili.com/bangumi/play/ss...
https://www.bilibili.com/bangumi/media/md...
https://www.bilibili.com/cheese/play/ep...
https://www.bilibili.com/cheese/play/ss...
https://space.bilibili.com/<uid>/video
https://space.bilibili.com/<uid>/favlist
https://space.bilibili.com/<uid>/favlist?fid=...
https://www.bilibili.com/watchlater
https://space.bilibili.com/<uid>/lists?sid=...
https://www.bilibili.com/list/<uid>?sid=...
BV...
av...
ep...
ss...
md...
```

说明：

- 投稿视频全集支持直接使用 `BV...` 或 `av...`
- 番剧全集支持直接使用 `ep...`、`ss...`、`md...`
- 课程全集不要默认推荐直接使用 `ep...` 或 `ss...`，优先给完整 `cheese` 链接

## 选集支持

可以和 `-p/--episodes` 一起用的常见批量类型：

- 投稿视频全集
- 番剧全集
- 课程全集
- 合集

不要默认承诺支持 `-p` 的类型：

- 个人空间
- 视频列表
- 收藏夹
- 其他文档明确标注不支持选集的批量入口

## 额外说明

- `b23.tv` 这类短链接只要最终会重定向到受支持链接，也可以尝试
- 用户说“只给你一个 BV/av/ep/ss/md 能不能下”时，先判断它属于单个还是批量入口，再决定是否需要 `-b`
