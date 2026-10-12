"""
Upstox API v2 Live Market Data & Option Chain Fetcher.
Reads access token directly from desktop and fetches real-time option chains, spot prices, and Greeks.
"""

import os
import json
import re
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional
from datetime import datetime, date

# Default paths for Upstox API token
TOKEN_PATHS = [
    os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive", "Desktop", "Upstox API.txt"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", "Upstox API.txt"),
    "Upstox API.txt"
]

# Extended NSE F&O Symbols Map
INSTRUMENT_MAP = {
    # Indices
    "NIFTY": "NSE_INDEX|Nifty 50",
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",

    # Top F&O Equities
    "RELIANCE": "NSE_EQ|INE002A01018",
    "TCS": "NSE_EQ|INE467B01029",
    "INFY": "NSE_EQ|INE009A01021",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "SBIN": "NSE_EQ|INE062A01020",
    "TATAMOTORS": "NSE_EQ|INE155A01022",
    "BAJFINANCE": "NSE_EQ|INE296A01024",
    "BHARTIARTL": "NSE_EQ|INE397D01024",
    "ITC": "NSE_EQ|INE154A01025",
    "LT": "NSE_EQ|INE018A01030",
    "AXISBANK": "NSE_EQ|INE238A01034",
    "KOTAKBANK": "NSE_EQ|INE237A01028",
    "MARUTI": "NSE_EQ|INE585B01010",
    "WIPRO": "NSE_EQ|INE075A01022",
    "SUNPHARMA": "NSE_EQ|INE044A01036",
    "HCLTECH": "NSE_EQ|INE860A01027",
    "TITAN": "NSE_EQ|INE280A01028",
    "ASIANPAINT": "NSE_EQ|INE021A01026",
    "TATASTEEL": "NSE_EQ|INE081A01020"
}

# Standard NSE Lot Sizes
LOT_SIZE_MAP = {
    "RELIANCE": 500,
    "NIFTY": 25,
    "NIFTY 50": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "TCS": 175,
    "INFY": 400,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "SBIN": 750,
    "TATAMOTORS": 575,
    "BAJFINANCE": 125,
    "BHARTIARTL": 475,
    "ITC": 1600,
    "LT": 175,
    "AXISBANK": 625,
    "KOTAKBANK": 400,
    "MARUTI": 50,
    "WIPRO": 1500
}

def get_upstox_token() -> str:
    """Reads the Upstox API token from the Desktop txt file."""
    for path in TOKEN_PATHS:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    return token
    raise FileNotFoundError("Could not find 'Upstox API.txt' on Desktop or OneDrive Desktop.")

