from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from biliass import BlockOptions

from yutto.core.result import Artifact, ArtifactKind
from yutto.utils.danmaku import write_danmaku
from yutto.utils.metadata import write_chapter_info, write_metadata
from yutto.utils.subtitle import write_subtitle

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from yutto.downloader.planner import DownloadPlan
    from yutto.types import EpisodeData
    from yutto.utils.danmaku import DanmakuOptions


@dataclass(frozen=True, slots=True)
class WrittenResource:
    kind: ArtifactKind
    paths: tuple[Path, ...]
    labels: tuple[str, ...] = ()

    @property
    def artifacts(self) -> tuple[Artifact, ...]:
        return tuple(Artifact(kind=self.kind, path=path) for path in self.paths)


class ArtifactWriter:
    """Own resource sidecars and temporary muxing resources."""

    def write(self, episode_data: EpisodeData, plan: DownloadPlan) -> Iterator[WrittenResource]:
        resources = plan.resources

        if resources.subtitle_languages:
            paths = tuple(
                write_subtitle(subtitle["lines"], plan.paths.output, subtitle["lang"])
                for subtitle in episode_data["subtitles"]
            )
            yield WrittenResource(
                kind=ArtifactKind.SUBTITLE,
                paths=paths,
                labels=resources.subtitle_languages,
            )

        if resources.has_danmaku:
            paths = tuple(
                write_danmaku(
                    episode_data["danmaku"],
                    plan.paths.output,
                    resources.danmaku_height,
                    resources.danmaku_width,
                    create_danmaku_options(plan),
                )
            )
            yield WrittenResource(
                kind=ArtifactKind.DANMAKU,
                paths=paths,
                labels=(str(resources.danmaku_save_type),),
            )

        if resources.has_metadata:
            metadata = episode_data["metadata"]
            assert metadata is not None
            path = write_metadata(
                metadata,
                plan.paths.output,
                {
                    "premiered": resources.metadata.premiered,
                    "dateadded": resources.metadata.dateadded,
                },
            )
            yield WrittenResource(kind=ArtifactKind.METADATA, paths=(path,))

        if resources.has_cover:
            cover_data = episode_data["cover_data"]
            assert cover_data is not None
            plan.paths.cover.write_bytes(cover_data)
            if resources.save_cover:
                plan.paths.saved_cover.write_bytes(cover_data)
                yield WrittenResource(kind=ArtifactKind.COVER, paths=(plan.paths.saved_cover,))

        if resources.has_chapter_info:
            write_chapter_info(
                plan.item,
                episode_data["chapter_info_data"],
                plan.paths.chapter_info,
            )

    def cleanup_temporary(self, plan: DownloadPlan) -> None:
        if plan.resources.has_chapter_info:
            plan.paths.chapter_info.unlink(missing_ok=True)
        if plan.resources.has_cover:
            plan.paths.cover.unlink(missing_ok=True)


def create_danmaku_options(plan: DownloadPlan) -> DanmakuOptions:
    options = plan.resources.danmaku
    return {
        "font_size": options.font_size,
        "font": options.font,
        "opacity": options.opacity,
        "display_region_ratio": options.display_region_ratio,
        "speed": options.speed,
        "block_options": BlockOptions(
            block_top=options.block_top,
            block_bottom=options.block_bottom,
            block_scroll=options.block_scroll,
            block_reverse=options.block_reverse,
            block_special=options.block_special,
            block_colorful=options.block_colorful,
            block_keyword_patterns=list(options.block_keyword_patterns),
        ),
    }
