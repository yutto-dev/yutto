from typing import Any, Literal, Union
from enum import Enum


class ErrorCode(Enum):

    UNSUPPORTED_PYTHON_VERSION_ERROR = 9
    HTTP_STATUS_ERROR = 10
    NO_ACCESS_PERMISSION_ERROR = 11
    UNSUPPORTED_TYPE_ERROR = 12
    WRONG_ARGUMENT_ERROR = 13
    WRONG_URL_ERROR = 14
    EPISODE_NOT_FOUND_ERROR = 15


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


if __name__ == "__main__":
    import sys

    try:
        raise HttpStatusError("HTTP 错误")
    except (HttpStatusError, UnSupportedTypeError) as e:
        print(e.code.value, e.message)
        sys.exit(e.code.value)
