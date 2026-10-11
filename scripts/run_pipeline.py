"""Unified pipeline runner executing end-to-end quantitative research workflow.

Runs data verification, screening, hedge fitting, backtest simulation,
performance metrics, and publication figures across train, validation,
and (if unlocked) out-of-sample test periods using local caches.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd

from src.backtest import compute_weights
from src.config import load_config
from src.data import download_prices, slice_period
from src.metrics import (
    compute_by_year_table,
    compute_per_pair_table,
    compute_portfolio_metrics,
)
from src.pairs import (
    construct_spread,
    fit_hedge,
    half_life,
    screen_pairs,
    zscore,
)
from src.plotting import (
    compute_chained_equity,
    plot_chained_equity,
    plot_drawdown,
    plot_full_span_drawdown,
    plot_gross_vs_net_equity,
    plot_per_pair_pnl,
    plot_signals_with_markers,
    plot_test_zscore_signals,
    plot_trade_distributions,
)
from src.portfolio import compute_turnover, run_portfolio
from src.signals import generate_signals
from src.validation import build_clean_panel


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run end-to-end pairs trading research pipeline across evaluation periods."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/baseline.yaml",
        help="Path to YAML configuration file.",
    )
    return parser.parse_args()


def get_git_commit_hash() -> str:
    """Retrieve current Git commit hash or fallback to frozen tag."""
    try:
        commit = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT_DIR,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        return commit
    except Exception:
        return "UNKNOWN_COMMIT"


def main():
    args = parse_args()
    config_path = ROOT_DIR / args.config
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    cfg = load_config(str(config_path))
    print("=" * 80)
    print(f"STARTING RESEARCH PIPELINE with config: {args.config}")
    print(f"  Unlock Test Period: {cfg.dates.unlock_test}")
    print("=" * 80)

    # Output directories
    data_dir = ROOT_DIR / "data" / "processed"
    raw_dir = ROOT_DIR / "data" / "raw"
    results_dir = ROOT_DIR / "reports" / "results"
    figures_dir = ROOT_DIR / "reports" / "figures"

    data_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # STAGE 1: Data Acquisition / Verification (Using Cache)
    # -------------------------------------------------------------------------
    print("\n[Stage 1/6] Verifying Adjusted Close Price Data...")
    processed_file = data_dir / "close.parquet"
    if processed_file.exists():
        print(f"  Reusing cached price panel: {processed_file}")
        full_close = pd.read_parquet(processed_file)
    else:
        print("  Cached data not found. Fetching raw price history...")
        tickers = [t for sec in cfg.universe.values() for t in sec]
        raw_df, meta = download_prices(
            tickers=tickers,
            start=cfg.dates.download_start,
            end=cfg.dates.download_end,
            cache_dir=raw_dir,
            threads=False,
        )
        full_close, _ = build_clean_panel(raw_df)
        full_close.to_parquet(processed_file)
        print(f"  Processed clean panel saved to: {processed_file}")

    print(f"  Total price panel shape: {full_close.shape[0]} days x {full_close.shape[1]} tickers")

    # -------------------------------------------------------------------------
    # STAGE 2: Pair Screening (Using Cache)
    # -------------------------------------------------------------------------
    print("\n[Stage 2/6] Verifying Pair Screening Registry...")
    selected_pairs_path = results_dir / "selected_pairs.csv"
    screening_path = results_dir / "pair_screening.csv"

    if selected_pairs_path.exists():
        print(f"  Reusing cached selected pairs registry: {selected_pairs_path}")
        selected_pairs_df = pd.read_csv(selected_pairs_path)
    else:
        print("  Cached screening not found. Screening training data (2018–2021)...")
        train_close = slice_period(full_close, "train", cfg)
        screening_df, selected_pairs_df = screen_pairs(train_close, cfg)
        screening_df.to_csv(screening_path, index=False)
        selected_pairs_df.to_csv(selected_pairs_path, index=False)
        print(f"  Saved selected pairs registry ({len(selected_pairs_df)} pairs): {selected_pairs_path}")

    # -------------------------------------------------------------------------
    # STAGE 3: Hedge Parameters & Spreads (Using Cache)
    # -------------------------------------------------------------------------
    print("\n[Stage 3/6] Verifying Frozen Hedge Parameters...")
    hedge_params_path = results_dir / "hedge_params.csv"

    if hedge_params_path.exists():
        print(f"  Reusing cached hedge parameters: {hedge_params_path}")
        hedge_df = pd.read_csv(hedge_params_path)
    else:
        print("  Fitting frozen OLS hedge ratios on training window...")
        train_close = slice_period(full_close, "train", cfg)
        records = []
        for _, row in selected_pairs_df.iterrows():
            pair = row["pair"]
            a = row["leg_a"]
            b = row["leg_b"]
            sec = row["sector"]
            is_expl = bool(row.get("is_exploratory", False))
            log_a_train = np.log(train_close[a])
            log_b_train = np.log(train_close[b])
            fit_res = fit_hedge(log_a_train, log_b_train)
            params = {
                "alpha": fit_res["alpha"],
                "beta": fit_res["beta"],
                "leg_a": a,
                "leg_b": b,
            }
            train_spread = construct_spread(train_close, params)
            hl = half_life(train_spread)
            w_a, w_b = compute_weights(fit_res["beta"])
            records.append({
                "pair": pair,
                "leg_a": a,
                "leg_b": b,
                "sector": sec,
                "alpha": fit_res["alpha"],
                "beta": fit_res["beta"],
                "r_squared": fit_res["r_squared"],
                "res_mean_train": float(train_spread.mean()),
                "res_std_train": float(train_spread.std(ddof=1)),
                "half_life_train": hl,
                "weight_a": w_a,
                "weight_b": w_b,
                "is_exploratory": is_expl,
            })
        hedge_df = pd.DataFrame(records)
        hedge_df.to_csv(hedge_params_path, index=False)
        print(f"  Saved hedge parameters: {hedge_params_path}")

    # -------------------------------------------------------------------------
    # STAGE 4: Multi-Period Backtesting
    # -------------------------------------------------------------------------
    periods = ["train", "validation"]
    if cfg.dates.unlock_test:
        periods.append("test")

    print(f"\n[Stage 4/6] Executing Portfolio Backtests for periods: {periods}...")
    daily_results = {}
    trades_results = {}

    for period in periods:
        print(f"  Simulating {period} period backtest...")
        res = run_portfolio(cfg=cfg, period=period)
        daily_path = results_dir / f"{period}_daily.csv"
        trades_path = results_dir / f"{period}_trades.csv"
        res.daily.to_csv(daily_path, index=True)
        res.trades.to_csv(trades_path, index=False)
        daily_results[period] = res.daily
        trades_results[period] = res.trades

    # -------------------------------------------------------------------------
    # STAGE 5: Performance Metrics & Period Diagnostics
    # -------------------------------------------------------------------------
    print(f"\n[Stage 5/6] Generating Performance Metrics & Diagnostic Reports...")
    pairs = hedge_df["pair"].tolist()
    initial_cap = float(cfg.capital.initial_capital)
    pair_cap = initial_cap / float(len(pairs))

    period_summaries = {}

    for period in periods:
        daily_df = daily_results[period]
        trades_df = trades_results[period]
        turnover = compute_turnover(trades_df, daily_df, annualization=cfg.capital.annualization)

        # 1. Comprehensive JSON metrics
        metrics = compute_portfolio_metrics(
            daily_df=daily_df,
            trades_df=trades_df,
            initial_capital=initial_cap,
            pair_capital=pair_cap,
            pairs=pairs,
            turnover=turnover,
            period_name=period,
            annualization=cfg.capital.annualization,
        )
        json_path = results_dir / f"{period}_metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        # 2. Per-pair breakdown table CSV
        per_pair_df = compute_per_pair_table(
            daily_df=daily_df,
            trades_df=trades_df,
            pair_capital=pair_cap,
            pairs=pairs,
            annualization=cfg.capital.annualization,
        )
        per_pair_df.to_csv(results_dir / f"{period}_per_pair.csv", index=False)

        # 3. By-year breakdown table CSV
        by_year_df = compute_by_year_table(
            daily_df=daily_df,
            trades_df=trades_df,
            initial_capital=initial_cap,
            annualization=cfg.capital.annualization,
        )
        by_year_df.to_csv(results_dir / f"{period}_by_year.csv", index=False)

        # 4. Period diagnostic plots
        plot_gross_vs_net_equity(
            daily_df=daily_df,
            initial_capital=initial_cap,
            out_path=figures_dir / f"{period}_gross_vs_net_equity.png",
            title=f"Portfolio Equity Curve: Gross vs. Net ({period.capitalize()} Period)",
        )
        plot_drawdown(
            equity_series=daily_df["equity"],
            out_path=figures_dir / f"{period}_drawdown.png",
            title=f"Portfolio Underwater Drawdown ({period.capitalize()} Period)",
        )
        plot_per_pair_pnl(
            per_pair_df=per_pair_df,
            out_path=figures_dir / f"{period}_per_pair_pnl.png",
            title=f"Per-Pair Net P&L Contribution ({period.capitalize()} Period)",
        )
        plot_trade_distributions(
            trades_df=trades_df,
            out_path=figures_dir / f"{period}_trade_distributions.png",
            title=f"Trade Return and Holding Duration Distributions ({period.capitalize()} Period)",
        )

        period_summaries[period] = metrics

    # If test period was run, write/refresh test_run_log.json
    if "test" in periods:
        config_bytes = config_path.read_bytes()
        config_sha = hashlib.sha256(config_bytes).hexdigest()
        commit_hash = get_git_commit_hash()
        test_log_path = results_dir / "test_run_log.json"
        log_payload = {
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "git_commit_hash": commit_hash,
            "git_tag": "frozen-v1",
            "config_file": str(args.config),
            "config_sha256": config_sha,
            "evaluation_period": "test",
            "status": "COMPLETED_ONCE",
        }
        with open(test_log_path, "w", encoding="utf-8") as f:
            json.dump(log_payload, f, indent=2)
        print(f"  Test run audit log updated: {test_log_path}")

    # -------------------------------------------------------------------------
    # STAGE 6: Multi-Period Chained Equity, Full Drawdown & Test Signals
    # -------------------------------------------------------------------------
    print("\n[Stage 6/6] Generating Multi-Period and Full-Span Visualizations...")
    train_daily = daily_results["train"]
    val_daily = daily_results["validation"]
    test_daily = daily_results.get("test", None)

    # 1. Chained net equity curve with shaded periods
    chained_fig = figures_dir / "chained_equity.png"
    plot_chained_equity(
        train_daily_df=train_daily,
        val_daily_df=val_daily,
        test_daily_df=test_daily,
        out_path=chained_fig,
        initial_capital=initial_cap,
        chaining_method="compounded",
        title="Multi-Period Chained Portfolio Net Equity (2018–2024)",
    )
    print(f"  Chained net equity chart saved: {chained_fig}")

    # 2. Full-span underwater drawdown
    chained_eq_series = compute_chained_equity(
        train_daily_df=train_daily,
        val_daily_df=val_daily,
        test_daily_df=test_daily,
        initial_capital=initial_cap,
        method="compounded",
    )
    full_dd_fig = figures_dir / "full_span_drawdown.png"
    plot_full_span_drawdown(
        chained_equity_series=chained_eq_series,
        train_end_date=cfg.dates.train_end,
        val_end_date=cfg.dates.validation_end,
        out_path=full_dd_fig,
        title="Full-Span Portfolio Underwater Drawdown (2018–2024)",
    )
    print(f"  Full-span drawdown chart saved: {full_dd_fig}")

    # 3. Test period z-score and signals plots (if test unlocked)
    if test_daily is not None:
        test_prices = slice_period(full_close, "test", cfg)
        z_dict = {}
        sig_dict = {}
        for _, row in hedge_df.iterrows():
            pair_name = row["pair"]
            params = {
                "alpha": float(row["alpha"]),
                "beta": float(row["beta"]),
                "leg_a": row["leg_a"],
                "leg_b": row["leg_b"],
            }
            spread = construct_spread(test_prices, params)
            z = zscore(spread, mu_train=float(row["res_mean_train"]), sd_train=float(row["res_std_train"]))
            sig_df = generate_signals(
                z=z,
                entry_z=cfg.signals.entry_z,
                exit_z=cfg.signals.exit_z,
                max_hold_days=cfg.signals.max_hold_days,
                stop_z=cfg.signals.stop_z,
                close_at_end=True,
            )
            z_dict[pair_name] = z
            sig_dict[pair_name] = sig_df

            # Also generate individual test signal plot
            pair_fig = figures_dir / f"{pair_name}_test_zscore_signals.png"
            plot_signals_with_markers(
                z_series=z,
                signals_df=sig_df,
                entry_z=cfg.signals.entry_z,
                exit_z=cfg.signals.exit_z,
                split_date=cfg.dates.test_end,
                out_path=pair_fig,
                pair_name=f"{pair_name} (Test 2023–2024)",
            )

        # Multi-panel test signal plot
        test_signals_multi_fig = figures_dir / "test_zscore_signals.png"
        plot_test_zscore_signals(
            z_series_dict=z_dict,
            signals_df_dict=sig_dict,
            entry_z=cfg.signals.entry_z,
            exit_z=cfg.signals.exit_z,
            out_path=test_signals_multi_fig,
            title="Test Period Spread Z-Scores and Trade Signals (2023–2024)",
        )
        print(f"  Test z-score signal charts saved: {test_signals_multi_fig}")

    # -------------------------------------------------------------------------
    # PIPELINE SUMMARY TABLE
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    print(f"{'Metric':<30} | " + " | ".join(f"{p.upper():<14}" for p in periods))
    print("-" * 80)

    summary_rows = [
        ("Trading Days", lambda m: f"{m['trading_days']}"),
        ("Initial Capital ($)", lambda m: f"{m['initial_capital']:,.0f}"),
        ("Ending Equity ($)", lambda m: f"{m['ending_equity']:,.2f}"),
        ("Net Cumulative Return", lambda m: f"{m['performance_comparison']['net']['cumulative_return']*100:+.2f}%"),
        ("Net Annualized CAGR", lambda m: f"{m['performance_comparison']['net']['annualized_return_cagr']*100:+.2f}%"),
        ("Net Sharpe (rf=0)", lambda m: f"{m['performance_comparison']['net']['sharpe_ratio_rf_0']:.4f}"),
        ("Max Drawdown", lambda m: f"{m['performance_comparison']['net']['max_drawdown']*100:.2f}%"),
        ("Gross P&L ($)", lambda m: f"{m['performance_comparison']['gross']['total_pnl']:+,.2f}"),
        ("Friction Drag ($)", lambda m: f"{m['costs']['total_all_costs']:,.2f}"),
        ("Net P&L ($)", lambda m: f"{m['performance_comparison']['net']['total_pnl']:+,.2f}"),
        ("Cost Drag (% of Gross)", lambda m: f"{m['costs']['cost_drag_on_gross_pnl']*100:.1f}%"),
        ("Total Trades", lambda m: f"{m['trade_statistics']['n_trades']}"),
        ("Win Rate", lambda m: f"{m['trade_statistics']['win_rate']*100:.2f}%"),
        ("Turnover (annualized)", lambda m: f"{m['market_exposure']['annualized_turnover']:.2f}x"),
    ]

    for label, extractor in summary_rows:
        row_str = f"{label:<30} | " + " | ".join(f"{extractor(period_summaries[p]):<14}" for p in periods)
        print(row_str)

    print("=" * 80)
    print("Pipeline completed successfully.\n")


if __name__ == "__main__":
    main()
