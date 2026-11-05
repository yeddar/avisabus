"""`DriverViewNotifier` of block 3: there is no driver view to refresh (`alert_cancel` and
`alert_expiry` use it). `driver_demand` replaces it in block 4."""


class NoopDriverViewNotifier:
    def alert_removed(self, session_id: str) -> None:
        return None
