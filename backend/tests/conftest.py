"""Shared fixtures. Tests never touch the network or the real clock."""

from datetime import UTC, datetime

import pytest

from tests.support.fake_clock import FakeClock

DEFAULT_NOW = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(DEFAULT_NOW)
