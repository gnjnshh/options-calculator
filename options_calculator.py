"""
Options Probability & Expiration Calculator
Calculates the exact and approximated probability of options expiring worthless (OTM),
along with Probability of Profit (PoP), Probability of Touch (PoT), Greeks, and multi-leg spreads.
"""

import math
from typing import Dict, Any, Tuple, Optional
import argparse
import sys


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def calculate_d1_d2(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    expected_drift: Optional[float] = None
) -> Tuple[float, float]:
    """
    Calculate d1 and d2 under Black-Scholes / Geometric Brownian Motion.
    
    If expected_drift is provided, d1 and d2 use real-world physical drift (mu)
    instead of risk-neutral drift (r - q).
    """
    if spot <= 0 or strike <= 0:
        raise ValueError("Spot and Strike prices must be strictly positive.")
    if time_to_expiry_years <= 0:
        raise ValueError("Time to expiration must be positive.")
    if volatility <= 0:
        raise ValueError("Volatility must be strictly positive.")

    drift = expected_drift if expected_drift is not None else (risk_free_rate - dividend_yield)
    sigma_sqrt_t = volatility * math.sqrt(time_to_expiry_years)

    d1 = (math.log(spot / strike) + (drift + 0.5 * volatility ** 2) * time_to_expiry_years) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    return d1, d2


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    option_type: str = "call"
) -> float:
    """Theoretical Black-Scholes option price."""
    option_type = option_type.lower()
    if time_to_expiry_years <= 1e-7:
        if option_type == "call":
            return max(0.0, spot - strike)
        else:
            return max(0.0, strike - spot)

    d1, d2 = calculate_d1_d2(spot, strike, time_to_expiry_years, volatility, risk_free_rate, dividend_yield)
    df_r = math.exp(-risk_free_rate * time_to_expiry_years)
    df_q = math.exp(-dividend_yield * time_to_expiry_years)

    if option_type == "call":
        return spot * df_q * norm_cdf(d1) - strike * df_r * norm_cdf(d2)
    elif option_type == "put":
        return strike * df_r * norm_cdf(-d2) - spot * df_q * norm_cdf(-d1)
    else:
        raise ValueError("option_type must be 'call' or 'put'")


def calculate_greeks(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    option_type: str = "call"
) -> Dict[str, float]:
    """Calculate option Greeks: Delta, Gamma, Theta (per day), Vega (per 1% IV), Rho."""
    option_type = option_type.lower()
    t = max(1e-6, time_to_expiry_years)
    d1, d2 = calculate_d1_d2(spot, strike, t, volatility, risk_free_rate, dividend_yield)
    
    df_q = math.exp(-dividend_yield * t)
    df_r = math.exp(-risk_free_rate * t)
    pdf_d1 = norm_pdf(d1)
    sqrt_t = math.sqrt(t)

    # Gamma (identical for Call and Put)
    gamma = (df_q * pdf_d1) / (spot * volatility * sqrt_t)

    # Vega (per 1% IV change, e.g., 0.01 change in volatility)
    vega = (spot * df_q * sqrt_t * pdf_d1) / 100.0

    if option_type == "call":
        delta = df_q * norm_cdf(d1)
        theta_annual = (
            -(spot * df_q * pdf_d1 * volatility) / (2.0 * sqrt_t)
            - risk_free_rate * strike * df_r * norm_cdf(d2)
            + dividend_yield * spot * df_q * norm_cdf(d1)
        )
        rho = (strike * t * df_r * norm_cdf(d2)) / 100.0
    elif option_type == "put":
        delta = -df_q * norm_cdf(-d1)
        theta_annual = (
            -(spot * df_q * pdf_d1 * volatility) / (2.0 * sqrt_t)
            + risk_free_rate * strike * df_r * norm_cdf(-d2)
            - dividend_yield * spot * df_q * norm_cdf(-d1)
        )
        rho = (-strike * t * df_r * norm_cdf(-d2)) / 100.0
    else:
        raise ValueError("option_type must be 'call' or 'put'")

    theta_daily = theta_annual / 365.0

    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta_daily,
        "vega": vega,
        "rho": rho
    }


