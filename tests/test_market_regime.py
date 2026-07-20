from __future__ import annotations

from unittest import TestCase

import pandas as pd

from ashare_data.market_regime import classify_market_regime, map_current_market_regime


def _market_frame(closes):
    return pd.DataFrame(
        {"close": closes},
        index=pd.bdate_range("2024-01-02", periods=len(closes)),
    )


class HistoricalMarketRegimeTest(TestCase):
    def test_classifies_uptrend_using_only_prior_bars(self):
        closes = [3000 * (1.002 ** index) for index in range(150)]
        frame = _market_frame(closes)
        as_of_date = frame.index[120]

        result = classify_market_regime(frame, as_of_date=as_of_date)

        self.assertEqual(result["regime"], "上涨")
        self.assertEqual(result["signal_date"], frame.index[119].strftime("%Y-%m-%d"))
        self.assertLess(pd.Timestamp(result["signal_date"]), as_of_date)

    def test_future_prices_do_not_change_past_classification(self):
        closes = [3000 * (1.002 ** index) for index in range(150)]
        frame = _market_frame(closes)
        as_of_date = frame.index[120]
        original = classify_market_regime(frame, as_of_date=as_of_date)
        frame.loc[frame.index >= as_of_date, "close"] = 100

        changed_future = classify_market_regime(frame, as_of_date=as_of_date)

        self.assertEqual(changed_future, original)

    def test_maps_realtime_breadth_regime_to_historical_regime(self):
        self.assertEqual(map_current_market_regime("偏强"), "上涨")
        self.assertEqual(map_current_market_regime("震荡"), "震荡")
        self.assertEqual(map_current_market_regime("偏弱"), "下跌")
        self.assertEqual(map_current_market_regime("极弱"), "下跌")

