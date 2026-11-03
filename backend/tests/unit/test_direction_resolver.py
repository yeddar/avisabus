"""`normalize_destination`, `resolve_direction` and the headsign shown (design §3, v1.4).

Real cases: SAE destinations of E-01 (night, 2026-11-02) and E-03 (day, 2026-11-03) in
`progress/explore_destinations.md` (H-2, H-7; raw answers in
`progress/explore_destinations_samples/night_20261102/` and `day_20261103/`). Their candidates are
`headsigns_at_stop(stop, line)` and their departing directions the directions with some trip whose
minimum `stop_sequence` is at the stop, both over the full feed `23-10-2026` imported with
`avisabus gtfs import` (direction ids as derived by `gtfs_import`).
"""

import pytest

from avisabus.domain.services.direction_resolver import (
    DEFAULT_ALIASES,
    DirectionCandidate,
    destination_similarity,
    normalize_destination,
    resolve_destination,
    resolve_direction,
)

pytestmark = pytest.mark.spec("stop_arrivals_api.AC-06")

C = DirectionCandidate

# --- Real multi-direction cases (stop, line, SAE text, candidates, departing, expected). ---

AV_CID_2271 = (C(0, "Passeig Marítim - Hospital Malva-rosa"), C(1, "Avinguda del Cid"))
XATIVA_SANT_ISIDRE_2277 = (C(0, "Xàtiva - Institut Lluís Vives"), C(1, "Sant Isidre"))
LINE_28_2277 = (C(0, "Xàtiva - Institut Lluís Vives"), C(1, "Ciutat de l'Artista Faller"))
LINE_9_2312 = (C(0, "Sant Pau - Estació del Nord"), C(1, "Forn d'Alcedo"))
LINE_4_2403 = (C(0, "Plaça de l'Ajuntament - Ateneu"), C(1, "Natzaret"))
LINE_26_2014 = (C(0, "Poeta Querol - Teatre Principal"), C(1, "Moncada - Alfara"))
LINE_16_2014 = (C(0, "Poeta Querol - Teatre Principal"), C(1, "Vinalesa - Plaça d'Ausiàs March"))
LINE_99_TERMINALS = (C(0, "Mendizábal - Doctor Álvaro López"), C(1, "Palau de Congressos"))
C3_LOOP_1074 = (C(0, "Conselleria d'Educació"), C(1, "Eduard Boscà - Balears"))
C3_LOOP_1075 = (
    C(0, "Avinguda Campanar - Centre de Salut"),
    C(1, "Cardenal Benlloch (imparell) - Port"),
)
C2_LOOP_651 = (C(0, "Plaça d'Espanya - Ermita"), C(1, "Blasco Ibáñez - Facultat de Geografia"))
C2_LOOP_996 = (C(0, "Estació d'autobusos"), C(1, "Estadi de Mestalla (front)"))
C1_TERMINALS = (C(0, "Xàtiva - Institut Lluís Vives"), C(1, "Blanqueria - Pare d'Òrfens"))

# Resolved by text (rule 3), whatever the departing directions are.
TEXT_CASES = [
    ("2271", "93", "Av. Cid", AV_CID_2271, 1),
    ("2277", "72", "Sant Isidre", XATIVA_SANT_ISIDRE_2277, 1),
    ("2277", "28", "C.Art.Faller", LINE_28_2277, 1),
    ("2312", "9", "Est.del Nord", LINE_9_2312, 0),
    ("2312", "9", "Forn d'Alcedo", LINE_9_2312, 1),
    ("2403", "4", "Natzaret", LINE_4_2403, 1),
    ("2014", "26", "Moncada", LINE_26_2014, 1),
    ("2014", "16", "Vinalesa", LINE_16_2014, 1),
    ("1751", "99", "P. Congressos", LINE_99_TERMINALS, 1),
    ("1265", "C3", "Ed. Bosca", C3_LOOP_1074, 1),
    ("1266", "C3", "C. Benlloch", C3_LOOP_1075, 1),
    ("229", "C3", "Campanar", C3_LOOP_1075, 0),
    ("166", "C2", "Pl. Espanya", C2_LOOP_651, 0),
    ("691", "C2", "Blasco Ibáñez", C2_LOOP_651, 1),
    ("1057", "C2", "Est. Autobusos", C2_LOOP_996, 0),
]

