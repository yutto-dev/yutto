from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest
from returns.result import Success

import yutto.__main__ as main_module
import yutto.download_manager as download_manager_module
import yutto.extractor.bangumi as bangumi_module
import yutto.extractor.cheese as cheese_module
import yutto.validator as validator_module
from yutto._native import InvalidUrlError
from yutto.core.execution import ExecutionScope
from yutto.core.request import DownloadRequest
from yutto.download_manager import DownloadManager
from yutto.exceptions import (
    EpisodeNotFoundError,
    ErrorCode,
    NotLoginError,
    WrongArgumentError,
    WrongUrlError,
    YuttoBaseException,
)
from yutto.extractor.bangumi import BangumiExtractor
from yutto.extractor.cheese import CheeseExtractor
from yutto.input_parser import parse_episodes_selection
from yutto.types import SeasonId
from yutto.utils.fetcher import Fetcher
from yutto.utils.filter import PublicationTimeFilter
from yutto.utils.functional import as_sync
from yutto.validator import validate_batch_selection

pytestmark = pytest.mark.processor

if TYPE_CHECKING:
    from pathlib import Path

    from yutto.types import ExtractorOptions


def make_request(url: str = "BV1structured") -> DownloadRequest:
    return DownloadRequest.model_validate({"source": {"url": url}})


def assert_error(error: YuttoBaseException, message: str, code: ErrorCode) -> None:
    assert str(error) == message
    assert error.message == message
    assert error.code is code


@pytest.mark.processor
def test_selection_validation_raises_structured_argument_errors():
    with pytest.raises(WrongArgumentError) as exc_info:
        validate_batch_selection("1,,2")
    assert_error(
        exc_info.value,
        "选集参数（1,,2）格式不正确呀～重新检查一下下～",
        ErrorCode.WRONG_ARGUMENT_ERROR,
    )

    with pytest.raises(WrongArgumentError) as exc_info:
        parse_episodes_selection("0", 12)
    assert_error(
        exc_info.value,
        "不可使用 0 作为剧集号（剧集号从 1 开始计算）",
        ErrorCode.WRONG_ARGUMENT_ERROR,
    )

    with pytest.raises(WrongArgumentError) as exc_info:
        parse_episodes_selection("4~2", 12)
    assert_error(
        exc_info.value,
        "终点值（2）应不小于起点值（4）",
        ErrorCode.WRONG_ARGUMENT_ERROR,
    )


