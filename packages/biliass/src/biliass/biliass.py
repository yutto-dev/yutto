# pyright: basic

from __future__ import annotations

import json
import logging
import math
import random
import re
from typing import TYPE_CHECKING, NamedTuple, TypeVar

from biliass._core import CommentPosition, DmSegMobileReply, read_comments_from_protobuf, read_comments_from_xml

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


T = TypeVar("T")


class Comment(NamedTuple):
    # The position when the comment is replayed
    timeline: float  # 0
    # The UNIX timestamp when the comment is submitted
    timestamp: float  # 1
    # A sequence of 1, 2, 3, ..., used for sorting
    no: int  # 2
    # The content of the comment
    comment: str  # 3
    # 0 for regular moving comment,
    # 1 for bottom centered comment,
    # 2 for top centered comment,
    # 3 for reversed moving comment
    pos: int | str  # 4
    # Font color represented in 0xRRGGBB,
    # e.g. 0xffffff for white
    color: int  # 5
    # Font size
    size: float  # 6
    # The estimated height in pixels
    # i.e. (comment.count('\n')+1)*size
    height: float  # 7
    # The estimated width in pixels
    # i.e. calculate_length(comment)*size
    width: float  # 8


def read_comments_bilibili_xml(text: str | bytes, fontsize: float) -> Generator[Comment, None, None]:
    if isinstance(text, bytes):
        text = text.decode()
    res_rs = read_comments_from_xml(text, fontsize)
    return (
        Comment(
            comment_rs.timeline,
            comment_rs.timestamp,
            comment_rs.no,
            comment_rs.comment,
            {
                CommentPosition.Scroll: 0,
                CommentPosition.Bottom: 1,
                CommentPosition.Top: 2,
                CommentPosition.Reversed: 3,
                CommentPosition.Special: "bilipos",
            }[comment_rs.pos],
            comment_rs.color,
            comment_rs.size,
            comment_rs.height,
            comment_rs.width,
        )
        for comment_rs in res_rs
    )


def read_comments_bilibili_protobuf(protobuf: bytes | str, fontsize: float) -> Generator[Comment, None, None]:
    assert isinstance(protobuf, bytes), "protobuf supports bytes only"
    res_rs = list(read_comments_bilibili_protobuf_rs(protobuf, fontsize))
    res_py = list(read_comments_bilibili_protobuf_py(protobuf, fontsize))
    assert len(res_rs) == len(
        res_py
    ), f"Protobuf parsing results have different lengths, rs {len(res_rs)} != py {len(res_py)}"
    for comment_rs, comment_py in zip(res_rs, res_py):
        assert (
            comment_rs.timeline == comment_py.timeline
        ), f"timeline, rs: {comment_rs.timeline}, py: {comment_py.timeline}"
        assert (
            comment_rs.timestamp == comment_py.timestamp
        ), f"timestamp, rs: {comment_rs.timestamp}, py: {comment_py.timestamp}"
        assert comment_rs.no == comment_py.no, f"no, rs: {comment_rs.no}, py: {comment_py.no}"
        assert comment_rs.comment == comment_py.comment, f"comment, rs: {comment_rs.comment}, py: {comment_py.comment}"
        assert comment_rs.pos == comment_py.pos, f"pos, rs: {comment_rs.pos}, py: {comment_py.pos}"
        assert comment_rs.color == comment_py.color, f"color, rs: {comment_rs.color}, py: {comment_py.color}"
        assert comment_rs.size == comment_py.size, f"size, rs: {comment_rs.size}, py: {comment_py.size}"
        assert comment_rs.height == comment_py.height, f"height, rs: {comment_rs.height}, py: {comment_py.height}"
        assert comment_rs.width == comment_py.width, f"width, rs: {comment_rs.width}, py: {comment_py.width}"

    assert res_rs == res_py, "Protobuf parsing results are different"
    return (comment for comment in res_rs)


def read_comments_bilibili_protobuf_rs(protobuf: bytes, fontsize: float) -> Generator[Comment, None, None]:
    res_rs = read_comments_from_protobuf(protobuf, fontsize)
    return (
        Comment(
            comment_rs.timeline,
            comment_rs.timestamp,
            comment_rs.no,
            comment_rs.comment,
            {
                CommentPosition.Scroll: 0,
                CommentPosition.Bottom: 1,
                CommentPosition.Top: 2,
                CommentPosition.Reversed: 3,
                CommentPosition.Special: "bilipos",
            }[comment_rs.pos],
            comment_rs.color,
            comment_rs.size,
            comment_rs.height,
            comment_rs.width,
        )
        for comment_rs in res_rs
    )


