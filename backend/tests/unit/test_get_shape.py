"""`GetShape` with the in-memory network (position_estimation T-05)."""

import pytest

from avisabus.application.get_shape import GetShape
from avisabus.domain.errors import NoActiveFeedError, ShapeNotFoundError
from avisabus.domain.models.network import ShapePoint
from avisabus.domain.models.position import ShapeStop, ShapeView
from tests.support.network import FEED, FakeNetwork


@pytest.fixture
def network() -> FakeNetwork:
    network = FakeNetwork()
    network.add_line("93", color="1E90FF")
    network.shapes["s93"] = [ShapePoint(39.45, -0.38, 1, 0.0), ShapePoint(39.46, -0.37, 2, 1400.0)]
    network.shape_lines["s93"] = "93"
    network.shape_stop_lists["s93"] = [ShapeStop("508", "Parc de l'Oest", 39.45, -0.38, 3)]
    network.shapes["orphan"] = [ShapePoint(39.45, -0.38, 1, 0.0)]  # no trip uses it
    return network


@pytest.mark.spec("position_estimation.AC-13")
async def test_shape_view_with_coordinates_as_lon_lat(network: FakeNetwork) -> None:
    assert await GetShape(network).execute("s93") == ShapeView(
        shape_id="s93",
        line="93",
        color="1E90FF",
        coordinates=((-0.38, 39.45), (-0.37, 39.46)),
        stops=(ShapeStop("508", "Parc de l'Oest", 39.45, -0.38, 3),),
        feed_version_id=FEED.version_id,
    )


@pytest.mark.spec("position_estimation.AC-15")
@pytest.mark.parametrize("shape_id", ["ghost", "orphan"])
async def test_unknown_shape_or_shape_without_trips(network: FakeNetwork, shape_id: str) -> None:
    with pytest.raises(ShapeNotFoundError) as raised:
        await GetShape(network).execute(shape_id)
    assert raised.value.shape_id == shape_id
    assert shape_id not in str(raised.value)


async def test_no_active_feed(network: FakeNetwork) -> None:
    network.feed = None
    with pytest.raises(NoActiveFeedError):
        await GetShape(network).execute("s93")