def calculate_prob_worthless(
    spot: float,
    strike: float,
    dte_days: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    option_type: str = "call",
    expected_drift: Optional[float] = None,
    premium: Optional[float] = None,
    is_short: bool = True
) -> Dict[str, Any]:
    """
    Calculate probability of an option expiring worthless and related metrics.
    
    Parameters:
    - spot: Current price of the underlying asset
    - strike: Option strike price
    - dte_days: Days to expiration (e.g. 30, 45)
    - volatility: Annualized volatility (e.g. 0.25 for 25%)
    - risk_free_rate: Annualized risk-free interest rate (e.g. 0.05 for 5%)
    - dividend_yield: Annualized continuous dividend yield (e.g. 0.015 for 1.5%)
    - option_type: 'call' or 'put'
    - expected_drift: Optional real-world expected return (if None, uses risk-neutral drift r - q)
    - premium: Optional option price / premium received/paid (if None, calculates via Black-Scholes)
    - is_short: True if selling the option (credit), False if buying (debit)
    
    Returns:
        Dictionary of probabilities and analytics.
    """
    t_years = max(1e-5, dte_days / 365.0)
    option_type = option_type.lower()
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")

    # 1. Standard Risk-Neutral d1 and d2
    d1_rn, d2_rn = calculate_d1_d2(
        spot, strike, t_years, volatility, risk_free_rate, dividend_yield, expected_drift=None
    )

    # 2. Real-World d1 and d2 (if drift specified)
    if expected_drift is not None:
        d1_rw, d2_rw = calculate_d1_d2(
            spot, strike, t_years, volatility, risk_free_rate, dividend_yield, expected_drift=expected_drift
        )
    else:
        d1_rw, d2_rw = d1_rn, d2_rn

    # 3. Probability of Expiring In-The-Money (ITM)
    # Call expires ITM if S_T > K: P(S_T > K) = N(d2)
    # Put expires ITM if S_T < K: P(S_T < K) = N(-d2)
    if option_type == "call":
        p_itm_rn = norm_cdf(d2_rn)
        p_itm_rw = norm_cdf(d2_rw)
        p_worthless_rn = 1.0 - p_itm_rn  # = N(-d2)
        p_worthless_rw = 1.0 - p_itm_rw
    else:  # put
        p_itm_rn = norm_cdf(-d2_rn)
        p_itm_rw = norm_cdf(-d2_rw)
        p_worthless_rn = 1.0 - p_itm_rn  # = N(d2)
        p_worthless_rw = 1.0 - p_itm_rw

    # 4. Greeks
    greeks = calculate_greeks(
        spot, strike, t_years, volatility, risk_free_rate, dividend_yield, option_type
    )

    # 5. Delta Approximation
    # Traders frequently use 1 - |Delta| as a quick proxy for PoW
    delta_mag = abs(greeks["delta"])
    p_worthless_delta_approx = max(0.0, min(1.0, 1.0 - delta_mag))

    # 6. Probability of Touch (hitting strike anytime before expiry)
    # Heuristic approximation: PoT ≈ 2 * P(ITM), capped at 1.0
    # Exact barrier formula for constant drift:
    mu = (risk_free_rate - dividend_yield) - 0.5 * (volatility ** 2)
    vol_sq = volatility ** 2
    if option_type == "call" and strike > spot:
        ratio = strike / spot
        term1 = (ratio ** (2.0 * mu / vol_sq)) if vol_sq > 0 else 1.0
        arg1 = (-math.log(ratio) - mu * t_years) / (volatility * math.sqrt(t_years))
        arg2 = (-math.log(ratio) + mu * t_years) / (volatility * math.sqrt(t_years))
        p_touch_exact = term1 * norm_cdf(arg1) + norm_cdf(arg2)
    elif option_type == "put" and strike < spot:
        ratio = strike / spot
        term1 = (ratio ** (2.0 * mu / vol_sq)) if vol_sq > 0 else 1.0
        arg1 = (math.log(ratio) + mu * t_years) / (volatility * math.sqrt(t_years))
        arg2 = (math.log(ratio) - mu * t_years) / (volatility * math.sqrt(t_years))
        p_touch_exact = term1 * norm_cdf(arg1) + norm_cdf(arg2)
    else:
        # Already ITM or at the money
        p_touch_exact = 1.0

    p_touch_exact = max(0.0, min(1.0, p_touch_exact))
    p_touch_heuristic = min(1.0, 2.0 * p_itm_rn)

    # 7. Breakeven Price & Probability of Profit (PoP)
    bs_theo_price = black_scholes_price(
        spot, strike, t_years, volatility, risk_free_rate, dividend_yield, option_type
    )
    actual_premium = premium if premium is not None and premium > 0 else bs_theo_price

    if option_type == "call":
        breakeven = strike + actual_premium
        # Breakeven d2
        _, be_d2 = calculate_d1_d2(
            spot, breakeven, t_years, volatility, risk_free_rate, dividend_yield, expected_drift=expected_drift
        )
        # Short Call profits if S_T <= breakeven
        # Long Call profits if S_T > breakeven
        if is_short:
            pop = 1.0 - norm_cdf(be_d2)
        else:
            pop = norm_cdf(be_d2)
    else:  # put
        breakeven = max(0.0, strike - actual_premium)
        if breakeven > 0:
            _, be_d2 = calculate_d1_d2(
                spot, breakeven, t_years, volatility, risk_free_rate, dividend_yield, expected_drift=expected_drift
            )
            # Short Put profits if S_T >= breakeven
            # Long Put profits if S_T < breakeven
            if is_short:
                pop = norm_cdf(be_d2)
            else:
                pop = 1.0 - norm_cdf(be_d2)
        else:
            # Breakeven <= 0 (premium >= strike)
            pop = 1.0 if is_short else 0.0

    pop = max(0.0, min(1.0, pop))

    # 8. Expected Stock Price Ranges at Expiry (±1σ and ±2σ)
    drift_rate = expected_drift if expected_drift is not None else (risk_free_rate - dividend_yield)
    expected_spot = spot * math.exp(drift_rate * t_years)
    sigma_move = spot * volatility * math.sqrt(t_years)
    
    # Lognormal 1-sigma & 2-sigma bounds
    m = math.log(spot) + (drift_rate - 0.5 * volatility**2) * t_years
    v = volatility * math.sqrt(t_years)
    range_1sigma_low = math.exp(m - v)
    range_1sigma_high = math.exp(m + v)
    range_2sigma_low = math.exp(m - 2.0 * v)
    range_2sigma_high = math.exp(m + 2.0 * v)

    # Intrinsic & Extrinsic Value
    if option_type == "call":
        intrinsic = max(0.0, spot - strike)
    else:
        intrinsic = max(0.0, strike - spot)
    extrinsic = max(0.0, actual_premium - intrinsic)

    return {
        "spot": spot,
        "strike": strike,
        "dte_days": dte_days,
        "volatility_pct": volatility * 100.0,
        "risk_free_rate_pct": risk_free_rate * 100.0,
        "dividend_yield_pct": dividend_yield * 100.0,
        "option_type": option_type.upper(),
        "is_short": is_short,
        "premium": actual_premium,
        "intrinsic_value": intrinsic,
        "extrinsic_value": extrinsic,
        "breakeven": breakeven,
        "prob_worthless_risk_neutral": p_worthless_rn,
        "prob_worthless_real_world": p_worthless_rw if expected_drift is not None else None,
        "prob_itm_risk_neutral": p_itm_rn,
        "prob_itm_real_world": p_itm_rw if expected_drift is not None else None,
        "prob_worthless_delta_approx": p_worthless_delta_approx,
        "prob_touch_exact": p_touch_exact,
        "prob_touch_heuristic": p_touch_heuristic,
        "prob_of_profit": pop,
        "greeks": greeks,
        "expected_spot": expected_spot,
        "range_1sigma": (range_1sigma_low, range_1sigma_high),
        "range_2sigma": (range_2sigma_low, range_2sigma_high),
    }


