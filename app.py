import io
import math

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from ortools.sat.python import cp_model

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="1D Stock Cutting Optimiser",
    page_icon="✂️",
    layout="wide",
)

st.title("✂️ 1D Stock Cutting Optimiser")
st.caption(
    "Minimise material cost by cutting required parts from available stock bars. "
    "Profile matching is exact (`l1 × l2`). Powered by Google OR-Tools CP-SAT."
)

# ── Default data ──────────────────────────────────────────────────────────────
DEFAULT_STOCKS = pd.DataFrame([
    {"name": "HEA200_6m",  "profile_l1": 200, "profile_l2": 200, "length_mm": 6000,  "cost_per_bar": 42.50},
    {"name": "HEA200_12m", "profile_l1": 200, "profile_l2": 200, "length_mm": 12000, "cost_per_bar": 78.00},
    {"name": "IPE300_6m",  "profile_l1": 150, "profile_l2": 300, "length_mm": 6000,  "cost_per_bar": 55.00},
    {"name": "IPE300_12m", "profile_l1": 150, "profile_l2": 300, "length_mm": 12000, "cost_per_bar": 102.00},
    {"name": "RHS100_6m",  "profile_l1": 100, "profile_l2": 100, "length_mm": 6000,  "cost_per_bar": 28.00},
])

DEFAULT_PARTS = pd.DataFrame([
    {"name": "beam_A",   "profile": "200\u00d7200", "length_mm": 2400, "quantity": 3},
    {"name": "beam_B",   "profile": "200\u00d7200", "length_mm": 1800, "quantity": 4},
    {"name": "column_C", "profile": "150\u00d7300", "length_mm": 3200, "quantity": 2},
    {"name": "column_D", "profile": "150\u00d7300", "length_mm": 900,  "quantity": 5},
    {"name": "brace_E",  "profile": "100\u00d7100", "length_mm": 1100, "quantity": 6},
    {"name": "brace_F",  "profile": "100\u00d7100", "length_mm": 750,  "quantity": 4},
])

# ── Session state ─────────────────────────────────────────────────────────────
if "stocks_df" not in st.session_state:
    st.session_state.stocks_df = DEFAULT_STOCKS.copy()
if "parts_df" not in st.session_state:
    st.session_state.parts_df = DEFAULT_PARTS.copy()
if "editor_ver" not in st.session_state:
    st.session_state.editor_ver = 0  # bump this to reset data_editor internal state


# ── CSV helpers ───────────────────────────────────────────────────────────────
COMBINED_COLS = ["section", "name", "profile", "length_mm", "cost_per_bar", "quantity"]

def build_combined_csv(stocks_df, parts_df):
    """Merge stocks + parts into a single downloadable CSV."""
    s = stocks_df.copy()
    s["section"] = "stock"
    s["profile"] = s.apply(
        lambda r: f"{int(r.profile_l1)}\u00d7{int(r.profile_l2)}", axis=1
    )
    s["quantity"] = ""
    s_out = s[COMBINED_COLS]

    p = parts_df.copy()
    p["section"] = "part"
    p["cost_per_bar"] = ""
    p_out = p[COMBINED_COLS]

    return pd.concat([s_out, p_out], ignore_index=True).to_csv(index=False)


def _split_profile(s):
    s = str(s).replace("x", "\u00d7").replace("X", "\u00d7")
    a, b = s.split("\u00d7")
    return int(a), int(b)


def parse_combined_csv(text):
    """Parse combined CSV back into (stocks_df, parts_df)."""
    df = pd.read_csv(io.StringIO(text))
    df.columns = df.columns.str.strip()

    s_rows = df[df["section"] == "stock"].copy()
    p_rows = df[df["section"] == "part"].copy()

    profile_tuples = [_split_profile(p) for p in s_rows["profile"]]
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


# ── Input tables ──────────────────────────────────────────────────────────────
col_stock, col_parts = st.columns(2)
ver = st.session_state.editor_ver

