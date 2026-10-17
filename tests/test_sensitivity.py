"""Unit tests for sensitivity analysis engine and break-even calculations."""

from dataclasses import replace
import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.sensitivity import (
    LABEL_SENSITIVITY,
    compute_breakeven_costs,
    run_cost_grid,
    run_entry_exit_grid,
    run_execution_lag_grid,
    run_max_hold_grid,
    run_rolling_zscore_comparison,
)


@pytest.fixture(scope="module")
def base_cfg():
    cfg = load_config("configs/test_run.yaml")
    return replace(cfg, dates=replace(cfg.dates, unlock_test=True))


def test_sensitivity_label_strictly_enforced(base_cfg):
    """Verify that every sensitivity output row is labeled 'sensitivity, not selection'."""
    res_df = run_entry_exit_grid(
        base_cfg=base_cfg,
        periods=["validation"],
        entry_grid=[2.0],
        exit_grid=[0.5],
    )
    assert not res_df.empty
    assert (res_df["label"] == LABEL_SENSITIVITY).all()


def test_entry_exit_grid_dimensions_and_finite_sharpe(base_cfg):
    """Verify 3x3 entry/exit grid returns 9 runs on validation period with finite values."""
    res_df = run_entry_exit_grid(
        base_cfg=base_cfg,
        periods=["validation"],
        entry_grid=[1.5, 2.0, 2.5],
        exit_grid=[0.0, 0.5, 1.0],
    )
    assert len(res_df) == 9
    assert set(res_df["entry_z"]) == {1.5, 2.0, 2.5}
    assert set(res_df["exit_z"]) == {0.0, 0.5, 1.0}
    assert res_df["net_sharpe"].notna().all()


def test_cost_grid_monotonic_pnl_decay(base_cfg):
    """Verify that Net P&L strictly decreases as friction costs increase."""
    cost_df = run_cost_grid(
        base_cfg=base_cfg,
        periods=["validation"],
        cost_per_side_grid=[0.0, 5.0, 10.0, 20.0],
        borrow_grid=[50.0],
    )
    assert len(cost_df) == 4
    pnl_series = cost_df.sort_values("cost_per_side_bps")["net_pnl"].values
    # Net P&L must strictly decrease with higher trade costs
    diffs = np.diff(pnl_series)
    assert (diffs < 0).all(), f"Net P&L did not strictly decrease with costs: {pnl_series}"


def test_breakeven_cost_linear_interpolation():
    """Verify break-even cost calculation on known synthetic linear decay."""
    # Synthetic case: Gross - Borrow = $10,000 at Cost=0; at Cost=10 bps Net = -$2,000.
    # Linear slope: (-2000 - 10000)/10 = -1200 $/bps.
    # Break-even = 10000 / 1200 = 8.33 bps.
    synth_df = pd.DataFrame([
        {"period": "test", "cost_per_side_bps": 0.0, "borrow_bps_annual": 50.0, "gross_pnl": 12000.0, "borrow_costs": 2000.0, "net_pnl": 10000.0},
        {"period": "test", "cost_per_side_bps": 5.0, "borrow_bps_annual": 50.0, "gross_pnl": 12000.0, "borrow_costs": 2000.0, "net_pnl": 4000.0},
        {"period": "test", "cost_per_side_bps": 10.0, "borrow_bps_annual": 50.0, "gross_pnl": 12000.0, "borrow_costs": 2000.0, "net_pnl": -2000.0},
        {"period": "test", "cost_per_side_bps": 20.0, "borrow_bps_annual": 50.0, "gross_pnl": 12000.0, "borrow_costs": 2000.0, "net_pnl": -14000.0},
    ])
    be_df = compute_breakeven_costs(synth_df, baseline_borrow_bps=50.0)
    assert len(be_df) == 1
    calculated_be = be_df["breakeven_cost_per_side_bps"].iloc[0]
    assert np.isclose(calculated_be, 8.33, atol=0.01)


def test_execution_lag_and_max_hold_runs(base_cfg):
    """Verify execution lag and max hold grids execute cleanly on validation."""
    lag_df = run_execution_lag_grid(base_cfg, periods=["validation"], lags=[1, 2])
    assert len(lag_df) == 2
    assert (lag_df["label"] == LABEL_SENSITIVITY).all()

    mh_df = run_max_hold_grid(base_cfg, periods=["validation"], max_hold_grid=[15, 30, 60])
    assert len(mh_df) == 3
    assert (mh_df["label"] == LABEL_SENSITIVITY).all()


def test_rolling_zscore_comparison_executes(base_cfg):
    """Verify causal rolling 60-day zscore runs and produces valid comparison record."""
    z_df = run_rolling_zscore_comparison(base_cfg, periods=["validation"])
    assert len(z_df) == 2
    methods = set(z_df["zscore_method"])
    assert methods == {"training_fixed", "rolling_60"}
    assert (z_df["label"] == LABEL_SENSITIVITY).all()
