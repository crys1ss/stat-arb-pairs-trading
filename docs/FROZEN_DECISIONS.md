# Frozen Research Decisions (Day 10)

This document formalizes and freezes all quantitative research decisions, universe specifications, data partitions, statistical parameters, execution rules, and model artifacts prior to executing the out-of-sample test evaluation on the 2023–2024 test period.

---

## 1. Cryptographic Hashes of Frozen Artifacts

To guarantee immutability and complete research integrity, the SHA-256 hashes of the frozen configuration and selected pair registry are recorded below:

| Artifact | File Path | SHA-256 Hash |
| :--- | :--- | :--- |
| **Baseline Configuration** | `configs/baseline.yaml` | `40f7c5f8b1ab2a0c53c5b7866c87d6a8bd3ad1bb1b30639f311a2f6426ec39d0` |
| **Selected Pairs Registry** | `reports/results/selected_pairs.csv` | `52c64903406c29327353774343c683f2f90942fd638c478392cfdb6493a23c51` |

---

## 2. Universe Definition

The investment universe consists of 18 large-cap U.S. equities selected based on clear economic rationale: constituents of the S&P 500 continuously listed from 2018-01-01 through 2024-12-31 with homogeneous business models within their respective sectors.

- **Banks (6 tickers)**: `JPM`, `BAC`, `C`, `WFC`, `USB`, `PNC`  
  *Rationale*: Highly liquid U.S. money-center and regional commercial banks sharing common interest rate cycle exposure, credit spread dynamics, and Federal Reserve regulatory regimes.
- **Energy (6 tickers)**: `XOM`, `CVX`, `COP`, `EOG`, `OXY`, `DVN`  
  *Rationale*: Integrated oil & gas and upstream exploration & production (E&P) firms driven by shared global crude oil (WTI/Brent) and Henry Hub natural gas commodity fundamentals.
- **Consumer Staples (6 tickers)**: `KO`, `PEP`, `PG`, `CL`, `KMB`, `MDLZ`  
  *Rationale*: Defensive consumer packaged goods manufacturers exhibiting stable cash flows, brand equity, pricing power, and resilient demand across business cycles.

---

## 3. Data Partitions & Calendar Dates

The historical dataset spans 1,760 active NYSE/NASDAQ trading days from 2018-01-02 to 2024-12-30 (calendar bounds 2018-01-01 to 2024-12-31). The dataset was acquired once to preserve consistent dividend and split adjustments:

- **In-Sample Calibration / Training Window**:  
  `2018-01-01` to `2021-12-31` (4 calendar years, 1,008 trading days).  
  *Purpose*: Exploratory data analysis, unit-root testing, cointegration screening, AR(1) half-life estimation, and OLS hedge parameter fitting.
- **Clean Validation Window**:  
  `2022-01-01` to `2022-12-31` (1 calendar year, 251 trading days).  
  *Purpose*: Parameter sanity checks, execution mechanics validation, cost drag analysis, and accounting invariant testing without data leakage into the test set.
- **Out-of-Sample Test Window**:  
  `2023-01-01` to `2024-12-31` (2 calendar years, 501 trading days).  
  *Purpose*: Strictly reserved for final one-shot out-of-sample performance evaluation on Day 10. Locked prior to this freeze via `unlock_test: false`.

---

## 4. Selected Pairs & Screening Methodology

### Screening Protocol
Candidate pairs were restricted to intra-sector pairs (15 banks, 15 energy, 15 staples = 45 pairs total) to ensure fundamental economic linkage and eliminate spurious statistical cointegration. For each candidate pair $(A, B)$ (ordered alphabetically such that $A < B$):
1. **Engle-Granger Cointegration Test**: Evaluated bidirectional Engle-Granger ADF tests ($A \sim B$ and $B \sim A$ with constant term `'c'`). The conservative pair test statistic was defined as $\max(p_{A|B}, p_{B|A})$.
2. **Family-Wise Error Rate (FWER) Control**: Applied Holm-Bonferroni step-down correction at significance level $\alpha = 0.05$ across the 45 hypotheses.
3. **Mean-Reversion Half-Life**: Estimated via AR(1) regression on training residuals $\Delta s_t = \phi s_{t-1} + \epsilon_t$, enforcing $1.0 \le \tau = -\frac{\ln(2)}{\ln(1 + \phi)} \le 60.0$ trading days.

