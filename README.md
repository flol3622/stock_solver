# ✂️ 1D Stock Cutting Optimiser

> Pack required structural parts into stock bars at minimum cost.
> Profile matching is exact (`l1 × l2`). Powered by **Google OR-Tools CP-SAT**.

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://stocksolver-1d.streamlit.app/)

---

## 🚀 Getting Started

### Option A — Hosted app *(no install)*

**→ [stocksolver-1d.streamlit.app](https://stocksolver-1d.streamlit.app/)**

Open in your browser and start optimising immediately.

### Option B — Run locally *(one command)*

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) — a fast Python package manager (~10 s install).

```bash
uvx --from git+https://github.com/flol3622/stock_solver stock-solver
```

Downloads the app and all dependencies into an isolated environment and opens it in your browser automatically.

---

## 📖 How to Use

| Step | What to do |
|------|------------|
| 1 | **Available Stock** — enter bar types: name, profile dimensions (`l1 × l2` in mm), bar length, cost per bar. Add / remove rows freely. |
| 2 | **Required Parts** — enter each part: name, profile (dropdown from your stock table), length in mm, quantity. |
| 3 | **▶ Optimise** — the solver assigns parts to bars and minimises total purchase cost. |
| 4 | Review KPI metrics, the cutting plan table, and the Gantt-style bar chart. |
| 5 | Download per-profile **vector PDFs** for workshop use. |

### 💾 Save & load your data

Expand the **Load / Save** section at any time to:

- **Download** all inputs as a single CSV for reuse.
- **Upload** a saved CSV — choose *Replace all* or *Add rows* to your current tables.

**CSV format:**

```csv
section,name,profile,length_mm,cost_per_bar,quantity
stock,HEA200_6m,200x200,6000,42.5,
part,beam_A,200x200,2400,,3
```

Profiles can be written as `200x200` or `200×200`.

---

## 🛠️ For Developers

### Project structure

```
stock_solver/
├── app.py          # Streamlit UI — entry point
├── solver.py       # OR-Tools CP-SAT optimisation logic
├── chart.py        # Matplotlib cutting plan charts
├── data.py         # Default data, CSV helpers, profile utilities
├── _cli.py         # uvx / console-script entry point
├── pyproject.toml  # uv project & dependency manifest
└── .streamlit/
    └── config.toml # Theme and server settings
```

### Run from source

```bash
git clone https://github.com/flol3622/stock_solver
cd stock_solver
uv run streamlit run app.py
```

`uv` creates a virtual environment and installs all dependencies on first run.

### Deploy on Streamlit Cloud

The live app runs from the `main` branch of [github.com/flol3622/stock_solver](https://github.com/flol3622/stock_solver).

To deploy your own fork:

1. Fork the repo on GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select your fork, branch `main`, entry point `app.py`.
4. **Deploy** — Streamlit Cloud reads `pyproject.toml` to install dependencies.

### Manage dependencies

```bash
uv add <package>        # add a runtime dependency
uv add --dev <package>  # add a dev-only dependency
```

### Key design decisions

| Concern | Approach |
|---------|----------|
| Optimisation | CP-SAT per profile group — exact, typically < 1 s |
| Profile matching | Exact `(l1, l2)` tuple equality |
| Cost representation | Integer cents inside CP-SAT (no float domains) |
| Upload deduplication | `(filename, size)` fingerprint prevents rerun loops |
| Chart display | `st.image` at 200 DPI for sharp browser preview; PDF export is vector |
