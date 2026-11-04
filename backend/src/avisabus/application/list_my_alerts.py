"""Use case: active alerts of a device in every stop (alert_create AC-10, AC-11)."""

from avisabus.domain.models.alert import Alert
from avisabus.domain.ports.alerts import AlertRepository


class ListMyAlerts:
    def __init__(self, alerts: AlertRepository) -> None:
        self._alerts = alerts

    async def execute(self, device_hash: str) -> list[Alert]:
        """By `created_at`. Every stored alert is active (expired ones are deleted)."""
        return self._alerts.list_by_device(device_hash)