def read_comments_bilibili_protobuf_py(protobuf: bytes, fontsize: float) -> Generator[Comment, None, None]:
    replies = DmSegMobileReply.decode(protobuf)

    for i, elem in enumerate(replies.elems):
        try:
            assert elem.mode in (1, 4, 5, 6, 7, 8)
            if elem.mode in (1, 4, 5, 6):
                c = filter_bad_chars(elem.content.replace("/n", "\n"))
                size = int(elem.fontsize) * fontsize / 25.0
                yield Comment(
                    elem.progress / 1000,  # 视频内出现的时间
                    elem.ctime,  # 弹幕的发送时间（时间戳）
                    i,
                    c,
                    {1: 0, 4: 2, 5: 1, 6: 3}[elem.mode],
                    elem.color,
                    size,
                    (c.count("\n") + 1) * size,
                    calculate_length(c) * size,
                )
            elif elem.mode == 7:  # positioned comment
                c = elem.content
                yield Comment(
                    elem.progress / 1000,
                    elem.ctime,
                    i,
                    filter_bad_chars(c),
                    "bilipos",
                    elem.color,
                    elem.fontsize,
                    0,
                    0,
                )
            elif elem.mode == 8:
                pass  # ignore scripted comment
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            logging.warning(f"Invalid comment: {elem.content}")
            continue


