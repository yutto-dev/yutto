from __future__ import annotations

import warnings

# Protobuf 5.28.0 adds a runtime check for version mismatch between the generated code and the runtime library
# It's useful for debugging, but it will make user confused when they see the warning
# See same issue https://github.com/protocolbuffers/protobuf/issues/18096 for more information

warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    message=r"Protobuf gencode version ([\.\d]+) is older than the runtime version ([\.\d]+) at protobuf/danmaku\.proto\.",
)


from .biliass import (  # noqa: E402
    Danmaku2ASS as Danmaku2ASS,
    ReadCommentsBilibiliProtobuf as ReadCommentsBilibiliProtobuf,
    ReadCommentsBilibiliXml as ReadCommentsBilibiliXml,
)

__version__ = "1.3.12"
