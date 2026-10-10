"""Script to execute candidate-pair cointegration screening on training data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from src.config import load_config
from src.data import slice_period
from src.pairs import screen_pairs


def parse_args():
    parser = argparse.ArgumentParser(description="Screen candidate pairs using Engle-Granger and Holm correction.")
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

    data_file = ROOT_DIR / "data" / "processed" / "close.parquet"
    if not data_file.exists():
        raise FileNotFoundError(f"Processed price panel missing at {data_file}. Run scripts/fetch_data.py first.")

    full_close = pd.read_parquet(data_file)
    train_prices = slice_period(full_close, "train", cfg)
    print(f"Training price panel: {train_prices.shape} ({train_prices.index.min().date()} to {train_prices.index.max().date()})")

    results_dir = ROOT_DIR / "reports" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("Screening candidate pairs within sectors...")
    screening_df, selected_df = screen_pairs(train_prices, cfg)

    # Save outputs
    screening_csv = results_dir / "pair_screening.csv"
    selected_csv = results_dir / "selected_pairs.csv"

    screening_df.to_csv(screening_csv, index=False)
    selected_df.to_csv(selected_csv, index=False)

    total_tested = len(screening_df)
    passed_raw = int((screening_df["raw_p"] < cfg.screening.alpha).sum())
    passed_holm = int((screening_df["holm_p"] < cfg.screening.alpha).sum())
    passed_hl = int(((screening_df["half_life_days"] >= cfg.screening.min_half_life_days) &
                     (screening_df["half_life_days"] <= cfg.screening.max_half_life_days)).sum())
    passed_both = int(screening_df["passes_screening"].sum())

    print("\n" + "=" * 60)
    print("SCREENING FUNNEL SUMMARY (TRAINING PERIOD 2018-2021)")
    print("=" * 60)
    print(f"Candidate pairs tested:               {total_tested}")
    print(f"Passed raw Engle-Granger (p < 0.05):  {passed_raw}")
    print(f"Passed Holm-adjusted (p < 0.05):     {passed_holm}")
    print(f"Passed half-life filter [1, 60] days: {passed_hl}")
    print(f"Passed both (primary selection):      {passed_both}")
    print("=" * 60)

    is_exploratory = bool(selected_df["is_exploratory"].iloc[0]) if not selected_df.empty else False
    if is_exploratory:
        print(f"\n[NOTE] 0 pairs passed Holm at alpha=0.05. Using pre-registered EXPLORATORY set (n={len(selected_df)}):")
    else:
        print(f"\nSelected Pairs (n={len(selected_df)}):")

    display_cols = ["pair", "sector", "correlation", "raw_p", "holm_p", "half_life_days", "alpha", "beta", "is_exploratory"]
    print(selected_df[display_cols].to_string(index=False))

    print(f"\nScreening results saved to: {screening_csv}")
    print(f"Selected pairs saved to:    {selected_csv}")


if __name__ == "__main__":
    main()
