# Statistical Arbitrage in Equity Markets: Cointegration-Based Pairs Trading with Out-of-Sample Validation

[![Unit Tests](https://img.shields.io/badge/pytest-69%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)]()
[![Research Status](https://img.shields.io/badge/research-frozen--v1-orange.svg)]()

A modular, production-grade quantitative research framework evaluating whether cointegration-based pairs trading generates robust risk-adjusted alpha in U.S. large-cap equities after realistic transaction friction, execution delays, and market structural breaks.

---

## 1. Overview & Research Question

Pairs trading is historically grounded in the economic hypothesis of relative valuation equilibrium: fundamentally linked companies within the same industrial sector share common stochastic drivers. While temporary liquidity shocks cause relative prices to dislocate, economic substitution forces are hypothesized to restore mean reversion.

### Research Question
> *Can an intra-sector cointegration pairs-trading strategy achieve positive, statistically significant risk-adjusted returns after realistic execution lag, transaction fees, and short borrow costs in U.S. large-cap equities—and what structural mechanisms explain its performance out-of-sample?*

---

## 2. Headline Results (Out-of-Sample 2023–2024)

Evaluated across an untouched 2-year out-of-sample window (501 active trading days, 2023-01-01 to 2024-12-31) with strictly frozen pre-test model parameters:

* **Gross Trading P&L**: **+$10,586.12** (Gross Sharpe: `0.20`, Gross Return: `+1.06%`)
* **Net P&L After Friction**: **-$7,613.28** (Net Sharpe: `-0.12`, Cost Drag: `171.92%`)
* **Break-Even Cost Threshold**: **5.12 bps** per side per leg (vs. `10.00 bps` baseline execution friction)

> **Empirical Bottom Line**: The strategy captured genuine gross economic mispricings, but transaction friction consumed **171.9%** of gross earnings. Out-of-sample failure was primarily driven by **structural parameter breakdown and cointegration decay** (0 of 5 candidate pairs remained cointegrated out-of-sample), rendering static hedge ratios fragile against persistent spread divergence.

---

## 3. Methodology & Mathematical Intuition

```
Raw Prices (Yahoo Finance) ──► Clean Price Panel (close.parquet) ──► ADF / KPSS Stationarity
                                                                            │
Reports & Verification ◄── Performance Metrics ◄── Portfolio Simulator ◄── Cointegration Screening
  • 69 Unit Tests           • HAC Beta Exposure     • 1-Day Execution Lag    • Holm-Bonferroni FWER
  • Failure Analysis        • Friction Breakdown    • Slippage + Borrow      • Half-Life Filter
```

### Step 1: Cointegration & Spread Formulation
For two log-price series $\ln(P_{A,t})$ and $\ln(P_{B,t})$ integrated of order one ($I(1)$), cointegration guarantees a stationary linear combination:

$$s_t = \ln(P_{A,t}) - \hat{\alpha} - \hat{\beta} \ln(P_{B,t}) \sim I(0)$$

where hedge parameters $\hat{\alpha}$ and $\hat{\beta}$ are estimated via Ordinary Least Squares (OLS) strictly over the in-sample calibration window. To eliminate regression normalization bias, we compute bidirectional Engle-Granger tests and evaluate against the conservative maximum p-value: $p_{\text{pair}} = \max(p_{A|B}, p_{B|A})$.

### Step 2: Multiple Testing Control (Holm-Bonferroni)
Screening $m = 45$ intra-sector pairs simultaneously inflates the family-wise error rate ($1 - 0.95^{45} \approx 90.1\%$). We apply the step-down Holm-Bonferroni correction:

$$\tilde{p}_{(i)} = \max_{k \le i} \min\left(1.0, \, (m - k + 1) \cdot p_{(k)}\right)$$

Pairs are further filtered through an Ornstein-Uhlenbeck mean-reversion half-life bound: $t_{1/2} = -\frac{\ln 2}{\ln(1 + \phi)} \in [1, 60]\text{ days}$.

### Step 3: Spread Z-Score & Causal Execution Logic
Signals are generated from spread deviations normalized by frozen in-sample mean ($\mu_{\text{train}}$) and volatility ($\sigma_{\text{train}}$):

$$z_t = \frac{s_t - \mu_{\text{train}}}{\sigma_{\text{train}}}$$

* **Long Spread Entry ($z_t \le -2.0$)**: Buy leg A, short leg B ($N_A = \frac{C \cdot |w_A|}{P_{A,t}}$, $N_B = -\text{sgn}(\beta)\frac{C \cdot |w_B|}{P_{B,t}}$).
* **Short Spread Entry ($z_t \ge +2.0$)**: Short leg A, buy leg B.
* **Mean-Reversion Exit ($|z_t| \le 0.5$)**: Close position when spread reverts within 0.5 standard deviations.
* **Time-Stop Liquidation**: Unconditionally liquidate open positions if held for $\ge 30$ trading days.
* **Execution Realism**: Signals evaluated at day $t$ close fill strictly at day $t+1$ close (`execution_lag = 1`). Transaction friction includes 5.0 bps commission + 5.0 bps slippage (10.0 bps/side) plus 50.0 bps annualized short borrow fees.

---

## 4. System Architecture

```
stat-arb-pairs-trading/
├── configs/
│   ├── baseline.yaml            # Canonical in-sample parameters (SHA-256 frozen)
│   └── test_run.yaml            # Single out-of-sample execution config (unlock_test: true)
├── src/
│   ├── config.py                # Type-safe dataclass configurations and validation
│   ├── data.py                  # Yahoo Finance retrieval, disk caching, and time slicing
│   ├── validation.py            # Calendar alignment, bad ticks, and monotonic index guards
│   ├── pairs.py                 # Engle-Granger, Holm-Bonferroni, and OU half-life filters
│   ├── signals.py               # Deterministic state-machine signal engine
│   ├── backtest.py              # Single-pair backtest simulator with friction tracking
│   ├── portfolio.py             # Multi-pair capital allocation and portfolio aggregator
│   ├── metrics.py               # Annualized CAGR, Sharpe, max drawdown, and turnover
│   ├── failure_analysis.py      # Newey-West HAC beta, CUSUM breaks, and trade autopsy
│   └── plotting.py              # Visualizations and publication-grade charts
├── scripts/
│   ├── fetch_data.py            # Acquire and validate market price dataset
│   ├── run_pipeline.py          # Unified end-to-end research pipeline runner
│   ├── run_sensitivity.py       # 84-point parameter robustness and break-even grid
│   └── run_failure_analysis.py  # Statistical stability and failure mode diagnostics
├── tests/                       # 69 deterministic unit and property-based tests
├── docs/                        # Research protocol, methodology, and frozen decisions
└── reports/
    ├── research_report.md       # Comprehensive 12-section institutional research paper
    ├── results/                 # Machine-readable CSVs, JSON metrics, and audit logs
    └── figures/                 # 44 publication-ready SVG/PNG diagnostic plots
```

---

## 5. Quickstart & Reproducibility

### Installation
Clone the repository and install locked dependencies in a virtual environment:
```bash
git clone https://github.com/your-username/stat-arb-pairs-trading.git
cd stat-arb-pairs-trading
python -m venv venv
# On Windows: venv\Scripts\activate | On macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### Data Acquisition
Fetch and validate daily adjusted price history across Banking, Energy, and Consumer Staples universes:
```bash
python scripts/fetch_data.py
```
*Note: Clean prices are persisted to local cache (`data/processed/close.parquet`).*

### Single End-to-End Pipeline Command
Execute data verification, pair screening, hedge fitting, backtest simulation, metrics calculation, and chart generation in a single command:
```bash
python scripts/run_pipeline.py --config configs/test_run.yaml
```

### Run Test Suite
Execute the deterministic test suite covering signal timing, execution lag, cost accounting, and statistical calculations:
```bash
pytest -q
# Output: 69 passed in ~6.0s
```

---

## 6. Key Empirical Visualizations

### Multi-Period Chained Net Equity (2018–2024)
*Net portfolio equity chained across Calibration (2018–2021), Validation (2022), and Out-of-Sample Test (2023–2024).*
![Chained Net Equity](reports/figures/chained_equity.png)

### Out-of-Sample Gross vs. Net Equity Curve
*The strategy delivered steady positive gross trading profits ($+\$10.6\text{k}$) but suffered negative net returns ($-\$7.6\text{k}$) after trade friction ($10.0\text{ bps}$) and short borrow costs ($50\text{ bps/year}$).*
![Gross vs Net Performance](reports/figures/test_gross_vs_net_equity.png)

### Transaction Cost Sensitivity & Break-Even Analysis
*Parameter sensitivity across transaction fees and borrow rates reveals a razor-thin break-even margin of 5.12 bps per side per leg.*
![Sensitivity Cost Curve](reports/figures/sensitivity_cost_curve.png)

### Failure Mode: Non-Reverting Divergence Case Study
*Spread breakdown in `COP_DVN` demonstrating non-reversion and liquidation at the 30-day time-stop horizon, accounting for -$36,982.71 in net losses.*
![Worst Trade Divergence](reports/figures/worst_trade_1_divergence.png)

---

## 7. Limitations & Data-Use Notice

### Institutional & Modeling Limitations
1. **Survivorship Bias**: Universe tickers were chosen from current S&P 500 constituents listed continuously from 2018 to 2024, excluding delisted or distressed firms.
2. **Small Universe**: 18 large-cap stocks (45 intra-sector pairs) constrained diversification across idiosyncratic spread shocks.
3. **Dividend Liabilities on Short Borrow**: Cash dividends were adjusted into price series rather than debited as physical cash flows on ex-dividend dates.
4. **Borrow Rate Invariance**: Borrow fee was modeled as a static 50 bps annual rate; hard-to-borrow spikes and recall risks were not simulated.
5. **Close-to-Close Execution**: Fills were executed at day $t+1$ close without modeling Market-on-Close (MOC) order book imbalances.
6. **Zero Endogenous Market Impact**: Fixed 5.0 bps slippage assumed infinite liquidity at close without square-root price impact penalties.
7. **Single Chronological Partition**: The timeline was split once (4y train, 1y validation, 2y test) rather than evaluated via combinatorial purged cross-validation.
8. **Pre-Registered Fallback**: Zero pairs cleared strict Holm-Bonferroni testing in training; the top 5 pairs by raw p-value were traded as an exploratory basket.

### Data-Use & Educational Disclaimer
*Market data is accessed via the Yahoo Finance API for personal, non-commercial academic research and educational evaluation only. This project does not constitute financial, investment, or trading advice. Past simulated performance is no guarantee of future trading results.*

---

## 8. Future Research Directions

1. **Johansen Multivariate Cointegration**: Extend bivariate regressions to cointegrated triplets and sector baskets ($k > 2$).
2. **Kalman Filter Dynamic Hedge Ratios**: Replace rigid in-sample OLS with state-space models tracking time-varying betas ($\beta_t$).
3. **Walk-Forward Periodic Re-Screening**: Re-estimate cointegration filters and hedge parameters on rolling 12-month windows.
4. **Point-in-Time Historical Constituent Universes**: Integrate survivorship-bias-free historical index constituent panels.
5. **High-Performance C++ Simulation Core**: Re-architect the event-driven backtesting loop into compiled C++ (pybind11) for high-frequency tick analysis.