### Screening Outcome & Pre-Registered Fallback
- 3 pairs passed raw Engle-Granger cointegration ($p < 0.05$): `BAC_PNC`, `MDLZ_PG`, `MDLZ_PEP`.
- 0 pairs passed Holm-Bonferroni correction ($p_{adj} < 0.05$), demonstrating that strong statistical cointegration under strict FWER control across 45 hypotheses is rare.
- 27 pairs satisfied the half-life bound $[1.0, 60.0]$ days.
- **Fallback Rule**: As pre-registered in `PROGRESS.md` prior to screening, the top 5 pairs with the lowest raw bidirectional p-values meeting the half-life criteria were selected as an exploratory portfolio:

| Pair | Sector | Raw $p$-value | Holm $p$-value | Half-Life (days) | Correlation | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BAC_PNC** | Banks | 0.004881 | 0.219645 | 20.49 | 0.8949 | Exploratory |
| **MDLZ_PG** | Staples | 0.008796 | 0.387024 | 21.64 | 0.6875 | Exploratory |
| **MDLZ_PEP** | Staples | 0.031582 | 1.000000 | 20.49 | 0.7696 | Exploratory |
| **COP_DVN** | Energy | 0.053133 | 1.000000 | 26.87 | 0.8249 | Exploratory |
| **COP_CVX** | Energy | 0.090284 | 1.000000 | 30.11 | 0.8457 | Exploratory |

All 5 pairs are explicitly flagged as `is_exploratory: True`.

---

## 5. Hedge Parameters & Spread Definitions

Hedge ratios were estimated via static OLS on the log prices of the training period (2018–2021):
$$\ln(P_{A,t}) = \alpha + \beta \ln(P_{B,t}) + \epsilon_t$$

The spread is defined as:
$$s_t = \ln(P_{A,t}) - \alpha - \beta \ln(P_{B,t})$$

The normalized spread z-score is computed using strictly fixed training-period statistics:
$$z_t = \frac{s_t - \mu_{\text{train}}}{\sigma_{\text{train}}}$$
where $\mu_{\text{train}} = 0$ by OLS construction and $\sigma_{\text{train}}$ is the standard deviation of training residuals. These parameters are strictly frozen across validation and test periods:

| Pair | $\alpha$ | $\beta$ | $R^2$ | $\sigma_{\text{train}}$ | Weight $w_A$ | Weight $w_B$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BAC_PNC** | -1.116556 | 0.928138 | 0.9640 | 0.038920 | +0.518635 | -0.481365 |
| **MDLZ_PG** | +0.741559 | 0.665193 | 0.9399 | 0.040961 | +0.600531 | -0.399469 |
| **MDLZ_PEP** | -0.974865 | 1.019173 | 0.9479 | 0.038150 | +0.495252 | -0.504748 |
| **COP_DVN** | +2.465923 | 0.460606 | 0.8665 | 0.085251 | +0.684647 | -0.315353 |
| **COP_CVX** | -2.997540 | 1.546718 | 0.8404 | 0.093211 | +0.392662 | -0.607338 |

Capital weights are defined as $w_A = \frac{1}{1 + \beta}$ and $w_B = -\frac{\beta}{1 + \beta}$ such that $|w_A| + |w_B| = 1.0$.

---

## 6. Signal & Execution Parameters

### Signal State Machine Rules
- **Entry Conditions**:
  - Enter **Long Spread** ($+1$ state: buy leg A, short leg B) when $z_t \le -2.0$.
  - Enter **Short Spread** ($-1$ state: short leg A, buy leg B) when $z_t \ge +2.0$.
- **Exit Conditions**:
  - Exit Long Spread when $z_t \ge -0.5$ (capturing mean reversion towards 0).
  - Exit Short Spread when $z_t \le +0.5$ (capturing mean reversion towards 0).
  - Exit on Max Holding Horizon: Liquidate if `days_held >= 30` trading days.
  - Stop Loss: `stop_z = null` (no divergence stop loss applied).
- **Boundary & Causality Constraints**:
  - No re-entry on the same bar as an exit.
  - No overlapping positions.
  - NaN z-scores hold existing positions without initiating new trades.
  - Truncation causality: Truncating the price series at bar $t$ produces identical states for all bars $\le t$.
  - Period-end exit: All open positions at the final bar of a period are liquidated (`close_at_end: true`).

### Execution & Cost Parameters
- **Execution Lag**: 1 trading day (`execution_lag = 1`). Decisions evaluated at close $t$ fill at close $t+1$.
- **Sizing**: Fixed capital of $\$200,000$ per pair ($\$1,000,000$ total capital / 5 pairs). Shares calculated at fill:
  $$N_A = \frac{\text{Capital} \cdot |w_A|}{P_{A, \text{fill}}}, \quad N_B = \frac{\text{Capital} \cdot |w_B|}{P_{B, \text{fill}}}$$
  Shares remain fixed until position liquidation.
