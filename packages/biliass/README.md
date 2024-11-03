# biliass

<p align="center">
   <a href="https://python.org/" target="_blank"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/biliass?logo=python&style=flat-square"></a>
   <a href="https://pypi.org/project/biliass/" target="_blank"><img src="https://img.shields.io/pypi/v/biliass?style=flat-square" alt="pypi"></a>
   <a href="https://pypi.org/project/biliass/" target="_blank"><img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/biliass?style=flat-square"></a>
   <a href="https://actions-badge.atrox.dev/yutto-dev/biliass/goto?ref=main"><img alt="Build Status" src="https://img.shields.io/endpoint.svg?url=https%3A%2F%2Factions-badge.atrox.dev%2Fyutto-dev%2Fbiliass%2Fbadge%3Fref%3Dmain&style=flat-square&label=Test" /></a>
   <a href="LICENSE"><img alt="LICENSE" src="https://img.shields.io/github/license/yutto-dev/biliass?style=flat-square"></a>
   <a href="https://gitmoji.dev"><img src="https://img.shields.io/badge/gitmoji-%20😜%20😍-FFDD67?style=flat-square" alt="Gitmoji"></a>
   <a href="https://codspeed.io/yutto-dev/yutto"><img src="https://img.shields.io/endpoint?url=https://codspeed.io/badge.json&style=flat-square" alt="CodSpeed Badge"/></a>
</p>

biliass，高性能且易于使用的 bilibili 弹幕转换工具（XML/Protobuf 格式转 ASS），基于 [Danmaku2ASS](https://github.com/m13253/danmaku2ass)，使用 rust 重写

## Install

```bash
pip install biliass
```

## Usage

```bash
# XML 弹幕
biliass danmaku.xml -s 1920x1080 -o danmaku.ass
# protobuf 弹幕
biliass danmaku.pb -s 1920x1080 -f protobuf -o danmaku.ass
```

```python
from biliass import convert_to_ass

# xml
convert_to_ass(
    xml_text_or_bytes,
    1920,
    1080,
    input_format="xml",
    display_region_ratio=1.0,
    font_face="sans-serif",
    font_size=25,
    text_opacity=0.8,
    duration_marquee=15.0,
    duration_still=10.0,
    block_options=None,
    reduce_comments=False,
)

# protobuf
convert_to_ass(
    protobuf_bytes, # only bytes
    1920,
    1080,
    input_format="protobuf",
    display_region_ratio=1.0,
    font_face="sans-serif",
    font_size=25,
    text_opacity=0.8,
    duration_marquee=15.0,
    duration_still=10.0,
    block_options=None,
    reduce_comments=False,
)
```