# Not resolved by text: rule 4, the direction whose trips start at the stop (AC-19).
DEPARTING_CASES = [
    ("1959", "C1", "Cntr.Històric", C1_TERMINALS, 0),
    ("2277", "C1", "Cntr.Històric", C1_TERMINALS, 1),
    ("2230", "99", "La Malva-rosa", LINE_99_TERMINALS, 0),
    ("231", "C3", "Campanar", C3_LOOP_1074, 0),
    ("346", "C2", "Av. Aragó", C2_LOOP_996, 1),
]

# Every real multi-direction case with its real departing directions.
REAL_CASES = [
    *(
        (stop, line, text, cands, frozenset(deps), expected)
        for (stop, line, text, cands, expected), deps in zip(
            TEXT_CASES,
            [{1}, {1}, {1}, {1}, {1}, {1}, {1}, {1}, {1}, {1}, {1}, {0}, {0}, {1}, {0}],
            strict=True,
        )
    ),
    *(
        (stop, line, text, cands, frozenset({expected}), expected)
        for stop, line, text, cands, expected in DEPARTING_CASES
    ),
]

# Real single-direction cases (rule 1): the SAE text often has nothing to do with the headsign.
SINGLE_DIRECTION_CASES = [
    ("508", "93", "Pass. Marítim", (C(0, "Passeig Marítim - Hospital Malva-rosa"),), 0),
    ("2070", "99", "La Malva-rosa", (C(0, "Mendizábal - Doctor Álvaro López"),), 0),
    ("1679", "C3", "Campanar", (C(0, "Conselleria d'Educació"),), 0),
    ("2223", "C1", "Cntr.Històric", (C(0, "Xàtiva - Institut Lluís Vives"),), 0),
    ("795", "C1", "Cntr.Històric", (C(1, "Blanqueria - Pare d'Òrfens"),), 1),
    ("701", "C2", "Av. Aragó", (C(1, "Estadi de Mestalla (front)"),), 1),
    ("2312", "62", "Benimàmet", (C(1, "Terramelar"),), 1),
]


def _resolve(
    text: str,
    candidates: tuple[DirectionCandidate, ...],
    departing: frozenset[int] = frozenset(),
    override: str | None = None,
) -> int | None:
    return resolve_direction(
        text,
        candidates,
        DEFAULT_ALIASES,
        override_headsign=override,
        departing_directions=departing,
    )


# --- normalize_destination ---


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("Pass. Marítim", {"passeig", "maritim"}),
        ("Est.del Nord", {"estacio", "nord"}),
        ("Pta.de la Mar", {"porta", "mar"}),
        ("Fta. S.Lluis", {"fonteta", "sant", "lluis"}),
        ("Ed. Bosca", {"eduard", "bosca"}),
        ("Est.J.Sorolla", {"estacio", "joaquin", "sorolla"}),
        ("Vinalesa - Plaça d'Ausiàs March", {"vinalesa", "placa", "ausias", "march"}),
        ("Cardenal Benlloch (imparell) - Port", {"cardenal", "benlloch", "imparell", "port"}),
        ("Sant Marcel.li", {"sant", "marcel", "li"}),
        ("Hosp. La Fe", {"hospital", "fe"}),
        ("Av. Aragó", {"avinguda", "arago"}),
        ("Pg. Marítim", {"passeig", "maritim"}),
        ("  ", set()),
    ],
)
def test_normalize_destination_folds_case_accents_punctuation_and_expands_aliases(
    text: str, tokens: set[str]
) -> None:
    assert normalize_destination(text, DEFAULT_ALIASES) == frozenset(tokens)


def test_c_is_not_an_alias_of_carrer() -> None:
    # v1.4: "C. Benlloch" is Cardenal Benlloch and "C.Art.Faller" is Ciutat de l'Artista Faller.
    assert "c" not in DEFAULT_ALIASES
    assert normalize_destination("C. Benlloch", DEFAULT_ALIASES) == {"c", "benlloch"}


def test_stop_words_map_to_empty_and_are_dropped() -> None:
    for word in ("de", "d", "del", "dels", "la", "l", "el", "els", "les", "i", "y"):
        assert DEFAULT_ALIASES[word] == ""
    assert normalize_destination("De la I del Y", DEFAULT_ALIASES) == frozenset()


def test_normalize_destination_uses_the_given_aliases_only() -> None:
    assert normalize_destination("Pass. Marítim", {}) == {"pass", "maritim"}
    assert normalize_destination("Foo bar", {"foo": "baz", "bar": ""}) == {"baz"}


# --- similarity: Jaccard with 1-to-1 prefix pairs (len >= 3) ---


