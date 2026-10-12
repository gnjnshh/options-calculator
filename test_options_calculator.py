"""
Unit tests for Options Probability Calculator.
"""

import unittest
import math
from options_calculator import (
    norm_cdf,
    calculate_d1_d2,
    black_scholes_price,
    calculate_greeks,
    calculate_prob_worthless,
    calculate_spread_prob_worthless,
    calculate_iron_condor_prob_worthless,
    monte_carlo_verify
)


class TestOptionsCalculator(unittest.TestCase):

    def test_norm_cdf(self):
        self.assertAlmostEqual(norm_cdf(0.0), 0.5, places=5)
        self.assertAlmostEqual(norm_cdf(1.96), 0.975002, places=4)
        self.assertAlmostEqual(norm_cdf(-1.96), 0.024998, places=4)

    def test_call_otm_prob_worthless(self):
        # Spot = 100, Strike = 110, DTE = 30, IV = 20%, r = 5%
        # An OTM Call should have high probability of expiring worthless (> 70%)
        res = calculate_prob_worthless(
            spot=100.0,
            strike=110.0,
            dte_days=30.0,
            volatility=0.20,
            risk_free_rate=0.05,
            option_type="call"
        )
        self.assertGreater(res["prob_worthless_risk_neutral"], 0.70)
        self.assertLess(res["prob_worthless_risk_neutral"], 1.0)
        self.assertAlmostEqual(
            res["prob_worthless_risk_neutral"] + res["prob_itm_risk_neutral"],
            1.0,
            places=6
        )

    def test_put_otm_prob_worthless(self):
        # Spot = 100, Strike = 90, DTE = 30, IV = 20%, r = 5%
        # An OTM Put (strike 90 below 100) should have high probability of expiring worthless
        res = calculate_prob_worthless(
            spot=100.0,
            strike=90.0,
            dte_days=30.0,
            volatility=0.20,
            risk_free_rate=0.05,
            option_type="put"
        )
        self.assertGreater(res["prob_worthless_risk_neutral"], 0.70)
        self.assertAlmostEqual(
            res["prob_worthless_risk_neutral"] + res["prob_itm_risk_neutral"],
            1.0,
            places=6
        )

    def test_atm_options_probabilities(self):
        # Spot = 100, Strike = 100, DTE = 365, IV = 20%, r = 0%
        # ATM options with r=0 should have roughly ~50% probability
        res_call = calculate_prob_worthless(
            spot=100.0,
            strike=100.0,
            dte_days=365.0,
            volatility=0.20,
            risk_free_rate=0.0,
            option_type="call"
        )
        res_put = calculate_prob_worthless(
            spot=100.0,
            strike=100.0,
            dte_days=365.0,
            volatility=0.20,
            risk_free_rate=0.0,
            option_type="put"
        )
        # d2 = (0 - 0.5 * 0.04) / 0.20 = -0.02 / 0.20 = -0.1
        # N(d2) = N(-0.1) ≈ 0.46017. Call PoW = 1 - 0.46017 = 0.5398
        self.assertAlmostEqual(res_call["prob_worthless_risk_neutral"], 0.5398, places=3)
        self.assertAlmostEqual(res_put["prob_worthless_risk_neutral"], 0.4602, places=3)

    def test_deep_otm_itm_limits(self):
        # Deep OTM Call (Strike 300 when spot is 100)
        res_deep_otm = calculate_prob_worthless(
            spot=100.0, strike=300.0, dte_days=30.0, volatility=0.20, option_type="call"
        )
        self.assertAlmostEqual(res_deep_otm["prob_worthless_risk_neutral"], 1.0, places=4)

        # Deep ITM Call (Strike 20 when spot is 100)
        res_deep_itm = calculate_prob_worthless(
            spot=100.0, strike=20.0, dte_days=30.0, volatility=0.20, option_type="call"
        )
        self.assertAlmostEqual(res_deep_itm["prob_worthless_risk_neutral"], 0.0, places=4)

    def test_black_scholes_put_call_parity(self):
        # S=100, K=100, T=0.5, sigma=0.25, r=0.05
        spot, strike, t_years, vol, r = 100.0, 100.0, 0.5, 0.25, 0.05
        call_price = black_scholes_price(spot, strike, t_years, vol, r, 0.0, "call")
        put_price = black_scholes_price(spot, strike, t_years, vol, r, 0.0, "put")

        # Put-Call Parity: C - P = S - K * exp(-rT)
        lhs = call_price - put_price
        rhs = spot - strike * math.exp(-r * t_years)
        self.assertAlmostEqual(lhs, rhs, places=5)

    def test_greeks(self):
        # Call delta should be between 0 and 1, Put delta between -1 and 0
        g_call = calculate_greeks(100.0, 100.0, 0.5, 0.20, 0.05, 0.0, "call")
        g_put = calculate_greeks(100.0, 100.0, 0.5, 0.20, 0.05, 0.0, "put")

        self.assertGreater(g_call["delta"], 0.0)
        self.assertLess(g_call["delta"], 1.0)
        self.assertLess(g_put["delta"], 0.0)
        self.assertGreater(g_put["delta"], -1.0)
        self.assertAlmostEqual(g_call["delta"] - g_put["delta"], 1.0, places=5)
        self.assertAlmostEqual(g_call["gamma"], g_put["gamma"], places=5)

    def test_credit_spreads(self):
        # Bull Put Spread: S=100, Short Put K=95, Long Put K=90
        spread = calculate_spread_prob_worthless(
            spot=100.0, short_strike=95.0, long_strike=90.0, dte_days=30.0, volatility=0.20
        )
        self.assertGreater(spread["prob_both_worthless"], 0.70)
        self.assertGreater(spread["prob_of_profit"], spread["prob_both_worthless"])

    def test_iron_condor(self):
        # S=100, Put K=90, Call K=110
        condor = calculate_iron_condor_prob_worthless(
            spot=100.0, put_strike=90.0, call_strike=110.0, dte_days=30.0, volatility=0.20, net_credit=1.5
        )
        self.assertGreater(condor["prob_both_worthless"], 0.60)
        self.assertGreater(condor["prob_of_profit"], condor["prob_both_worthless"])

    def test_monte_carlo_convergence(self):
        # Compare Monte Carlo simulation with analytical solution
        analytical = calculate_prob_worthless(
            spot=100.0, strike=105.0, dte_days=45.0, volatility=0.25, risk_free_rate=0.04, option_type="call"
        )
        mc = monte_carlo_verify(
            spot=100.0, strike=105.0, dte_days=45.0, volatility=0.25, risk_free_rate=0.04, option_type="call",
            num_simulations=50_000
        )
        # Analytical vs MC should be within ~0.5% (0.005)
        self.assertAlmostEqual(
            analytical["prob_worthless_risk_neutral"],
            mc["simulated_prob_worthless"],
            places=2
        )


if __name__ == "__main__":
    unittest.main()