def make_upstox_request(endpoint_url: str, custom_token: Optional[str] = None) -> Dict[str, Any]:
    """Makes an authenticated GET request to Upstox API v2."""
    token = custom_token or get_upstox_token()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(endpoint_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Upstox API HTTP {e.code} Error: {body}")
    except Exception as e:
        raise RuntimeError(f"Upstox API Connection Error: {e}")

def get_expiry_dates(symbol: str = "RELIANCE", custom_token: Optional[str] = None) -> List[str]:
    """Fetches available option expiry dates for a symbol."""
    sym_clean = symbol.strip().upper()
    inst_key = INSTRUMENT_MAP.get(sym_clean, sym_clean)
    url = f"https://api.upstox.com/v2/option/contract?instrument_key={urllib.parse.quote(inst_key)}"
    res = make_upstox_request(url, custom_token)
    contracts = res.get("data", [])
    expiries = sorted(list(set(c["expiry"] for c in contracts if "expiry" in c)))
    return expiries

def get_live_option_chain(symbol: str = "RELIANCE", expiry_date: Optional[str] = None, custom_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches the live option chain for a given symbol and expiry date.
    """
    sym_clean = symbol.strip().upper()
    inst_key = INSTRUMENT_MAP.get(sym_clean, sym_clean)
    if not expiry_date:
        expiries = get_expiry_dates(sym_clean, custom_token)
        if not expiries:
            raise ValueError(f"No option expiries found for symbol '{symbol}'")
        expiry_date = expiries[0]

    url = f"https://api.upstox.com/v2/option/chain?instrument_key={urllib.parse.quote(inst_key)}&expiry_date={expiry_date}"
    res = make_upstox_request(url, custom_token)
    return {
        "symbol": sym_clean,
        "instrument_key": inst_key,
        "expiry_date": expiry_date,
        "data": res.get("data", [])
    }

def parse_option_query(text: str) -> Dict[str, Any]:
    """
    Deterministically parses exact standard ticker strings such as:
    - 'RELIANCE 27 OCT 1140 PUT'
    - 'RELIANCE 27 OCT 1140 PE'
    - 'NIFTY 27 OCT 22400 CE'
    - 'RELIANCE 27 OCT 1140 PUT SHORT 3.35'
    - 'BANKNIFTY 27 OCT 48000 PE BUY 85'
    """
    text = text.strip()
    
    # 1. Match expiry like '27 OCT' or '27-OCT' or 'OCT 27'
    exp_match = re.search(r'\b(\d{1,2})\s*[- ]\s*([A-Za-z]{3})\b', text, re.I)
    exp_day = None
    exp_month = None
    expiry_str = None
    if exp_match:
        exp_day = int(exp_match.group(1))
        exp_month = exp_match.group(2).upper()
        expiry_str = f"{exp_day} {exp_month}"
        cleaned_text = text[:exp_match.start()] + ' ' + text[exp_match.end():]
    else:
        cleaned_text = text

    # 2. Extract Option Type (PUT/PE vs CALL/CE)
    opt_type = 'put' if re.search(r'\b(put|pe)\b', cleaned_text, re.I) else ('call' if re.search(r'\b(call|ce)\b', cleaned_text, re.I) else 'put')
    
    # 3. Position Stance (Short/Sell vs Long/Buy)
    is_short = False if re.search(r'\b(long|buy)\b', cleaned_text, re.I) else True

    # 4. Symbol is the first non-keyword word
    words = cleaned_text.split()
    symbol = 'RELIANCE'
    for w in words:
        if re.match(r'^[A-Za-z]+$', w) and w.upper() not in ('PUT', 'PE', 'CALL', 'CE', 'SHORT', 'SELL', 'LONG', 'BUY', 'LOT'):
            symbol = w.upper()
            break

    # 5. Extract numbers from cleaned_text (excluding the expiry day)
    num_matches = re.findall(r'\b\d+(?:\.\d+)?\b', cleaned_text)
    strike = None
    price = None
    if num_matches:
        nums = [float(n) for n in num_matches]
        if len(nums) == 1:
            strike = nums[0]
        else:
            nums.sort()
            strike = nums[-1] # Largest is strike
            price = nums[0]   # Smaller is entry / sold price

    return {
        "symbol": symbol,
        "expiry_day": exp_day,
        "expiry_month": exp_month,
        "expiry_str": expiry_str,
        "strike": strike,
        "option_type": opt_type,
        "is_short": is_short,
        "price": price
    }

def get_live_contract_data(
    symbol: str = "RELIANCE",
    strike: float = 1140.0,
    option_type: str = "put",
    expiry_date: Optional[str] = None,
    custom_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetches live market data and Greeks for a specific strike & option type.
    """
    chain_info = get_live_option_chain(symbol, expiry_date, custom_token)
    chain = chain_info["data"]
    option_type = option_type.lower()

    target = None
    for item in chain:
        if abs(item.get("strike_price", 0) - strike) < 0.1:
            target = item
            break

    if not target:
        available_strikes = [item.get("strike_price") for item in chain]
        raise ValueError(f"Strike {strike} not found. Available strikes: {available_strikes[:10]}...")

    spot = target.get("underlying_spot_price")
    opt_data = target.get("put_options" if option_type == "put" else "call_options", {})
    mkt = opt_data.get("market_data", {})
    greeks = opt_data.get("option_greeks", {})

    # Calculate exact Days to Expiration (DTE)
    exp_str = chain_info["expiry_date"]
    exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
    today = date.today()
    days_diff = (exp_date - today).days
    dte_days = max(0.1, float(days_diff))

    sym_upper = symbol.strip().upper()
    lot_size = LOT_SIZE_MAP.get(sym_upper, 500)

    return {
        "symbol": sym_upper,
        "spot": spot,
        "strike": strike,
        "option_type": option_type.upper(),
        "expiry_date": exp_str,
        "dte_days": dte_days,
        "lot_size": lot_size,
        "ltp": mkt.get("ltp"),
        "bid": mkt.get("bid_price"),
        "ask": mkt.get("ask_price"),
        "volume": mkt.get("volume"),
        "oi": mkt.get("oi"),
        "prev_close": mkt.get("close_price"),
        "iv": greeks.get("iv"),
        "upstox_delta": greeks.get("delta"),
        "upstox_theta": greeks.get("theta"),
        "upstox_gamma": greeks.get("gamma"),
        "upstox_vega": greeks.get("vega"),
        "upstox_pop": greeks.get("pop")
    }

if __name__ == "__main__":
    print("Testing Natural Query Parser:")
    print("Query: 'Reliance put 1140 short' ->", parse_option_query("Reliance put 1140 short"))
    print("Query: 'Nifty 22500 call buy 80' ->", parse_option_query("Nifty 22500 call buy 80"))
