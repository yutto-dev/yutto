from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypedDict

if TYPE_CHECKING:
    from pathlib import Path

    from yutto.bilibili_typing.codec import AudioCodec, VideoCodec
    from yutto.bilibili_typing.quality import AudioQuality, VideoQuality
    from yutto.utils.danmaku import DanmakuData, DanmakuOptions
    from yutto.utils.metadata import ChapterInfoData, MetaData
    from yutto.utils.subtitle import SubtitleData


class BilibiliId(NamedTuple):
    """所有 bilibili id 的基类"""

    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BilibiliId):
            return False
        return self.value == other.value

    def to_dict(self) -> dict[str, str]:
        raise NotImplementedError("请不要直接使用 BilibiliId")


class AvId(BilibiliId):
    """AId 与 BvId 的统一，大多数 API 只需要其中一种即可正常工作

    ### Examples

    ``` python
    # 初始化
    # 这两个 Id 事实上是完全一样的，指向同一个资源
    # 因此我们只获取其一即可，在能够获取 BvId 的情况下建议使用 BvId
    aid = AId("808982399")
    bvid = BvId("BV1f34y1k7D5")

    # 使用
    # 由于 B 站大多数需要 aid/bvid 的接口都是只提供其一即可，
    # 因此我们可以直接这样通过格式化的方式来产生一个合法的接口链接
    api = "https://api.bilibili.com/x/player/pagelist?aid={aid}&bvid={bvid}&jsonp=jsonp"
    api = api.format(aid=aid.value, bvid="")
    api = api.format(aid="", bvid=bvid.value)

    # 为了方便，继承了 AvId 的 AId 和 BvId 都可以通过 to_dict 方法简化这一步
    api = api.format(**aid.to_dict())
    api = api.format(**bvid.to_dict())
    # 这样就完全屏蔽了 aid 和 bvid 的差异了
    ```
    """

    # id conversion based on
    # https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/misc/bvid_desc.md

    XOR_CODE = 23442827791579
    MASK_CODE = 2251799813685247
    MAX_AID = 1 << 51
    ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
    ENCODE_MAP = 8, 7, 0, 5, 1, 3, 2, 4, 6
    DECODE_MAP = tuple(reversed(ENCODE_MAP))

    BASE = len(ALPHABET)
    PREFIX = "BV1"
    PREFIX_LEN = len(PREFIX)
    CODE_LEN = len(ENCODE_MAP)

    @staticmethod
    def av2bv(aid: int) -> str:
        bvid = [""] * 9
        tmp = (AvId.MAX_AID | aid) ^ AvId.XOR_CODE
        for i in range(AvId.CODE_LEN):
            bvid[AvId.ENCODE_MAP[i]] = AvId.ALPHABET[tmp % AvId.BASE]
            tmp //= AvId.BASE
        return AvId.PREFIX + "".join(bvid)

    @staticmethod
    def bv2av(bvid: str) -> int:
        assert bvid[:3] == AvId.PREFIX

        bvid = bvid[3:]
        tmp = 0
        for i in range(AvId.CODE_LEN):
            idx = AvId.ALPHABET.index(bvid[AvId.DECODE_MAP[i]])
            tmp = tmp * AvId.BASE + idx
        return (tmp & AvId.MASK_CODE) ^ AvId.XOR_CODE

    def to_dict(self) -> dict[str, str]:
        raise NotImplementedError("请不要直接使用 AvId")

    def to_url(self) -> str:
        raise NotImplementedError("请不要直接使用 AvId")

    def as_aid(self) -> AId:
        if isinstance(self, AId):
            return self
        return AId(str(self.bv2av(self.value)))

    def as_bvid(self) -> BvId:
        if isinstance(self, BvId):
            return self
        return BvId(self.av2bv(int(self.value)))


class AId(AvId):
    """AID"""

    def to_dict(self):
        return {"aid": self.value, "bvid": ""}

    def to_url(self) -> str:
        return f"https://www.bilibili.com/video/av{self.value}"


class BvId(AvId):
    """BVID"""

    def to_dict(self):
        return {
            "aid": "",
            "bvid": self.value,
        }

    def to_url(self) -> str:
        return f"https://www.bilibili.com/video/{self.value}"


class CId(BilibiliId):
    """视频 ID"""

    def to_dict(self):
        return {"cid": self.value}


class EpisodeId(BilibiliId):
    """番剧剧集 ID"""

    def to_dict(self):
        return {"episode_id": self.value}


class MediaId(BilibiliId):
    """番剧 ID"""

    def to_dict(self):
        return {"media_id": self.value}


class SeasonId(BilibiliId):
    """番剧（季） ID"""

    def to_dict(self):
        return {"season_id": self.value}


class MId(BilibiliId):
    """用户 ID"""

    def to_dict(self):
        return {"mid": self.value}


class FId(BilibiliId):
    """收藏夹 ID"""

    def to_dict(self):
        return {"fid": self.value}


class SeriesId(BilibiliId):
    """视频合集 ID"""

    def to_dict(self):
        return {"series_id": self.value}


def format_ids(*id: BilibiliId):
    id_dicts = [i.to_dict() for i in id]
    formatted_ids = [f"{k}: {v}" for i in id_dicts for k, v in i.items() if v]
    return ", ".join(formatted_ids)


class VideoUrlMeta(TypedDict):
    url: str
    mirrors: list[str]
    codec: VideoCodec
    width: int
    height: int
    quality: VideoQuality


class AudioUrlMeta(TypedDict):
    url: str
    mirrors: list[str]
    codec: AudioCodec
    width: int
    height: int
    quality: AudioQuality


class MultiLangSubtitle(TypedDict):
    lang: str
    lines: SubtitleData


class EpisodeData(TypedDict):
    """剧集数据，包含了一个视频资源的基本信息以及相关资源"""

    videos: list[VideoUrlMeta]
    audios: list[AudioUrlMeta]
    subtitles: list[MultiLangSubtitle]
    metadata: MetaData | None
    danmaku: DanmakuData
    cover_data: bytes | None
    chapter_info_data: list[ChapterInfoData]
    output_dir: Path
    tmp_dir: Path
    filename: str


class DownloaderOptions(TypedDict):
    require_video: bool
    require_chapter_info: bool
    save_cover: bool
    video_quality: VideoQuality
    video_download_codec: VideoCodec
    video_save_codec: str
    video_download_codec_priority: list[VideoCodec] | None
    require_audio: bool
    audio_quality: AudioQuality
    audio_download_codec: AudioCodec
    audio_save_codec: str
    output_format: str
    output_format_audio_only: str
    overwrite: bool
    block_size: int
    num_workers: int
    metadata_format: dict[str, str]
    banned_mirrors_pattern: str | None
    danmaku_options: DanmakuOptions


class FavouriteMetaData(TypedDict):
    fid: FId
    title: str


class UserInfo(TypedDict):
    vip_status: bool
    is_login: bool


if __name__ == "__main__":
    aid = AId("add")
    cid = CId("xxx")
    print("?aid={aid}&bvid={bvid}&cid={cid}".format(**aid.to_dict(), **cid.to_dict()))
