"""Script to generate signals and plot z-score trajectory with trade markers for selected pairs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd
from src.config import load_config
from src.data import slice_period
from src.pairs import construct_spread, zscore
from src.plotting import plot_signals_with_markers
from src.signals import generate_signals


def parse_args():
    parser = argparse.ArgumentParser(description="Generate signals for selected pairs on train and validation.")
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
    print(f"Loaded config from {args.config}")

    results_dir = ROOT_DIR / "reports" / "results"
    figures_dir = ROOT_DIR / "reports" / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    hedge_params_csv = results_dir / "hedge_params.csv"
    if not hedge_params_csv.exists():
        raise FileNotFoundError(f"Hedge parameters missing at {hedge_params_csv}. Run scripts/build_spreads.py first.")

    hedge_df = pd.read_csv(hedge_params_csv)

    data_file = ROOT_DIR / "data" / "processed" / "close.parquet"
    full_close = pd.read_parquet(data_file)

    train_prices = slice_period(full_close, "train", cfg)
    val_prices = slice_period(full_close, "validation", cfg)
    train_val_prices = pd.concat([train_prices, val_prices]).sort_index()
    train_end = cfg.dates.train_end

    print("\nGenerating signals for selected pairs (Train 2018–2021 + Validation 2022)...")

    for _, row in hedge_df.iterrows():
        pair_name = row["pair"]
        leg_a = row["leg_a"]
        leg_b = row["leg_b"]
        mu_train = float(row["res_mean_train"])
        sd_train = float(row["res_std_train"])
        is_exploratory = bool(row.get("is_exploratory", False))

        params = {
            "alpha": float(row["alpha"]),
            "beta": float(row["beta"]),
            "leg_a": leg_a,
            "leg_b": leg_b,
        }

        # Construct spread and normalized z-score
        spread = construct_spread(train_val_prices, params)
        z = zscore(spread, mu_train=mu_train, sd_train=sd_train)

        # Generate signals
        sig_df = generate_signals(
            z=z,
            entry_z=cfg.signals.entry_z,
            exit_z=cfg.signals.exit_z,
            max_hold_days=cfg.signals.max_hold_days,
            stop_z=cfg.signals.stop_z,
        )

        n_entries = int(sig_df["entry_flag"].sum())
        n_exits = int(sig_df["exit_flag"].sum())
        print(f"  {pair_name} ({row['sector']}): {n_entries} entries, {n_exits} exits")

        # Plot z-score with trade markers
        out_fig = figures_dir / f"{pair_name}_zscore_signals.png"
        plot_signals_with_markers(
            z_series=z,
            signals_df=sig_df,
            entry_z=cfg.signals.entry_z,
            exit_z=cfg.signals.exit_z,
            split_date=train_end,
            out_path=out_fig,
            pair_name=f"{pair_name} ({'EXPLORATORY' if is_exploratory else 'CONFIRMED'})",
        )

    print(f"\nSignal plots successfully generated and saved to {figures_dir}")


if __name__ == "__main__":
    main()