with col_stock:
    st.subheader("📦 Available Stock")
    st.caption("Each row = one purchasable bar type. Add / remove rows as needed.")
    stocks_input = st.data_editor(
        st.session_state.stocks_df,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "name":         st.column_config.TextColumn("Name", required=True),
            "profile_l1":   st.column_config.NumberColumn("Profile l1 (mm)", min_value=1, step=1, format="%d"),
            "profile_l2":   st.column_config.NumberColumn("Profile l2 (mm)", min_value=1, step=1, format="%d"),
            "length_mm":    st.column_config.NumberColumn("Length (mm)", min_value=1, step=1, format="%d"),
            "cost_per_bar": st.column_config.NumberColumn("Cost / bar (€)", min_value=0.0, step=0.5, format="%.2f"),
        },
        key=f"stocks_editor_{ver}",
    )

# Build profile option list from whatever is currently in the stocks editor
available_profiles = sorted({
    f"{int(r.profile_l1)}\u00d7{int(r.profile_l2)}"
    for _, r in stocks_input.dropna(subset=["profile_l1", "profile_l2"]).iterrows()
    if pd.notna(r.profile_l1) and pd.notna(r.profile_l2)
}) or ["—"]

with col_parts:
    st.subheader("🔩 Required Parts")
    st.caption("Profile is a dropdown of profiles currently defined in the stock table.")
    parts_input = st.data_editor(
        st.session_state.parts_df,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "name":      st.column_config.TextColumn("Name", required=True),
            "profile":   st.column_config.SelectboxColumn(
                             "Profile", options=available_profiles, required=True
                         ),
            "length_mm": st.column_config.NumberColumn("Length (mm)", min_value=1, step=1, format="%d"),
            "quantity":  st.column_config.NumberColumn("Qty", min_value=1, step=1, format="%d"),
        },
        key=f"parts_editor_{ver}",
    )

# ── Load / Save ───────────────────────────────────────────────────────────────
with st.expander("📂 Load / Save Inputs"):
    dl_col, up_col = st.columns(2)

    with dl_col:
        st.markdown("**⬇ Download current inputs as CSV**")
        csv_bytes = build_combined_csv(stocks_input, parts_input).encode()
        st.download_button(
            "Download inputs.csv",
            data=csv_bytes,
            file_name="cutting_inputs.csv",
            mime="text/csv",
        )

    with up_col:
        st.markdown("**⬆ Upload inputs CSV**")
        mode = st.radio("On upload:", ["Replace all", "Add rows"], horizontal=True, key="upload_mode")
        uploaded = st.file_uploader(
            "Choose file", type=["csv"], key="csv_upload", label_visibility="collapsed"
        )
        if uploaded is not None:
            file_sig = (uploaded.name, uploaded.size)
            if st.session_state.get("last_upload_sig") != file_sig:
                try:
                    new_stocks, new_parts = parse_combined_csv(uploaded.read().decode())
                    if mode == "Replace all":
                        st.session_state.stocks_df = new_stocks
                        st.session_state.parts_df  = new_parts
                    else:
                        st.session_state.stocks_df = pd.concat(
                            [stocks_input, new_stocks], ignore_index=True
                        )
                        st.session_state.parts_df = pd.concat(
                            [parts_input, new_parts], ignore_index=True
                        )
                    st.session_state.last_upload_sig = file_sig
                    st.session_state.editor_ver += 1
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to parse CSV: {exc}")

st.divider()


