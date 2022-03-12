import asyncio
import platform

from yutto.utils.console.logger import Logger


def initial_async_policy():
    if platform.system() == "Windows":
        Logger.debug("Windows 平台，单独设置 EventLoopPolicy")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore


def install_uvloop():
    try:
        import uvloop  # type: ignore
    except ImportError:
        # 即便未安装也没有什么影响，因此没有添加 WARNING 的必要
        # see also: https://github.com/yutto-dev/yutto/issues/69
        pass
    else:
        uvloop.install()  # type: ignore
        Logger.info("成功使用 uvloop 加速协程")
