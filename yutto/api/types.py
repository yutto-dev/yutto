from typing import NamedTuple


class BilibiliId(NamedTuple):
    value: str

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.__str__()


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


if __name__ == "__main__":
    aid = AId("add")
    cid = CId("xxx")
    print("?aid={aid}&bvid={bvid}&cid={cid}".format(**aid.to_dict(), **cid.to_dict()))
