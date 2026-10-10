# Project Progress & Handoff Log

## Status
- Day: 7 of 14
- Current Phase: Single-pair backtest simulation engine complete.
- Test Status: All tests passing (`pytest -q`, 44 passed).

## Decisions log
- Fixed capital base convention: Evaluated daily return as net_pnl / capital across the backtest to maintain stationary risk exposure.
- Execution lag contract: Decisions at close t fill at close t + execution_lag (assert lag >= 1) to eliminate look-ahead bias.
- Explicit costs: Traded notional commissions + slippage charged per leg at entry and exit; short notional borrow cost accrued daily.
- Period-end liquidation: Open positions at the final bar are force-closed with exit trade costs and exit_reason 'period_end'.

## Day log
### Day 7: Single-Pair Backtest Engine
- Implemented: `src/backtest.py` (`backtest_pair`, `compute_weights`, `BacktestResult`) outputting daily series (`gross_pnl`, `trade_cost`, `borrow_cost`, `net_pnl`, `return`) and detailed trade log table.
- Tested: `tests/test_backtest.py` with hand-computed paths covering execution lag (t+1), exact hand-calculated P&L, single-charge trade costs, borrow accrual, zero-trade behavior, period-end force close, and lag-2 shift. Full suite: 44 passed.
- Remaining: Day 8 multi-pair portfolio aggregation and performance metrics.

## Next
- Next commands:
  - Day 8 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then build multi-pair portfolio and risk/return metrics.
