"""
data.py — Default datasets and CSV import/export helpers.
"""
import io

import pandas as pd

# ── Column order for the combined CSV format ──────────────────────────────────
COMBINED_COLS = ["section", "name", "profile", "length_mm", "cost_per_bar", "quantity"]

# ── Built-in example data ─────────────────────────────────────────────────────
DEFAULT_STOCKS = pd.DataFrame([
    {"name": "HEA200_6m",  "profile_l1": 200, "profile_l2": 200, "length_mm": 6000,  "cost_per_bar": 42.50},
    {"name": "HEA200_12m", "profile_l1": 200, "profile_l2": 200, "length_mm": 12000, "cost_per_bar": 78.00},
    {"name": "IPE300_6m",  "profile_l1": 150, "profile_l2": 300, "length_mm": 6000,  "cost_per_bar": 55.00},
    {"name": "IPE300_12m", "profile_l1": 150, "profile_l2": 300, "length_mm": 12000, "cost_per_bar": 102.00},
    {"name": "RHS100_6m",  "profile_l1": 100, "profile_l2": 100, "length_mm": 6000,  "cost_per_bar": 28.00},
])

DEFAULT_PARTS = pd.DataFrame([
    {"name": "beam_A",   "profile": "200×200", "length_mm": 2400, "quantity": 3},
    {"name": "beam_B",   "profile": "200×200", "length_mm": 1800, "quantity": 4},
    {"name": "column_C", "profile": "150×300", "length_mm": 3200, "quantity": 2},
    {"name": "column_D", "profile": "150×300", "length_mm": 900,  "quantity": 5},
    {"name": "brace_E",  "profile": "100×100", "length_mm": 1100, "quantity": 6},
    {"name": "brace_F",  "profile": "100×100", "length_mm": 750,  "quantity": 4},
])


# ── Profile string helpers ────────────────────────────────────────────────────
def split_profile(s: str) -> tuple[int, int]:
    """Parse '200×300' (or '200x300') into (200, 300)."""
    s = str(s).replace("x", "×").replace("X", "×")
    a, b = s.split("×")
    return int(a), int(b)


def profile_str(l1: int, l2: int) -> str:
    return f"{l1}×{l2}"


# ── Combined CSV build / parse ────────────────────────────────────────────────
def build_combined_csv(stocks_df: pd.DataFrame, parts_df: pd.DataFrame) -> str:
    """Merge stock + parts tables into a single CSV string."""
    s = stocks_df.copy()
    s["section"] = "stock"
    s["profile"] = s.apply(lambda r: profile_str(int(r.profile_l1), int(r.profile_l2)), axis=1)
    s["quantity"] = ""
    s_out = s[COMBINED_COLS]

    p = parts_df.copy()
    p["section"] = "part"
    p["cost_per_bar"] = ""
    p_out = p[COMBINED_COLS]

    return pd.concat([s_out, p_out], ignore_index=True).to_csv(index=False)


def parse_combined_csv(text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse a combined CSV string back into (stocks_df, parts_df)."""
    df = pd.read_csv(io.StringIO(text))
    df.columns = df.columns.str.strip()

    s_rows = df[df["section"] == "stock"].copy()
    p_rows = df[df["section"] == "part"].copy()

    profile_tuples = [split_profile(p) for p in s_rows["profile"]]
    stocks_out = pd.DataFrame({
        "name":         s_rows["name"].values,
        "profile_l1":   [t[0] for t in profile_tuples],
        "profile_l2":   [t[1] for t in profile_tuples],
        "length_mm":    s_rows["length_mm"].astype(int).values,
        "cost_per_bar": s_rows["cost_per_bar"].astype(float).values,
    })

    parts_out = pd.DataFrame({
        "name":      p_rows["name"].values,
        "profile":   p_rows["profile"].values,
        "length_mm": p_rows["length_mm"].astype(int).values,
        "quantity":  p_rows["quantity"].astype(int).values,
    })

    return stocks_out.reset_index(drop=True), parts_out.reset_index(drop=True)