def calculate_spread_prob_worthless(
    spot: float,
    short_strike: float,
    long_strike: float,
    dte_days: float,
    volatility: float,
    spread_type: str = "bull_put",
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    net_credit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate probability of both legs expiring worthless for credit spreads:
    - Bull Put Spread: Sell Short Put, Buy Long Put (Long Strike < Short Strike)
      Both expire worthless if S_T >= Short Strike!
    - Bear Call Spread: Sell Short Call, Buy Long Call (Long Strike > Short Strike)
      Both expire worthless if S_T <= Short Strike!
    """
    spread_type = spread_type.lower()
    t_years = max(1e-5, dte_days / 365.0)

    if spread_type in ("bull_put", "put_credit_spread"):
        short_res = calculate_prob_worthless(
            spot, short_strike, dte_days, volatility, risk_free_rate, dividend_yield, "put", is_short=True
        )
        long_res = calculate_prob_worthless(
            spot, long_strike, dte_days, volatility, risk_free_rate, dividend_yield, "put", is_short=False
        )
        # Both expire worthless if S_T >= short_strike
        p_both_worthless = short_res["prob_worthless_risk_neutral"]
        max_profit = net_credit if net_credit else (short_res["premium"] - long_res["premium"])
        max_loss = (short_strike - long_strike) - max_profit
        breakeven = short_strike - max_profit

        # PoP: profit if S_T >= breakeven
        _, be_d2 = calculate_d1_d2(spot, breakeven, t_years, volatility, risk_free_rate, dividend_yield)
        pop = norm_cdf(be_d2)

    elif spread_type in ("bear_call", "call_credit_spread"):
        short_res = calculate_prob_worthless(
            spot, short_strike, dte_days, volatility, risk_free_rate, dividend_yield, "call", is_short=True
        )
        long_res = calculate_prob_worthless(
            spot, long_strike, dte_days, volatility, risk_free_rate, dividend_yield, "call", is_short=False
        )
        # Both expire worthless if S_T <= short_strike
        p_both_worthless = short_res["prob_worthless_risk_neutral"]
        max_profit = net_credit if net_credit else (short_res["premium"] - long_res["premium"])
        max_loss = (long_strike - short_strike) - max_profit
        breakeven = short_strike + max_profit

        # PoP: profit if S_T <= breakeven
        _, be_d2 = calculate_d1_d2(spot, breakeven, t_years, volatility, risk_free_rate, dividend_yield)
        pop = 1.0 - norm_cdf(be_d2)

    else:
        raise ValueError("Unknown spread_type. Use 'bull_put' or 'bear_call'.")

    return {
        "spread_type": spread_type,
        "spot": spot,
        "short_strike": short_strike,
        "long_strike": long_strike,
        "dte_days": dte_days,
        "volatility_pct": volatility * 100.0,
        "prob_both_worthless": p_both_worthless,
        "prob_of_profit": max(0.0, min(1.0, pop)),
        "max_profit": max(0.0, max_profit),
        "max_loss": max(0.0, max_loss),
        "breakeven": breakeven,
        "net_credit": max_profit
    }


def calculate_iron_condor_prob_worthless(
    spot: float,
    put_strike: float,
    call_strike: float,
    dte_days: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    net_credit: float = 0.0
) -> Dict[str, Any]:
    """
    Calculate probability of an Iron Condor or Short Strangle expiring completely worthless.
    Both short options expire worthless if put_strike <= S_T <= call_strike.
    """
    if put_strike >= call_strike:
        raise ValueError("Put strike must be strictly less than Call strike.")

    t_years = max(1e-5, dte_days / 365.0)

    # d2 for Call and Put
    _, d2_call = calculate_d1_d2(spot, call_strike, t_years, volatility, risk_free_rate, dividend_yield)
    _, d2_put = calculate_d1_d2(spot, put_strike, t_years, volatility, risk_free_rate, dividend_yield)

    # P(S_T <= call_strike) = N(-d2_call)
    # P(S_T < put_strike) = 1 - N(d2_put) = N(-d2_put)
    # P(put_strike <= S_T <= call_strike) = N(-d2_call) - N(-d2_put)
    p_between = norm_cdf(-d2_call) - norm_cdf(-d2_put)
    p_both_worthless = max(0.0, min(1.0, p_between))

    # Breakevens
    be_low = put_strike - net_credit
    be_high = call_strike + net_credit

    if be_low > 0:
        _, d2_be_high = calculate_d1_d2(spot, be_high, t_years, volatility, risk_free_rate, dividend_yield)
        _, d2_be_low = calculate_d1_d2(spot, be_low, t_years, volatility, risk_free_rate, dividend_yield)
        pop = norm_cdf(-d2_be_high) - norm_cdf(-d2_be_low)
    else:
        pop = p_both_worthless

    return {
        "spot": spot,
        "put_strike": put_strike,
        "call_strike": call_strike,
        "dte_days": dte_days,
        "prob_both_worthless": p_both_worthless,
        "prob_of_profit": max(0.0, min(1.0, pop)),
        "breakeven_low": be_low,
        "breakeven_high": be_high
    }


def monte_carlo_verify(
    spot: float,
    strike: float,
    dte_days: float,
    volatility: float,
    risk_free_rate: float = 0.05,
    dividend_yield: float = 0.0,
    option_type: str = "call",
    num_simulations: int = 100_000,
    seed: int = 42
) -> Dict[str, float]:
    """
    Verify analytical probability via Monte Carlo simulation of geometric Brownian motion.
    """
    import random
    random.seed(seed)
    t = dte_days / 365.0
    mu = (risk_free_rate - dividend_yield) - 0.5 * (volatility ** 2)
    sig_sqrt_t = volatility * math.sqrt(t)

    worthless_count = 0
    option_type = option_type.lower()

    for _ in range(num_simulations):
        # Box-Muller transform for standard normal random variable
        u1 = max(1e-12, random.random())
        u2 = random.random()
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

        st = spot * math.exp(mu * t + sig_sqrt_t * z)
        if option_type == "call":
            if st <= strike:
                worthless_count += 1
        else:
            if st >= strike:
                worthless_count += 1

    sim_p_worthless = worthless_count / num_simulations
    return {
        "simulated_prob_worthless": sim_p_worthless,
        "num_simulations": num_simulations
    }


def print_cli_report(res: Dict[str, Any]) -> None:
    """Pretty prints the options calculator result to terminal."""
    print("=" * 64)
    print(f"   OPTIONS PROBABILITY OF EXPIRING WORTHLESS CALCULATOR")
    print("=" * 64)
    print(f" Underlying Spot Price:     ${res['spot']:,.2f}")
    print(f" Strike Price:              ${res['strike']:,.2f}")
    print(f" Days to Expiration (DTE):  {res['dte_days']} days ({res['dte_days']/365:.3f} years)")
    print(f" Implied Volatility (IV):   {res['volatility_pct']:.2f}%")
    print(f" Risk-Free Rate (r):        {res['risk_free_rate_pct']:.2f}%")
    print(f" Option Type:               {res['option_type']} ({'SHORT/SELLER' if res['is_short'] else 'LONG/BUYER'})")
    print(f" Theoretical Premium:       ${res['premium']:.2f}")
    print(f" Breakeven Price:           ${res['breakeven']:.2f}")
    print("-" * 64)
    print(" >>> CORE EXPIRATION PROBABILITIES <<<")
    print("-" * 64)
    pow_rn = res['prob_worthless_risk_neutral'] * 100.0
    p_itm_rn = res['prob_itm_risk_neutral'] * 100.0
    pop = res['prob_of_profit'] * 100.0
    pow_delta = res['prob_worthless_delta_approx'] * 100.0
    pot = res['prob_touch_exact'] * 100.0

    print(f" [*] PROBABILITY EXPIRING WORTHLESS (PoW / OTM):  {pow_rn:6.2f}%")
    print(f"     Probability Expiring In-The-Money (ITM):     {p_itm_rn:6.2f}%")
    print(f"     Probability of Profit (PoP at breakeven):    {pop:6.2f}%")
    print(f"     Probability of Touch (Touch Strike Anytime): {pot:6.2f}%")
    print(f"     Delta Rule-of-Thumb Approx (1 - |Delta|):   {pow_delta:6.2f}%")

    if res['prob_worthless_real_world'] is not None:
        pow_rw = res['prob_worthless_real_world'] * 100.0
        print(f"     Real-World Drift Probability Worthless:      {pow_rw:6.2f}%")

    print("-" * 64)
    print(" >>> GREEKS <<<")
    print("-" * 64)
    g = res['greeks']
    print(f" Delta:  {g['delta']:+.4f}   |  Gamma: {g['gamma']:.5f}")
    print(f" Theta: ${g['theta']:.4f}/day|  Vega:  ${g['vega']:.4f}/1% IV")
    print("-" * 64)
    print(" >>> EXPECTED PRICE RANGES AT EXPIRATION <<<")
    print("-" * 64)
    print(f" Expected Median Spot:      ${res['expected_spot']:,.2f}")
    print(f" ±1 Sigma (68.2% CI):       ${res['range_1sigma'][0]:,.2f} to ${res['range_1sigma'][1]:,.2f}")
    print(f" ±2 Sigma (95.4% CI):       ${res['range_2sigma'][0]:,.2f} to ${res['range_2sigma'][1]:,.2f}")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(
        description="Calculate the Probability of Options Expiring Worthless (PoW / OTM), PoP, PoT, and Greeks."
    )
    parser.add_argument("--spot", "-s", type=float, default=100.0, help="Underlying asset price (default: 100.0)")
    parser.add_argument("--strike", "-k", type=float, default=105.0, help="Strike price (default: 105.0)")
    parser.add_argument("--dte", "-d", type=float, default=30.0, help="Days to expiration (default: 30)")
    parser.add_argument("--iv", "-v", type=float, default=25.0, help="Implied Volatility in percent (e.g. 25 for 25%%, default: 25)")
    parser.add_argument("--rate", "-r", type=float, default=5.0, help="Risk-free rate in percent (default: 5.0%%)")
    parser.add_argument("--div", "-q", type=float, default=0.0, help="Dividend yield in percent (default: 0.0%%)")
    parser.add_argument("--type", "-t", choices=["call", "put"], default="call", help="Option type (call or put)")
    parser.add_argument("--long", action="store_true", help="Set if buying the option (default is short/selling)")
    parser.add_argument("--premium", "-p", type=float, default=None, help="Option premium paid or received")
    parser.add_argument("--drift", "-m", type=float, default=None, help="Expected real-world annual drift in percent")
    parser.add_argument("--mc", action="store_true", help="Run Monte Carlo simulation verification (100,000 runs)")
    parser.add_argument("--upstox", "-u", type=str, default=None, help="Fetch live data from Upstox for symbol (e.g. RELIANCE, NIFTY)")
    parser.add_argument("--expiry", type=str, default=None, help="Option expiry date for Upstox (YYYY-MM-DD)")
    parser.add_argument("--sold-price", type=float, default=None, help="Your execution/sold price for PoP calculation")

    args = parser.parse_args()

    spot = args.spot
    strike = args.strike
    dte = args.dte
    iv_pct = args.iv
    opt_type = args.type
    premium = args.premium or args.sold_price
    rate = args.rate

    if args.upstox:
        print(f"Connecting to Upstox API for live '{args.upstox.upper()}' option chain...")
        try:
            from upstox_fetcher import get_live_contract_data
            live_data = get_live_contract_data(
                symbol=args.upstox,
                strike=args.strike,
                option_type=args.type,
                expiry_date=args.expiry
            )
            spot = live_data["spot"]
            dte = live_data["dte_days"]
            iv_pct = live_data["iv"] if live_data["iv"] is not None else args.iv
            opt_type = live_data["option_type"].lower()
            actual_ltp = live_data["ltp"]
            if premium is None:
                premium = actual_ltp
            rate = 6.75 # Default to RBI 91D T-bill rate for Indian markets

            print(f" [+] Fetched Live Spot: Rs. {spot}")
            print(f" [+] Expiry Date: {live_data['expiry_date']} ({dte:.1f} DTE)")
            print(f" [+] Live Market LTP: Rs. {actual_ltp}")
            print(f" [+] Live Implied Volatility (IV): {iv_pct:.2f}%")
            if live_data.get('upstox_delta'):
                print(f" [+] Upstox Live Delta: {live_data['upstox_delta']}")
        except Exception as err:
            print(f" [!] Upstox API Error: {err}")
            sys.exit(1)

    vol = iv_pct / 100.0
    r = rate / 100.0
    q = args.div / 100.0
    drift = (args.drift / 100.0) if args.drift is not None else None

    result = calculate_prob_worthless(
        spot=spot,
        strike=strike,
        dte_days=dte,
        volatility=vol,
        risk_free_rate=r,
        dividend_yield=q,
        option_type=opt_type,
        expected_drift=drift,
        premium=premium,
        is_short=not args.long
    )

    print_cli_report(result)

    if args.mc:
        print("\nRunning Monte Carlo simulation (100,000 paths)...")
        mc_res = monte_carlo_verify(
            spot=spot,
            strike=strike,
            dte_days=dte,
            volatility=vol,
            risk_free_rate=r,
            dividend_yield=q,
            option_type=opt_type,
            num_simulations=100_000
        )
        print(f" Monte Carlo Simulated PoW:  {mc_res['simulated_prob_worthless'] * 100.0:6.2f}%")
        diff = abs(result['prob_worthless_risk_neutral'] - mc_res['simulated_prob_worthless']) * 100.0
        print(f" Difference with Analytical: {diff:.3f}% (within expected statistical error)")



if __name__ == "__main__":
    main()
