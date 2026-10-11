# Project Progress & Handoff Log

## Status
- Day: 9 of 14
- Current Phase: Performance metrics and train/validation reporting complete.
- Test Status: All tests passing (`pytest -q`, 56 passed).

## Decisions log
- Metric constraints: Stated risk_free_rate = 0.0 in output; zero-volatility/zero-trade cases strictly return NaN, never inf.
- Friction analysis: Isolated gross vs net P&L showing cost drag was 6.30% in train vs 69.51% in validation.
- Test isolation: Verified report_metrics.py strictly blocks test period access before Day 10 freeze.

## Day log
### Day 9: Performance Metrics & Diagnostic Reporting
- Implemented: `src/metrics.py`, `scripts/report_metrics.py`, and 4 plotting functions in `src/plotting.py`.
- Tested: `tests/test_metrics.py` covering drawdown, Sharpe, CAGR consistency, and zero-trade edge cases. Full suite: 56 passed.
- Outputs generated: `{train,validation}_metrics.json`, `{train,validation}_per_pair.csv`, `{train,validation}_by_year.csv`, and 8 figures in `reports/figures/`.
- Factual observations from `reports/results/`:
  1. Train Net CAGR was 4.93% (0.049312) with Sharpe 1.9782 and max drawdown 1.17% (0.011685).
  2. Train friction drag totaled $14,267.22 ($12,967.88 trade costs, $1,299.34 borrow), representing 6.30% of gross P&L ($226,590.84).
  3. Train win rate was 96.88% (31 wins, 1 loss across 32 trades) with mean holding period 21.7 days and profit factor 83.39.
  4. Train concentration HHI was 0.2315, with COP_CVX (29.41%) and COP_DVN (28.52%) leading net P&L.
  5. Validation Net CAGR fell to 0.49% (0.004923) with Sharpe 0.1537 and max drawdown 2.92% (0.029154).
  6. Validation friction drag totaled $11,178.86 ($9,746.26 trade, $1,432.60 borrow), absorbing 69.51% of gross P&L ($16,082.34).
  7. Validation win rate was 62.50% (15 wins, 9 losses across 24 trades) with turnover rising to 9.71x and HHI of 0.3036.
- Remaining: Day 10 freeze and out-of-sample test period evaluation.

## Next
- Next commands:
  - Day 10 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, unlock test window, and evaluate out-of-sample test period.
