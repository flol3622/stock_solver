"""
solver.py — 1-D cutting stock optimisation via Google OR-Tools CP-SAT.

Each profile group is solved independently. Decision variables:
  x[b, j]  BoolVar — piece j is placed on bar-slot b
  y[b]     BoolVar — bar-slot b is actually used
  t[b]     IntVar  — stock type index used for bar-slot b

Objective: minimise total purchase cost of used bars.
"""
import pandas as pd
from ortools.sat.python import cp_model


def _piece_label(group_pieces: pd.DataFrame, piece_idx: int) -> str:
    if "piece_id" in group_pieces.columns:
        return str(group_pieces.at[piece_idx, "piece_id"])
    return str(group_pieces.at[piece_idx, "name"])


def _greedy_bar_slot_upper_bound(piece_lengths: list[int], stock_lengths: list[int]) -> int:
    """Return a feasible bar-count bound using the longest stock length."""
    max_stock_length = max(stock_lengths)
    remaining_by_bar: list[int] = []

    for piece_length in sorted(piece_lengths, reverse=True):
        best_bar = None
        best_remaining_after_cut = None

        for bar, remaining in enumerate(remaining_by_bar):
            if piece_length <= remaining:
                remaining_after_cut = remaining - piece_length
                if (
                    best_remaining_after_cut is None
                    or remaining_after_cut < best_remaining_after_cut
                ):
                    best_bar = bar
                    best_remaining_after_cut = remaining_after_cut

        if best_bar is None:
            remaining_by_bar.append(max_stock_length - piece_length)
        else:
            remaining_by_bar[best_bar] -= piece_length

    return len(remaining_by_bar)


def solve_profile_group(
    profile: tuple[int, int],
    group_stocks: pd.DataFrame,
    group_pieces: pd.DataFrame,
) -> list[dict]:
    """
    Solve the cutting stock problem for a single profile.

    Parameters
    ----------
    profile       : (l1, l2) tuple identifying this profile group
    group_stocks  : rows from the stocks DataFrame matching this profile
    group_pieces  : expanded piece instances (one row per piece) for this profile

    Returns
    -------
    List of bar dicts, each containing:
        stock_name, length_mm, cost, cuts, waste_mm, profile
    """
    model = cp_model.CpModel()

    s_idx = list(group_stocks.index)
    p_idx = list(group_pieces.index)

    s_len  = {i: int(group_stocks.at[i, "length_mm"])                 for i in s_idx}
    s_cost = {i: int(round(group_stocks.at[i, "cost_per_bar"] * 100)) for i in s_idx}
    p_len  = {j: int(group_pieces.at[j, "length_mm"])                 for j in p_idx}

    if not s_idx:
        raise RuntimeError(f"No stock for profile {profile}")
    if not p_idx:
        return []

    max_stock_length = max(s_len.values())
    oversized = [j for j in p_idx if p_len[j] > max_stock_length]
    if oversized:
        sample = ", ".join(
            f"{_piece_label(group_pieces, j)} ({p_len[j]} mm)"
            for j in oversized[:5]
        )
        if len(oversized) > 5:
            sample += f", and {len(oversized) - 5} more"
        raise RuntimeError(
            f"Piece(s) too long for profile {profile}: {sample}. "
            f"Longest stock is {max_stock_length} mm."
        )

    # The old total-length estimate can be too small for bin packing. Start from
    # a known feasible solution using the longest stock, then allow any larger
    # bar count that could still beat that solution on cost.
    greedy_bars = _greedy_bar_slot_upper_bound(list(p_len.values()), list(s_len.values()))
    cheapest_longest_stock = min(
        s_cost[i] for i in s_idx
        if s_len[i] == max_stock_length
    )
    min_bar_cost = min(s_cost.values())
    if min_bar_cost > 0:
        max_bars = min(
            len(p_idx),
            max(greedy_bars, greedy_bars * cheapest_longest_stock // min_bar_cost),
        )
    else:
        max_bars = len(p_idx)

    s_lengths_list = [s_len[i] for i in s_idx]
    s_costs_list   = [s_cost[i] for i in s_idx]

    # Decision variables
    x, y, t = {}, [], []
    for b in range(max_bars):
        y.append(model.new_bool_var(f"y_{b}"))
        t.append(model.new_int_var(0, len(s_idx) - 1, f"t_{b}"))
        for j in p_idx:
            x[b, j] = model.new_bool_var(f"x_{b}_{j}")

    # Each piece assigned to exactly one bar
    for j in p_idx:
        model.add(sum(x[b, j] for b in range(max_bars)) == 1)

    # Bar slots are interchangeable, so pack used bars toward the front.
    for b in range(max_bars - 1):
        model.add(y[b] >= y[b + 1])

    # Length feasibility + bar-used indicator
    for b in range(max_bars):
        bar_len_var = model.new_int_var(min(s_lengths_list), max(s_lengths_list), f"bl_{b}")
        model.add_element(t[b], s_lengths_list, bar_len_var)
        model.add(sum(p_len[j] * x[b, j] for j in p_idx) <= bar_len_var)
        for j in p_idx:
            model.add(x[b, j] <= y[b])
        model.add(sum(x[b, j] for j in p_idx) >= y[b])

    # Cost objective (in integer cents to stay within CP-SAT integer domain)
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
        raise RuntimeError(
            f"No solution for profile {profile}: {solver.status_name(status)}"
        )

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
                "cost":       float(stock_row["cost_per_bar"]),
                "cuts":       cuts,
                "waste_mm":   int(stock_row["length_mm"]) - used,
                "profile":    profile,
            })
    return results
