# Project Progress & Handoff Log

## Status
- Day: 3 of 14
- Current Phase: Exploratory data analysis, return distributions, and order-of-integration diagnostics complete.
- Test Status: All tests passing (`pytest -q`, 19 passed).

## Decisions log
- Pre-registered screening fallback: If zero pairs pass Holm at 0.05, the primary finding is that no pairs pass. Because the backtester still needs evaluating, the pipeline continues on an EXPLORATORY set: the 5 lowest raw p-value pairs that pass the half-life filter. Every downstream output for this set is labelled EXPLORATORY.
- Integration verdict: 18 of 18 tickers are plausibly I(1) on training window (2018–2021). Zero tickers excluded. All 18 exhibited non-stationary log price levels (ADF p > 0.05) and stationary first differences (ADF p < 0.001, KPSS p > 0.05).
- Heavy tails: Confirmed leptokurtic daily returns across all assets (excess kurtosis from 6.4 in XOM to 84.1 in OXY), justifying non-Gaussian risk modeling.
- Isolated notebook: Created clean 8-cell `notebooks/exploratory_analysis.ipynb` containing zero calculation logic, purely consuming generated CSVs and figures.

## Day log
### Day 3: Exploratory Analysis & Order of Integration
- Implemented: `src/stats_tests.py` (`adf_test`, `kpss_test`), `src/plotting.py` (normalized prices, log prices, correlation heatmap), `scripts/run_eda.py`, and `notebooks/exploratory_analysis.ipynb`.
- Tested: `tests/test_stats_tests.py` verifying ADF unit root detection on seeded random walk, rejection on AR(1) phi=0.5, and graceful NaN handling. Full suite: 19 passed.
- Outputs generated: `reports/results/return_stats.csv`, `reports/results/integration_tests.csv`, and 3 figures in `reports/figures/`.
- Remaining: Day 4 candidate pair screening with Holm multiple testing correction on training data.

## Next
- Next commands:
  - Day 4 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then execute Engle-Granger pair screening with Holm correction.
