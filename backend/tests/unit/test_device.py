"""Anonymous device identifier: validation and keyed hash (realtime_events T-01)."""

import hashlib
import hmac

import pytest

from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.domain.errors import DomainError, InvalidDeviceIdError
from avisabus.domain.models.device import DeviceId, parse_device_id
from avisabus.domain.models.events import Event
from avisabus.domain.ports.device import DeviceHasher
from avisabus.domain.ports.events import device_channel

DEVICE = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
SECRET = b"test-secret-0123456789abcdef0123"
# Computed once with the formula of design §3: key = HMAC-SHA256(secret, "avisabus:device-id:v1"),
# hash = HMAC-SHA256(key, device_id) in hexadecimal.
HASH_DEVICE = "933f9970ee1da660a4f1081c73b0446600a5c8aa34d0ce302c82d62051a5b76f"


@pytest.mark.spec("realtime_events.AC-04")
@pytest.mark.parametrize(
    "raw",
    [
        DEVICE,
        "00000000-0000-4000-8000-000000000000",
        "ffffffff-ffff-4fff-bfff-ffffffffffff",
        "12345678-abcd-4abc-9abc-123456789abc",
        "12345678-abcd-4abc-aabc-123456789abc",
    ],
)
def test_accepts_canonical_uuid_v4(raw: str) -> None:
    assert parse_device_id(raw).value == raw


@pytest.mark.spec("realtime_events.AC-04")
@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not-a-uuid",
        DEVICE.upper(),  # uppercase is not canonical
        "3F2B8C1E-9a4d-4e6f-8b2a-1c3d5e7f9a0b",
        DEVICE.replace("-", ""),  # no hyphens
        "{" + DEVICE + "}",  # braces
        "urn:uuid:" + DEVICE,
        DEVICE + "\n",  # trailing newline
        " " + DEVICE,
        DEVICE + "0",  # 37 characters
        DEVICE[:-1],  # 35 characters
        "3f2b8c1e-9a4d-1e6f-8b2a-1c3d5e7f9a0b",  # version 1
        "3f2b8c1e-9a4d-5e6f-8b2a-1c3d5e7f9a0b",  # version 5
        "3f2b8c1e-9a4d-4e6f-7b2a-1c3d5e7f9a0b",  # variant 0xxx
        "3f2b8c1e-9a4d-4e6f-cb2a-1c3d5e7f9a0b",  # variant 110x
        "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0g",  # not hexadecimal
        "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0٣",  # non-ASCII digit
        "00000000-0000-0000-0000-000000000000",  # nil UUID
    ],
)
def test_rejects_anything_else(raw: str | None) -> None:
    with pytest.raises(InvalidDeviceIdError):
        parse_device_id(raw)


@pytest.mark.spec("realtime_events.AC-04")
def test_invalid_device_id_error_is_a_domain_error_without_the_value() -> None:
    with pytest.raises(InvalidDeviceIdError) as caught:
        parse_device_id(DEVICE.upper())
    assert isinstance(caught.value, DomainError)
    assert DEVICE.upper() not in str(caught.value)
    assert DEVICE.upper() not in repr(caught.value)


@pytest.mark.spec("realtime_events.AC-05")
def test_device_id_repr_and_str_never_show_the_value() -> None:
    device = parse_device_id(DEVICE)
    for text in (repr(device), str(device), f"{device}", f"{device!r}", repr([device])):
        assert DEVICE not in text
        assert text == "DeviceId(***)" or "DeviceId(***)" in text


@pytest.mark.spec("realtime_events.AC-05")
def test_hash_matches_the_fixed_test_vector() -> None:
    hasher: DeviceHasher = HmacDeviceHasher(SECRET)
    assert hasher.hash(parse_device_id(DEVICE)) == HASH_DEVICE


@pytest.mark.spec("realtime_events.AC-05")
def test_hash_uses_a_key_derived_from_the_secret_with_domain_separation() -> None:
    key = hmac.new(SECRET, b"avisabus:device-id:v1", hashlib.sha256).digest()
    expected = hmac.new(key, DEVICE.encode(), hashlib.sha256).hexdigest()
    assert HmacDeviceHasher(SECRET).hash(DeviceId(DEVICE)) == expected
    # Not the secret itself: a stop token or another use of the secret never gives this hash.
    direct = hmac.new(SECRET, DEVICE.encode(), hashlib.sha256).hexdigest()
    assert expected != direct


@pytest.mark.spec("realtime_events.AC-05")
def test_hash_is_64_lowercase_hex_characters_and_stable() -> None:
    first = HmacDeviceHasher(SECRET).hash(parse_device_id(DEVICE))
    second = HmacDeviceHasher(SECRET).hash(parse_device_id(DEVICE))
    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")
    assert DEVICE not in first


@pytest.mark.spec("realtime_events.AC-05")
def test_hash_depends_on_the_secret_and_on_the_device() -> None:
    device = parse_device_id(DEVICE)
    other_device = parse_device_id("00000000-0000-4000-8000-000000000000")
    hasher = HmacDeviceHasher(SECRET)
    assert hasher.hash(device) != HmacDeviceHasher(b"another-secret-0123456789abcdef!").hash(device)
    assert hasher.hash(device) != hasher.hash(other_device)


def test_device_channel_is_named_after_the_hash() -> None:
    assert device_channel(HASH_DEVICE) == f"device:{HASH_DEVICE}"


def test_event_message_puts_the_type_first_and_the_payload_after() -> None:
    event = Event(type="alert.registered", payload={"alert_id": "a1", "stop_id": "508"})
    assert event.message() == {"type": "alert.registered", "alert_id": "a1", "stop_id": "508"}
    assert list(event.message()) == ["type", "alert_id", "stop_id"]
