import sys
from enum import Enum
from types import TracebackType
from typing import Union, Type


class ErrorCode(Enum):
    # 发生错误
    UNSUPPORTED_PYTHON_VERSION_ERROR = 9
    HTTP_STATUS_ERROR = 10
    NO_ACCESS_PERMISSION_ERROR = 11
    UNSUPPORTED_TYPE_ERROR = 12
    WRONG_ARGUMENT_ERROR = 13
    WRONG_URL_ERROR = 14
    EPISODE_NOT_FOUND_ERROR = 15
    MAX_RETRY_ERROR = 16
    NOT_FOUND_ERROR = 17

    # 异常状况，但并不算错误
    PAUSED_DOWNLOAD = 101


class SuccessCode(Enum):
    SUCCESS = 0


ReturnCode = Union[ErrorCode, SuccessCode]


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


def handleUncaughtException(exctype: Type[Exception], exception: Exception, trace: TracebackType):
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
