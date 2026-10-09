"""Script to acquire, cache, validate, and process price data for the configured universe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from src.config import load_config
from src.data import download_prices
from src.validation import (
    build_clean_panel,
    check_abnormal_returns,
    check_calendar_alignment,
    check_date_ranges,
    check_duplicate_dates,
    check_missing_values,
    check_monotonic_index,
    check_non_positive_prices,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch and validate equity price data.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/baseline.yaml",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force fresh download from Yahoo Finance, bypassing parquet cache.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"Loading configuration from {args.config}...")
    cfg = load_config(args.config)

    # 1. Download / retrieve cached prices
    raw_dir = ROOT_DIR / "data" / "raw"
    processed_dir = ROOT_DIR / "data" / "processed"
    reports_dir = ROOT_DIR / "reports" / "results"
    processed_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching price data...")
    raw_df = download_prices(cfg, refresh=args.refresh, raw_dir=raw_dir)
    print(f"Raw data shape: {raw_df.shape}")

    # 2. Build clean close panel (Strictly NO forward filling)
    clean_close, missing_log = build_clean_panel(raw_df)
    processed_file = processed_dir / "close.parquet"
    clean_close.to_parquet(processed_file)
    print(f"Clean close panel written to {processed_file} (shape: {clean_close.shape})")

    # 3. Validation checks
    dups = check_duplicate_dates(clean_close)
    is_monotonic = check_monotonic_index(clean_close)
    non_pos = check_non_positive_prices(clean_close)
    abnormal_rets = check_abnormal_returns(clean_close, threshold=0.25)
    cal_align = check_calendar_alignment(clean_close)
    date_ranges = check_date_ranges(clean_close)
    missing_vals = check_missing_values(clean_close)

    print(f"Index is strictly monotonic: {is_monotonic}")
    print(f"Duplicate date count: {len(dups)}")
    print(f"Abnormal return events (|r| > 25%): {len(abnormal_rets)}")

    # 4. Compile comprehensive data quality summary
    sec_map = cfg.universe.sector_map
    summary_rows = []
    for ticker in cfg.universe.all_tickers:
        sector = sec_map.get(ticker, "unknown")
        cal_row = cal_align[cal_align["ticker"] == ticker].iloc[0] if not cal_align[cal_align["ticker"] == ticker].empty else {}
        dr_row = date_ranges[date_ranges["ticker"] == ticker].iloc[0] if not date_ranges[date_ranges["ticker"] == ticker].empty else {}
        mv_row = missing_vals[missing_vals["ticker"] == ticker].iloc[0] if not missing_vals[missing_vals["ticker"] == ticker].empty else {}
        ab_count = int((abnormal_rets["ticker"] == ticker).sum()) if not abnormal_rets.empty else 0

        prices = clean_close[ticker].dropna() if ticker in clean_close.columns else pd.Series(dtype=float)
        min_p = float(prices.min()) if not prices.empty else float("nan")
        max_p = float(prices.max()) if not prices.empty else float("nan")

        summary_rows.append({
            "ticker": ticker,
            "sector": sector,
            "union_days": cal_row.get("union_trading_days", len(clean_close)),
            "valid_days": cal_row.get("days_present", len(prices)),
            "missing_days": cal_row.get("days_missing", 0),
            "coverage_pct": cal_row.get("coverage_pct", 100.0),
            "first_date": dr_row.get("first_valid_date", None),
            "last_date": dr_row.get("last_valid_date", None),
            "min_price": round(min_p, 4),
            "max_price": round(max_p, 4),
            "non_positive_count": non_pos.get(ticker, 0),
            "abnormal_returns_count": ab_count,
        })

    dq_df = pd.DataFrame(summary_rows)
    dq_file = reports_dir / "data_quality.csv"
    dq_df.to_csv(dq_file, index=False)
    print(f"Data quality report saved to {dq_file}")

    if not abnormal_rets.empty:
        ab_file = reports_dir / "abnormal_returns.csv"
        abnormal_rets.to_csv(ab_file, index=False)
        print(f"Abnormal returns log saved to {ab_file}")

    if not missing_log.empty:
        ml_file = reports_dir / "missing_data_log.csv"
        missing_log.to_csv(ml_file, index=False)
        print(f"Missing observations log saved to {ml_file}")

    print("\nData Quality Summary:")
    print(dq_df.to_string(index=False))


if __name__ == "__main__":
    main()
