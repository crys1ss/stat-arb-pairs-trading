"""CLI runner script to execute backtest for train or validation period and save results."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import load_config
from src.portfolio import run_portfolio


def parse_args():
    parser = argparse.ArgumentParser(description="Run portfolio backtest on train or validation period.")
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

    print(f"Running portfolio backtest for period '{args.period}' using config {args.config}...")
    res = run_portfolio(cfg=cfg, period=args.period)

    results_dir = ROOT_DIR / "reports" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    daily_path = results_dir / f"{args.period}_daily.csv"
    trades_path = results_dir / f"{args.period}_trades.csv"

    res.daily.to_csv(daily_path, index=True)
    res.trades.to_csv(trades_path, index=False)

    print(f"\nBacktest completed successfully for period: {args.period}")
    print(f"  Daily metrics written to: {daily_path} ({len(res.daily)} trading days)")
    print(f"  Trade log written to:     {trades_path} ({len(res.trades)} total trades)")
    print(f"  Initial Capital:          ${cfg.capital.initial_capital:,.2f}")
    ending_equity = float(res.daily['equity'].iloc[-1]) if not res.daily.empty else cfg.capital.initial_capital
    print(f"  Ending Equity:            ${ending_equity:,.2f}")
    total_net_pnl = float(res.daily['net_pnl'].sum()) if not res.daily.empty else 0.0
    print(f"  Total Net P&L:            ${total_net_pnl:,.2f}")
    print(f"  Annualized Turnover:      {res.turnover:.2f}x\n")


if __name__ == "__main__":
    main()
