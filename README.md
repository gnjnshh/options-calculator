# Options Probability & Risk Analytics Dashboard ⚡

An institutional-grade Options Probability Calculator that computes the exact mathematical probability of options expiring worthless (Out-of-The-Money / OTM), along with Probability of Profit (PoP), Probability of Touch (PoT), Greeks, and spread analytics.

Includes live integration with the **Upstox API v2** for real-time NSE option chains and spot prices.

---

## 🌟 Key Features

1. **Exact Ticker Analysis Bar**:
   - Deterministically analyzes standard contract ticker formats (no AI/LLM parsing needed):
     - `RELIANCE 27 OCT 1140 PUT`
     - `RELIANCE 27 OCT 1140 PUT SHORT 3.35`
     - `NIFTY 27 OCT 22400 CE`
     - `BANKNIFTY 27 OCT 48000 PE`
     - `TCS 27 OCT 3900 PE`

2. **Institutional Probability Metrics**:
   - **PoW (Probability of Expiring Worthless)**: Exact Black-Scholes lognormal $N(d_2)$ probability that the option finishes OTM.
   - **PoP (Probability of Profit)**: Evaluates the chance of finishing beyond your entry breakeven price.
   - **PoT (Probability of Touch)**: Barrier reflection formula ($\approx 2 \times P(\text{ITM})$) for the probability of touching the strike anytime before expiry.
   - **Trader Delta Proxy**: Comparison against $1 - |\Delta|$.

3. **Live Upstox API v2 Market Sync**:
   - Real-time NSE spot prices, live LTP, bid/ask spreads, open interest (OI), traded volume, and implied volatility (IV).

4. **Expiration Payoff & P&L Scenarios Matrix**:
   - Clear tabular breakdown of payoff across market rallies, flat moves, and drops, marking exact Breakeven and Maximum Profit levels.

5. **Dynamic Log-Normal Probability Density Chart**:
   - Interactive SVG/Canvas curve with green shaded zones for **Worthless (Max Profit)** and red shaded zones for **In-The-Money (Risk Zone)**.

---

## 🚀 1-Click Free Hosting on GitHub Pages

Because the Upstox API supports direct browser CORS requests, you can host this entire dashboard **100% free forever** on GitHub Pages:

1. In this repository, go to **Settings** > **Pages** (in the left sidebar).
2. Under **Build and deployment** > **Source**:
   - Select **GitHub Actions** (the included `.github/workflows/deploy.yml` will automatically build and deploy it).
   - *OR* select **Deploy from a branch** > branch `main` > `/ (root)` and click **Save**.
3. Your dashboard will be live at:
   ```
   https://gnjnshh.github.io/options-calculator/
   ```

---

## 💻 Running Locally

### Option A: Interactive Web App + Local Server
```bash
python serve.py
```
Automatically launches your default browser at `http://localhost:8000/index.html` and proxies Upstox API requests using the token from your Desktop (`Upstox API.txt`).

### Option B: Terminal CLI
```bash
# Live Upstox calculation for RELIANCE 1140 Put (with your sold price of Rs. 3.35)
python options_calculator.py --upstox RELIANCE --strike 1140 --type put --sold-price 3.35

# Live Upstox calculation for NIFTY 50
python options_calculator.py --upstox NIFTY --strike 22400 --type call

# Custom offline scenario with 100,000-path Monte Carlo verification
python options_calculator.py --spot 100 --strike 105 --dte 30 --iv 25 --type call --mc
```

---

## 📐 Mathematical Formulation

Under Black-Scholes geometric Brownian motion:
$$dS_t = \mu S_t dt + \sigma S_t dW_t$$

The log-return at expiration $T$ has normal distribution:
$$\ln\left(\frac{S_T}{S_0}\right) \sim \mathcal{N}\left(\left(r - q - \frac{1}{2}\sigma^2\right)T, \sigma^2 T\right)$$

### $d_1$ and $d_2$:
$$d_1 = \frac{\ln(S_0 / K) + (r - q + \frac{1}{2}\sigma^2)T}{\sigma\sqrt{T}}$$
$$d_2 = d_1 - \sigma\sqrt{T} = \frac{\ln(S_0 / K) + (r - q - \frac{1}{2}\sigma^2)T}{\sigma\sqrt{T}}$$

### Probability of Expiring Worthless (PoW / OTM):
- **Call Option**: $\text{PoW}_{\text{Call}} = P(S_T \le K) = 1 - N(d_2) = N(-d_2)$
- **Put Option**: $\text{PoW}_{\text{Put}} = P(S_T \ge K) = 1 - N(-d_2) = N(d_2)$

### Probability of Touch (PoT):
$$\text{PoT} \approx \min\left(1.0, 2 \times P(\text{ITM})\right) = \min\left(1.0, 2 \times (1 - \text{PoW})\right)$$