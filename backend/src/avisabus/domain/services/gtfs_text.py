"""Text normalisation for GTFS names (RF-32: names are shown exactly as in the feed)."""


def clean_name(value: str) -> str:
    """Remove leading and trailing whitespace only; inner spacing and characters are kept."""
    return value.strip()