class AssText:
    def __init__(self):
        self._text = ""

    def write_comment_bilibili_positioned(self, c, width, height, styleid):
        # BiliPlayerSize = (512, 384)  # Bilibili player version 2010
        # BiliPlayerSize = (540, 384)  # Bilibili player version 2012
        # BiliPlayerSize = (672, 438)  # Bilibili player version 2014
        BiliPlayerSize = (891, 589)  # Bilibili player version 2021 (flex)
        ZoomFactor = get_zoom_factor(BiliPlayerSize, (width, height))

        def get_position(InputPos, isHeight):
            isHeight = int(isHeight)  # True -> 1
            if isinstance(InputPos, int):
                return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
            elif isinstance(InputPos, float):
                if InputPos > 1:
                    return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
                else:
                    return BiliPlayerSize[isHeight] * ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
            else:
                try:
                    InputPos = int(InputPos)
                except ValueError:
                    InputPos = float(InputPos)
                return get_position(InputPos, isHeight)

        try:
            special_comment_data = json.loads(c[3])
            if not isinstance(special_comment_data, list):
                raise ValueError("Invalid comment")
            comment_args = safe_list(special_comment_data)
            text = ass_escape(str(comment_args[4]).replace("/n", "\n"))
            from_x = comment_args.get(0, 0)
            from_y = comment_args.get(1, 0)
            to_x = comment_args.get(7, from_x)
            to_y = comment_args.get(8, from_y)
            from_x = get_position(from_x, False)
            from_y = get_position(from_y, True)
            to_x = get_position(to_x, False)
            to_y = get_position(to_y, True)
            alpha = safe_list(str(comment_args.get(2, "1")).split("-"))
            from_alpha = float(alpha.get(0, 1))  # pyright: ignore
            to_alpha = float(alpha.get(1, from_alpha))  # pyright: ignore
            from_alpha = 255 - round(from_alpha * 255)
            to_alpha = 255 - round(to_alpha * 255)
            rotate_z = int(comment_args.get(5, 0))  # pyright: ignore
            rotate_y = int(comment_args.get(6, 0))  # pyright: ignore
            lifetime = float(wrap_default(comment_args.get(3, 4500), 4500))
            duration = int(comment_args.get(9, lifetime * 1000))  # pyright: ignore
            delay = int(comment_args.get(10, 0))  # pyright: ignore
            fontface = comment_args.get(12)
            isborder = comment_args.get(11, "true")
            from_rotarg = convert_flash_rotation(rotate_y, rotate_z, from_x, from_y, width, height)
            to_rotarg = convert_flash_rotation(rotate_y, rotate_z, to_x, to_y, width, height)
            styles = ["\\org(%d, %d)" % (width / 2, height / 2)]
            if from_rotarg[0:2] == to_rotarg[0:2]:
                styles.append("\\pos({:.0f}, {:.0f})".format(*from_rotarg[0:2]))
            else:
                styles.append(
                    "\\move({:.0f}, {:.0f}, {:.0f}, {:.0f}, {:.0f}, {:.0f})".format(
                        *(from_rotarg[0:2] + to_rotarg[0:2] + (delay, delay + duration))
                    )
                )
            styles.append("\\frx{:.0f}\\fry{:.0f}\\frz{:.0f}\\fscx{:.0f}\\fscy{:.0f}".format(*from_rotarg[2:7]))
            if (from_x, from_y) != (to_x, to_y):
                styles.append(f"\\t({delay:d}, {delay + duration:d}, ")
                styles.append("\\frx{:.0f}\\fry{:.0f}\\frz{:.0f}\\fscx{:.0f}\\fscy{:.0f}".format(*to_rotarg[2:7]))
                styles.append(")")
            if fontface:
                styles.append(f"\\fn{ass_escape(fontface)}")
            styles.append("\\fs%.0f" % (c[6] * ZoomFactor[0]))
            if c[5] != 0xFFFFFF:
                styles.append(f"\\c&H{convert_color(c[5])}&")
                if c[5] == 0x000000:
                    styles.append("\\3c&HFFFFFF&")
            if from_alpha == to_alpha:
                styles.append(f"\\alpha&H{from_alpha:02X}")
            elif (from_alpha, to_alpha) == (255, 0):
                styles.append(f"\\fad({lifetime * 1000:.0f},0)")
            elif (from_alpha, to_alpha) == (0, 255):
                styles.append(f"\\fad(0, {lifetime * 1000:.0f})")
            else:
                styles.append(
                    f"\\fade({from_alpha:d}, {to_alpha:d}, {to_alpha:d}, 0, {lifetime * 1000:.0f}, {lifetime * 1000:.0f}, {lifetime * 1000:.0f})"
                )
            if isborder == "false":
                styles.append("\\bord0")
            self._text += "Dialogue: -1,{start},{end},{styleid},,0,0,0,,{{{styles}}}{text}\n".format(
                start=convert_timestamp(c[0]),
                end=convert_timestamp(c[0] + lifetime),
                styles="".join(styles),
                text=text,
                styleid=styleid,
            )
        except (IndexError, ValueError):
            try:
                logging.warning(f"Invalid comment: {c[3]!r}")
            except IndexError:
                logging.warning(f"Invalid comment: {c!r}")

    def write_head(self, width, height, fontface, fontsize, alpha, styleid):
        self._text += """[Script Info]
; Script generated by biliass (based on Danmaku2ASS)
; https://github.com/yutto-dev/yutto/tree/main/packages/biliass
Script Updated By: biliass (https://github.com/yutto-dev/yutto/tree/main/packages/biliass)
ScriptType: v4.00+
PlayResX: %(width)d
PlayResY: %(height)d
Aspect Ratio: %(width)d:%(height)d
Collisions: Normal
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: %(styleid)s, %(fontface)s, %(fontsize).0f, &H%(alpha)02XFFFFFF, &H%(alpha)02XFFFFFF, &H%(alpha)02X000000, &H%(alpha)02X000000, 0, 0, 0, 0, 100, 100, 0.00, 0.00, 1, %(outline).0f, 0, 7, 0, 0, 0, 0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % {
            "width": width,
            "height": height,
            "fontface": fontface,
            "fontsize": fontsize,
            "alpha": 255 - round(alpha * 255),
            "outline": max(fontsize / 25.0, 1),
            "styleid": styleid,
        }

    def write_comment(
        self,
        c,
        row,
        width,
        height,
        bottom_reserved,
        fontsize,
        duration_marquee,
        duration_still,
        styleid,
    ):
        text = ass_escape(c[3])
        styles = []
        if c[4] == 1:
            styles.append("\\an8\\pos(%(halfwidth)d, %(row)d)" % {"halfwidth": width / 2, "row": row})
            duration = duration_still
        elif c[4] == 2:
            styles.append(
                "\\an2\\pos(%(halfwidth)d, %(row)d)"
                % {
                    "halfwidth": width / 2,
                    "row": convert_type2(row, height, bottom_reserved),
                }
            )
            duration = duration_still
        elif c[4] == 3:
            styles.append(
                "\\move(%(neglen)d, %(row)d, %(width)d, %(row)d)"
                % {"width": width, "row": row, "neglen": -math.ceil(c[8])}
            )
            duration = duration_marquee
        else:
            styles.append(
                "\\move(%(width)d, %(row)d, %(neglen)d, %(row)d)"
                % {"width": width, "row": row, "neglen": -math.ceil(c[8])}
            )
            duration = duration_marquee
        if not (-1 < c[6] - fontsize < 1):
            styles.append(f"\\fs{c[6]:.0f}")
        if c[5] != 0xFFFFFF:
            styles.append(f"\\c&H{convert_color(c[5])}&")
            if c[5] == 0x000000:
                styles.append("\\3c&HFFFFFF&")
        self._text += "Dialogue: 2,{start},{end},{styleid},,0000,0000,0000,,{{{styles}}}{text}\n".format(
            start=convert_timestamp(c[0]),
            end=convert_timestamp(c[0] + duration),
            styles="".join(styles),
            text=text,
            styleid=styleid,
        )

    def to_file(self, f):
        f.write(self._text)

    def to_string(self):
        return self._text


# Result: (f, dx, dy)
# To convert: NewX = f*x+dx, NewY = f*y+dy
def get_zoom_factor(SourceSize, TargetSize):
    try:
        if (SourceSize, TargetSize) == get_zoom_factor.cached_size:
            return get_zoom_factor.cached_result
    except AttributeError:
        pass
    get_zoom_factor.cached_size = (SourceSize, TargetSize)
    try:
        SourceAspect = SourceSize[0] / SourceSize[1]
        TargetAspect = TargetSize[0] / TargetSize[1]
        if TargetAspect < SourceAspect:  # narrower
            ScaleFactor = TargetSize[0] / SourceSize[0]
            get_zoom_factor.cached_result = (
                ScaleFactor,
                0,
                (TargetSize[1] - TargetSize[0] / SourceAspect) / 2,
            )
        elif TargetAspect > SourceAspect:  # wider
            ScaleFactor = TargetSize[1] / SourceSize[1]
            get_zoom_factor.cached_result = (
                ScaleFactor,
                (TargetSize[0] - TargetSize[1] * SourceAspect) / 2,
                0,
            )
        else:
            get_zoom_factor.cached_result = (TargetSize[0] / SourceSize[0], 0, 0)
        return get_zoom_factor.cached_result
    except ZeroDivisionError:
        get_zoom_factor.cached_result = (1, 0, 0)
        return get_zoom_factor.cached_result


# Calculation is based on https://github.com/jabbany/CommentCoreLibrary/issues/5#issuecomment-40087282
#                     and https://github.com/m13253/danmaku2ass/issues/7#issuecomment-41489422
# ASS FOV = width*4/3.0
# But Flash FOV = width/math.tan(100*math.pi/360.0)/2 will be used instead
# Result: (transX, transY, rotX, rotY, rotZ, scaleX, scaleY)
def convert_flash_rotation(rotY, rotZ, X, Y, width, height):
    def wrap_angle(deg):
        return 180 - ((180 - deg) % 360)

    rotY = wrap_angle(rotY)
    rotZ = wrap_angle(rotZ)
    if rotY in (90, -90):
        rotY -= 1
    if rotY == 0 or rotZ == 0:
        outX = 0
        outY = -rotY  # Positive value means clockwise in Flash
        outZ = -rotZ
        rotY *= math.pi / 180.0
        rotZ *= math.pi / 180.0
    else:
        rotY *= math.pi / 180.0
        rotZ *= math.pi / 180.0
        outY = math.atan2(-math.sin(rotY) * math.cos(rotZ), math.cos(rotY)) * 180 / math.pi
        outZ = math.atan2(-math.cos(rotY) * math.sin(rotZ), math.cos(rotZ)) * 180 / math.pi
        outX = math.asin(math.sin(rotY) * math.sin(rotZ)) * 180 / math.pi
    trX = (
        (X * math.cos(rotZ) + Y * math.sin(rotZ)) / math.cos(rotY)
        + (1 - math.cos(rotZ) / math.cos(rotY)) * width / 2
        - math.sin(rotZ) / math.cos(rotY) * height / 2
    )
    trY = Y * math.cos(rotZ) - X * math.sin(rotZ) + math.sin(rotZ) * width / 2 + (1 - math.cos(rotZ)) * height / 2
    trZ = (trX - width / 2) * math.sin(rotY)
    FOV = width * math.tan(2 * math.pi / 9.0) / 2
    try:
        scaleXY = FOV / (FOV + trZ)
    except ZeroDivisionError:
        logging.error(f"Rotation makes object behind the camera: trZ == {trZ:.0f}")
        scaleXY = 1
    trX = (trX - width / 2) * scaleXY + width / 2
    trY = (trY - height / 2) * scaleXY + height / 2
    if scaleXY < 0:
        scaleXY = -scaleXY
        outX += 180
        outY += 180
        logging.error(f"Rotation makes object behind the camera: trZ == {trZ:.0f} < {FOV:.0f}")
    return (
        trX,
        trY,
        wrap_angle(outX),
        wrap_angle(outY),
        wrap_angle(outZ),
        scaleXY * 100,
        scaleXY * 100,
    )


def process_comments(
    comments,
    width,
    height,
    bottom_reserved,
    fontface,
    fontsize,
    alpha,
    duration_marquee,
    duration_still,
    filters_regex,
    reduced,
    progress_callback,
):
    styleid = f"biliass_{random.randint(0, 0xFFFF):04x}"
    ass = AssText()
    ass.write_head(width, height, fontface, fontsize, alpha, styleid)
    rows = [[None] * (height - bottom_reserved + 1) for i in range(4)]
    for idx, comment in enumerate(comments):
        if progress_callback and idx % 1000 == 0:
            progress_callback(idx, len(comments))
        if isinstance(comment.pos, int):
            skip = False
            for filter_regex in filters_regex:
                if filter_regex and filter_regex.search(comment.comment):
                    skip = True
                    break
            if skip:
                continue
            row = 0
            rowmax = height - bottom_reserved - comment.height
            while row <= rowmax:
                freerows = test_free_rows(
                    rows,
                    comment,
                    row,
                    width,
                    height,
                    bottom_reserved,
                    duration_marquee,
                    duration_still,
                )
                if freerows >= comment.height:
                    mark_comment_row(rows, comment, row)
                    ass.write_comment(
                        comment,
                        row,
                        width,
                        height,
                        bottom_reserved,
                        fontsize,
                        duration_marquee,
                        duration_still,
                        styleid,
                    )
                    break
                else:
                    row += freerows or 1
            else:
                if not reduced:
                    row = find_alternative_row(rows, comment, height, bottom_reserved)
                    mark_comment_row(rows, comment, row)
                    ass.write_comment(
                        comment,
                        row,
                        width,
                        height,
                        bottom_reserved,
                        fontsize,
                        duration_marquee,
                        duration_still,
                        styleid,
                    )
        elif comment.pos == "bilipos":
            ass.write_comment_bilibili_positioned(comment, width, height, styleid)
        else:
            logging.warning(f"Invalid comment: {comment.comment!r}")
    if progress_callback:
        progress_callback(len(comments), len(comments))
    return ass.to_string()


def test_free_rows(
    rows: list[Comment | None],
    comment: Comment,
    row: int,
    width,
    height,
    bottom_reserved,
    duration_marquee,
    duration_still,
):
    res = 0
    rowmax = height - bottom_reserved
    target_row = None
    if comment.pos in (1, 2):
        while row < rowmax and res < comment.height:
            if target_row != rows[comment.pos][row]:
                target_row = rows[comment.pos][row]
                if target_row and target_row[0] + duration_still > comment.timeline:
                    break
            row += 1
            res += 1
    else:
        try:
            threshold_time = comment.timeline - duration_marquee * (1 - width / (comment.width + width))
        except ZeroDivisionError:
            threshold_time = comment.timeline - duration_marquee
        while row < rowmax and res < comment.height:
            if target_row != rows[comment.pos][row]:
                target_row = rows[comment.pos][row]
                try:
                    if target_row and (
                        target_row[0] > threshold_time
                        or target_row[0] + target_row[8] * duration_marquee / (target_row[8] + width) > comment.timeline
                    ):
                        break
                except ZeroDivisionError:
                    pass
            row += 1
            res += 1
    return res


def find_alternative_row(rows, comment: Comment, height, bottom_reserved):
    res = 0
    for row in range(height - bottom_reserved - math.ceil(comment.height)):
        if not rows[comment.pos][row]:
            return row
        elif rows[comment.pos][row][0] < rows[comment.pos][res][0]:
            res = row
    return res


def mark_comment_row(rows: list[Comment | None], comment: Comment, row: int):
    try:
        for i in range(row, row + math.ceil(comment.height)):
            rows[comment.pos][i] = comment
    except IndexError:
        pass


def ass_escape(s):
    def replace_leading_space(s):
        sstrip = s.strip(" ")
        slen = len(s)
        if slen == len(sstrip):
            return s
        else:
            llen = slen - len(s.lstrip(" "))
            rlen = slen - len(s.rstrip(" "))
            return "".join(("\u2007" * llen, sstrip, "\u2007" * rlen))

    return "\\N".join(
        replace_leading_space(i) or " "
        for i in str(s).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").split("\n")
    )


def calculate_length(s):
    return max(map(len, s.split("\n")))  # May not be accurate


def convert_timestamp(timestamp):
    timestamp = round(timestamp * 100.0)
    hour, minute = divmod(timestamp, 360000)
    minute, second = divmod(minute, 6000)
    second, centsecond = divmod(second, 100)
    return "%d:%02d:%02d.%02d" % (int(hour), int(minute), int(second), int(centsecond))


def convert_color(RGB, width=1280, height=576):
    if RGB == 0x000000:
        return "000000"
    elif RGB == 0xFFFFFF:
        return "FFFFFF"
    R = (RGB >> 16) & 0xFF
    G = (RGB >> 8) & 0xFF
    B = RGB & 0xFF
    if width < 1280 and height < 576:
        return f"{B:02X}{G:02X}{R:02X}"
    else:  # VobSub always uses BT.601 colorspace, convert to BT.709

        def clip_byte(x):
            return 255 if x > 255 else 0 if x < 0 else round(x)

        return "{:02X}{:02X}{:02X}".format(  # noqa: UP032
            clip_byte(R * 0.00956384088080656 + G * 0.03217254540203729 + B * 0.95826361371715607),
            clip_byte(R * -0.10493933142075390 + G * 1.17231478191855154 + B * -0.06737545049779757),
            clip_byte(R * 0.91348912373987645 + G * 0.07858536372532510 + B * 0.00792551253479842),
        )


def convert_type2(row, height, bottom_reserved):
    return height - bottom_reserved - row


def filter_bad_chars(string: str) -> str:
    return re.sub("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\u2028\u2029]", "\ufffd", string)


class safe_list(list):
    def get(self, index, default=None):
        def is_empty(value):
            return value is None or value == ""

        try:
            return self[index] if not is_empty(self[index]) else default
        except IndexError:
            return default


def wrap_default(value: T | None, default: T) -> T:
    return default if value is None else value


def Danmaku2ASS(
    inputs: list[str | bytes] | str | bytes,
    stage_width: int,
    stage_height: int,
    input_format: str = "xml",
    reserve_blank: float = 0,
    font_face: str = "sans-serif",
    font_size: float = 25.0,
    text_opacity: float = 1.0,
    duration_marquee: float = 5.0,
    duration_still: float = 5.0,
    comment_filter: str | None = None,
    is_reduce_comments: bool = False,
    progress_callback: Callable[..., None] | None = None,
) -> str:
    comment_filters: list[str] = [comment_filter] if comment_filter is not None else []
    filters_regex = []
    for comment_filter in comment_filters:
        try:
            if comment_filter:
                filters_regex.append(re.compile(comment_filter))
        except:  # noqa: E722
            raise ValueError(f"Invalid regular expression: {comment_filter}") from None

    comments: list[Comment] = []
    if not isinstance(inputs, list):
        inputs = [inputs]
    for input in inputs:
        if input_format == "xml":
            comments.extend(read_comments_bilibili_xml(input, font_size))
        else:
            if isinstance(input, str):
                logging.warning("Protobuf can only be read from bytes")
            comments.extend(read_comments_bilibili_protobuf(input, font_size))
    comments.sort()
    return process_comments(
        comments,
        stage_width,
        stage_height,
        reserve_blank,
        font_face,
        font_size,
        text_opacity,
        duration_marquee,
        duration_still,
        filters_regex,
        is_reduce_comments,
        progress_callback,
    )
