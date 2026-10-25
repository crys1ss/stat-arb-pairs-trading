# Project Progress & Handoff Log

## Status
- Day: 15 of 15
- Current Phase: Post-v1.0 review patches applied, reproducibility verified, v1.1 released.
- Test Status: All tests passing (`pytest -q`, 74 passed).

## Decisions log
- Permanent Rule on Post-Test Modifications: Any parameter change made after seeing test results must be logged, and the test set must then be described as no longer untouched.
- Research freeze: Frozen all parameters, dates, pairs, and SHA-256 hashes in `docs/FROZEN_DECISIONS.md`; committed and tagged `frozen-v1`.
- Failure diagnosis: Diagnostics confirm out-of-sample decay stems from cointegration breakdown (0 of 5 cointegrated in test) and structural parameter drift (CUSUM p < 0.0001), not systematic market beta.
- Reproducibility verification: Clean reproduction test verified in fresh virtual environment and cloned repository; all metrics replicated with 0 discrepancies.
- Engine bug in execution_lag >= 2: Found and resolved after test evaluation. Single-slot pending execution replaced with FIFO queues scheduled from signal machine flags alone, and terminal bar entry guard added. No strategy parameter changed. Baseline train, validation, and test outputs verified identical to the cent. Only lag-2 sensitivity rows changed. Per the permanent rule, the test period was viewed several times (baseline Day 10, sensitivity Day 11, diagnostics Day 12) and is not untouched.

