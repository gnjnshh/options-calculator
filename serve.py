"""
Local server for Options Probability Calculator with live Upstox API proxy.
Usage:
    python serve.py
"""

import http.server
import socketserver
import webbrowser
import os
import sys
import json
import urllib.parse
from typing import Dict, Any, List, Optional
from upstox_fetcher import (
    get_live_contract_data,
    get_expiry_dates,
    get_live_option_chain,
    parse_option_query,
    get_upstox_token,
    INSTRUMENT_MAP,
    LOT_SIZE_MAP
)
from options_calculator import calculate_prob_worthless

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class AppHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/upstox/token":
            self.handle_token()
        elif parsed.path == "/api/upstox/parse":
            self.handle_parse(parsed.query)
        elif parsed.path == "/api/upstox/expiries":
            self.handle_expiries(parsed.query)
        elif parsed.path == "/api/upstox/strikes":
            self.handle_strikes(parsed.query)
        elif parsed.path == "/api/upstox/analyze":
            self.handle_analyze(parsed.query)
        elif parsed.path == "/api/upstox":
            self.handle_analyze(parsed.query)
        else:
            super().do_GET()

    def send_json(self, status_code: int, data: Dict[str, Any]):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def handle_token(self):
        try:
            tok = get_upstox_token()
            self.send_json(200, {"status": "success", "token": tok})
        except Exception as e:
            self.send_json(404, {"status": "error", "message": str(e)})

    def handle_parse(self, query_str):
        params = urllib.parse.parse_qs(query_str)
        q = params.get("q", [""])[0]
        parsed = parse_option_query(q)
        self.send_json(200, {"status": "success", "parsed": parsed})

    def handle_expiries(self, query_str):
        params = urllib.parse.parse_qs(query_str)
        symbol = params.get("symbol", ["RELIANCE"])[0]
        token = params.get("token", [None])[0]
        try:
            expiries = get_expiry_dates(symbol, token)
            self.send_json(200, {"status": "success", "expiries": expiries})
        except Exception as e:
            self.send_json(500, {"status": "error", "message": str(e)})

    def handle_strikes(self, query_str):
        params = urllib.parse.parse_qs(query_str)
        symbol = params.get("symbol", ["RELIANCE"])[0]
        expiry = params.get("expiry", [None])[0]
        token = params.get("token", [None])[0]
        try:
            chain_info = get_live_option_chain(symbol, expiry, token)
            chain = chain_info.get("data", [])
            strikes = []
            spot = 0
            for item in chain:
                strikes.append(item.get("strike_price"))
                if not spot:
                    spot = item.get("underlying_spot_price", 0)
            strikes.sort()
            self.send_json(200, {
                "status": "success",
                "symbol": symbol.upper(),
                "spot": spot,
                "expiry": chain_info["expiry_date"],
                "strikes": strikes
            })
        except Exception as e:
            self.send_json(500, {"status": "error", "message": str(e)})

    def handle_analyze(self, query_str):
        params = urllib.parse.parse_qs(query_str)
        symbol = params.get("symbol", ["RELIANCE"])[0].upper()
        strike = float(params.get("strike", [1140.0])[0])
        opt_type = params.get("type", ["put"])[0].lower()
        expiry = params.get("expiry", [None])[0]
        is_short = params.get("is_short", ["true"])[0].lower() in ("true", "1", "yes")
        
        sold_price = params.get("sold_price", [None])[0]
        sold_price = float(sold_price) if sold_price else None
        token = params.get("token", [None])[0]

        try:
            live = get_live_contract_data(symbol, strike, opt_type, expiry, token)
            iv = (live["iv"] / 100.0) if live.get("iv") else 0.25
            r = 0.0675 # 6.75% RBI rate
            entry_price = sold_price if sold_price is not None else live["ltp"]
            lot_size = live.get("lot_size", 500)

            res = calculate_prob_worthless(
                spot=live["spot"],
                strike=strike,
                dte_days=live["dte_days"],
                volatility=iv,
                risk_free_rate=r,
                option_type=opt_type,
                premium=entry_price,
                is_short=is_short
            )

            # Calculate P&L scenarios
            current_unrealized = 0.0
            if sold_price is not None and live.get("ltp") is not None:
                if is_short:
                    current_unrealized = (sold_price - live["ltp"]) * lot_size
                else:
                    current_unrealized = (live["ltp"] - sold_price) * lot_size

            # Expiration scenarios
            max_profit = (entry_price * lot_size) if is_short else float("inf")
            
            scenarios = []
            test_moves = [0.05, 0.02, 0.0, -0.02, -0.05]
            for move in test_moves:
                scen_spot = round(live["spot"] * (1.0 + move), 2)
                if opt_type == "call":
                    scen_intrinsic = max(0.0, scen_spot - strike)
                else:
                    scen_intrinsic = max(0.0, strike - scen_spot)
                
                if is_short:
                    scen_pnl = (entry_price - scen_intrinsic) * lot_size
                else:
                    scen_pnl = (scen_intrinsic - entry_price) * lot_size
                
                scenarios.append({
                    "move_pct": move * 100.0,
                    "spot_price": scen_spot,
                    "intrinsic": scen_intrinsic,
                    "pnl": round(scen_pnl, 2),
                    "status": "Worthless (Full Profit)" if scen_intrinsic == 0 and is_short else ("ITM" if scen_intrinsic > 0 else "OTM")
                })

            data = {
                "status": "success",
                "market": live,
                "lot_size": lot_size,
                "entry_price": entry_price,
                "is_short": is_short,
                "current_unrealized_pnl": current_unrealized,
                "max_profit": max_profit if max_profit != float("inf") else None,
                "probabilities": {
                    "pow": res["prob_worthless_risk_neutral"],
                    "pop": res["prob_of_profit"],
                    "pot": res["prob_touch_exact"],
                    "delta_proxy": res["prob_worthless_delta_approx"],
                    "breakeven": res["breakeven"]
                },
                "greeks": {
                    "delta": res["greeks"]["delta"],
                    "gamma": res["greeks"]["gamma"],
                    "theta_daily_share": res["greeks"]["theta"],
                    "theta_daily_lot": res["greeks"]["theta"] * lot_size * (-1 if is_short else 1),
                    "vega": res["greeks"]["vega"],
                },
                "expected_ranges": {
                    "sigma1": res["range_1sigma"],
                    "sigma2": res["range_2sigma"]
                },
                "scenarios": scenarios
            }

            self.send_json(200, data)
        except Exception as e:
            self.send_json(500, {"status": "error", "message": str(e)})

def run():
    port = PORT
    for attempt in range(10):
        try:
            with socketserver.TCPServer(("", port), AppHandler) as httpd:
                url = f"http://localhost:{port}/index.html"
                print("=" * 60)
                print(f" Options Calculator + Upstox Live Server running!")
                print(f" Local Web URL: {url}")
                print(f" Press Ctrl+C to stop.")
                print("=" * 60)
                webbrowser.open(url)
                httpd.serve_forever()
                break
        except OSError:
            port += 1

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nServer stopped.")
