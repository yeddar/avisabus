from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.config import Settings


@pytest.fixture
def db_settings(tmp_path: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, env="test", database_url=f"sqlite:///{tmp_path / 'avisabus.sqlite'}"
    )


@pytest.fixture
def engine(db_settings: Settings) -> Iterator[Engine]:
    engine = create_engine(db_settings)
    init_db(engine)
    yield engine
    engine.dispose()
