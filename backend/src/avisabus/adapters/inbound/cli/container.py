"""Dependencies of the CLI commands. Tests replace `build_cli_container` (design §8)."""

from dataclasses import dataclass

from sqlalchemy import Engine

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.application.get_feed_info import GetFeedInfo
from avisabus.application.import_gtfs_feed import ImportGtfsFeed
from avisabus.application.set_occupancy_override import (
    ClearOccupancyOverride,
    ListOccupancyOverrides,
    SetOccupancyOverride,
)
from avisabus.config import Settings
from avisabus.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CliContainer:
    engine: Engine
    import_gtfs_feed: ImportGtfsFeed
    get_feed_info: GetFeedInfo
    set_occupancy_override: SetOccupancyOverride
    clear_occupancy_override: ClearOccupancyOverride
    list_occupancy_overrides: ListOccupancyOverrides

    def close(self) -> None:
        self.engine.dispose()


def build_cli_container(settings: Settings, clock: Clock) -> CliContainer:
    engine = create_engine(settings)
    init_db(engine)
    network = SqliteNetworkRepository(engine)
    overrides = SqliteOccupancyOverrideRepository(engine)
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
        set_occupancy_override=SetOccupancyOverride(
            network=network, overrides=overrides, clock=clock
        ),
        clear_occupancy_override=ClearOccupancyOverride(network=network, overrides=overrides),
        list_occupancy_overrides=ListOccupancyOverrides(overrides=overrides, clock=clock),
    )
