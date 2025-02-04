---
aside: true
---

# 资源选择参数

这里有一些参数专用于资源选择，比如选择是否下载弹幕、音频、视频等等。

## 仅下载视频流

- 参数 `--video-only`
- 默认值 `False`

::: tip

这里「仅下载视频流」是指视频中音视频流仅选择视频流，而不是仅仅下载视频而不下载弹幕字幕等资源，如果需要取消字幕等资源下载，请额外使用 `--no-danmaku` 等参数。

「仅下载音频流」也是同样的。

:::

## 仅下载音频流

- 参数 `--audio-only`
- 默认值 `False`

仅下载其中的音频流，保存为 `.m4a` 文件。

## 不生成弹幕文件

- 参数 `--no-danmaku`
- 默认值 `False`

## 仅生成弹幕文件

- 参数 `--danmaku-only`
- 默认值 `False`

## 不生成字幕文件

- 参数 `--no-subtitle`
- 默认值 `False`

## 仅生成字幕文件

- 参数 `--subtitle-only`
- 默认值 `False`

## 生成媒体元数据文件

- 参数 `--with-metadata`
- 默认值 `False`

目前媒体元数据生成尚在试验阶段，可能提取出的信息并不完整。

## 仅生成媒体元数据文件

- 参数 `--metadata-only`
- 默认值 `False`

## 不生成视频封面

- 参数 `--no-cover`
- 默认值 `False`

::: tip

当前仅支持为包含视频流的视频生成封面。

:::

## 生成视频流封面时单独保存封面

- 参数 `--save-cover`
- 默认值 `False`

## 仅生成视频封面

- 参数 `--cover-only`
- 默认值 `False`

## 不生成章节信息

- 参数 `--no-chapter-info`
- 默认值 `False`

不生成章节信息，包含 MetaData 和嵌入视频流的章节信息。

## 配置项

与命令行界面完全不同，配置文件可以直接表明你要下载的资源类型，比如：

```toml [yutto.toml]
[resource]
require_audio = false
require_subtitle = false
require_danmaku = false
```

如上配置表明了你不需要音频、字幕和弹幕资源。

具体配置项如下：

### 是否需要视频流

- 配置项 `resource.video_only`
- 默认值 `True`

### 是否需要音频流

- 配置项 `resource.require_audio`
- 默认值 `True`

### 是否需要弹幕

- 配置项 `resource.require_danmaku`
- 默认值 `True`

### 是否需要字幕

- 配置项 `resource.require_subtitle`
- 默认值 `True`

### 是否需要媒体元数据

- 配置项 `resource.require_metadata`
- 默认值 `False`

### 是否需要视频封面

- 配置项 `resource.require_cover`
- 默认值 `True`

### 是否需要章节信息

- 配置项 `resource.require_chapter_info`
- 默认值 `True`

### 生成视频流封面时单独保存封面

- 配置项 `resource.save_cover`
- 默认值 `False`
