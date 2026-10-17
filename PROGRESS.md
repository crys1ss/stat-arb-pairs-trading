# Project Progress & Handoff Log

## Status
- Day: 11 of 14
- Current Phase: Robustness and sensitivity analysis complete across train, val, and test.
- Test Status: All tests passing (`pytest -q`, 63 passed).

## Decisions log
- Permanent Rule on Post-Test Modifications: Any parameter change made after seeing test results must be logged, and the test set must then be described as no longer untouched.
- Research freeze: Frozen all parameters, dates, pairs, and SHA-256 hashes in `docs/FROZEN_DECISIONS.md`; committed and tagged `frozen-v1`.
- Sensitivity protocol: All variations strictly labeled "sensitivity, not selection"; baseline frozen decisions and headline results remain unchanged.
- Break-even calculation: Zero-net-alpha cost per side determined via linear interpolation across the friction grid.

## Day log
### Day 11: Robustness, Parameter Sensitivity & Break-Even Friction Analysis
- Implemented: `src/sensitivity.py`, `scripts/run_sensitivity.py`, `tests/test_sensitivity.py`, heatmap/cost curve visualizers in `src/plotting.py`, and `reports/results/sensitivity_*.csv`.
- Tested: `tests/test_sensitivity.py` (6 passed). Full suite: 63 passed.
- Factual observations from `reports/results/sensitivity_*.csv` and `sensitivity_breakeven.csv`:
  1. Break-even cost per side per leg (Net P&L = $0): Train 173.73 bps, Validation 15.03 bps, Out-of-Sample Test 5.12 bps.
  2. Test Net P&L sign persistence: Negative sign does not unconditionally survive the grid (17 negative / 11 positive across 28 test runs).
  3. The negative baseline result (-$7,613.28) is friction-dominated: survives costs >= 5.12 bps, but flips positive under lower friction (<5.12 bps), lower entry z (z=1.5 yields +$49,742.00, Sharpe 0.82), longer holding (60d yields +$18,021.64, Sharpe 0.32), or adaptive rolling 60d z-score (+$19,034.76, Sharpe 0.37).
- Remaining: Day 12 failure mode & regime analysis; Days 13–14 research report, documentation, and recruiter polish.

## Next
- Next commands:
  - Day 12 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then analyze sub-period divergence and failure modes.
