"""`DriverDirectory` of block 3: there are no drivers yet, so every alert stays
`PENDING_DRIVER` (alert_create AC-09). `driver_demand` replaces it in block 4."""

from datetime import date

from avisabus.domain.ports.alerts import DriverRef


class NoDriverDirectory:
    def find_driver(
        self, line: str, direction_id: int, trip_id: str, service_date: date
    ) -> DriverRef | None:
        return None
