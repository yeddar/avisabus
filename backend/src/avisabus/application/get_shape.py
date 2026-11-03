"""Use case: a shape of the active feed for the map (position_estimation AC-13–AC-15)."""

from avisabus.domain.errors import NoActiveFeedError, ShapeNotFoundError
from avisabus.domain.models.position import ShapeView
from avisabus.domain.ports.network import NetworkRepository


class GetShape:
    def __init__(self, network: NetworkRepository) -> None:
        self._network = network

    async def execute(self, shape_id: str) -> ShapeView:
        """Raises `NoActiveFeedError` and `ShapeNotFoundError` (no points, or no trip of the
        active feed uses the shape, so it has no line)."""
        feed = self._network.active_feed()
        if feed is None:
            raise NoActiveFeedError()
        points = self._network.shape_points(shape_id)
        line = self._network.shape_line(shape_id) if points else None
        if line is None:
            raise ShapeNotFoundError(shape_id)
        return ShapeView(
            shape_id=shape_id,
            line=line.short_name,
            color=line.color or None,
            coordinates=tuple((point.lon, point.lat) for point in points),
            stops=tuple(self._network.shape_stops(shape_id)),
            feed_version_id=feed.version_id,
        )