## Day log
### Day 12: Risk, Stability & Failure Mode Analysis
- Implemented: `src/failure_analysis.py`, `scripts/run_failure_analysis.py`, `tests/test_failure_analysis.py`, divergence visualizers in `src/plotting.py`, and `reports/results/failure_analysis.md`.
- Tested: `tests/test_failure_analysis.py` (6 passed). Full suite: 69 passed.
- Factual observations from diagnostic outputs:
  1. Market Exposure: |beta| is small across all periods (0.0075–0.0318) with R² at most ~5% (train R² = 0.0460, full span R² = 0.0028). Newey-West t-stat is significant in validation (beta = -0.0233, t = -2.31, p = 0.0211) and test (beta = -0.0318, t = -2.66, p = 0.0079), but not significant in train (p = 0.1539) or full span (p = 0.5422). Drawdown was primarily idiosyncratic.
  2. Cointegration Decay: 0 of 5 pairs cointegrated at 5% in test window (p-values 0.207–0.951; half-lives lengthened to >40 days).
  3. Structural Breaks: CUSUM test rejected parameter stability for 100% of candidate pairs (all p-values < 0.0001, test statistics 5.99–13.05 vs 1% crit 1.63). Rolling betas drifted up to 140.5% (MDLZ_PG).
  4. Worst Trades: 100% of top 5 worst losses exited on 30-day `max_hold` timeout (Rank #1 COP_DVN -$35.5k, Rank #2 COP_DVN -$14.5k) as spreads drifted without mean-reverting.

### Day 13: Quantitative Research Report & Metric Audit
- Implemented: `reports/research_report.md` covering all 12 brief sections, 8 embedded figures, 5 structured tables, and verification appendix.
- Verified: Complete metric audit table cross-referencing all 50+ cited statistics against `reports/results/` files with 100% exact matches.
- Core Empirical Findings:
  1. Statistical Arbitrage Verdict: Gross positive ($10.6k) but net negative (-$7.6k, -0.38% CAGR, Sharpe -0.1189) due to 171.9% cost drag. Break-even cost is 5.12 bps vs 10 bps baseline.
  2. Decay Diagnosis: Total cointegration breakdown in test (0 of 5 cointegrated) and structural parameter drift (CUSUM p < 0.0001).
  3. Market Exposure: |beta| is small in all periods (|beta| <= 0.0318, full span beta +0.0075, p = 0.5422). Significant negative beta in validation and test, not significant in train or full span.
- Full suite: 69 passed (`pytest -q`).
- Remaining: None (14-day milestone execution complete).

### Day 14: Documentation, Verification, Hygiene & CV Bullets
- Implemented: Hiring-manager ready `README.md` (equations, architecture, 4 figures, quickstart, data disclaimer), `docs/CHECKLIST.md` (100% passed across sections 4–14), CV bullets.
- Tested: Clean reproducibility test executed in isolated venv from fresh clone; full pipeline produced identical results (69 unit tests passed).
- Hygiene: 0 files > 5MB, 0 secrets, 0 uncommitted raw/processed caches, 0 TODOs.
- Tagged: `git tag v1.0`.

### Day 15: Post-v1.0 Review Patch & Verification
- Implemented: Fixed lag >= 2 FIFO queue execution bug and terminal bar entry guard in `src/backtest.py`; fixed `full_prices` `UnboundLocalError` and aligned `min_periods=60` in `src/portfolio.py`; dynamic pair count in `src/sensitivity.py`; `--recompute` verification mode in `scripts/run_pipeline.py`; Section 9 post-freeze addendum in `docs/FROZEN_DECISIONS.md`; corrected half-life (-ln(2)/gamma) and entry-fixed borrow fee documentation in `docs/METHODOLOGY.md` and `README.md`.
- Tested: `tests/test_frozen_hashes.py` (2 passed), `test_backtest.py` (10 passed), `test_portfolio.py` (8 passed). Full test suite: 74 passed (`pytest -q`).
- Reproducibility: `python scripts/run_pipeline.py --config configs/test_run.yaml --recompute` printed MATCH with 0 file changes; baseline outputs identical to the cent (train $212,323.62, val $4,903.47, test -$7,613.28); test lag 2 updated to +$7,126.53 (39 trades).

### Day 16: Reviewer Weaknesses Addressed & Honest Quantitative Framing
- Implemented: Added `time_stop_cooldown_days` to `SignalsConfig` (`src/config.py`), state machine (`src/signals.py`), `simulate_portfolio` (`src/portfolio.py`), and browser simulator (`site/js/engine.js`, `site/js/playground.js`, `site/index.html`).
- Validation-Only Evaluation: Evaluated cooldown strictly on the validation period (2022) to avoid test set snooping. Introducing a 5-day cooldown eliminated immediate re-entries into broken pairs, boosting validation Net P&L from +$4,904.17 (24 trades) to +$45,430.03 (20 trades).
- Restated Headline: Honestly reframed research conclusion across README, research report, and demo site: "No statistically valid pairs were found in screening; trading the fallback basket lost money after real costs" (0 pairs survived Holm-Bonferroni; COP_DVN p=0.053 and COP_CVX p=0.090 failed even uncorrected 5% testing). Cointegration never existed for COP_DVN.
- Addressed Inconsistencies:
  1. Author attributed to Tanay (@crys1ss) and repo clone URL set to `github.com/crys1ss/stat-arb-pairs-trading.git`.
  2. Overclaims dropped: removed "production-grade" and "institutional research paper".
  3. Market beta clarified as "economically negligible" (|beta| <= 0.0318) rather than claiming "robust neutrality", noting t = -2.66 in test.
  4. Screening funnel table rewritten to present independent filters (27 half-life, 3 raw p, 0 Holm) rather than a false 3->0->27 funnel.
  5. Half-life approximation (-ln(2)/gamma) and modeling disclosures (borrow on entry notional, 29-day max hold) documented explicitly.
- Tests: Added `test_time_stop_cooldown` in `tests/test_signals.py` (75 passed). Parity verified: `node site/tests/parity.js` passed (< $1 diff on all 95 trades).

## Next
- Configure GitHub Pages build source to GitHub Actions under repo Settings > Pages.
- Add simulation link (`https://crys1ss.github.io/stat-arb-pairs-trading/`) to GitHub repository "About" website field.

