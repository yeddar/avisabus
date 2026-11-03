import hmac

import pytest

from avisabus.adapters.outbound.security import hmac_stop_token
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.domain.ports.stop_token import StopTokenSigner

SECRET = b"test-secret-0123456789abcdef0123"
# Computed once with the formula of design §3 (HMAC-SHA256, first 16 bytes, base64url, no "=").
TOKEN_508 = "83Rg_QTPgamZSDGo9T168g"  # noqa: S105 (public test vector)


@pytest.fixture
def signer() -> HmacStopTokenSigner:
    return HmacStopTokenSigner(SECRET)


def test_hmac_signer_implements_the_port(signer: HmacStopTokenSigner) -> None:
    port: StopTokenSigner = signer
    assert port.sign("508") == TOKEN_508


@pytest.mark.spec("stop_tokens_qr.AC-01")
def test_token_matches_the_fixed_test_vector(signer: HmacStopTokenSigner) -> None:
    assert signer.sign("508") == TOKEN_508


@pytest.mark.spec("stop_tokens_qr.AC-01")
def test_token_is_deterministic_22_chars_base64url_without_padding(
    signer: HmacStopTokenSigner,
) -> None:
    token = signer.sign("508")
    assert token == HmacStopTokenSigner(SECRET).sign("508")
    assert len(token) == 22
    assert "=" not in token
    assert set(token) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")


@pytest.mark.spec("stop_tokens_qr.AC-01")
def test_token_depends_on_stop_and_secret(signer: HmacStopTokenSigner) -> None:
    assert signer.sign("509") != TOKEN_508
    assert HmacStopTokenSigner(b"another-secret-0123456789abcdef!").sign("508") != TOKEN_508


@pytest.mark.spec("stop_tokens_qr.AC-02")
def test_correct_pair_is_accepted(signer: HmacStopTokenSigner) -> None:
    assert signer.verify("508", TOKEN_508) is True


@pytest.mark.spec("stop_tokens_qr.AC-02")
@pytest.mark.parametrize(
    ("stop_id", "token"),
    [
        pytest.param("509", TOKEN_508, id="token-of-another-stop"),
        pytest.param("508", TOKEN_508[:-1], id="truncated"),
        pytest.param("508", TOKEN_508[:11], id="half"),
        pytest.param("508", TOKEN_508 + "A", id="too-long"),
        pytest.param("508", "", id="empty"),
        pytest.param("508", TOKEN_508[:-1] + "=", id="padding-char"),
        pytest.param("508", TOKEN_508[:-1] + "+", id="standard-base64-char"),
        pytest.param("508", TOKEN_508[:-1] + "ñ", id="non-ascii"),
        pytest.param("508", TOKEN_508[:-1] + "\udcff", id="lone-surrogate"),
        pytest.param("508", TOKEN_508[:-1] + " ", id="space"),
        pytest.param("508", TOKEN_508.swapcase(), id="other-case"),
        pytest.param("\udcff", TOKEN_508, id="unencodable-stop-id"),
    ],
)
def test_invalid_tokens_are_rejected_without_raising(
    signer: HmacStopTokenSigner, stop_id: str, token: str
) -> None:
    assert signer.verify(stop_id, token) is False


@pytest.mark.spec("stop_tokens_qr.AC-03")
@pytest.mark.parametrize("token", [TOKEN_508, "A" * 22])
def test_tokens_are_compared_with_compare_digest(
    signer: HmacStopTokenSigner, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    calls: list[tuple[object, object]] = []
    real_compare_digest = hmac.compare_digest

    def spy(a: str, b: str) -> bool:
        calls.append((a, b))
        return real_compare_digest(a, b)

    monkeypatch.setattr(hmac_stop_token.hmac, "compare_digest", spy)
    expected = token == TOKEN_508
    assert signer.verify("508", token) is expected
    assert calls == [(TOKEN_508, token)]


@pytest.mark.spec("stop_tokens_qr.AC-03")
def test_verification_result_comes_from_compare_digest(
    signer: HmacStopTokenSigner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proves no other comparison (e.g. `==`) decides: the double's answer is returned."""
    monkeypatch.setattr(hmac_stop_token.hmac, "compare_digest", lambda _a, _b: False)
    assert signer.verify("508", TOKEN_508) is False
