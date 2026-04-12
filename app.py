"""
app.py — Streamlit UI for the 1-D Stock Cutting Optimiser.

Run locally:   uv run streamlit run app.py
Deploy:        push to GitHub, connect repo on share.streamlit.io
"""
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from chart import build_color_map, draw_cutting_plan, fig_to_pdf, fig_to_png
from data import (
    DEFAULT_PARTS,
    DEFAULT_STOCKS,
    build_combined_csv,
    parse_combined_csv,
    profile_str,
    split_profile,
)
from solver import solve_profile_group

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

# ── Session state ─────────────────────────────────────────────────────────────
if "stocks_df" not in st.session_state:
    st.session_state.stocks_df = DEFAULT_STOCKS.copy()
if "parts_df" not in st.session_state:
    st.session_state.parts_df = DEFAULT_PARTS.copy()
if "editor_ver" not in st.session_state:
    st.session_state.editor_ver = 0

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

# Profile dropdown options derived live from the stock table
available_profiles = sorted({
    profile_str(int(r.profile_l1), int(r.profile_l2))
    for _, r in stocks_input.dropna(subset=["profile_l1", "profile_l2"]).iterrows()
    if pd.notna(r.profile_l1) and pd.notna(r.profile_l2)
}) or ["—"]

with col_parts:
    st.subheader("🔩 Required Parts")
    st.caption("Profile dropdown is populated from the stock table above.")
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
        st.download_button(
            "Download inputs.csv",
            data=build_combined_csv(stocks_input, parts_input).encode(),
            file_name="cutting_inputs.csv",
            mime="text/csv",
        )

    with up_col:
        st.markdown("**⬆ Upload inputs CSV**")
        mode     = st.radio("On upload:", ["Replace all", "Add rows"], horizontal=True, key="upload_mode")
        uploaded = st.file_uploader("Choose file", type=["csv"], key="csv_upload", label_visibility="collapsed")

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

# ── Optimise ──────────────────────────────────────────────────────────────────
if st.button("▶ Optimise", type="primary"):

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
    parts["profile"]  = [split_profile(p) for p in parts["profile"]]

    if not errors:
        unmatched = set(parts["profile"]) - set(stocks["profile"])
        if unmatched:
            errors.append(
                "No stock found for profile(s): "
                + ", ".join(f"{a}x{b}" for a, b in unmatched)
            )

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    pieces = parts.loc[parts.index.repeat(parts.quantity.astype(int))].reset_index(drop=True).copy()
    pieces["piece_id"] = pieces["name"] + "_" + (pieces.groupby("name").cumcount() + 1).astype(str)

    part_color = build_color_map(sorted(parts["name"].unique()))

    all_results = []
    profiles    = parts["profile"].unique()

    progress = st.progress(0, text="Solving...")
    for idx, prof in enumerate(profiles):
        g_stocks = stocks[stocks["profile"] == prof].reset_index(drop=True)
        g_pieces = pieces[pieces["profile"] == prof].reset_index(drop=True)
        progress.progress(idx / len(profiles), text=f"Solving profile {prof[0]}x{prof[1]}...")
        try:
            bars = solve_profile_group(prof, g_stocks, g_pieces)
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()
        for bar in bars:
            bar["bar_no"] = len(all_results) + 1
            all_results.append(bar)
    progress.progress(1.0, text="Done")

    total_cost  = sum(b["cost"]      for b in all_results)
    total_waste = sum(b["waste_mm"]  for b in all_results)
    total_mat   = sum(b["length_mm"] for b in all_results)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Bars used",      len(all_results))
    k2.metric("Total material", f"{total_mat:,} mm")
    k3.metric("Total waste",    f"{total_waste:,} mm  ({100*total_waste/total_mat:.1f}%)")
    k4.metric("Total cost",     f"EUR {total_cost:.2f}")

    st.divider()

    st.subheader("Cutting Plan Summary")
    rows = []
    for b in all_results:
        cuts_str = ", ".join(f"{pid} ({pl} mm)" for pid, _, pl in b["cuts"])
        rows.append({
            "Bar #":    b["bar_no"],
            "Profile":  f"{b['profile'][0]}x{b['profile'][1]}",
            "Stock":    b["stock_name"],
            "Length":   f"{b['length_mm']} mm",
            "Cuts":     cuts_str,
            "Waste":    f"{b['waste_mm']} mm  ({100*b['waste_mm']/b['length_mm']:.1f}%)",
            "Cost":     f"{b['cost']:.2f}",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.divider()

    st.subheader("Full Cutting Plan")
    fig_all = draw_cutting_plan(all_results, part_color)
    st.image(fig_to_png(fig_all, dpi=400), width='stretch')
    st.download_button(
        "Download Full Plan as PDF",
        data=fig_to_pdf(fig_all),
        file_name="cutting_plan_full.pdf",
        mime="application/pdf",
        key="pdf_full",
    )
    plt.close(fig_all)

    st.divider()

    st.subheader("Per-Profile Breakdown")
    for prof in profiles:
        group_bars = [b for b in all_results if b["profile"] == prof]
        prof_label = f"{prof[0]}x{prof[1]}"
        with st.expander(
            f"Profile {prof_label}  -  {len(group_bars)} bar(s)  "
            f"EUR {sum(b['cost'] for b in group_bars):.2f}",
            expanded=True,
        ):
            fig_p = draw_cutting_plan(
                group_bars, part_color,
                title_prefix=f"Profile {prof_label}  - ",
            )
            st.image(fig_to_png(fig_p, dpi=400), width='stretch')
            st.download_button(
                f"Download Profile {prof_label} as PDF",
                data=fig_to_pdf(fig_p),
                file_name=f"cutting_plan_{prof_label}.pdf",
                mime="application/pdf",
                key=f"pdf_{prof_label}",
            )
            plt.close(fig_p)
