# Project Progress & Handoff Log

## Status
- Day: 10 of 14
- Current Phase: Research decisions frozen (tag `frozen-v1`), out-of-sample test evaluation complete.
- Test Status: All tests passing (`pytest -q`, 57 passed).

## Decisions log
- Permanent Rule on Post-Test Modifications: Any parameter change made after seeing test results must be logged, and the test set must then be described as no longer untouched.
- Research freeze: Frozen all parameters, dates, pairs, and SHA-256 hashes in `docs/FROZEN_DECISIONS.md`; committed and tagged `frozen-v1`.
- Chaining method: Multi-period net equity continuously compounded $E_t = C_0 \prod(1+r_t)$ across train, val, and test.

## Day log
### Day 10: Research Decision Freeze, Out-of-Sample Evaluation & Pipeline Runner
- Implemented: `docs/FROZEN_DECISIONS.md`, `configs/test_run.yaml`, `scripts/run_pipeline.py`, chained equity & drawdown plots in `src/plotting.py`, and `reports/results/test_run_log.json`.
- Tested: `tests/test_metrics.py` (added chaining tests). Full suite: 57 passed.
- Factual observations from `reports/results/test_metrics.json` (out-of-sample test 2023–2024, 501 trading days):
  1. Test Net CAGR was -0.38% (-0.003837) with Sharpe -0.1189, ending equity $992,386.72, and max drawdown 3.71% (0.037096, duration 478 days).
  2. Test gross P&L was +$10,586.12, but friction drag totaled $18,199.40 ($15,602.81 trade costs, $2,596.59 borrow), resulting in cost drag of 171.92% and net P&L of -$7,613.28.
  3. Test win rate was 46.15% (18 wins, 21 losses across 39 trades) with mean holding period 26.87 days and turnover 7.93x.
  4. Test concentration HHI was 0.3732, led by COP_DVN (55.74% of absolute P&L).
- Remaining: Day 11 post-test synthesis and failure mode analysis.

## Next
- Next commands:
  - Day 11 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then analyze out-of-sample decay mechanics.
