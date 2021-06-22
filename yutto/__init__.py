import sys

from yutto.exceptions import ErrorCode

# 应当在其他模块（特别是含 3.9 语法的模块）被调用前执行
if (sys.version_info.major, sys.version_info.minor) < (3, 9):
    print("请使用 Python3.9 及以上版本哦～")
    sys.exit(ErrorCode.UNSUPPORTED_PYTHON_VERSION_ERROR.value)
