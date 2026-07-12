from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest

from yutto.utils.filter import PublicationTimeFilter


def test_publication_time_filter_parses_supported_formats_and_is_left_closed():
    publication_filter = PublicationTimeFilter.from_strings(
        "2024-01-02 03:04:05",
        "2024-01-03",
    )

    assert publication_filter.start_time == datetime.datetime(2024, 1, 2, 3, 4, 5)
    assert publication_filter.end_time == datetime.datetime(2024, 1, 3)
    assert publication_filter.matches(int(publication_filter.start_time.timestamp()))
    assert not publication_filter.matches(int(publication_filter.end_time.timestamp()))
    assert publication_filter.start_timestamp == int(publication_filter.start_time.timestamp())


def test_publication_time_filter_defaults_are_recomputed_per_request():
    before = datetime.datetime.now() + datetime.timedelta(days=1)
    publication_filter = PublicationTimeFilter.from_strings()
    after = datetime.datetime.now() + datetime.timedelta(days=1)

    assert publication_filter.start_time == datetime.datetime(1971, 1, 1)
    assert before <= publication_filter.end_time <= after


def test_invalid_syntax_falls_back_but_invalid_calendar_date_still_raises():
    publication_filter = PublicationTimeFilter.from_strings("not-a-date", "also-not-a-date")

    assert publication_filter.start_time == datetime.datetime(1971, 1, 1)
    assert publication_filter.end_time > datetime.datetime.now()
    with pytest.raises(ValueError):
        PublicationTimeFilter.from_strings("2024-02-31")


def test_reversed_and_separately_created_filters_keep_independent_windows():
    first = PublicationTimeFilter.from_strings("2024-01-02", "2024-01-01")
    second = PublicationTimeFilter.from_strings("2025-02-03", "2025-02-04")

    assert not first.matches(int(datetime.datetime(2024, 1, 1, 12).timestamp()))
    assert first.start_time == datetime.datetime(2024, 1, 2)
    assert second.start_time == datetime.datetime(2025, 2, 3)
    with pytest.raises(FrozenInstanceError):
        first.start_time = second.start_time  # ty: ignore[invalid-assignment]
