# Project Progress & Handoff Log

## Status
- Day: 6 of 14
- Current Phase: Causal signal generation state machine complete.
- Test Status: All tests passing (`pytest -q`, 36 passed).

## Decisions log
- Execution contract: Explicitly documented in `src/signals.py` docstrings that signals evaluated at close t execute strictly at close t + execution_lag (lag >= 1) to eliminate look-ahead bias.
- State invariants: Enforced zero re-entry on exit bars, zero overlapping positions, and hold-through-NaN behavior.
- Causality proven: Verified that truncating input at bar t leaves all prior states strictly unchanged.
- Period end exit: Implemented `close_at_end: bool = False` allowing explicit 'period_end' liquidation while preserving default truncation causality.

## Day log
### Day 6: Signal Generation State Machine
- Implemented: `src/signals.py` (`generate_signals`), `scripts/generate_pair_signals.py`, and `plot_signals_with_markers` in `src/plotting.py`.
- Tested: `tests/test_signals.py` covering long/short entries, mean-reversion with zero crossing, max hold duration, no re-entry on exit, NaN handling, stop loss, truncation causality, and period-end exit. Full suite: 36 passed.
- Outputs generated: 5 z-score trade marker figures in `reports/figures/` across train and validation windows.
- Remaining: Day 7 single-pair backtest engine with transaction costs, slippage, and borrow fees.

## Next
- Next commands:
  - Day 7 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then build `src/backtest.py` single-pair engine.