# ── Solver ────────────────────────────────────────────────────────────────────
def solve_profile_group(profile, group_stocks, group_pieces):
    model = cp_model.CpModel()

    s_idx = list(group_stocks.index)
    p_idx = list(group_pieces.index)

    s_len  = {i: int(group_stocks.at[i, "length_mm"])                for i in s_idx}
    s_cost = {i: int(round(group_stocks.at[i, "cost_per_bar"] * 100)) for i in s_idx}
    p_len  = {j: int(group_pieces.at[j, "length_mm"])                for j in p_idx}

    max_bars       = sum(math.ceil(sum(p_len.values()) / s_len[i]) for i in s_idx)
    s_lengths_list = [s_len[i] for i in s_idx]
    s_costs_list   = [s_cost[i] for i in s_idx]

    x, y, t = {}, [], []
    for b in range(max_bars):
        y.append(model.new_bool_var(f"y_{b}"))
        t.append(model.new_int_var(0, len(s_idx) - 1, f"t_{b}"))
        for j in p_idx:
            x[b, j] = model.new_bool_var(f"x_{b}_{j}")

    for j in p_idx:
        model.add(sum(x[b, j] for b in range(max_bars)) == 1)

    for b in range(max_bars):
        bar_len_var = model.new_int_var(min(s_lengths_list), max(s_lengths_list), f"bl_{b}")
        model.add_element(t[b], s_lengths_list, bar_len_var)
        model.add(sum(p_len[j] * x[b, j] for j in p_idx) <= bar_len_var)
        for j in p_idx:
            model.add(x[b, j] <= y[b])
        model.add(sum(x[b, j] for j in p_idx) >= y[b])

    bar_cost_vars = []
    for b in range(max_bars):
        bc = model.new_int_var(min(s_costs_list), max(s_costs_list), f"bc_{b}")
        model.add_element(t[b], s_costs_list, bc)
        used_cost = model.new_int_var(0, max(s_costs_list), f"uc_{b}")
        model.add_multiplication_equality(used_cost, [bc, y[b]])
        bar_cost_vars.append(used_cost)

    model.minimize(sum(bar_cost_vars))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"No solution for profile {profile}: {solver.status_name(status)}")

    results = []
    for b in range(max_bars):
        if solver.value(y[b]):
            si        = solver.value(t[b])
            stock_row = group_stocks.iloc[si]
            cuts_on   = [j for j in p_idx if solver.value(x[b, j])]
            cuts      = [
                (group_pieces.at[j, "piece_id"], group_pieces.at[j, "name"], p_len[j])
                for j in cuts_on
            ]
            used = sum(p_len[j] for j in cuts_on)
            results.append({
                "stock_name": stock_row["name"],
                "length_mm":  int(stock_row["length_mm"]),
                "cost":       stock_row["cost_per_bar"],
                "cuts":       cuts,
                "waste_mm":   int(stock_row["length_mm"]) - used,
                "profile":    profile,
            })
    return results


# ── Visualisation ─────────────────────────────────────────────────────────────
def _is_dark(rgba, threshold=0.35):
    r, g, b, *_ = rgba
    return (0.299 * r + 0.587 * g + 0.114 * b) < threshold


def draw_cutting_plan(results, part_color, title_prefix="", dpi=150):
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

        prof_str = f"{b['profile'][0]}\u00d7{b['profile'][1]}"
        ax.text(
            -bar_len * 0.01, y_bot + bar_h / 2,
            f"Bar {b['bar_no']}\n{b['stock_name']}\n{prof_str}  \u20ac{b['cost']:.2f}",
            ha="right", va="center", fontsize=7.5, color="#222",
        )

    max_len = max(b["length_mm"] for b in results)
    ax.set_xlim(-max_len * 0.18, max_len * 1.02)
    ax.set_ylim(-gap, n_bars * row_h)
    ax.set_xlabel("Length (mm)", fontsize=9)
    ax.set_title(
        f"{title_prefix}Cutting plan \u2014 {n_bars} bar(s)  |  "
        f"Total cost \u20ac{sum(b['cost'] for b in results):.2f}  |  "
        f"Waste {100 * sum(b['waste_mm'] for b in results) / sum(b['length_mm'] for b in results):.1f}%",
        fontsize=10, pad=10,
    )
    ax.set_yticks([])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    return fig


def fig_to_pdf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def fig_to_png(fig, dpi=200):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.getvalue()


