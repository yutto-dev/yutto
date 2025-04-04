from __future__ import annotations

from pathlib import Path
from typing import Literal, TypeAlias, TypedDict

from biliass import BlockOptions, convert_to_ass

DanmakuSourceType = Literal["xml", "protobuf"]
DanmakuSaveType = Literal["xml", "ass", "protobuf"]

DanmakuSourceDataXml = str
DanmakuSourceDataProtobuf = bytes
DanmakuSourceDataType: TypeAlias = DanmakuSourceDataXml | DanmakuSourceDataProtobuf


class DanmakuOptions(TypedDict):
    font_size: int | None
    font: str
    opacity: float
    display_region_ratio: float
    speed: float
    block_options: BlockOptions


class DanmakuData(TypedDict):
    source_type: DanmakuSourceType | None
    save_type: DanmakuSaveType | None
    data: list[DanmakuSourceDataType]


EmptyDanmakuData: DanmakuData = {"source_type": None, "save_type": None, "data": []}


def write_xml_danmaku(xml_danmaku: str, filepath: Path):
    with filepath.open("w", encoding="utf-8") as f:
        f.write(xml_danmaku)


def write_protobuf_danmaku(protobuf_danmaku: bytes, filepath: Path):
    with filepath.open("wb") as f:
        f.write(protobuf_danmaku)


def write_ass_danmaku(
    danmaku: list[str | bytes],
    input_format: Literal["xml", "protobuf"],
    filepath: Path,
    height: int,
    width: int,
    options: DanmakuOptions,
):
    with filepath.open(
        "w",
        encoding="utf-8-sig",
        errors="replace",
    ) as f:
        f.write(
            convert_to_ass(
                danmaku,
                width,
                height,
                input_format=input_format,
                display_region_ratio=options["display_region_ratio"],
                font_face=options["font"],
                font_size=options["font_size"] if options["font_size"] is not None else width / 40,
                text_opacity=options["opacity"],
                duration_marquee=8.0 / options["speed"],
                duration_still=5.0 / options["speed"],
                block_options=options["block_options"],
                reduce_comments=True,
            )
        )


def write_danmaku(
    danmaku: DanmakuData,
    video_path: str | Path,
    height: int,
    width: int,
    options: DanmakuOptions,
) -> str | None:
    video_path = Path(video_path)
    video_name = video_path.stem
    if danmaku["source_type"] == "xml":
        xml_danmaku = danmaku["data"]
        assert isinstance(xml_danmaku[0], str)
        if danmaku["save_type"] == "xml":
            file_path = video_path.with_suffix(".xml")
            write_xml_danmaku(xml_danmaku[0], file_path)
        elif danmaku["save_type"] == "ass":
            file_path = video_path.with_suffix(".ass")
            write_ass_danmaku(xml_danmaku, "xml", file_path, height, width, options)
        else:
            return None
    elif danmaku["source_type"] == "protobuf":
        protobuf_danmaku = danmaku["data"]
        assert isinstance(protobuf_danmaku[0], bytes)
        if danmaku["save_type"] == "ass":
            file_path = video_path.with_suffix(".ass")
            write_ass_danmaku(protobuf_danmaku, "protobuf", file_path, height, width, options)
        elif danmaku["save_type"] == "protobuf":
            if len(protobuf_danmaku) == 1:
                file_path = video_path.with_suffix(".pb")
                write_protobuf_danmaku(protobuf_danmaku[0], file_path)
            else:
                for i in range(len(protobuf_danmaku)):
                    file_path = video_path.with_name(f"{video_name}_{i:02}.pb")
                    protobuf_danmaku_item = protobuf_danmaku[i]
                    assert isinstance(protobuf_danmaku_item, bytes)
                    write_protobuf_danmaku(protobuf_danmaku_item, file_path)
        else:
            return None
    else:
        return None
