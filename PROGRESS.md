# Project Progress & Handoff Log

## Status
- Day: 5 of 14
- Current Phase: Pair screening (Day 4) and hedge ratio estimation / spread construction (Day 5) complete.
- Test Status: All tests passing (`pytest -q`, 28 passed).

## Decisions log
- Screening funnel: 45 candidate pairs tested; 3 passed raw Engle-Granger (p < 0.05); 0 passed Holm (p < 0.05); 27 passed half-life [1, 60] d. Primary finding: zero pairs statistically cointegrated after FWER correction.
- Exploratory selection: Activated pre-registered fallback with top 5 lowest raw-p pairs passing half-life: BAC_PNC (p=0.0049), MDLZ_PG (p=0.0088), MDLZ_PEP (p=0.0316), COP_DVN (p=0.0531), COP_CVX (p=0.0903). Labelled EXPLORATORY.
- Frozen parameters: Alpha, beta, training spread mean and std frozen from 2018–2021; zero refitting on validation/test data.

## Day log
### Days 4 & 5: Screening, Hedge Ratios, and Spread Construction
- Implemented: `src/pairs.py` (screening, Engle-Granger, AR(1) half-life, Holm step-down, OLS hedge fitting, spread and z-score), `scripts/screen_pairs.py`, `scripts/build_spreads.py`, and `docs/METHODOLOGY.md`.
- Tested: `tests/test_pairs.py` and `tests/test_spread.py` (known Holm vectors, cointegration vs random walk, AR(1) half-life, no-lookahead invariant). Full suite: 28 passed.
- Outputs generated: `pair_screening.csv`, `selected_pairs.csv`, `hedge_params.csv`, `rolling_beta.csv`, and 11 pair/diagnostic figures in `reports/figures/`.
- Remaining: Day 6 causal signal generation state machine.

## Next
- Next commands:
  - Day 6 start: Read `docs/AGENT_RULES.md` and `PROGRESS.md`, then build `src/signals.py` state machine.