def test_similarity_is_jaccard_over_normalized_tokens() -> None:
    assert destination_similarity({"sant", "isidre"}, {"sant", "isidre"}) == 1.0
    assert destination_similarity({"vinalesa"}, {"vinalesa", "placa", "ausias", "march"}) == 0.25
    assert destination_similarity(frozenset(), {"x"}) == 0.0
    assert destination_similarity({"a"}, {"b"}) == 0.0


def test_similarity_counts_prefixes_of_at_least_three_letters() -> None:
    # "arag" is a prefix of "arago"; "ma" is too short to count as one.
    assert destination_similarity({"arag"}, {"arago"}) == 1.0
    assert destination_similarity({"ma"}, {"maritim"}) == 0.0
    assert destination_similarity({"mar"}, {"maritim"}) == 1.0


def test_similarity_pairs_prefix_tokens_one_to_one() -> None:
    # "mar" is a prefix of both: it counts once, so |A∩B| = 1 and |A∪B| = 1 + 2 - 1.
    assert destination_similarity({"mar"}, {"marina", "maritim"}) == 0.5
    # Each token of the other side is also used once.
    assert destination_similarity({"mar", "mari"}, {"marina"}) == 0.5


def test_similarity_prefers_exact_pairs_before_prefix_pairs() -> None:
    # Pairing "mar"-"mar" exactly leaves "marina"-"mari" as a prefix pair: 2 matches.
    assert destination_similarity({"mar", "mari"}, {"mar", "marina"}) == 1.0


# --- resolve_direction: order of resolution ---


@pytest.mark.spec("stop_arrivals_api.AC-07")
def test_no_candidates_is_unresolved() -> None:
    assert _resolve("Alboraia", ()) is None


@pytest.mark.spec("stop_arrivals_api.AC-05")
@pytest.mark.parametrize(("stop", "line", "text", "candidates", "expected"), SINGLE_DIRECTION_CASES)
def test_single_direction_is_assigned_without_comparing_texts(
    stop: str, line: str, text: str, candidates: tuple[DirectionCandidate, ...], expected: int
) -> None:
    assert _resolve(text, candidates) == expected


@pytest.mark.spec("stop_arrivals_api.AC-05")
def test_single_direction_with_several_headsigns_wins_over_override_and_departing() -> None:
    candidates = (C(1, "Tres Creus"), C(1, "Hospital General"))
    assert _resolve("Xyz", candidates, departing=frozenset({0}), override="Nowhere") == 1


@pytest.mark.parametrize(("stop", "line", "text", "candidates", "expected"), TEXT_CASES)
def test_real_destinations_resolved_by_text(
    stop: str, line: str, text: str, candidates: tuple[DirectionCandidate, ...], expected: int
) -> None:
    assert _resolve(text, candidates) == expected


@pytest.mark.spec("stop_arrivals_api.AC-19")
@pytest.mark.parametrize(
    ("stop", "line", "text", "candidates", "departing", "expected"), REAL_CASES
)
def test_real_destinations_at_terminals_with_their_departing_directions(
    stop: str,
    line: str,
    text: str,
    candidates: tuple[DirectionCandidate, ...],
    departing: frozenset[int],
    expected: int,
) -> None:
    assert _resolve(text, candidates, departing) == expected


@pytest.mark.spec("stop_arrivals_api.AC-07")
@pytest.mark.parametrize(("stop", "line", "text", "candidates", "expected"), DEPARTING_CASES)
def test_generic_destinations_at_terminals_are_unresolved_without_departing_rule(
    stop: str, line: str, text: str, candidates: tuple[DirectionCandidate, ...], expected: int
) -> None:
    assert _resolve(text, candidates) is None


@pytest.mark.spec("stop_arrivals_api.AC-19")
@pytest.mark.parametrize(("stop", "line", "text", "candidates", "expected"), DEPARTING_CASES)
def test_departing_direction_resolves_generic_destinations_at_terminals(
    stop: str, line: str, text: str, candidates: tuple[DirectionCandidate, ...], expected: int
) -> None:
    assert _resolve(text, candidates, frozenset({expected})) == expected


@pytest.mark.spec("stop_arrivals_api.AC-19")
def test_text_wins_over_departing_direction() -> None:
    # 2312: the 9 that arrives from "Est.del Nord" is direction 0 although direction 1 departs.
    assert _resolve("Est.del Nord", LINE_9_2312, frozenset({1})) == 0


