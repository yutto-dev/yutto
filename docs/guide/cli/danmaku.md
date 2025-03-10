---
aside: true
---

# 弹幕设置参数 <Badge text="Experimental" type="warning"/>

通过与 biliass 的集成，我提供了一些 ASS 弹幕选项，包括字号、字体、速度等～

## 弹幕字体大小

- 参数 `--danmaku-font-size`
- 配置项 `danmaku.font_size`
- 默认值 `video_width / 40`

## 弹幕字体

- 参数 `--danmaku-font`
- 配置项 `danmaku.font`
- 默认值 `"SimHei"`

## 弹幕不透明度

- 参数 `--danmaku-opacity`
- 配置项 `danmaku.opacity`
- 默认值 `0.8`

## 弹幕显示区域与视频高度的比例

- 参数 `--danmaku-display-region-ratio`
- 配置项 `danmaku.display_region_ratio`
- 默认值 `1.0`

## 弹幕速度

- 参数 `--danmaku-speed`
- 配置项 `danmaku.speed`
- 默认值 `1.0`

## 屏蔽顶部弹幕

- 参数 `--danmaku-block-top`
- 配置项 `danmaku.block_top`
- 默认值 `False`

## 屏蔽底部弹幕

- 参数 `--danmaku-block-bottom`
- 配置项 `danmaku.block_bottom`
- 默认值 `False`

## 屏蔽滚动弹幕

- 参数 `--danmaku-block-scroll`
- 配置项 `danmaku.block_scroll`
- 默认值 `False`

## 屏蔽逆向弹幕

- 参数 `--danmaku-block-reverse`
- 配置项 `danmaku.block_reverse`
- 默认值 `False`

## 屏蔽固定弹幕（顶部、底部）

- 参数 `--danmaku-block-fixed`
- 配置项 `danmaku.block_fixed`
- 默认值 `False`

## 屏蔽高级弹幕

- 参数 `--danmaku-block-special`
- 配置项 `danmaku.block_special`
- 默认值 `False`

## 屏蔽彩色弹幕

- 参数 `--danmaku-block-colorful`
- 配置项 `danmaku.block_colorful`
- 默认值 `False`

## 屏蔽关键词

- 参数 `--danmaku-block-keyword-patterns`
- 配置项 `danmaku.block_keyword_patterns`
- 默认值 `None`

按关键词屏蔽，支持正则，作为 CLI 参数使用 `,` 分隔，作为配置项直接使用列表即可：

```toml [yutto.toml]
[danmaku]
block_keyword_patterns = [
   ".*keyword1.*",
   ".*keyword2.*",
]
```
