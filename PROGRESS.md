# Project Progress & Handoff Log

## Status
- Day: 13 of 14
- Current Phase: Research report and metric audit complete.
- Test Status: All tests passing (`pytest -q`, 69 passed).

## Decisions log
- Permanent Rule on Post-Test Modifications: Any parameter change made after seeing test results must be logged, and the test set must then be described as no longer untouched.
- Research freeze: Frozen all parameters, dates, pairs, and SHA-256 hashes in `docs/FROZEN_DECISIONS.md`; committed and tagged `frozen-v1`.
- Failure diagnosis: Diagnostics confirm out-of-sample decay stems from cointegration breakdown (0 of 5 cointegrated in test) and structural parameter drift (CUSUM p < 0.0001), not systematic market beta.

## Day log
### Day 12: Risk, Stability & Failure Mode Analysis
- Implemented: `src/failure_analysis.py`, `scripts/run_failure_analysis.py`, `tests/test_failure_analysis.py`, divergence visualizers in `src/plotting.py`, and `reports/results/failure_analysis.md`.
- Tested: `tests/test_failure_analysis.py` (6 passed). Full suite: 69 passed.
- Factual observations from diagnostic outputs:
  1. Market Exposure: Strategy market beta is statistically near zero across all periods (Test Beta = -0.0318, Full Span Beta = +0.0075, R² = 0.0028). Drawdown was not market-direction-driven.
  2. Cointegration Decay: 0 of 5 pairs cointegrated at 5% in test window (p-values 0.207–0.951; half-lives lengthened to >40 days).
  3. Structural Breaks: CUSUM test rejected parameter stability for 100% of candidate pairs (all p-values < 0.0001, test statistics 5.99–13.05 vs 1% crit 1.63). Rolling betas drifted up to 140.5% (MDLZ_PG).
  4. Worst Trades: 100% of top 5 worst losses exited on 30-day `max_hold` timeout (Rank #1 COP_DVN -$35.5k, Rank #2 COP_DVN -$14.5k) as spreads drifted without mean-reverting.

### Day 13: Quantitative Research Report & Metric Audit
- Implemented: `reports/research_report.md` covering all 12 brief sections, 8 embedded figures, 5 structured tables, and verification appendix.
- Verified: Complete metric audit table cross-referencing all 50+ cited statistics against `reports/results/` files with 100% exact matches.
- Core Empirical Findings:
  1. Statistical Arbitrage Verdict: Gross positive ($10.6k) but net negative (-$7.6k, -0.38% CAGR, Sharpe -0.1189) due to 171.9% cost drag. Break-even cost is 5.12 bps vs 10 bps baseline.
  2. Decay Diagnosis: Total cointegration breakdown in test (0 of 5 cointegrated) and structural parameter drift (CUSUM p < 0.0001).
  3. Market Neutrality: Strategy maintains zero market exposure (beta +0.0075, p = 0.5422).
- Full suite: 69 passed (`pytest -q`).
- Remaining: Day 14 (recruiter README, CV bullet points, run_pipeline verification).

## Next
- Next commands:
  - Day 14 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then draft recruiter-facing `README.md`, CV bullets, and verify pipeline end-to-end.
