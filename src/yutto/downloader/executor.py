from __future__ import annotations

from typing import TYPE_CHECKING

from yutto.core.events import (
    DownloadArtifactCreated,
    DownloadItemSkipped,
    DownloadStage,
    DownloadStageChanged,
)
from yutto.core.operation import emit_download_event, emit_download_report
from yutto.core.result import Artifact, ArtifactKind, ItemResult, ItemSkipReason, ItemState
from yutto.downloader.artifact_writer import ArtifactWriter
from yutto.downloader.media_muxer import MediaMuxer
from yutto.downloader.transfer import cleanup_temporary_media, download_video_and_audio
from yutto.media.quality import audio_quality_map, video_quality_map

if TYPE_CHECKING:
    from yutto.core.execution import ExecutionScope
    from yutto.downloader.planner import DownloadPlan
    from yutto.types import EpisodeData


class DownloadExecutor:
    """Execute one immutable decision plan against its extractor payload."""

    def __init__(
        self,
        artifact_writer: ArtifactWriter | None = None,
        media_muxer: MediaMuxer | None = None,
    ):
        self._artifact_writer = artifact_writer if artifact_writer is not None else ArtifactWriter()
        self._media_muxer = media_muxer

    async def execute(
        self,
        scope: ExecutionScope,
        episode_data: EpisodeData,
        plan: DownloadPlan,
    ) -> ItemResult:
        plan.paths.output_dir.mkdir(parents=True, exist_ok=True)
        plan.paths.temporary_dir.mkdir(parents=True, exist_ok=True)
        emit_streams_selected(plan)

        artifacts: list[Artifact] = []
        emit_download_event(DownloadStageChanged(name=DownloadStage.WRITING_RESOURCES, item=plan.item))
        for resource in self._artifact_writer.write(episode_data, plan):
            artifacts.extend(resource.artifacts)
            if resource.kind is ArtifactKind.SUBTITLE:
                emit_download_report(f"{', '.join(resource.labels)} 字幕已全部生成", badge="字幕")
            elif resource.kind is ArtifactKind.DANMAKU:
                emit_download_report(f"{resource.labels[0]} 弹幕已生成".upper(), badge="弹幕")
            elif resource.kind is ArtifactKind.METADATA:
                emit_download_report("NFO 媒体描述文件已生成", badge="描述文件")
            elif resource.kind is ArtifactKind.COVER:
                emit_download_report("封面已生成", badge="封面")

        if not plan.has_media:
            emit_download_report("没有音视频需要下载", "warning")
            self._artifact_writer.cleanup_temporary(plan)
            if not plan.media_requested:
                return ItemResult(
                    state=ItemState.DONE,
                    output_path=plan.paths.output,
                    artifacts=tuple(artifacts),
                )
            emit_download_event(
                DownloadItemSkipped(
                    item=plan.item,
                    reason=ItemSkipReason.NO_MEDIA_STREAM,
                )
            )
            return ItemResult(
                state=ItemState.SKIPPED,
                output_path=plan.paths.output,
                skip_reason=ItemSkipReason.NO_MEDIA_STREAM,
                artifacts=tuple(artifacts),
            )

        if plan.paths.output.exists():
            if not plan.overwrite:
                emit_download_event(
                    DownloadItemSkipped(
                        item=plan.item,
                        reason=ItemSkipReason.ALREADY_EXISTS,
                    )
                )
                artifacts.append(Artifact(kind=ArtifactKind.MEDIA, path=plan.paths.output))
                self._artifact_writer.cleanup_temporary(plan)
                return ItemResult(
                    state=ItemState.SKIPPED,
                    output_path=plan.paths.output,
                    skip_reason=ItemSkipReason.ALREADY_EXISTS,
                    artifacts=tuple(artifacts),
                )
            emit_download_report("文件已存在，因启用 overwrite 选项强制删除……")
            plan.paths.output.unlink()

        await download_video_and_audio(scope, plan)

        emit_download_event(DownloadStageChanged(name=DownloadStage.POSTPROCESSING, item=plan.item))
        if plan.requires_audio_transcode_notice:
            assert plan.audio is not None
            emit_download_report(
                f"输出容器 {plan.paths.output.suffix} 无法直接封装 {plan.audio.codec} 音频，"
                f"将自动转码为 {plan.audio_save_codec}",
            )
        media_muxer = self._media_muxer if self._media_muxer is not None else MediaMuxer()
        await media_muxer.mux(plan)

        cleanup_temporary_media(plan)
        self._artifact_writer.cleanup_temporary(plan)
        artifacts.append(Artifact(kind=ArtifactKind.MEDIA, path=plan.paths.output))
        emit_download_event(DownloadArtifactCreated(item=plan.item, path=plan.paths.output))
        return ItemResult(
            state=ItemState.DONE,
            output_path=plan.paths.output,
            artifacts=tuple(artifacts),
        )


def emit_streams_selected(plan: DownloadPlan) -> None:
    if not plan.video_candidates:
        emit_download_report("不包含任何视频流")
    else:
        emit_download_report(f"共包含以下 {len(plan.video_candidates)} 个视频流：")
        for candidate in plan.video_candidates:
            assert candidate.width is not None and candidate.height is not None
            message = "{}{:2} [{:^4}] [{:>4}x{:<4}] <{:^8}> #{}".format(
                "*" if candidate.selected else " ",
                candidate.index,
                candidate.codec.upper(),
                candidate.width,
                candidate.height,
                video_quality_map[candidate.quality]["description"],
                candidate.mirror_count,
            )
            emit_download_report(message, color="blue" if candidate.selected else None)

    if not plan.audio_candidates:
        emit_download_report("不包含任何音频流")
    else:
        emit_download_report(f"共包含以下 {len(plan.audio_candidates)} 个音频流：")
        for candidate in plan.audio_candidates:
            message = "{}{:2} [{:^4}] <{:^8}>".format(
                "*" if candidate.selected else " ",
                candidate.index,
                candidate.codec.upper(),
                audio_quality_map[candidate.quality]["description"],
            )
            emit_download_report(
                message,
                color="magenta" if candidate.selected else None,
            )
