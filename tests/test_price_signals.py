import unittest

import pandas as pd

from signals.price_signals import buy_blocked, market_crash, shock_alert


def make(code, closes, vols, ul=None, ll=None, mcap=1000.0, start="2026-01-01"):
    n = len(closes)
    return pd.DataFrame({
        "Date": pd.bdate_range(start, periods=n), "Code": code,
        "AdjC": closes, "AdjVo": vols, "Va": [c * v for c, v in zip(closes, vols)],
        "UL": ul or [0] * n, "LL": ll or [0] * n, "MktCap": mcap})


def cat(*fs):
    return pd.concat(fs, ignore_index=True).sort_values(["Code", "Date"])


class PriceSignals(unittest.TestCase):
    def test_volume_surge_at_high_blocked(self):
        c = list(range(100, 100 + 130))
        v = [100.0] * 110 + [1000.0] * 20
        df = cat(make("A0001", c, v), make("B0001", c, [100.0] * 130))
        self.assertEqual(list(buy_blocked(df).index), ["A0001"])

    def test_surge_but_not_at_high_not_blocked(self):
        c = [200.0] * 100 + [100.0] * 30
        v = [100.0] * 110 + [1000.0] * 20
        self.assertTrue(buy_blocked(cat(make("A0001", c, v))).empty)

    def test_limit_up_blocked(self):
        ul = [0] * 129 + [1]
        df = cat(make("A0001", [100.0] * 130, [100.0] * 130, ul=ul))
        self.assertEqual(buy_blocked(df).loc["A0001", "reason"], "limit_up")

    def test_shock_alert(self):
        c = [100.0] * 29 + [80.0]
        v = [100.0] * 29 + [500.0]
        df = cat(make("A0001", c, v), make("B0001", [100.0] * 30, [100.0] * 30))
        self.assertEqual(list(shock_alert(df).index), ["A0001"])

    def test_shock_without_volume_not_alert(self):
        df = cat(make("A0001", [100.0] * 29 + [80.0], [100.0] * 30))
        self.assertTrue(shock_alert(df).empty)

    def test_market_crash(self):
        def stock(code):
            c = [100.0] * 60 + [97.0, 94.0, 91.0, 88.0, 85.0]
            return make(code, c, [100.0] * 60 + [400.0] * 5)
        res = market_crash(cat(stock("A0001"), stock("B0001")))
        self.assertTrue(res["alert"])
        self.assertLess(res["cum_return"], -0.10)

    def test_calm_market_no_alert(self):
        df = cat(make("A0001", [100.0] * 70, [100.0] * 70))
        self.assertFalse(market_crash(df)["alert"])


if __name__ == "__main__":
    unittest.main()
