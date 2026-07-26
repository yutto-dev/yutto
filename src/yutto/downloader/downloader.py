from __future__ import annotations

from typing import TYPE_CHECKING

from yutto.core.events import DownloadStage, DownloadStageChanged
from yutto.core.operation import emit_download_event, emit_download_report
from yutto.downloader.executor import DownloadExecutor
from yutto.downloader.planner import DownloadPlanner

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.core.request import DownloadRequest
    from yutto.core.result import ItemResult
    from yutto.types import EpisodeData


async def process_download(
    scope: ExecutionScope,
    episode_data: EpisodeData,
    request: DownloadRequest,
) -> ItemResult:
    """Plan and execute one episode while keeping planning side-effect free."""
    item = episode_data["info"]["path"].name
    emit_download_report(f"开始处理视频 {item}")
    emit_download_event(DownloadStageChanged(name=DownloadStage.PREPARING, item=item))
    plan = DownloadPlanner().plan(episode_data, request)
    return await DownloadExecutor().execute(scope, episode_data, plan)