- **Transaction Costs**:
  - Commissions: 5.0 bps ($0.0005$) per leg on traded notional at entry and exit.
  - Slippage: 5.0 bps ($0.0005$) per leg on traded notional at entry and exit.
- **Borrow Fees**: 50.0 bps annualized ($0.0050 / 252$) charged daily on the mark-to-market short equity notional.
- **Cash Return**: Risk-free rate $r_f = 0.0$ on unallocated cash reserves.

---

## 7. Chronological Record of Changes & Rationale (Day 1 to Day 10)

| Day / Commit | Component | Description of Change | Rationale / Scientific Grounding |
| :--- | :--- | :--- | :--- |
| **Day 1**<br>`e5a2996` | `configs/baseline.yaml`<br>`src/config.py` | Config scaffolding with typed Pydantic/dataclass schema, validation constraints ($exit\_z < entry\_z$, $lag \ge 1$, chronological dates), and `unlock_test: false`. | Enforce schema correctness at startup; programmatically prevent look-ahead bias and enforce test isolation. |
| **Day 2**<br>`183d449` | `src/data.py`<br>`src/validation.py` | Download daily closes via yfinance with single-threading (`threads=False`); build clean panel without forward-fill; add `PermissionError` guard in `slice_period` for test period. | Eliminate SQLite concurrency deadlocks on Windows; avoid look-ahead bias from synthetic data filling; enforce test isolation. |
| **Day 3**<br>`43d6d60` | `src/stats_tests.py`<br>`scripts/run_eda.py` | Implementation of ADF and KPSS unit root tests, summary statistics, and correlation heatmaps on training data. | Formally verify order of integration I(1) for all 18 candidate equities (all passed) and document non-Gaussian return kurtosis. |
| **Day 4**<br>`2537a1d` | `PROGRESS.md` | Pre-registered fallback rule for pair selection prior to running cointegration screening. | Eliminate researcher degrees of freedom and p-hacking by committing to fallback selection criteria beforehand. |
| **Day 4–5**<br>`c5290c3` | `src/pairs.py`<br>`scripts/screen_pairs.py`<br>`scripts/build_spreads.py` | Intra-sector Engle-Granger screening, bidirectional max p-value, Holm-Bonferroni correction, half-life estimation, and static OLS hedge estimation. | Zero pairs passed strict Holm FWER; activated pre-registered fallback to select top 5 pairs; froze hedge ratios on training period. |
| **Day 6**<br>`0dffc54`<br>`d935ed7` | `src/signals.py`<br>`scripts/generate_pair_signals.py` | Deterministic causal state machine for signal generation; added `close_at_end` parameter for clean period-end liquidation. | Prevent look-ahead bias; ensure strict truncation causality; formalize clean period termination. |
| **Day 7**<br>`f0e248a` | `src/backtest.py` | Single-pair simulation engine with $t+1$ fill lag, explicit trade commissions, slippage, daily borrow accrual, and trade logs. | Realistic microstructure modeling; separation of gross P&L, trade costs, and borrow fees. |
| **Day 8**<br>`bb363a9` | `src/portfolio.py`<br>`scripts/run_backtest.py` | Equal-weight multi-pair aggregation, daily cash tracking, exposure accounting, and 4 accounting invariants tested at $10^{-8}$ tolerance. | Guarantee mathematical consistency across trade logs, per-pair series, portfolio equity curves, and compounded returns. |
| **Day 9**<br>`22c09e3` | `src/metrics.py`<br>`scripts/report_metrics.py`<br>`src/plotting.py` | Performance metrics (Sharpe $r_f=0$, CAGR, max drawdown & duration, turnover, win rate, profit factor, HHI concentration, tables) and train/val plots. Safe NaN handling for zero-trade/zero-vol edge cases. | Establish standardized performance diagnostics; isolate and quantify friction drag on train vs validation data prior to test freeze. |
| **Day 10**<br>`Current` | `docs/FROZEN_DECISIONS.md` | Formal freeze of all universe, data partitions, selected pairs, hedge parameters, signal parameters, costs, and SHA-256 hashes. Git tag `frozen-v1`. | Scientific discipline: commit and tag research state prior to running out-of-sample test evaluation once. |

---

## 8. Formal Freeze Certification

All quantitative parameters, model specifications, universe definitions, and historical code artifacts are hereby frozen under Git tag `frozen-v1`. No subsequent adjustments to hedge ratios, signal thresholds, or execution rules may be made without documenting the test dataset as contaminated.

