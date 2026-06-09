"""
utils.py — Shared helpers for the stock cutting pipeline.
"""

# ── Display units ─────────────────────────────────────────────────────────────
# All internal values are stored in millimetres. These factors convert mm into
# the chosen display unit (factor = how many mm per 1 display unit).
DISPLAY_UNITS = {
    "mm": 1.0,
    "cm": 10.0,
    "m":  1000.0,
}


def to_display(mm: float, unit: str = "mm") -> float:
    """Convert a millimetre value into the chosen display unit (numeric only)."""
    return mm / DISPLAY_UNITS[unit]


def format_length(mm: float, unit: str = "mm", decimals: int = 0) -> str:
    """
    Format a millimetre value for display in ``unit`` with ``decimals`` places.

    Examples
    --------
    >>> format_length(2000, "cm", 1)
    '200.0 cm'
    >>> format_length(6000, "mm", 0)
    '6,000 mm'
    """
    return f"{to_display(mm, unit):,.{decimals}f} {unit}"


def sort_and_renumber(results: list[dict]) -> list[dict]:
    """
    Sort bars alphabetically by their comma-joined part names, break ties by
    original bar_no, then reassign bar_no 1..N in that order.
    """
    def _sort_key(b):
        parts_str = ",".join(name for _, name, _ in b["cuts"])
        return (parts_str, b["bar_no"])

    return [{**b, "bar_no": i + 1} for i, b in enumerate(sorted(results, key=_sort_key))]
