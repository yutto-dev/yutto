from __future__ import annotations

import sys
from enum import Enum
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from types import TracebackType


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


class MaxRetryError(YuttoBaseException):
    code = ErrorCode.MAX_RETRY_ERROR


class NotFoundError(YuttoBaseException):
    code = ErrorCode.NOT_FOUND_ERROR


class NotLoginError(YuttoBaseException):
    code = ErrorCode.NOT_LOGIN_ERROR


def handleUncaughtException(exctype: type[Exception], exception: Exception, trace: TracebackType):
    oldHook(exctype, exception, trace)
    if isinstance(exception, YuttoBaseException):
        sys.exit(exception.code.value)


sys.excepthook, oldHook = handleUncaughtException, sys.excepthook


if __name__ == "__main__":
    try:
        raise HttpStatusError("HTTP 错误")
    except (HttpStatusError, UnSupportedTypeError) as e:
        print(e.code.value, e.message)
        raise e
