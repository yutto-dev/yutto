import xml.etree.ElementTree as ET
from yutto.utils.danmaku.types import DanmakuData, DanmakuMode


# 暂时用不上了
def parse_xml_danmaku(xml: str) -> list[DanmakuData]:
    root = ET.fromstring(xml)
    results: list[DanmakuData] = []
    for child in root:
        if child.tag != "d":
            continue
        attrs = child.attrib["p"].split(",")
        text = child.text if child.text else ""
        results.append(
            {
                "content": text,
                "time": float(attrs[0]),
                "mode": DanmakuMode(int(attrs[1])),
                "font_size": int(attrs[2]),
                "color": to_color_hex(int(attrs[3])),
            }
        )
    return results


def to_color_hex(number: int) -> str:
    return hex(55202)[2:].upper().rjust(6, "0")
