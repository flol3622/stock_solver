# 1D Stock Cutting Optimiser

Minimise bar purchase cost by packing required structural parts into available stock bars. Profile compatibility is enforced exactly (`l1 × l2`). Powered by **Google OR-Tools CP-SAT**.

---

## For Users

### Using the hosted app

Open the app at your Streamlit Cloud URL and follow these steps:

1. **Available Stock** table — enter the bar types you can buy: name, cross-section dimensions (`l1` and `l2` in mm), bar length, and cost per bar. Add or remove rows freely.
2. **Required Parts** table — enter each part type: name, profile (chosen from a dropdown that reflects your stock table), length in mm, and how many pieces you need.
3. **Load / Save** — expand this section to:
   - **Download** your current inputs as a single CSV file for later reuse.
   - **Upload** a previously saved CSV, choosing whether to *replace* the tables entirely or *add* the rows to what is already there.
4. Press **▶ Optimise**.
5. Review the KPI summary, cutting plan table, and the Gantt-style chart.
6. Download individual profile charts as **vector PDF** for workshop use.

### CSV format

The combined CSV uses a `section` column to tag rows as `stock` or `part`:

```
section,name,profile,length_mm,cost_per_bar,quantity
stock,HEA200_6m,200x200,6000,42.5,
part,beam_A,200x200,2400,,3
```

Profiles can be written as `200x200` or `200×200`.

---

## For Developers

### Project structure

```
stock_solver/
├── app.py          # Streamlit UI — entry point
├── solver.py       # OR-Tools CP-SAT optimisation logic
├── chart.py        # Matplotlib cutting plan charts
├── data.py         # Default data, CSV helpers, profile utilities
├── pyproject.toml  # UV project / dependency manifest
├── README.md
└── .streamlit/
    └── config.toml # Streamlit theme and server settings
```

### Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/YOUR_USERNAME/stock-solver
cd stock-solver
uv run streamlit run app.py
```

`uv` will create a virtual environment and install all dependencies automatically on first run.

### One-liner from GitHub (no clone)

```bash
uvx --from "git+https://github.com/YOUR_USERNAME/stock-solver" \
    --with streamlit --with ortools --with matplotlib --with pandas \
    streamlit run https://raw.githubusercontent.com/YOUR_USERNAME/stock-solver/main/app.py
```

> **Note:** This one-liner only works if `app.py` imports are resolvable. For multi-module projects like this one, a full clone + `uv run` is the recommended approach.

### Deploy on Streamlit Cloud

1. Push the repository to GitHub (all files including `pyproject.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select your repository, branch `main`, and set **Main file path** to `app.py`.
4. Click **Deploy**. Streamlit Cloud reads `pyproject.toml` to install dependencies automatically.

### Add / update dependencies

```bash
uv add <package>      # add a runtime dependency
uv add --dev <package> # add a dev-only dependency
```

### Key design decisions

| Concern | Approach |
|---|---|
| Optimisation | CP-SAT per profile group (exact, small instances < 1 s) |
| Profile matching | Exact `(l1, l2)` tuple equality — no fuzzy matching |
| Cost representation | Integer cents inside CP-SAT to avoid float domains |
| Upload deduplication | `(filename, size)` fingerprint in session state prevents rerun loops |
| Chart display | `st.image` with 200 DPI PNG for crisp browser preview; PDF export is vector |
