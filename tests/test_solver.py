import unittest

import pandas as pd

from solver import solve_profile_group


class SolveProfileGroupTest(unittest.TestCase):
    def test_uses_enough_slots_when_total_length_bound_is_too_low(self):
        stocks = pd.DataFrame([
            {"name": "stock_10", "length_mm": 10, "cost_per_bar": 1.0},
        ])
        pieces = pd.DataFrame([
            {"name": f"piece_{idx}", "piece_id": f"piece_{idx}", "length_mm": length}
            for idx, length in enumerate([6, 6, 6, 6, 6, 4, 4], start=1)
        ])

        bars = solve_profile_group((1, 1), stocks, pieces)

        self.assertEqual(len(bars), 5)
        self.assertEqual(sum(len(bar["cuts"]) for bar in bars), len(pieces))

    def test_allows_more_bars_when_short_stock_is_cheaper(self):
        stocks = pd.DataFrame([
            {"name": "long", "length_mm": 10, "cost_per_bar": 100.0},
            {"name": "short", "length_mm": 5, "cost_per_bar": 1.0},
        ])
        pieces = pd.DataFrame([
            {"name": f"piece_{idx}", "piece_id": f"piece_{idx}", "length_mm": 5}
            for idx in range(1, 5)
        ])

        bars = solve_profile_group((1, 1), stocks, pieces)

        self.assertEqual(len(bars), 4)
        self.assertEqual({bar["stock_name"] for bar in bars}, {"short"})
        self.assertEqual(sum(bar["cost"] for bar in bars), 4.0)

    def test_reports_oversized_pieces_before_solving(self):
        stocks = pd.DataFrame([
            {"name": "stock_10", "length_mm": 10, "cost_per_bar": 1.0},
        ])
        pieces = pd.DataFrame([
            {"name": "piece", "piece_id": "piece_1", "length_mm": 11},
        ])

        with self.assertRaisesRegex(RuntimeError, "piece_1 .* Longest stock is 10 mm"):
            solve_profile_group((1, 1), stocks, pieces)


if __name__ == "__main__":
    unittest.main()
