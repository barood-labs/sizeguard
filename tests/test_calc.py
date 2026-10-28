import unittest

from sizeguard.calc import liquidation_price, plan


class TestLiquidation(unittest.TestCase):
    def test_long_10x(self):
        # entry 100, L=10, mm=0.5% → 100*(1-0.1+0.005)=90.5
        self.assertAlmostEqual(liquidation_price(100, 10, "long", 0.005), 90.5)

    def test_short_10x(self):
        self.assertAlmostEqual(liquidation_price(100, 10, "short", 0.005), 109.5)


class TestPlan(unittest.TestCase):
    def test_basic_long_sizing(self):
        p = plan(
            balance=10_000,
            risk_pct=1,
            entry=100,
            stop=98,
            leverage=5,
            side="long",
            taker=0.0004,
            maker=0.0002,
            mm_rate=0.005,
        )
        self.assertAlmostEqual(p.risk_usd, 100)
        self.assertAlmostEqual(p.units, 50)  # 100 / 2
        self.assertAlmostEqual(p.notional, 5000)
        self.assertAlmostEqual(p.margin, 1000)
        self.assertTrue(p.stop_safe)  # stop 98 > liq 90.5*... wait entry 100 L5 mm0.5 → 100*(1-0.2+0.005)=80.5
        self.assertAlmostEqual(p.liquidation, 80.5)
        self.assertAlmostEqual(p.fee_round_trip, 5000 * 0.0004 * 2)

    def test_unsafe_stop(self):
        # High leverage so liq sits above the stop
        p = plan(
            balance=10_000,
            risk_pct=1,
            entry=100,
            stop=95,
            leverage=25,
            side="long",
            mm_rate=0.005,
        )
        # liq = 100*(1-1/25+0.005)=100*(1-0.04+0.005)=96.5 → stop 95 < 96.5 → unsafe
        self.assertFalse(p.stop_safe)
        self.assertAlmostEqual(p.liquidation, 96.5)

    def test_funding_cost_long_pays(self):
        p = plan(
            balance=10_000,
            risk_pct=1,
            entry=100,
            stop=98,
            leverage=5,
            side="long",
            funding_rate=0.0001,
            funding_interval_h=8,
            hold_days=1,
            taker=0.0,
            maker=0.0,
        )
        # 3 periods/day * 0.0001 * 5000 notional = 1.5
        self.assertAlmostEqual(p.funding_periods, 3.0)
        self.assertAlmostEqual(p.funding_cost, 1.5)

    def test_short_receives_positive_funding(self):
        p = plan(
            balance=10_000,
            risk_pct=1,
            entry=100,
            stop=102,
            leverage=5,
            side="short",
            funding_rate=0.0001,
            funding_interval_h=8,
            hold_days=1,
            taker=0.0,
            maker=0.0,
        )
        self.assertAlmostEqual(p.funding_cost, -1.5)


if __name__ == "__main__":
    unittest.main()
