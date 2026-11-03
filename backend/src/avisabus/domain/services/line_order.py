"""Natural order of commercial lines (AC-13): numeric lines ascending, then alphanumeric ones."""

import re

_PARTS = re.compile(r"(\d+)")


def natural_line_key(short_name: str) -> tuple[int, tuple[tuple[int, int | str], ...]]:
    """`"7" < "70" < "100" < "C1" < "C2" < "C10" < "N1"`."""
    group = 0 if short_name.isdigit() else 1
    parts = tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in _PARTS.split(short_name) if part
    )
    return group, parts