@pytest.mark.spec("stop_arrivals_api.AC-19")
@pytest.mark.spec("stop_arrivals_api.AC-07")
def test_departing_rule_needs_exactly_one_departing_candidate_direction() -> None:
    assert _resolve("Cntr.Històric", C1_TERMINALS, frozenset({0, 1})) is None
    assert _resolve("Cntr.Històric", C1_TERMINALS, frozenset({2})) is None
    assert _resolve("Cntr.Històric", C1_TERMINALS, frozenset({0, 2})) is None


def test_best_score_must_reach_the_threshold() -> None:
    candidates = (C(0, "Alfa Beta Gamma Delta Epsilon"), C(1, "Zeta"))
    # 1 / 5 = 0.2 reaches the default threshold (>=).
    assert _resolve("Alfa", candidates) == 0
    six = (C(0, "Alfa Beta Gamma Delta Epsilon Eta"), C(1, "Zeta"))
    assert _resolve("Alfa", six) is None
    assert resolve_direction("Alfa", candidates, DEFAULT_ALIASES, min_score=0.25) is None


@pytest.mark.spec("stop_arrivals_api.AC-07")
def test_best_score_must_be_strictly_greater_than_every_other_direction() -> None:
    candidates = (C(0, "Plaça Nova"), C(1, "Plaça Vella"))
    assert _resolve("Plaça", candidates) is None
    assert _resolve("Plaça", candidates, frozenset({1})) == 1


def test_best_headsign_of_each_direction_counts() -> None:
    # Direction 0 has a variant that matches better than direction 1's only headsign.
    candidates = (C(0, "Port"), C(0, "Sant Isidre - Port"), C(1, "Sant Isidre - Hospital"))
    assert _resolve("Sant Isidre Port", candidates) == 0


def test_tokens_shorter_than_three_letters_never_match_by_prefix() -> None:
    # Without the alias `ed`, "Ed. Bosca" would only match "bosca" with "bosca".
    assert normalize_destination("Ed. Bosca", {}) == {"ed", "bosca"}
    assert resolve_direction("Ed. Bosca", C3_LOOP_1074, {}) == 1
    assert resolve_direction("Ed.", C3_LOOP_1074, {}) is None


# --- Overrides by headsign (AC-20) ---


@pytest.mark.spec("stop_arrivals_api.AC-20")
def test_override_headsign_is_translated_to_its_direction_at_the_stop() -> None:
    # Text alone says 1 ("Av. Cid"); the override names the headsign of direction 0.
    assert _resolve("Av. Cid", AV_CID_2271, override="Passeig Marítim - Hospital Malva-rosa") == 0
    # Same override text, other direction numbering at another stop: follows the headsign.
    swapped = (C(1, "Passeig Marítim - Hospital Malva-rosa"), C(0, "Avinguda del Cid"))
    assert _resolve("Av. Cid", swapped, override="Passeig Marítim - Hospital Malva-rosa") == 1


@pytest.mark.spec("stop_arrivals_api.AC-20")
def test_override_wins_over_departing_direction() -> None:
    assert (
        _resolve("Cntr.Històric", C1_TERMINALS, frozenset({0}), "Blanqueria - Pare d'Òrfens") == 1
    )


@pytest.mark.spec("stop_arrivals_api.AC-20")
def test_override_whose_headsign_is_not_at_the_stop_is_ignored() -> None:
    assert _resolve("Av. Cid", AV_CID_2271, override="Estació del Nord") == 1
    assert _resolve("Cntr.Històric", C1_TERMINALS, override="Estació del Nord") is None
    assert _resolve("Cntr.Històric", C1_TERMINALS, frozenset({1}), "Estació del Nord") == 1


# --- Headsign shown as destination (AC-09) ---


@pytest.mark.spec("stop_arrivals_api.AC-09")
def test_destination_of_a_single_direction_is_its_most_frequent_headsign() -> None:
    # Candidates come most frequent first within each direction (headsigns_at_stop order).
    candidates = (C(1, "Tres Creus (imparell) - Hospital General"), C(1, "Tres Creus"))
    resolution = resolve_destination("Tres Creus", candidates, DEFAULT_ALIASES)
    assert resolution is not None
    assert resolution.direction_id == 1
    assert resolution.headsign == "Tres Creus (imparell) - Hospital General"


