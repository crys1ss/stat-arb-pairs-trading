"""Script to fit frozen hedge ratios, build spreads, compute rolling beta diagnostics, and generate figures."""

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
from src.pairs import construct_spread, fit_hedge, half_life, zscore
from src.plotting import plot_pair_prices, plot_pair_spread, plot_rolling_betas


def parse_args():
    parser = argparse.ArgumentParser(description="Fit hedge parameters and construct spreads.")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/baseline.yaml",
        help="Path to YAML configuration file.",
    )
    return parser.parse_args()


def compute_rolling_beta(
    log_a: pd.Series,
    log_b: pd.Series,
    window: int = 252,
) -> pd.Series:
    """Compute rolling OLS beta of log_a on log_b over a specified window."""
    rolling_beta = pd.Series(index=log_a.index, dtype=float)
    x = log_b.values
    y = log_a.values
    n = len(x)

    for i in range(window - 1, n):
        x_win = x[i - window + 1 : i + 1]
        y_win = y[i - window + 1 : i + 1]
        X = np.column_stack([np.ones_like(x_win), x_win])
        params, _, _, _ = np.linalg.lstsq(X, y_win, rcond=None)
        rolling_beta.iloc[i] = float(params[1])

    return rolling_beta


def main():
    args = parse_args()
    cfg = load_config(args.config)
    print(f"Loaded config from {args.config}")

    results_dir = ROOT_DIR / "reports" / "results"
    figures_dir = ROOT_DIR / "reports" / "figures"
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    selected_csv = results_dir / "selected_pairs.csv"
    if not selected_csv.exists():
        raise FileNotFoundError(f"Selected pairs missing at {selected_csv}. Run scripts/screen_pairs.py first.")

    selected_pairs_df = pd.read_csv(selected_csv)
    print(f"Loaded {len(selected_pairs_df)} selected pairs from {selected_csv}")

    data_file = ROOT_DIR / "data" / "processed" / "close.parquet"
    full_close = pd.read_parquet(data_file)

    # Slice train and validation data
    train_prices = slice_period(full_close, "train", cfg)
    val_prices = slice_period(full_close, "validation", cfg)
    train_val_prices = pd.concat([train_prices, val_prices]).sort_index()

    train_end = cfg.dates.train_end

    hedge_records = []
    rolling_betas: dict[str, pd.Series] = {}
    frozen_betas: dict[str, float] = {}

    for _, row in selected_pairs_df.iterrows():
        pair_name = row["pair"]
        leg_a = row["leg_a"]
        leg_b = row["leg_b"]
        sector = row["sector"]
        is_exploratory = bool(row.get("is_exploratory", False))

        # 1. Fit OLS strictly on training log prices
        log_a_train = np.log(train_prices[leg_a])
        log_b_train = np.log(train_prices[leg_b])
        hedge_res = fit_hedge(log_a_train, log_b_train)

        # Spread on training data
        params = {
            "alpha": hedge_res["alpha"],
            "beta": hedge_res["beta"],
            "leg_a": leg_a,
            "leg_b": leg_b,
        }
        train_spread = construct_spread(train_prices, params)
        mu_train = float(train_spread.mean())
        sd_train = float(train_spread.std(ddof=1))
        hl = half_life(train_spread)

        # Dollar weights according to position mapping formula
        abs_beta = abs(hedge_res["beta"])
        w_a = 1.0 / (1.0 + abs_beta)
        w_b = -hedge_res["beta"] / (1.0 + abs_beta)

        hedge_records.append({
            "pair": pair_name,
            "leg_a": leg_a,
            "leg_b": leg_b,
            "sector": sector,
            "alpha": round(hedge_res["alpha"], 6),
            "beta": round(hedge_res["beta"], 6),
            "r_squared": round(hedge_res["r_squared"], 4),
            "res_mean_train": round(mu_train, 6),
            "res_std_train": round(sd_train, 6),
            "half_life_train": round(hl, 2) if not np.isnan(hl) else float("nan"),
            "weight_a": round(w_a, 6),
            "weight_b": round(w_b, 6),
            "is_exploratory": is_exploratory,
        })

        frozen_betas[pair_name] = hedge_res["beta"]

        # 2. Construct spread over combined train + validation using FROZEN parameters
        train_val_spread = construct_spread(train_val_prices, params)

        # 3. Figures for each selected pair
        # Prices and log prices
        price_fig = figures_dir / f"{pair_name}_prices_and_log.png"
        plot_pair_prices(train_val_prices, leg_a, leg_b, split_date=train_end, out_path=price_fig)

        # Spread with frozen calibration bands
        spread_fig = figures_dir / f"{pair_name}_spread_bands.png"
        plot_pair_spread(
            spread=train_val_spread,
            mu_train=mu_train,
            sd_train=sd_train,
            entry_z=cfg.signals.entry_z,
            exit_z=cfg.signals.exit_z,
            split_date=train_end,
            out_path=spread_fig,
            pair_name=f"{pair_name} ({'EXPLORATORY' if is_exploratory else 'CONFIRMED'})",
        )

        # 4. Diagnostic: Rolling 252-day OLS beta
        log_a_tv = np.log(train_val_prices[leg_a])
        log_b_tv = np.log(train_val_prices[leg_b])
        rolling_betas[pair_name] = compute_rolling_beta(log_a_tv, log_b_tv, window=252)

    # Save hedge parameters table
    hedge_df = pd.DataFrame(hedge_records)
    hedge_csv = results_dir / "hedge_params.csv"
    hedge_df.to_csv(hedge_csv, index=False)
    print(f"Hedge parameters saved to {hedge_csv}")

    # Save rolling beta diagnostic
    rolling_beta_df = pd.DataFrame(rolling_betas, index=train_val_prices.index)
    rolling_beta_csv = results_dir / "rolling_beta.csv"
    rolling_beta_df.to_csv(rolling_beta_csv)
    print(f"Rolling beta diagnostics saved to {rolling_beta_csv}")

    # Plot rolling betas diagnostic
    rolling_beta_fig = figures_dir / "rolling_beta.png"
    plot_rolling_betas(rolling_beta_df, frozen_betas, split_date=train_end, out_path=rolling_beta_fig)
    print(f"Rolling beta figure saved to {rolling_beta_fig}")

    print("\nFitted Hedge Parameters (Train Window 2018–2021):")
    print(hedge_df[["pair", "sector", "alpha", "beta", "r_squared", "res_std_train", "half_life_train", "weight_a", "weight_b"]].to_string(index=False))


if __name__ == "__main__":
    main()
