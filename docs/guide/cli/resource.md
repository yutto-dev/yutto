---
aside: true
---

# 资源选择参数

这里有一些参数专用于资源选择，你可以告诉我你需要哪些资源，比如弹幕、音频、视频等等。

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

## 选择字幕语言

- 参数 `--subtitle-languages`
- 默认值 `all`（下载所有可用字幕）

使用逗号分隔 B 站字幕的语言代码（`lan`，不是显示名称 `lan_doc`）：

```bash
# 仅下载中文字幕
yutto <url> --subtitle-languages zh
# 仅下载中文和英文字幕
yutto <url> --subtitle-languages zh,en
# 仅生成中文和英文字幕文件，不下载音视频等其它资源
yutto <url> --subtitle-only --subtitle-languages zh,en
# 覆盖配置文件中的语言选择，恢复下载全部字幕
yutto <url> --subtitle-languages all
```

语言代码不区分大小写。`zh` 匹配 `zh-CN`、`zh-Hans`、`zh-Hant` 等地区/文字变体及 `ai-zh` 自动生成字幕；`en` 同样匹配 `en-US`、`ai-en` 等。也可以指定更具体的代码（如 `zh-Hans`）缩小范围，或指定 `ai-zh` 仅选择自动生成的中文字幕。

该选项适用于投稿视频、番剧和课程，在拉取字幕内容之前过滤，不改变现有字幕文件命名。没有匹配语言时不生成字幕文件，也不会回退到全部字幕；它不会启用已被 `--no-subtitle` 或 `resource.require_subtitle = false` 禁用的字幕。与 `--ai-translation-language` 的原声翻译设置相互独立。

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

### 字幕语言选择

- 配置项 `resource.subtitle_languages`
- 默认值 `[]`（下载所有可用字幕）

匹配规则与 `--subtitle-languages` 相同，配置值使用语言代码数组。命令行参数会替换配置中的数组，而不是追加。

```toml [yutto.toml]
[resource]
subtitle_languages = ["zh", "en"] # 仅中文和英文；仅中文可使用 ["zh"]
# subtitle_languages = []        # 下载全部字幕
```

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
