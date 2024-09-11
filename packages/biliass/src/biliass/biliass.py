from __future__ import annotations

import json
import logging
import math
import random
import re
import xml.dom.minidom
from collections.abc import Callable, Generator
from typing import TypeVar, Union

from biliass.protobuf.danmaku_pb2 import DanmakuEvent

#
# ReadComments**** protocol
#
# Input:
#     text:         Input XML string
#     fontsize:  Default font size
#
# Output:
#     yield a tuple:
#         (timeline, timestamp, no, comment, pos, color, size, height, width)
#     timeline:  The position when the comment is replayed
#     timestamp: The UNIX timestamp when the comment is submitted
#     no:        A sequence of 1, 2, 3, ..., used for sorting
#     comment:   The content of the comment
#     pos:       0 for regular moving comment,
#                1 for bottom centered comment,
#                2 for top centered comment,
#                3 for reversed moving comment
#     color:     Font color represented in 0xRRGGBB,
#                e.g. 0xffffff for white
#     size:      Font size
#     height:    The estimated height in pixels
#                i.e. (comment.count('\n')+1)*size
#     width:     The estimated width in pixels
#                i.e. CalculateLength(comment)*size
#


T = TypeVar("T")
Comment = tuple[float, float, int, str, Union[int, str], int, float, float, float]


def ReadCommentsBilibiliXml(
    text: str | bytes, fontsize: float
) -> Generator[Comment, None, None]:
    if isinstance(text, bytes):
        text = text.decode()
    text = FilterBadChars(text)
    dom = xml.dom.minidom.parseString(text)
    version = dom.version
    assert version in ["1.0", "2.0"], f"未知的 XML 版本号 {version}"
    if version == "1.0":
        return ReadCommentsBilibiliXmlV1(text, fontsize)
    else:
        return ReadCommentsBilibiliXmlV2(text, fontsize)


def ReadCommentsBilibiliXmlV1(
    text: str, fontsize: float
) -> Generator[Comment, None, None]:
    dom = xml.dom.minidom.parseString(text)
    comment_element = dom.getElementsByTagName("d")
    for i, comment in enumerate(comment_element):
        try:
            p = str(comment.getAttribute("p")).split(",")
            assert len(p) >= 5
            assert p[1] in ("1", "4", "5", "6", "7", "8")
            if comment.childNodes.length > 0:
                if p[1] in ("1", "4", "5", "6"):
                    c = str(comment.childNodes[0].wholeText).replace("/n", "\n")
                    size = int(p[2]) * fontsize / 25.0
                    yield (
                        float(p[0]),
                        int(p[4]),
                        i,
                        c,
                        {"1": 0, "4": 2, "5": 1, "6": 3}[p[1]],
                        int(p[3]),
                        size,
                        (c.count("\n") + 1) * size,
                        CalculateLength(c) * size,
                    )
                elif p[1] == "7":  # positioned comment
                    c = str(comment.childNodes[0].wholeText)
                    yield (
                        float(p[0]),
                        int(p[4]),
                        i,
                        c,
                        "bilipos",
                        int(p[3]),
                        int(p[2]),
                        0,
                        0,
                    )
                elif p[1] == "8":
                    pass  # ignore scripted comment
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            logging.warning(f"Invalid comment: {comment.toxml()}")
            continue


def ReadCommentsBilibiliXmlV2(
    text: str, fontsize: float
) -> Generator[Comment, None, None]:
    dom = xml.dom.minidom.parseString(text)
    comment_element = dom.getElementsByTagName("d")
    for i, comment in enumerate(comment_element):
        try:
            p = str(comment.getAttribute("p")).split(",")
            assert len(p) >= 7
            assert p[3] in ("1", "4", "5", "6", "7", "8")
            if comment.childNodes.length > 0:
                time = float(p[2]) / 1000.0
                if p[3] in ("1", "4", "5", "6"):
                    c = str(comment.childNodes[0].wholeText).replace("/n", "\n")
                    size = int(p[4]) * fontsize / 25.0
                    yield (
                        time,
                        int(p[6]),
                        i,
                        c,
                        {"1": 0, "4": 2, "5": 1, "6": 3}[p[3]],
                        int(p[5]),
                        size,
                        (c.count("\n") + 1) * size,
                        CalculateLength(c) * size,
                    )
                elif p[3] == "7":  # positioned comment
                    c = str(comment.childNodes[0].wholeText)
                    yield (time, int(p[6]), i, c, "bilipos", int(p[5]), int(p[4]), 0, 0)
                elif p[3] == "8":
                    pass  # ignore scripted comment
        except (AssertionError, AttributeError, IndexError, TypeError, ValueError):
            logging.warning(f"Invalid comment: {comment.toxml()}")
            continue


