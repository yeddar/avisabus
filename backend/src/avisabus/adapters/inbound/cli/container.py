"""Dependencies of the CLI commands. Tests replace `build_cli_container` (design §8)."""

from dataclasses import dataclass

from sqlalchemy import Engine

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.application.get_feed_info import GetFeedInfo
from avisabus.application.import_gtfs_feed import ImportGtfsFeed
from avisabus.config import Settings
from avisabus.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CliContainer:
    engine: Engine
    import_gtfs_feed: ImportGtfsFeed
    get_feed_info: GetFeedInfo

    def close(self) -> None:
        self.engine.dispose()


def build_cli_container(settings: Settings, clock: Clock) -> CliContainer:
    engine = create_engine(settings)
    init_db(engine)
    network = SqliteNetworkRepository(engine)
    return CliContainer(
        engine=engine,
        import_gtfs_feed=ImportGtfsFeed(
            open_reader=CsvGtfsFeedReader,
            writer=SqliteGtfsFeedWriter(engine),
            clock=clock,
            batch_size=settings.gtfs_batch_size,
            warning_days=settings.gtfs_expiry_warning_days,
        ),
        get_feed_info=GetFeedInfo(
            network=network,
            source=network,
            clock=clock,
            warning_days=settings.gtfs_expiry_warning_days,
        ),
    )