# ── Run button ─────────────────────────────────────────────────────────────────
if st.button("\u25b6 Optimise", type="primary"):
    stocks = stocks_input.copy().dropna(subset=["name"]).reset_index(drop=True)
    parts  = parts_input.copy().dropna(subset=["name"]).reset_index(drop=True)

    errors = []
    if stocks.empty:
        errors.append("Stock table is empty.")
    if parts.empty:
        errors.append("Parts table is empty.")
    if not stocks.empty and stocks["name"].duplicated().any():
        errors.append("Stock names must be unique.")
    if not parts.empty and parts["name"].duplicated().any():
        errors.append("Part names must be unique.")

    stocks["profile"] = list(zip(stocks.profile_l1.astype(int), stocks.profile_l2.astype(int)))
    parts["profile"]  = [_split_profile(p) for p in parts["profile"]]

    if not errors:
        unmatched = set(parts["profile"]) - set(stocks["profile"])
        if unmatched:
            errors.append(
                f"No stock found for profile(s): "
                f"{', '.join(f'{a}\u00d7{b}' for a, b in unmatched)}"
            )

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    # Expand to individual pieces
    pieces = parts.loc[parts.index.repeat(parts.quantity.astype(int))].reset_index(drop=True).copy()
    pieces["piece_id"] = pieces["name"] + "_" + (pieces.groupby("name").cumcount() + 1).astype(str)

    # Colour palette — no legend, so colours only help visually distinguish in chart labels
    all_part_names = sorted(parts["name"].unique())
    palette    = plt.colormaps["tab20"].resampled(max(len(all_part_names), 2))
    part_color = {n: palette(i) for i, n in enumerate(all_part_names)}

    # Solve per profile group
    all_results = []
    profiles    = parts["profile"].unique()

    progress = st.progress(0, text="Solving\u2026")
    for idx, prof in enumerate(profiles):
        g_stocks = stocks[stocks["profile"] == prof].reset_index(drop=True)
        g_pieces = pieces[pieces["profile"] == prof].reset_index(drop=True)
        progress.progress(idx / len(profiles), text=f"Solving profile {prof[0]}\u00d7{prof[1]}\u2026")
        try:
            bars = solve_profile_group(prof, g_stocks, g_pieces)
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()
        for bar in bars:
            bar["bar_no"] = len(all_results) + 1
            all_results.append(bar)
    progress.progress(1.0, text="Done \u2713")

    # ── KPI row ────────────────────────────────────────────────────────────────
    total_cost  = sum(b["cost"]      for b in all_results)
    total_waste = sum(b["waste_mm"]  for b in all_results)
    total_mat   = sum(b["length_mm"] for b in all_results)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Bars used",      len(all_results))
    k2.metric("Total material", f"{total_mat:,} mm")
    k3.metric("Total waste",    f"{total_waste:,} mm  ({100*total_waste/total_mat:.1f}%)")
    k4.metric("Total cost",     f"\u20ac{total_cost:.2f}")

    st.divider()

    # ── Summary table ──────────────────────────────────────────────────────────
    st.subheader("\U0001f4cb Cutting Plan Summary")
    rows = []
    for b in all_results:
        cuts_str = ", ".join(f"{pid} ({pl} mm)" for pid, _, pl in b["cuts"])
        rows.append({
            "Bar #":      b["bar_no"],
            "Profile":    f"{b['profile'][0]}\u00d7{b['profile'][1]}",
            "Stock":      b["stock_name"],
            "Bar length": f"{b['length_mm']} mm",
            "Cuts":       cuts_str,
            "Waste":      f"{b['waste_mm']} mm  ({100*b['waste_mm']/b['length_mm']:.1f}%)",
            "Cost (\u20ac)": f"{b['cost']:.2f}",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.divider()

    # ── Full plan chart + PDF download ─────────────────────────────────────────
    st.subheader("\U0001f4ca Full Cutting Plan")
    fig_all = draw_cutting_plan(all_results, part_color, dpi=150)
    st.image(fig_to_png(fig_all), use_container_width=True)
    st.download_button(
        "\u2b07 Download Full Plan as PDF",
        data=fig_to_pdf(fig_all),
        file_name="cutting_plan_full.pdf",
        mime="application/pdf",
        key="pdf_full",
    )
    plt.close(fig_all)

    st.divider()

    # ── Per-profile charts + PDF downloads ────────────────────────────────────
    st.subheader("\U0001f50d Per-Profile Breakdown")
    for prof in profiles:
        group_bars = [b for b in all_results if b["profile"] == prof]
        prof_str   = f"{prof[0]}\u00d7{prof[1]}"
        with st.expander(
            f"Profile {prof_str}  \u2014  {len(group_bars)} bar(s)  "
            f"\u20ac{sum(b['cost'] for b in group_bars):.2f}",
            expanded=True,
        ):
            fig_p = draw_cutting_plan(
                group_bars, part_color,
                title_prefix=f"Profile {prof_str}  \u2014 ", dpi=150,
            )
            st.image(fig_to_png(fig_p), use_container_width=True)
            st.download_button(
                f"\u2b07 Download Profile {prof_str} as PDF",
                data=fig_to_pdf(fig_p),
                file_name=f"cutting_plan_{prof_str.replace(chr(215), 'x')}.pdf",
                mime="application/pdf",
                key=f"pdf_{prof_str}",
            )
            plt.close(fig_p)
