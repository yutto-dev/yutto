from typing import NamedTuple, TypedDict

from yutto.media.codec import AudioCodec, VideoCodec
from yutto.media.quality import AudioQuality, VideoQuality
from yutto.utils.subtitle import SubtitleData


class BilibiliId(NamedTuple):
    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: "BilibiliId") -> bool:
        return self.value == other.value


class AvId(BilibiliId):
    def to_dict(self) -> dict[str, str]:
        raise NotImplementedError("请不要直接使用 AvId")


class AId(AvId):
    def to_dict(self):
        return {"aid": self.value, "bvid": ""}


class BvId(AvId):
    def to_dict(self):
        return {
            "aid": "",
            "bvid": self.value,
        }


class CId(BilibiliId):
    def to_dict(self):
        return {"cid": self.value}


class EpisodeId(BilibiliId):
    def to_dict(self):
        return {"episode_id": self.value}


class MediaId(BilibiliId):
    def to_dict(self):
        return {"media_id": self.value}


class SeasonId(BilibiliId):
    def to_dict(self):
        return {"season_id": self.value}


class HttpStatusError(Exception):
    pass


class NoAccessError(Exception):
    pass


class UnSupportedTypeError(Exception):
    pass


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


if __name__ == "__main__":
    aid = AId("add")
    cid = CId("xxx")
    print("?aid={aid}&bvid={bvid}&cid={cid}".format(**aid.to_dict(), **cid.to_dict()))