---

## 9. Post-Freeze Addendum (Day 15)

### 9.1 Cryptographic Hash Erratum (Line Endings)
The SHA-256 hash recorded in Section 1 for `reports/results/selected_pairs.csv` (`52c64903406c29327353774343c683f2f90942fd638c478392cfdb6493a23c51`) was computed on Windows using CRLF (`\r\n`) line endings. Under Git LF normalization (`* text=auto eol=lf`), the canonical LF SHA-256 hash is:
- **Canonical LF SHA-256 (`selected_pairs.csv`)**: `6952604f8d142d24d8fdd7bd1db45804665e49f6917f73c1b393c9d47cf7124d`
- **Original Windows CRLF SHA-256 (`selected_pairs.csv`)**: `52c64903406c29327353774343c683f2f90942fd638c478392cfdb6493a23c51`

Both hashes represent bit-for-bit identical tabular contents across all rows and columns. The baseline configuration file `configs/baseline.yaml` recorded hash (`40f7c5f8b1ab2a0c53c5b7866c87d6a8bd3ad1bb1b30639f311a2f6426ec39d0`) was already computed using LF line endings and is unchanged. Automated verification is enforced in `tests/test_frozen_hashes.py`.

### 9.2 Post-Freeze Code Modifications & Scientific Grounding
Per the research protocol, code modifications made subsequent to the Day 10 freeze (`frozen-v1`) are recorded chronologically below:

1. **Day 11 (Sensitivity Analysis)**:
   - `src/portfolio.py`: Added `rolling_60` branch to evaluate causal rolling 60-day z-score normalization during parameter robustness checks without altering baseline fixed in-sample statistics.
2. **Day 12 (Benchmark Data Retrieval)**:
   - `src/data.py`: Added `tickers` and `filename` parameters to `fetch_data()` and `load_clean_panel()` to download and cache SPY ETF benchmark price history for market exposure regression without altering the 18-ticker pairs panel cache.
3. **Day 15 (Independent Review Patches)**:
   - `src/backtest.py`: Replaced single-slot pending execution state (`pending_entry`, `pending_exit`) with FIFO queues (`pending_entries`, `pending_exits`) scheduled strictly from bar close signal flags rather than the engine's current position state. This resolved a bug where execution lag $\ge 2$ dropped interleaved exit and re-entry signals. Added a `t < n - 1` guard to entry fills to prevent positions opening on the final bar without exit logging or trade costs.
   - `src/portfolio.py`: Initialized `full_prices = None` prior to `if prices is None` check to prevent `UnboundLocalError` when a custom `prices` DataFrame is passed under `rolling_60`, and aligned the fallback branch to `min_periods=60`.
   - `scripts/run_pipeline.py`: Added `--recompute` verification mode to re-run pair screening and OLS hedge parameter fitting on training prices from local cache (`data/processed/close.parquet`), assert numerical match (`rtol=1e-5`) with frozen CSV files, print `MATCH`, and never overwrite frozen outputs. Shared `fit_hedge_params_df` loop across cached and recompute paths.
   - `src/sensitivity.py`: Dynamic pair count `len(res.pair_results)` substituted for hard-coded divisor `5.0` in `extract_summary_record`.

### 9.3 Documentation vs. Code Corrections (Item 8 Errata)
1. **Half-Life Formula**:
   - In Section 5.3, the Ornstein-Uhlenbeck half-life formula was stated as $\tau = -\frac{\ln(2)}{\ln(1+\phi)}$ from discrete AR(1) dynamics.
   - The actual implementation in `src/pairs.py` uses the continuous linear approximation $t_{1/2} = -\frac{\ln(2)}{\gamma}$, where $\gamma$ is the OLS slope of $\Delta s_t$ on $s_{t-1}$. For a typical 20-day half-life ($\gamma \approx -0.0341$), the difference is under 2%. The code implementation is preserved to guarantee frozen result immutability.
2. **Short Leg Borrow Fee Convention**:
   - In Section 6, borrow fees were documented as charged daily on mark-to-market short equity notional.
   - The actual implementation in `src/backtest.py` fixes the short leg notional at entry fill price ($\text{shares} \times P_{\text{entry}}$) and charges $\frac{\text{borrow\_bps\_annual}}{10^4 \times 252} \times \text{short\_notional}$ daily while held. For standard 20–30 day holding periods with modest price movements, this convention tracks mark-to-market borrow within fractions of a basis point. The original text in Section 6 is retained untouched per protocol.