def ReadCommentsBilibiliProtobuf(
    protobuf: bytes | str, fontsize: float
) -> Generator[Comment, None, None]:
    assert isinstance(protobuf, bytes), "protobuf 仅支持使用 bytes 转换"
    target = DanmakuEvent()
    target.ParseFromString(protobuf)
    for i, elem in enumerate(target.elems):
        try:
            assert elem.mode in (1, 4, 5, 6, 7, 8)
            if elem.mode in (1, 4, 5, 6):
                c = elem.content.replace("/n", "\n")
                size = int(elem.fontsize) * fontsize / 25.0
                yield (
                    elem.progress / 1000,  # 视频内出现的时间
                    elem.ctime,  # 弹幕的发送时间（时间戳）
                    i,
                    c,
                    {1: 0, 4: 2, 5: 1, 6: 3}[elem.mode],
                    elem.color,
                    size,
                    (c.count("\n") + 1) * size,
                    CalculateLength(c) * size,
                )
            elif elem.mode == 7:  # positioned comment
                c = elem.content
                yield (
                    elem.progress / 1000,
                    elem.ctime,
                    i,
                    c,
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

    def WriteCommentBilibiliPositioned(self, c, width, height, styleid):
        # BiliPlayerSize = (512, 384)  # Bilibili player version 2010
        # BiliPlayerSize = (540, 384)  # Bilibili player version 2012
        # BiliPlayerSize = (672, 438)  # Bilibili player version 2014
        BiliPlayerSize = (891, 589)  # Bilibili player version 2021 (flex)
        ZoomFactor = GetZoomFactor(BiliPlayerSize, (width, height))

        def GetPosition(InputPos, isHeight):
            isHeight = int(isHeight)  # True -> 1
            if isinstance(InputPos, int):
                return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
            elif isinstance(InputPos, float):
                if InputPos > 1:
                    return ZoomFactor[0] * InputPos + ZoomFactor[isHeight + 1]
                else:
                    return (
                        BiliPlayerSize[isHeight] * ZoomFactor[0] * InputPos
                        + ZoomFactor[isHeight + 1]
                    )
            else:
                try:
                    InputPos = int(InputPos)
                except ValueError:
                    InputPos = float(InputPos)
                return GetPosition(InputPos, isHeight)

        try:
            comment_args = safe_list(json.loads(c[3]))
            text = ASSEscape(str(comment_args[4]).replace("/n", "\n"))
            from_x = comment_args.get(0, 0)
            from_y = comment_args.get(1, 0)
            to_x = comment_args.get(7, from_x)
            to_y = comment_args.get(8, from_y)
            from_x = GetPosition(from_x, False)
            from_y = GetPosition(from_y, True)
            to_x = GetPosition(to_x, False)
            to_y = GetPosition(to_y, True)
            alpha = safe_list(str(comment_args.get(2, "1")).split("-"))
            from_alpha = float(alpha.get(0, 1))
            to_alpha = float(alpha.get(1, from_alpha))
            from_alpha = 255 - round(from_alpha * 255)
            to_alpha = 255 - round(to_alpha * 255)
            rotate_z = int(comment_args.get(5, 0))
            rotate_y = int(comment_args.get(6, 0))
            lifetime = float(wrap_default(comment_args.get(3, 4500), 4500))
            duration = int(comment_args.get(9, lifetime * 1000))
            delay = int(comment_args.get(10, 0))
            fontface = comment_args.get(12)
            isborder = comment_args.get(11, "true")
            from_rotarg = ConvertFlashRotation(
                rotate_y, rotate_z, from_x, from_y, width, height
            )
            to_rotarg = ConvertFlashRotation(
                rotate_y, rotate_z, to_x, to_y, width, height
            )
            styles = ["\\org(%d, %d)" % (width / 2, height / 2)]
            if from_rotarg[0:2] == to_rotarg[0:2]:
                styles.append("\\pos({:.0f}, {:.0f})".format(*from_rotarg[0:2]))
            else:
                styles.append(
                    "\\move({:.0f}, {:.0f}, {:.0f}, {:.0f}, {:.0f}, {:.0f})".format(
                        *(from_rotarg[0:2] + to_rotarg[0:2] + (delay, delay + duration))
                    )
                )
            styles.append(
                "\\frx{:.0f}\\fry{:.0f}\\frz{:.0f}\\fscx{:.0f}\\fscy{:.0f}".format(
                    *from_rotarg[2:7]
                )
            )
            if (from_x, from_y) != (to_x, to_y):
                styles.append(f"\\t({delay:d}, {delay + duration:d}, ")
                styles.append(
                    "\\frx{:.0f}\\fry{:.0f}\\frz{:.0f}\\fscx{:.0f}\\fscy{:.0f}".format(
                        *to_rotarg[2:7]
                    )
                )
                styles.append(")")
            if fontface:
                styles.append(f"\\fn{ASSEscape(fontface)}")
            styles.append("\\fs%.0f" % (c[6] * ZoomFactor[0]))
            if c[5] != 0xFFFFFF:
                styles.append(f"\\c&H{ConvertColor(c[5])}&")
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
                start=ConvertTimestamp(c[0]),
                end=ConvertTimestamp(c[0] + lifetime),
                styles="".join(styles),
                text=text,
                styleid=styleid,
            )
        except (IndexError, ValueError):
            try:
                logging.warning(f"Invalid comment: {c[3]!r}")
            except IndexError:
                logging.warning(f"Invalid comment: {c!r}")

    def WriteASSHead(self, width, height, fontface, fontsize, alpha, styleid):
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

    def WriteComment(
        self,
        c,
        row,
        width,
        height,
        bottomReserved,
        fontsize,
        duration_marquee,
        duration_still,
        styleid,
    ):
        text = ASSEscape(c[3])
        styles = []
        if c[4] == 1:
            styles.append(
                "\\an8\\pos(%(halfwidth)d, %(row)d)"
                % {"halfwidth": width / 2, "row": row}
            )
            duration = duration_still
        elif c[4] == 2:
            styles.append(
                "\\an2\\pos(%(halfwidth)d, %(row)d)"
                % {
                    "halfwidth": width / 2,
                    "row": ConvertType2(row, height, bottomReserved),
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
            styles.append(f"\\c&H{ConvertColor(c[5])}&")
            if c[5] == 0x000000:
                styles.append("\\3c&HFFFFFF&")
        self._text += "Dialogue: 2,{start},{end},{styleid},,0000,0000,0000,,{{{styles}}}{text}\n".format(
            start=ConvertTimestamp(c[0]),
            end=ConvertTimestamp(c[0] + duration),
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
def GetZoomFactor(SourceSize, TargetSize):
    try:
        if (SourceSize, TargetSize) == GetZoomFactor.Cached_Size:
            return GetZoomFactor.Cached_Result
    except AttributeError:
        pass
    GetZoomFactor.Cached_Size = (SourceSize, TargetSize)
    try:
        SourceAspect = SourceSize[0] / SourceSize[1]
        TargetAspect = TargetSize[0] / TargetSize[1]
        if TargetAspect < SourceAspect:  # narrower
            ScaleFactor = TargetSize[0] / SourceSize[0]
            GetZoomFactor.Cached_Result = (
                ScaleFactor,
                0,
                (TargetSize[1] - TargetSize[0] / SourceAspect) / 2,
            )
        elif TargetAspect > SourceAspect:  # wider
            ScaleFactor = TargetSize[1] / SourceSize[1]
            GetZoomFactor.Cached_Result = (
                ScaleFactor,
                (TargetSize[0] - TargetSize[1] * SourceAspect) / 2,
                0,
            )
        else:
            GetZoomFactor.Cached_Result = (TargetSize[0] / SourceSize[0], 0, 0)
        return GetZoomFactor.Cached_Result
    except ZeroDivisionError:
        GetZoomFactor.Cached_Result = (1, 0, 0)
        return GetZoomFactor.Cached_Result


# Calculation is based on https://github.com/jabbany/CommentCoreLibrary/issues/5#issuecomment-40087282
#                     and https://github.com/m13253/danmaku2ass/issues/7#issuecomment-41489422
# ASS FOV = width*4/3.0
# But Flash FOV = width/math.tan(100*math.pi/360.0)/2 will be used instead
# Result: (transX, transY, rotX, rotY, rotZ, scaleX, scaleY)
def ConvertFlashRotation(rotY, rotZ, X, Y, width, height):
    def WrapAngle(deg):
        return 180 - ((180 - deg) % 360)

    rotY = WrapAngle(rotY)
    rotZ = WrapAngle(rotZ)
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
        outY = (
            math.atan2(-math.sin(rotY) * math.cos(rotZ), math.cos(rotY)) * 180 / math.pi
        )
        outZ = (
            math.atan2(-math.cos(rotY) * math.sin(rotZ), math.cos(rotZ)) * 180 / math.pi
        )
        outX = math.asin(math.sin(rotY) * math.sin(rotZ)) * 180 / math.pi
    trX = (
        (X * math.cos(rotZ) + Y * math.sin(rotZ)) / math.cos(rotY)
        + (1 - math.cos(rotZ) / math.cos(rotY)) * width / 2
        - math.sin(rotZ) / math.cos(rotY) * height / 2
    )
    trY = (
        Y * math.cos(rotZ)
        - X * math.sin(rotZ)
        + math.sin(rotZ) * width / 2
        + (1 - math.cos(rotZ)) * height / 2
    )
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
        logging.error(
            f"Rotation makes object behind the camera: trZ == {trZ:.0f} < {FOV:.0f}"
        )
    return (
        trX,
        trY,
        WrapAngle(outX),
        WrapAngle(outY),
        WrapAngle(outZ),
        scaleXY * 100,
        scaleXY * 100,
    )


def ProcessComments(
    comments,
    width,
    height,
    bottomReserved,
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
    ass.WriteASSHead(width, height, fontface, fontsize, alpha, styleid)
    rows = [[None] * (height - bottomReserved + 1) for i in range(4)]
    for idx, i in enumerate(comments):
        if progress_callback and idx % 1000 == 0:
            progress_callback(idx, len(comments))
        if isinstance(i[4], int):
            skip = False
            for filter_regex in filters_regex:
                if filter_regex and filter_regex.search(i[3]):
                    skip = True
                    break
            if skip:
                continue
            row = 0
            rowmax = height - bottomReserved - i[7]
            while row <= rowmax:
                freerows = TestFreeRows(
                    rows,
                    i,
                    row,
                    width,
                    height,
                    bottomReserved,
                    duration_marquee,
                    duration_still,
                )
                if freerows >= i[7]:
                    MarkCommentRow(rows, i, row)
                    ass.WriteComment(
                        i,
                        row,
                        width,
                        height,
                        bottomReserved,
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
                    row = FindAlternativeRow(rows, i, height, bottomReserved)
                    MarkCommentRow(rows, i, row)
                    ass.WriteComment(
                        i,
                        row,
                        width,
                        height,
                        bottomReserved,
                        fontsize,
                        duration_marquee,
                        duration_still,
                        styleid,
                    )
        elif i[4] == "bilipos":
            ass.WriteCommentBilibiliPositioned(i, width, height, styleid)
        else:
            logging.warning(f"Invalid comment: {i[3]!r}")
    if progress_callback:
        progress_callback(len(comments), len(comments))
    return ass.to_string()


def TestFreeRows(
    rows, c, row, width, height, bottomReserved, duration_marquee, duration_still
):
    res = 0
    rowmax = height - bottomReserved
    targetRow = None
    if c[4] in (1, 2):
        while row < rowmax and res < c[7]:
            if targetRow != rows[c[4]][row]:
                targetRow = rows[c[4]][row]
                if targetRow and targetRow[0] + duration_still > c[0]:
                    break
            row += 1
            res += 1
    else:
        try:
            thresholdTime = c[0] - duration_marquee * (1 - width / (c[8] + width))
        except ZeroDivisionError:
            thresholdTime = c[0] - duration_marquee
        while row < rowmax and res < c[7]:
            if targetRow != rows[c[4]][row]:
                targetRow = rows[c[4]][row]
                try:
                    if targetRow and (
                        targetRow[0] > thresholdTime
                        or targetRow[0]
                        + targetRow[8] * duration_marquee / (targetRow[8] + width)
                        > c[0]
                    ):
                        break
                except ZeroDivisionError:
                    pass
            row += 1
            res += 1
    return res


def FindAlternativeRow(rows, c, height, bottomReserved):
    res = 0
    for row in range(height - bottomReserved - math.ceil(c[7])):
        if not rows[c[4]][row]:
            return row
        elif rows[c[4]][row][0] < rows[c[4]][res][0]:
            res = row
    return res


def MarkCommentRow(rows, c, row):
    try:
        for i in range(row, row + math.ceil(c[7])):
            rows[c[4]][i] = c
    except IndexError:
        pass


def ASSEscape(s):
    def ReplaceLeadingSpace(s):
        sstrip = s.strip(" ")
        slen = len(s)
        if slen == len(sstrip):
            return s
        else:
            llen = slen - len(s.lstrip(" "))
            rlen = slen - len(s.rstrip(" "))
            return "".join(("\u2007" * llen, sstrip, "\u2007" * rlen))

    return "\\N".join(
        ReplaceLeadingSpace(i) or " "
        for i in str(s)
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .split("\n")
    )


def CalculateLength(s):
    return max(map(len, s.split("\n")))  # May not be accurate


def ConvertTimestamp(timestamp):
    timestamp = round(timestamp * 100.0)
    hour, minute = divmod(timestamp, 360000)
    minute, second = divmod(minute, 6000)
    second, centsecond = divmod(second, 100)
    return "%d:%02d:%02d.%02d" % (int(hour), int(minute), int(second), int(centsecond))


def ConvertColor(RGB, width=1280, height=576):
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

        def ClipByte(x):
            return 255 if x > 255 else 0 if x < 0 else round(x)

        return "{:02X}{:02X}{:02X}".format(  # noqa: UP032
            ClipByte(
                R * 0.00956384088080656
                + G * 0.03217254540203729
                + B * 0.95826361371715607
            ),
            ClipByte(
                R * -0.10493933142075390
                + G * 1.17231478191855154
                + B * -0.06737545049779757
            ),
            ClipByte(
                R * 0.91348912373987645
                + G * 0.07858536372532510
                + B * 0.00792551253479842
            ),
        )


def ConvertType2(row, height, bottomReserved):
    return height - bottomReserved - row


def FilterBadChars(string: str) -> str:
    return re.sub("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]", "\ufffd", string)


class safe_list(list):
    def get(self, index, default=None):
        try:
            return self[index]
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
            raise ValueError(f"Invalid regular expression: {comment_filter}")

    comments: list[Comment] = []
    if not isinstance(inputs, list):
        inputs = [inputs]
    for input in inputs:
        if input_format == "xml":
            comments.extend(ReadCommentsBilibiliXml(input, font_size))
        else:
            if isinstance(input, str):
                logging.warning("Protobuf 只能使用 bytes 转换")
            comments.extend(ReadCommentsBilibiliProtobuf(input, font_size))
    comments.sort()
    return ProcessComments(
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
