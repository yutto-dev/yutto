from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import (
    ClassVar as _ClassVar,
    Iterable as _Iterable,
    Mapping as _Mapping,
    Optional as _Optional,
    Union as _Union,
)

DESCRIPTOR: _descriptor.FileDescriptor

class DanmakuElem(_message.Message):
    __slots__ = (
        "id",
        "progress",
        "mode",
        "fontsize",
        "color",
        "mid_hash",
        "content",
        "ctime",
        "action",
        "pool",
        "id_str",
    )
    ID_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    FONTSIZE_FIELD_NUMBER: _ClassVar[int]
    COLOR_FIELD_NUMBER: _ClassVar[int]
    MID_HASH_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    CTIME_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    POOL_FIELD_NUMBER: _ClassVar[int]
    ID_STR_FIELD_NUMBER: _ClassVar[int]
    id: int
    progress: int
    mode: int
    fontsize: int
    color: int
    mid_hash: str
    content: str
    ctime: int
    action: str
    pool: int
    id_str: str
    def __init__(
        self,
        id: _Optional[int] = ...,
        progress: _Optional[int] = ...,
        mode: _Optional[int] = ...,
        fontsize: _Optional[int] = ...,
        color: _Optional[int] = ...,
        mid_hash: _Optional[str] = ...,
        content: _Optional[str] = ...,
        ctime: _Optional[int] = ...,
        action: _Optional[str] = ...,
        pool: _Optional[int] = ...,
        id_str: _Optional[str] = ...,
    ) -> None: ...

class DanmakuEvent(_message.Message):
    __slots__ = ("elems",)
    ELEMS_FIELD_NUMBER: _ClassVar[int]
    elems: _containers.RepeatedCompositeFieldContainer[DanmakuElem]
    def __init__(
        self, elems: _Optional[_Iterable[_Union[DanmakuElem, _Mapping]]] = ...
    ) -> None: ...
