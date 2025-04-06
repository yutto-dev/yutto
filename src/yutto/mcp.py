# noqa: I002

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from yutto.download_manager import DownloadManager, DownloadTask
from yutto.utils.fetcher import FetcherContext

if TYPE_CHECKING:
    from mcp.server.session import ServerSession


@dataclass
class AppContext:
    download_manager: DownloadManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    ctx = FetcherContext()
    download_manager = DownloadManager()
    download_manager.start(ctx)
    try:
        yield AppContext(download_manager=download_manager)
    finally:
        # Cleanup on shutdown
        await download_manager.stop()


mcp = FastMCP("yutto", lifespan=app_lifespan)


def parse_args(url: str, dir: str):
    from yutto.cli.cli import cli

    parser = cli()
    args = parser.parse_args(["download", url, "-d", dir])
    return args


@mcp.tool()
async def add_task(
    ctx: Context,  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
    url: str = Field(description="The URL to download, you can also use a short link like 'BV1CrfKYLEeP'"),
    dir: str = Field(description="The directory to save the downloaded file"),
) -> str:
    """
    Use this tool to download a video from Bilibili using the given URL or short link.
    """
    ctx_typed = cast("Context[ServerSession, AppContext]", ctx)
    download_manager: DownloadManager = ctx_typed.request_context.lifespan_context.download_manager
    await download_manager.add_task(DownloadTask(args=parse_args(url, dir)))
    return "Task added"


def run_mcp():
    mcp.run()


if __name__ == "__main__":
    run_mcp()