@pytest.mark.spec("stop_arrivals_api.AC-09")
def test_destination_resolved_by_text_is_the_winning_headsign() -> None:
    candidates = (C(0, "Port"), C(0, "Sant Isidre - Port"), C(1, "Sant Isidre - Hospital"))
    resolution = resolve_destination("Sant Isidre Port", candidates, DEFAULT_ALIASES)
    assert resolution is not None
    assert (resolution.direction_id, resolution.headsign) == (0, "Sant Isidre - Port")


@pytest.mark.spec("stop_arrivals_api.AC-09")
def test_destination_resolved_by_override_is_the_override_headsign() -> None:
    candidates = (*AV_CID_2271, C(0, "Hospital Malva-rosa"))
    resolution = resolve_destination(
        "Av. Cid", candidates, DEFAULT_ALIASES, override_headsign="Hospital Malva-rosa"
    )
    assert resolution is not None
    assert (resolution.direction_id, resolution.headsign) == (0, "Hospital Malva-rosa")


@pytest.mark.spec("stop_arrivals_api.AC-09")
@pytest.mark.spec("stop_arrivals_api.AC-19")
def test_destination_resolved_by_departing_direction_is_its_most_similar_headsign() -> None:
    resolution = resolve_destination(
        "Cntr.Històric", C1_TERMINALS, DEFAULT_ALIASES, departing_directions=frozenset({1})
    )
    assert resolution is not None
    assert (resolution.direction_id, resolution.headsign) == (1, "Blanqueria - Pare d'Òrfens")
    # Ties keep the most frequent headsign (first candidate of the direction).
    candidates = (C(0, "Alfa"), C(1, "Beta Port"), C(1, "Gamma"), C(1, "Port Nou"))
    resolution = resolve_destination(
        "Port", candidates, DEFAULT_ALIASES, min_score=0.9, departing_directions=frozenset({1})
    )
    assert resolution is not None
    assert (resolution.direction_id, resolution.headsign) == (1, "Beta Port")


@pytest.mark.spec("stop_arrivals_api.AC-07")
def test_unresolved_destination_has_no_resolution() -> None:
    assert resolve_destination("Cntr.Històric", C1_TERMINALS, DEFAULT_ALIASES) is None


# --- Overrides proposed by the exploration (E-01/E-03), checked with the v1.4 algorithm ---

# Each proposal of `proposal_full_v2.json`, translated from direction number to the headsign of
# that direction at the stops where it was observed, with every real observation of its
# "line|SAE destination" (candidates and departing directions of that stop). C3|Campanar covers
# two half loops of direction 0 with different headsigns, so a single headsign could not even
# express it: both variants are listed.
PROPOSED_OVERRIDES = [
    ("99|La Malva-rosa", "Mendizábal - Doctor Álvaro López", LINE_99_TERMINALS, {0}, 0),
    ("99|P. Congressos", "Palau de Congressos", LINE_99_TERMINALS, {1}, 1),
    ("C3|Campanar", "Avinguda Campanar - Centre de Salut", C3_LOOP_1075, {0}, 0),
    ("C3|Campanar", "Conselleria d'Educació", C3_LOOP_1074, {0}, 0),
    ("C3|Ed. Bosca", "Eduard Boscà - Balears", C3_LOOP_1074, {1}, 1),
    ("C3|C. Benlloch", "Cardenal Benlloch (imparell) - Port", C3_LOOP_1075, {1}, 1),
    ("16|Vinalesa", "Vinalesa - Plaça d'Ausiàs March", LINE_16_2014, {1}, 1),
    ("26|Moncada", "Moncada - Alfara", LINE_26_2014, {1}, 1),
    ("C2|Av. Aragó", "Estadi de Mestalla (front)", C2_LOOP_996, {1}, 1),
]


@pytest.mark.spec("stop_arrivals_api.AC-20")
@pytest.mark.spec("stop_arrivals_api.AC-19")
@pytest.mark.parametrize(
    ("key", "headsign", "candidates", "departing", "expected"), PROPOSED_OVERRIDES
)
def test_proposed_overrides_are_not_needed_with_the_v14_algorithm(
    key: str,
    headsign: str,
    candidates: tuple[DirectionCandidate, ...],
    departing: set[int],
    expected: int,
) -> None:
    """None of them is kept in `config/direction_overrides.json`: without it, the real case
    already resolves to the direction of the override (aliases, threshold 0.2 or departing
    direction), so no test with a real sample fails without it."""
    destination = key.split("|", 1)[1]
    with_override = _resolve(destination, candidates, frozenset(departing), headsign)
    without_override = _resolve(destination, candidates, frozenset(departing))
    assert with_override == expected
    assert without_override == expected
