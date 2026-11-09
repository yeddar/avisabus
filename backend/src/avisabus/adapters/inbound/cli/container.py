"""Dependencies of the CLI commands. Tests replace `build_cli_container` (design §8)."""

from dataclasses import dataclass

import structlog
from sqlalchemy import Engine

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_driver_codes import SqliteDriverCodeRepository
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.adapters.outbound.qr.segno_renderer import SegnoQrRenderer
from avisabus.adapters.outbound.security.hmac_driver_code_hasher import HmacDriverCodeHasher
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.adapters.outbound.security.secrets_code_generator import SecretsCodeGenerator
from avisabus.application.driver_codes import CreateDriverCode, ListDriverCodes, RevokeDriverCode
from avisabus.application.generate_stop_qr_codes import GenerateStopQrCodes
from avisabus.application.get_feed_info import GetFeedInfo
from avisabus.application.import_gtfs_feed import ImportGtfsFeed
from avisabus.application.set_occupancy_override import (
    ClearOccupancyOverride,
    ListOccupancyOverrides,
    SetOccupancyOverride,
)
from avisabus.config import Settings, log_dev_stop_token_secret_warning
from avisabus.domain.ports.clock import Clock

DRIVER_CODES_LOGGER = "avisabus.driver_codes"


def _no_open_session(_code_id: str) -> bool:
    """Until `driver_session` exists no code can have a shift open (design §2)."""
    return False


@dataclass(frozen=True, slots=True)
class CliContainer:
    engine: Engine
    import_gtfs_feed: ImportGtfsFeed
    get_feed_info: GetFeedInfo
    set_occupancy_override: SetOccupancyOverride
    clear_occupancy_override: ClearOccupancyOverride
    list_occupancy_overrides: ListOccupancyOverrides
    generate_stop_qr_codes: GenerateStopQrCodes
    create_driver_code: CreateDriverCode
    list_driver_codes: ListDriverCodes
    revoke_driver_code: RevokeDriverCode

    def close(self) -> None:
        self.engine.dispose()


def build_cli_container(settings: Settings, clock: Clock) -> CliContainer:
    """Called by every CLI command right after `configure_logging`."""
    log_dev_stop_token_secret_warning(settings)
    engine = create_engine(settings)
    init_db(engine)
    network = SqliteNetworkRepository(engine)
    overrides = SqliteOccupancyOverrideRepository(engine)
    driver_codes = SqliteDriverCodeRepository(engine)
    logger = structlog.get_logger(DRIVER_CODES_LOGGER)
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
        generate_stop_qr_codes=GenerateStopQrCodes(
            network=network,
            signer=HmacStopTokenSigner(settings.stop_token_secret_bytes()),
            renderer=SegnoQrRenderer(),
            public_base_url=settings.public_base_url,
        ),
        create_driver_code=CreateDriverCode(
            repository=driver_codes,
            generator=SecretsCodeGenerator(),
            hasher=HmacDriverCodeHasher(settings.stop_token_secret_bytes()),
            clock=clock,
            logger=logger,
        ),
        list_driver_codes=ListDriverCodes(
            repository=driver_codes, has_open_session=_no_open_session
        ),
        revoke_driver_code=RevokeDriverCode(
            repository=driver_codes,
            clock=clock,
            has_open_session=_no_open_session,
            logger=logger,
        ),
    )
