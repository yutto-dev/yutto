from __future__ import annotations

from enum import Enum
from typing import TypeAlias


class ErrorCode(Enum):
    # 发生错误
    HTTP_STATUS_ERROR = 10
    NO_ACCESS_PERMISSION_ERROR = 11
    UNSUPPORTED_TYPE_ERROR = 12
    WRONG_ARGUMENT_ERROR = 13
    WRONG_URL_ERROR = 14
    EPISODE_NOT_FOUND_ERROR = 15
    MAX_RETRY_ERROR = 16
    NOT_FOUND_ERROR = 17
    NOT_LOGIN_ERROR = 18
    CRYPTO_ERROR = 19
    POSTPROCESSING_ERROR = 20
    RESOLVE_FAILED_ERROR = 21

    # 异常状况，但并不算错误
    PAUSED_DOWNLOAD = 101


class SuccessCode(Enum):
    SUCCESS = 0


ReturnCode: TypeAlias = ErrorCode | SuccessCode


class YuttoBaseException(Exception):
    code: ErrorCode
    message: str

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class HttpStatusError(YuttoBaseException):
    code = ErrorCode.HTTP_STATUS_ERROR


class NoAccessPermissionError(YuttoBaseException):
    code = ErrorCode.NO_ACCESS_PERMISSION_ERROR


class UnSupportedTypeError(YuttoBaseException):
    code = ErrorCode.UNSUPPORTED_TYPE_ERROR


class WrongArgumentError(YuttoBaseException):
    code = ErrorCode.WRONG_ARGUMENT_ERROR


class WrongUrlError(YuttoBaseException):
    code = ErrorCode.WRONG_URL_ERROR


class EpisodeNotFoundError(YuttoBaseException):
    code = ErrorCode.EPISODE_NOT_FOUND_ERROR


class MaxRetryError(YuttoBaseException):
    code = ErrorCode.MAX_RETRY_ERROR


class NotFoundError(YuttoBaseException):
    code = ErrorCode.NOT_FOUND_ERROR


class NotLoginError(YuttoBaseException):
    code = ErrorCode.NOT_LOGIN_ERROR


class CryptoError(YuttoBaseException):
    code = ErrorCode.CRYPTO_ERROR


class PostprocessingError(YuttoBaseException):
    code = ErrorCode.POSTPROCESSING_ERROR


class ResolveFailedError(YuttoBaseException):
    """解析任务未得到任何条目，且存在预期内的失败（多个失败聚合时使用；单一失败直接抛原始异常）"""

    code = ErrorCode.RESOLVE_FAILED_ERROR
