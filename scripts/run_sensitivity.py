"""Execution script for sensitivity and robustness analysis (Day 11).

Runs the parameter grids on train, validation, and test periods:
1. Entry / Exit z-score thresholds (9 runs at baseline costs)
2. Cost per side and borrow fee grid (12 runs at baseline parameters)
3. Maximum holding horizons (3 runs at baseline parameters)
4. Execution lag comparison (2 runs at baseline parameters)
5. Alternative causal rolling 60-day z-score comparison (2 runs at baseline parameters)

Outputs:
- reports/results/sensitivity_*.csv
- Break-even cost per period in reports/results/sensitivity_breakeven.csv
- reports/figures/sensitivity_entry_exit_heatmap.png
- reports/figures/sensitivity_cost_curve.png

All outputs are strictly labeled "sensitivity, not selection".
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from src.config import load_config
from src.plotting import (
    plot_sensitivity_cost_curves,
    plot_sensitivity_entry_exit_heatmaps,
)
from src.sensitivity import (
    compute_breakeven_costs,
    run_cost_grid,
    run_entry_exit_grid,
    run_execution_lag_grid,
    run_max_hold_grid,
    run_rolling_zscore_comparison,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run robustness and parameter sensitivity analysis across train, validation, and test."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/test_run.yaml",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="reports/results",
        help="Directory to save sensitivity CSV outputs.",
    )
    parser.add_argument(
        "--figures-dir",
        type=str,
        default="reports/figures",
        help="Directory to save sensitivity visualization charts.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config_path = ROOT_DIR / args.config
    results_dir = ROOT_DIR / args.results_dir
    figures_dir = ROOT_DIR / args.figures_dir

    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("STARTING SENSITIVITY & ROBUSTNESS ANALYSIS (Day 11)")
    print(f"  Configuration : {args.config}")
    print(f"  Results Dir   : {results_dir}")
    print(f"  Figures Dir   : {figures_dir}")
    print("  Note          : All outputs labeled 'sensitivity, not selection'")
    print("=" * 80)

    start_time = time.time()
    base_cfg = load_config(str(config_path))
    periods = ["train", "validation", "test"]

    # 1. Entry / Exit Z-Score Grid (9 runs per period)
    print("\n[Grid 1/5] Evaluating Entry vs Exit Z-score Grid (3x3)...")
    entry_exit_df = run_entry_exit_grid(
        base_cfg=base_cfg,
        periods=periods,
        entry_grid=[1.5, 2.0, 2.5],
        exit_grid=[0.0, 0.5, 1.0],
    )
    ee_path = results_dir / "sensitivity_entry_exit.csv"
    entry_exit_df.to_csv(ee_path, index=False)
    print(f"  Saved: {ee_path} ({len(entry_exit_df)} rows)")

    # 2. Friction Cost Grid (12 runs per period)
    print("\n[Grid 2/5] Evaluating Friction Cost Grid ({0,5,10,20} bps x {0,50,200} bps/yr)...")
    cost_df = run_cost_grid(
        base_cfg=base_cfg,
        periods=periods,
        cost_per_side_grid=[0.0, 5.0, 10.0, 20.0],
        borrow_grid=[0.0, 50.0, 200.0],
    )
    cost_path = results_dir / "sensitivity_costs.csv"
    cost_df.to_csv(cost_path, index=False)
    print(f"  Saved: {cost_path} ({len(cost_df)} rows)")

    # 3. Maximum Holding Horizon Grid (3 runs per period)
    print("\n[Grid 3/5] Evaluating Maximum Holding Horizon Grid ({15, 30, 60} days)...")
    max_hold_df = run_max_hold_grid(
        base_cfg=base_cfg,
        periods=periods,
        max_hold_grid=[15, 30, 60],
    )
    mh_path = results_dir / "sensitivity_max_hold.csv"
    max_hold_df.to_csv(mh_path, index=False)
    print(f"  Saved: {mh_path} ({len(max_hold_df)} rows)")

    # 4. Execution Lag Sensitivity (2 runs per period)
    print("\n[Grid 4/5] Evaluating Execution Lag Sensitivity (Lag 1 vs Lag 2)...")
    lag_df = run_execution_lag_grid(
        base_cfg=base_cfg,
        periods=periods,
        lags=[1, 2],
    )
    lag_path = results_dir / "sensitivity_execution_lag.csv"
    lag_df.to_csv(lag_path, index=False)
    print(f"  Saved: {lag_path} ({len(lag_df)} rows)")

    # 5. Causal Rolling 60-day Z-Score Comparison (2 runs per period)
    print("\n[Grid 5/5] Evaluating Causal Rolling 60-day Z-Score vs Fixed In-Sample...")
    zscore_df = run_rolling_zscore_comparison(
        base_cfg=base_cfg,
        periods=periods,
    )
    zscore_path = results_dir / "sensitivity_rolling_zscore.csv"
    zscore_df.to_csv(zscore_path, index=False)
    print(f"  Saved: {zscore_path} ({len(zscore_df)} rows)")

    # Break-Even Cost Analysis
    print("\n[Analysis] Computing Break-Even Friction Thresholds...")
    breakeven_df = compute_breakeven_costs(cost_df, baseline_borrow_bps=50.0)
    be_path = results_dir / "sensitivity_breakeven.csv"
    breakeven_df.to_csv(be_path, index=False)
    print(f"  Saved: {be_path}")

    # Combined master table
    combined_df = pd.concat([entry_exit_df, cost_df, max_hold_df, lag_df, zscore_df], ignore_index=True)
    all_runs_path = results_dir / "sensitivity_all_runs.csv"
    combined_df.to_csv(all_runs_path, index=False)
    print(f"  Saved master runs log: {all_runs_path} ({len(combined_df)} total runs)")

    # Visualizations
    print("\n[Visualizations] Generating Sensitivity Publication Figures...")
    ee_fig = plot_sensitivity_entry_exit_heatmaps(
        grid_df=entry_exit_df,
        out_path=figures_dir / "sensitivity_entry_exit_heatmap.png",
    )
    print(f"  Heatmap saved: {ee_fig}")

    cost_fig = plot_sensitivity_cost_curves(
        cost_df=cost_df,
        breakeven_df=breakeven_df,
        out_path=figures_dir / "sensitivity_cost_curve.png",
    )
    print(f"  Cost curves saved: {cost_fig}")

    elapsed = time.time() - start_time

    # Summary table output
    print("\n" + "=" * 80)
    print("BREAK-EVEN FRICTION THRESHOLDS (Zero-Net-Alpha Cost per Side per Leg)")
    print("=" * 80)
    for _, row in breakeven_df.iterrows():
        p = str(row["period"]).upper()
        be = row["breakeven_cost_per_side_bps"]
        pnl0 = row["gross_pnl"]
        base_pnl = row["baseline_net_pnl"]
        print(f"  {p:<12}: Break-even = {be:6.2f} bps | Gross P&L = ${pnl0:10,.2f} | Baseline Net P&L = ${base_pnl:10,.2f}")

    print("\n" + "=" * 80)
    print("TEST PERIOD NET P&L SIGN PERSISTENCE ACROSS SENSITIVITY GRID")
    print("=" * 80)
    test_runs = combined_df[combined_df["period"] == "test"]
    n_test = len(test_runs)
    n_test_neg = (test_runs["net_pnl"] < 0).sum()
    n_test_pos = (test_runs["net_pnl"] > 0).sum()
    n_test_zero = (test_runs["net_pnl"] == 0).sum()
    print(f"  Total Test Variations Evaluated : {n_test}")
    print(f"  Negative Net P&L Runs           : {n_test_neg} ({n_test_neg / n_test * 100:.1f}%)")
    print(f"  Positive Net P&L Runs           : {n_test_pos} ({n_test_pos / n_test * 100:.1f}%)")
    print(f"  Zero Net P&L Runs               : {n_test_zero}")
    print(f"  Execution Time                  : {elapsed:.2f} seconds")
    print("=" * 80)
    print("Sensitivity analysis complete.\n")


if __name__ == "__main__":
    main()
