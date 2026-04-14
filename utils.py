"""
utils.py — Shared helpers for the stock cutting pipeline.
"""


def sort_and_renumber(results: list[dict]) -> list[dict]:
    """
    Sort bars alphabetically by their comma-joined part names, break ties by
    original bar_no, then reassign bar_no 1..N in that order.
    """
    def _sort_key(b):
        parts_str = ",".join(name for _, name, _ in b["cuts"])
        return (parts_str, b["bar_no"])

    return [{**b, "bar_no": i + 1} for i, b in enumerate(sorted(results, key=_sort_key))]
