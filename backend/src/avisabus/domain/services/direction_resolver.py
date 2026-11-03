"""GTFS direction of an SAE arrival from its destination text (stop_arrivals_api design §3, R-02).

Order of resolution (v1.4):

1. no candidates → unresolved; every candidate in the same direction → that direction (AC-05);
2. override headsign (already looked up by "line|SAE destination") → direction of the candidate
   with that headsign; ignored if no candidate has it (AC-20);
3. text: best Jaccard similarity of each direction, if it reaches `min_score` and is strictly
   greater than the best of every other direction (AC-06);
4. departing direction: the only direction whose trips start at the stop, if it is a candidate
   (AC-19);
5. unresolved (AC-07).
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass

DEFAULT_ALIASES: Mapping[str, str] = {
    # Abbreviations.
    "pass": "passeig",
    "pg": "passeig",
    "est": "estacio",
    "av": "avinguda",
    "avda": "avinguda",
    "pl": "placa",
    "hosp": "hospital",
    "univ": "universitats",
    "pta": "porta",
    "fta": "fonteta",
    "s": "sant",
    "ed": "eduard",
    "j": "joaquin",
    # Stop words → "" (dropped).
    "de": "",
    "d": "",
    "del": "",
    "dels": "",
    "la": "",
    "l": "",
    "el": "",
    "els": "",
    "les": "",
    "i": "",
    "y": "",
}
"""v1.4: without `"c": "carrer"` ("C. Benlloch" is Cardenal, "C.Art.Faller" is Ciutat)."""

DEFAULT_MIN_SCORE = 0.2
MIN_PREFIX_LENGTH = 3

_NOT_ALPHANUMERIC = re.compile(r"[^0-9a-z]+")


@dataclass(frozen=True, slots=True)
class DirectionCandidate:
    """One `(direction_id, headsign)` of `headsigns_at_stop(stop, line)`.

    A direction may appear several times (route variants). Within a direction, candidates are
    expected most frequent first, as `headsigns_at_stop` returns them.
    """

    direction_id: int
    headsign: str


@dataclass(frozen=True, slots=True)
class DestinationResolution:
    direction_id: int
    headsign: str
    """GTFS headsign shown as destination (AC-09)."""


def normalize_destination(text: str, aliases: Mapping[str, str]) -> frozenset[str]:
    """casefold → NFKD without diacritics → non-alphanumeric = space → tokens → aliases →
    without empty tokens."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    tokens = (aliases.get(token, token) for token in _NOT_ALPHANUMERIC.sub(" ", plain).split())
    return frozenset(token for token in tokens if token)


def destination_similarity(a: Set[str], b: Set[str]) -> float:
    """`|A∩B| / |A∪B|`, where a pair of tokens also matches when one is a prefix of the other
    and the shorter has at least 3 letters.

    Pairs are 1-to-1 (each token is used once): exact pairs first, then prefix pairs greedily,
    shorter tokens first (ties in alphabetical order), each with the first free token of the
    other side in that same order. `|A∪B| = |A| + |B| − pairs`.
    """
    if not a or not b:
        return 0.0
    exact = a & b
    left = sorted(a - exact, key=_token_order)
    right = sorted(b - exact, key=_token_order)
    pairs = len(exact)
    for token in left:
        for index, other in enumerate(right):
            if _prefix_match(token, other):
                pairs += 1
                del right[index]
                break
    return pairs / (len(a) + len(b) - pairs)


def resolve_direction(
    destination: str,
    candidates: Sequence[DirectionCandidate],
    aliases: Mapping[str, str],
    min_score: float = DEFAULT_MIN_SCORE,
    override_headsign: str | None = None,
    departing_directions: frozenset[int] = frozenset(),
) -> int | None:
    """Direction of the arrival, or `None` if it cannot be resolved (module docstring)."""
    resolution = resolve_destination(
        destination, candidates, aliases, min_score, override_headsign, departing_directions
    )
    return None if resolution is None else resolution.direction_id


def resolve_destination(
    destination: str,
    candidates: Sequence[DirectionCandidate],
    aliases: Mapping[str, str],
    min_score: float = DEFAULT_MIN_SCORE,
    override_headsign: str | None = None,
    departing_directions: frozenset[int] = frozenset(),
) -> DestinationResolution | None:
    """`resolve_direction` plus the headsign shown as destination (AC-09):

    - single direction: its most frequent headsign at the stop;
    - override: the override headsign;
    - text or departing direction: the headsign of the direction most similar to the SAE text
      (ties: the most frequent).
    """
    if not candidates:
        return None
    directions = {candidate.direction_id for candidate in candidates}
    if len(directions) == 1:
        return DestinationResolution(candidates[0].direction_id, candidates[0].headsign)
    if override_headsign is not None:
        for candidate in candidates:
            if candidate.headsign == override_headsign:
                return DestinationResolution(candidate.direction_id, candidate.headsign)
    wanted = normalize_destination(destination, aliases)
    best: dict[int, tuple[float, str]] = {}
    for candidate in candidates:
        score = destination_similarity(wanted, normalize_destination(candidate.headsign, aliases))
        current = best.get(candidate.direction_id)
        if current is None or score > current[0]:
            best[candidate.direction_id] = (score, candidate.headsign)
    winner, (top, headsign) = max(best.items(), key=lambda item: item[1][0])
    if top >= min_score and all(top > score for d, (score, _) in best.items() if d != winner):
        return DestinationResolution(winner, headsign)
    if len(departing_directions) == 1:
        (departing,) = departing_directions
        if departing in best:
            return DestinationResolution(departing, best[departing][1])
    return None


def _token_order(token: str) -> tuple[int, str]:
    return len(token), token


def _prefix_match(a: str, b: str) -> bool:
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= MIN_PREFIX_LENGTH and longer.startswith(shorter)
