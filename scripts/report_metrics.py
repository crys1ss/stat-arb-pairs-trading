"""CLI script to compute performance metrics, tabular reports, and publication figures for train and validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from src.config import load_config
from src.metrics import (
    compute_by_year_table,
    compute_per_pair_table,
    compute_portfolio_metrics,
)
from src.plotting import (
    plot_drawdown,
    plot_gross_vs_net_equity,
    plot_per_pair_pnl,
    plot_trade_distributions,
)
from src.portfolio import compute_turnover, run_portfolio


def parse_args():
    parser = argparse.ArgumentParser(description="Generate performance metrics reports and figures.")
    parser.add_argument(
        "--period",
        type=str,
        default="train",
        choices=["train", "validation", "test"],
        help="Evaluation period: 'train', 'validation', or 'test'.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/baseline.yaml",
        help="Path to YAML configuration file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)

    # Strict check: Test period must be locked prior to Day 10 freeze
    if args.period == "test" and not cfg.dates.unlock_test:
        raise PermissionError(
            "Access to the out-of-sample 'test' period is strictly locked until the Day 10 freeze. "
            "Set `cfg.dates.unlock_test = True` only after all model decisions have been frozen."
        )

    results_dir = ROOT_DIR / "reports" / "results"
    figures_dir = ROOT_DIR / "reports" / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    daily_path = results_dir / f"{args.period}_daily.csv"
    trades_path = results_dir / f"{args.period}_trades.csv"

    # Load or run backtest if missing
    if not daily_path.exists() or not trades_path.exists():
        print(f"Daily/trades files missing for '{args.period}', executing portfolio backtest first...")
        res = run_portfolio(cfg=cfg, period=args.period)
        res.daily.to_csv(daily_path, index=True)
        res.trades.to_csv(trades_path, index=False)
        daily_df = res.daily
        trades_df = res.trades
        turnover = res.turnover
    else:
        daily_df = pd.read_csv(daily_path, index_col=0, parse_dates=True)
        trades_df = pd.read_csv(trades_path)
        turnover = compute_turnover(trades_df, daily_df, annualization=cfg.capital.annualization)

    hedge_params_path = results_dir / "hedge_params.csv"
    if not hedge_params_path.exists():
        raise FileNotFoundError(f"Hedge parameters missing at {hedge_params_path}.")
    hedge_df = pd.read_csv(hedge_params_path)
    pairs = hedge_df["pair"].tolist()

    initial_capital = float(cfg.capital.initial_capital)
    pair_capital = initial_capital / float(len(pairs))

    print(f"\nComputing performance metrics for period: '{args.period}'...")

    # 1. Comprehensive portfolio metrics JSON
    metrics_dict = compute_portfolio_metrics(
        daily_df=daily_df,
        trades_df=trades_df,
        initial_capital=initial_capital,
        pair_capital=pair_capital,
        pairs=pairs,
        turnover=turnover,
        period_name=args.period,
        annualization=cfg.capital.annualization,
    )

    metrics_json_path = results_dir / f"{args.period}_metrics.json"
    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(metrics_dict, f, indent=2)
    print(f"  Metrics JSON saved to: {metrics_json_path}")

    # 2. Per-pair breakdown table CSV
    per_pair_df = compute_per_pair_table(
        daily_df=daily_df,
        trades_df=trades_df,
        pair_capital=pair_capital,
        pairs=pairs,
        annualization=cfg.capital.annualization,
    )
    per_pair_csv_path = results_dir / f"{args.period}_per_pair.csv"
    per_pair_df.to_csv(per_pair_csv_path, index=False)
    print(f"  Per-pair table saved to: {per_pair_csv_path}")

    # 3. By-year breakdown table CSV
    by_year_df = compute_by_year_table(
        daily_df=daily_df,
        trades_df=trades_df,
        initial_capital=initial_capital,
        annualization=cfg.capital.annualization,
    )
    by_year_csv_path = results_dir / f"{args.period}_by_year.csv"
    by_year_df.to_csv(by_year_csv_path, index=False)
    print(f"  By-year table saved to: {by_year_csv_path}")

    # 4. Generate all 4 required figures
    print(f"Generating reporting charts in {figures_dir}...")
    plot_gross_vs_net_equity(
        daily_df=daily_df,
        initial_capital=initial_capital,
        out_path=figures_dir / f"{args.period}_gross_vs_net_equity.png",
        title=f"Portfolio Equity Curve: Gross vs. Net ({args.period.capitalize()} Period)",
    )

    plot_drawdown(
        equity_series=daily_df["equity"],
        out_path=figures_dir / f"{args.period}_drawdown.png",
        title=f"Portfolio Underwater Drawdown ({args.period.capitalize()} Period)",
    )

    plot_per_pair_pnl(
        per_pair_df=per_pair_df,
        out_path=figures_dir / f"{args.period}_per_pair_pnl.png",
        title=f"Per-Pair Net P&L Contribution ({args.period.capitalize()} Period)",
    )

    plot_trade_distributions(
        trades_df=trades_df,
        out_path=figures_dir / f"{args.period}_trade_distributions.png",
        title=f"Trade Return and Holding Duration Distributions ({args.period.capitalize()} Period)",
    )

    print(f"All reports and figures for '{args.period}' generated successfully.\n")


if __name__ == "__main__":
    main()
