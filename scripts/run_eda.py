"""Script to execute exploratory data analysis and order-of-integration testing on training data."""

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
from src.plotting import (
    plot_correlation_heatmap,
    plot_log_prices_by_sector,
    plot_normalized_prices_by_sector,
)
from src.stats_tests import adf_test, kpss_test


def parse_args():
    parser = argparse.ArgumentParser(description="Run EDA and order-of-integration analysis on training window.")
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

    # Ensure output directories exist
    results_dir = ROOT_DIR / "reports" / "results"
    figures_dir = ROOT_DIR / "reports" / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load clean processed close panel
    data_file = ROOT_DIR / "data" / "processed" / "close.parquet"
    if not data_file.exists():
        raise FileNotFoundError(f"Processed price panel missing at {data_file}. Run scripts/fetch_data.py first.")

    full_close = pd.read_parquet(data_file)
    print(f"Full price panel loaded: {full_close.shape}")

    # 2. Slice strictly for TRAIN period (2018-01-01 to 2021-12-31)
    train_prices = slice_period(full_close, "train", cfg)
    print(f"Train period slice: {train_prices.shape} ({train_prices.index.min().date()} to {train_prices.index.max().date()})")

    # 3. Summary statistics for daily log returns
    log_rets = np.log(train_prices / train_prices.shift(1)).dropna()
    sector_map = cfg.universe.sector_map

    stats_records = []
    for ticker in cfg.universe.all_tickers:
        r = log_rets[ticker]
        ann_mean = float(r.mean() * 252.0)
        ann_std = float(r.std(ddof=1) * np.sqrt(252.0))
        skew = float(r.skew())
        excess_kurt = float(r.kurtosis())  # Fisher excess kurtosis
        min_ret = float(r.min())
        max_ret = float(r.max())

        stats_records.append({
            "ticker": ticker,
            "sector": sector_map.get(ticker, "unknown"),
            "observations": len(r),
            "ann_mean": round(ann_mean, 6),
            "ann_std": round(ann_std, 6),
            "skewness": round(skew, 4),
            "excess_kurtosis": round(excess_kurt, 4),
            "min_return": round(min_ret, 6),
            "max_return": round(max_ret, 6),
        })

    stats_df = pd.DataFrame(stats_records)
    stats_out = results_dir / "return_stats.csv"
    stats_df.to_csv(stats_out, index=False)
    print(f"Return statistics saved to {stats_out}")

    # 4. Order-of-integration testing (ADF and KPSS on log levels and first differences)
    # Note: Statsmodels truncates KPSS asymptotic p-values to [0.01, 0.10].
    integration_records = []
    for ticker in cfg.universe.all_tickers:
        series = train_prices[ticker].dropna()
        log_level = np.log(series)
        d_log_level = log_level.diff().dropna()

        # Level tests
        adf_lvl = adf_test(log_level, regression="c", autolag="AIC")
        kpss_lvl = kpss_test(log_level, regression="c", nlags="auto")

        # Differenced tests
        adf_dif = adf_test(d_log_level, regression="c", autolag="AIC")
        kpss_dif = kpss_test(d_log_level, regression="c", nlags="auto")

        # Decision rule for I(1) plausibility:
        # Level is non-stationary: ADF fails to reject unit root (p > 0.05)
        # Differenced series is stationary: ADF rejects unit root (p <= 0.05) and KPSS fails to reject stationarity (p > 0.05)
        lvl_nonstat = bool(adf_lvl["pvalue"] > 0.05)
        dif_stat = bool(adf_dif["pvalue"] <= 0.05 and kpss_dif["pvalue"] > 0.05)
        i1_plausible = bool(lvl_nonstat and dif_stat)

        integration_records.append({
            "ticker": ticker,
            "sector": sector_map.get(ticker, "unknown"),
            "adf_level_stat": round(adf_lvl["stat"], 4),
            "adf_level_p": round(adf_lvl["pvalue"], 4),
            "kpss_level_stat": round(kpss_lvl["stat"], 4),
            "kpss_level_p": round(kpss_lvl["pvalue"], 4),
            "adf_diff_stat": round(adf_dif["stat"], 4),
            "adf_diff_p": round(adf_dif["pvalue"], 4),
            "kpss_diff_stat": round(kpss_dif["stat"], 4),
            "kpss_diff_p": round(kpss_dif["pvalue"], 4),
            "i1_plausible": i1_plausible,
        })

    integ_df = pd.DataFrame(integration_records)
    integ_out = results_dir / "integration_tests.csv"
    integ_df.to_csv(integ_out, index=False)
    print(f"Integration tests saved to {integ_out}")

    # 5. Publication figures
    fig_norm = figures_dir / "normalized_prices_by_sector.png"
    plot_normalized_prices_by_sector(train_prices, sector_map, fig_norm)
    print(f"Saved figure: {fig_norm}")

    fig_log = figures_dir / "log_prices_by_sector.png"
    plot_log_prices_by_sector(train_prices, sector_map, fig_log)
    print(f"Saved figure: {fig_log}")

    corr_matrix = log_rets.corr()
    fig_corr = figures_dir / "return_correlation_heatmap.png"
    plot_correlation_heatmap(corr_matrix, fig_corr)
    print(f"Saved figure: {fig_corr}")

    # Summary report to stdout
    n_i1 = int(integ_df["i1_plausible"].sum())
    print(f"\nOrder of Integration Summary: {n_i1} of {len(integ_df)} tickers are plausibly I(1).")
    print(integ_df[["ticker", "sector", "adf_level_p", "adf_diff_p", "kpss_diff_p", "i1_plausible"]].to_string(index=False))


if __name__ == "__main__":
    main()