@pytest.mark.processor
@as_sync
async def test_manager_raises_login_error(monkeypatch: pytest.MonkeyPatch):
    async def reject_login(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        return False

    monkeypatch.setattr(download_manager_module, "validate_user_info", reject_login)
    with pytest.raises(NotLoginError) as exc_info:
        await DownloadManager().process_request(
            ExecutionScope(cast("Any", object())),
            make_request(),
        )

    assert_error(
        exc_info.value,
        "启用了严格校验大会员或登录模式，请检查认证信息（--auth）或大会员状态！",
        ErrorCode.NOT_LOGIN_ERROR,
    )


@pytest.mark.processor
@as_sync
async def test_manager_raises_url_errors_without_network(monkeypatch: pytest.MonkeyPatch):
    async def accept_login(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        return True

    async def reject_url(scope: ExecutionScope, url: str):
        raise InvalidUrlError("invalid")

    monkeypatch.setattr(download_manager_module, "validate_user_info", accept_login)
    monkeypatch.setattr(Fetcher, "get_redirected_url", reject_url)
    with pytest.raises(WrongUrlError) as exc_info:
        await DownloadManager().process_request(
            ExecutionScope(cast("Any", object())),
            make_request("not-a-url"),
        )

    assert_error(
        exc_info.value,
        "无效的 url(not-a-url)～请检查一下链接是否正确～",
        ErrorCode.WRONG_URL_ERROR,
    )


@pytest.mark.processor
@as_sync
async def test_manager_reports_unmatched_url_as_structured_error(monkeypatch: pytest.MonkeyPatch):
    async def accept_login(scope: ExecutionScope, requirements: dict[str, bool]) -> bool:
        return True

    async def keep_url(scope: ExecutionScope, url: str):
        return Success(url)

    monkeypatch.setattr(download_manager_module, "validate_user_info", accept_login)
    monkeypatch.setattr(Fetcher, "get_redirected_url", keep_url)

    with pytest.raises(WrongUrlError) as exc_info:
        await DownloadManager().process_request(
            ExecutionScope(cast("Any", object())),
            make_request("https://example.com/unsupported"),
        )

    assert_error(
        exc_info.value,
        "url 不正确，也许该 url 仅支持批量下载，如果是这样，请使用参数 -b～",
        ErrorCode.WRONG_URL_ERROR,
    )


EMPTY_EXTRACTOR_OPTIONS: ExtractorOptions = {
    "episodes": "1",
    "with_extra_episodes": False,
    "skip_preview": False,
    "require_video": True,
    "require_audio": True,
    "require_danmaku": True,
    "require_subtitle": True,
    "subtitle_languages": None,
    "require_metadata": False,
    "require_cover": True,
    "require_chapter_info": True,
    "danmaku_format": "ass",
    "subpath_template": "{auto}",
    "ai_translation_language": None,
    "publication_time_filter": PublicationTimeFilter.from_strings(),
}


@pytest.mark.processor
@pytest.mark.parametrize(
    ("module", "extractor_type", "list_getter_name", "url"),
    [
        (bangumi_module, BangumiExtractor, "get_bangumi_list", "https://www.bilibili.com/bangumi/play/ep1"),
        (cheese_module, CheeseExtractor, "get_cheese_list", "https://www.bilibili.com/cheese/play/ep1"),
    ],
)
@as_sync
async def test_single_extractors_raise_when_episode_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    extractor_type: type[BangumiExtractor | CheeseExtractor],
    list_getter_name: str,
    url: str,
):
    async def get_season(scope: ExecutionScope, episode_id: Any) -> SeasonId:
        return SeasonId("1")

    async def get_empty_list(scope: ExecutionScope, season_id: SeasonId):
        return {"title": "空列表", "pages": []}

    monkeypatch.setattr(module, "get_season_id_by_episode_id", get_season)
    monkeypatch.setattr(module, list_getter_name, get_empty_list)
    extractor = extractor_type()
    assert extractor.match(url)

    with pytest.raises(EpisodeNotFoundError) as exc_info:
        await extractor.extract(
            ExecutionScope(cast("Any", object())),
            EMPTY_EXTRACTOR_OPTIONS,
        )

    assert_error(exc_info.value, "在列表中未找到该剧集", ErrorCode.EPISODE_NOT_FOUND_ERROR)


@pytest.mark.parametrize(
    ("failure", "exit_code", "message"),
    [
        (WrongUrlError("url 不正确呀～"), ErrorCode.WRONG_URL_ERROR.value, "url 不正确呀～"),
        (SystemExit(ErrorCode.WRONG_ARGUMENT_ERROR.value), ErrorCode.WRONG_ARGUMENT_ERROR.value, None),
        (KeyboardInterrupt(), ErrorCode.PAUSED_DOWNLOAD.value, "已终止下载，再次运行即可继续下载～"),
        (asyncio.CancelledError(), ErrorCode.PAUSED_DOWNLOAD.value, "已终止下载，再次运行即可继续下载～"),
    ],
    ids=["structured-error", "system-exit", "keyboard-interrupt", "cancelled"],
)
def test_download_cli_reports_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure: BaseException,
    exit_code: int,
    message: str | None,
):
    config = tmp_path / "yutto.toml"
    config.write_text("")
    monkeypatch.setattr(
        main_module.sys,
        "argv",
        [
            "yutto",
            "av1",
            "--config",
            str(config),
            "--auth-file",
            str(tmp_path / "auth.toml"),
            "--no-progress",
        ],
    )
    monkeypatch.setattr(validator_module, "FFmpeg", lambda: SimpleNamespace(video_encodecs=[], audio_encodecs=[]))

    def fail_download(scope_factory, requests, renderer, *, jobs):
        assert len(requests) == 1 and requests[0].source.url == "av1"
        raise failure

    monkeypatch.setattr(main_module, "run_download", fail_download)
    with pytest.raises(SystemExit) as exc_info:
        main_module.main()
    assert exc_info.value.code == exit_code
    captured = capsys.readouterr()
    if message is not None:
        assert captured.out.count(message) == 1
    else:
        assert "已终止下载" not in captured.out
    assert ("ERROR" in captured.out) == isinstance(failure, WrongUrlError)
    assert "Traceback" not in captured.out + captured.err
