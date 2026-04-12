"""
chart.py — Matplotlib visualisation for cutting plans.
"""
import io

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_dark(rgba, threshold: float = 0.35) -> bool:
    r, g, b, *_ = rgba
    return (0.299 * r + 0.587 * g + 0.114 * b) < threshold


def build_color_map(part_names: list[str]) -> dict:
    """Return a dict mapping each part name to an RGBA colour."""
    palette = plt.colormaps["tab20"].resampled(max(len(part_names), 2))
    return {name: palette(i) for i, name in enumerate(part_names)}


# ── Core drawing ──────────────────────────────────────────────────────────────
def draw_cutting_plan(
    results: list[dict],
    part_color: dict,
    title_prefix: str = "",
    dpi: int = 150,
) -> plt.Figure:
    """
    Draw a horizontal Gantt-style cutting plan.

    Parameters
    ----------
    results     : list of bar dicts (from solver.solve_profile_group)
    part_color  : name → RGBA mapping (from build_color_map)
    title_prefix: prepended to the chart title
    dpi         : figure resolution (screen rendering)
    """
    WASTE_COLOR = "#e0e0e0"
    n_bars      = len(results)
    bar_h, gap  = 0.6, 0.4
    row_h       = bar_h + gap

    fig, ax = plt.subplots(figsize=(14, max(4, n_bars * row_h + 1.5)), dpi=dpi)

    for row_idx, b in enumerate(results):
        y_bot    = (n_bars - 1 - row_idx) * row_h
        bar_len  = b["length_mm"]
        x_cursor = 0

        for piece_id, piece_name, piece_len in b["cuts"]:
            color = part_color[piece_name]
            ax.add_patch(mpatches.FancyBboxPatch(
                (x_cursor, y_bot), piece_len, bar_h,
                boxstyle="round,pad=0", linewidth=0.6,
                edgecolor="white", facecolor=color,
            ))
            short_id = piece_id.split("_")[-1]
            ax.text(
                x_cursor + piece_len / 2, y_bot + bar_h / 2,
                f"{piece_name}\n({short_id})  {piece_len} mm",
                ha="center", va="center", fontsize=7,
                color="white" if _is_dark(color) else "#333",
                fontweight="bold", clip_on=True,
            )
            x_cursor += piece_len

        if b["waste_mm"] > 0:
            ax.add_patch(mpatches.FancyBboxPatch(
                (x_cursor, y_bot), b["waste_mm"], bar_h,
                boxstyle="round,pad=0", linewidth=0.6,
                edgecolor="#aaa", facecolor=WASTE_COLOR,
            ))
            if b["waste_mm"] > 0.04 * bar_len:
                ax.text(
                    x_cursor + b["waste_mm"] / 2, y_bot + bar_h / 2,
                    f"waste\n{b['waste_mm']} mm",
                    ha="center", va="center", fontsize=7, color="#666",
                )

        prof_str = f"{b['profile'][0]}×{b['profile'][1]}"
        ax.text(
            -bar_len * 0.01, y_bot + bar_h / 2,
            f"Bar {b['bar_no']}\n{b['stock_name']}\n{prof_str}  €{b['cost']:.2f}",
            ha="right", va="center", fontsize=7.5, color="#222",
        )

    max_len     = max(b["length_mm"] for b in results)
    total_waste = sum(b["waste_mm"] for b in results)
    total_mat   = sum(b["length_mm"] for b in results)
    total_cost  = sum(b["cost"] for b in results)

    ax.set_xlim(-max_len * 0.18, max_len * 1.02)
    ax.set_ylim(-gap, n_bars * row_h)
    ax.set_xlabel("Length (mm)", fontsize=9)
    ax.set_title(
        f"{title_prefix}Cutting plan — {n_bars} bar(s)  |  "
        f"Total cost €{total_cost:.2f}  |  "
        f"Waste {100 * total_waste / total_mat:.1f}%",
        fontsize=10, pad=10,
    )
    ax.set_yticks([])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    return fig


# ── Export helpers ────────────────────────────────────────────────────────────
def fig_to_pdf(fig: plt.Figure) -> bytes:
    """Render figure to a vector PDF byte string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def fig_to_png(fig: plt.Figure, dpi: int = 200) -> bytes:
    """Render figure to a high-resolution PNG byte string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.getvalue()
