"""Prototype of design §3 (normalize_destination + resolve_direction), exploration only.

Literal transcription of specs/stop_arrivals_api/design.md §3 v1.3. Not production code.
"""
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

DEFAULT_ALIASES = {"pass": "passeig", "pg": "passeig", "est": "estacio", "av": "avinguda",
                   "avda": "avinguda", "pl": "placa", "hosp": "hospital", "univ": "universitats",
                   "c": "carrer"}


@dataclass(frozen=True)
class DirectionCandidate:
    direction_id: int
    headsign: str


def normalize_destination(text: str, aliases: Mapping[str, str]) -> frozenset[str]:
    folded = text.casefold()
    decomposed = unicodedata.normalize("NFKD", folded)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    spaced = re.sub(r"[^0-9a-z]+", " ", plain)  # "no alfanumérico = espacio"
    tokens = (aliases.get(tok, tok) for tok in spaced.split())
    return frozenset(t for t in tokens if t)


def _match(a: str, b: str) -> bool:
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 3 and long_.startswith(short)


def score(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard where prefix pairs (len >= 3) also count as matches.

    Interpretation: greedy 1-1 pairing of tokens (exact first, then prefix);
    |A∩B| = matched pairs, |A∪B| = |A| + |B| - matched.
    """
    if not a or not b:
        return 0.0
    left, right = set(a), set(b)
    matched = 0
    for tok in sorted(left & right):
        matched += 1
        left.discard(tok); right.discard(tok)
    for tok in sorted(left, key=len):
        for other in sorted(right, key=len):
            if _match(tok, other):
                matched += 1
                right.discard(other)
                break
    return matched / (len(a) + len(b) - matched)


def resolve_direction(destination: str, candidates: Sequence[DirectionCandidate],
                      aliases: Mapping[str, str], min_score: float = 0.34,
                      overrides: Mapping[tuple[str, str], int] | None = None,
                      line: str | None = None, explain: dict | None = None) -> int | None:
    if not candidates:
        return None
    dirs = {c.direction_id for c in candidates}
    if len(dirs) == 1:
        if explain is not None:
            explain["rule"] = "single_direction"
        return next(iter(dirs))
    if overrides and line is not None and (line, destination) in overrides:
        d = overrides[(line, destination)]
        if d in dirs:
            if explain is not None:
                explain["rule"] = "override"
            return d
    dest = normalize_destination(destination, aliases)
    best: dict[int, tuple[float, str]] = {}
    for c in candidates:
        s = score(dest, normalize_destination(c.headsign, aliases))
        if c.direction_id not in best or s > best[c.direction_id][0]:
            best[c.direction_id] = (s, c.headsign)
    ranked = sorted(best.items(), key=lambda kv: -kv[1][0])
    if explain is not None:
        explain["rule"] = "score"
        explain["best"] = {d: (round(s, 3), h) for d, (s, h) in best.items()}
    top_d, (top_s, _) = ranked[0]
    if top_s >= min_score and all(top_s > s for d, (s, _) in ranked[1:]):
        return top_d
    return None
