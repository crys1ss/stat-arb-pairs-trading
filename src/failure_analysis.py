"""Risk, stability, and failure analysis diagnostics engine (Day 12).

Implements statistical diagnostics to explain pairs-trading performance:
1. Market exposure: SPY beta regression with Newey-West HAC standard errors (5 lags)
2. Hedge-ratio instability: Rolling 252-day beta tracking and percentage deviation from frozen beta
3. Cointegration decay: Out-of-sample Engle-Granger re-estimation and half-life drift
4. Structural breaks: OLS-residual CUSUM test (breaks_cusumolsresid) over full span
5. Trade divergence: Pathological divergence analysis for the 5 worst trades
6. Subperiod breakdown: Performance by calendar year and stressed market regimes
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import breaks_cusumolsresid

from src.config import Config, load_config
from src.data import download_prices, slice_period
from src.metrics import (
    compute_annualized_return,
    compute_annualized_volatility,
    compute_cumulative_return,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_trade_metrics,
)
from src.pairs import construct_spread, engle_granger, half_life, zscore


def compute_market_exposure(
    cfg: Config,
    results_dir: Union[str, Path] = "reports/results",
    raw_dir: Union[str, Path] = "data/raw",
) -> pd.DataFrame:
    """Regress daily strategy returns on SPY market returns with Newey-West HAC (5 lags).

    Parameters
    ----------
    cfg : Config
        Validated pipeline configuration.
    results_dir : Union[str, Path], default "reports/results"
        Directory containing period daily portfolio CSVs.
    raw_dir : Union[str, Path], default "data/raw"
        Directory for caching SPY benchmark prices.

    Returns
    -------
    pd.DataFrame
        Table with period, beta, HAC t-stat, p-value, R-squared, and annualized alpha.
    """
    results_path = Path(results_dir)
    # Ensure SPY data is downloaded and cached
    spy_raw = download_prices(
        cfg=cfg,
        refresh=False,
        raw_dir=raw_dir,
        tickers=["SPY"],
        filename="spy.parquet",
    )

    if isinstance(spy_raw.columns, pd.MultiIndex):
        spy_close = spy_raw["Close"]["SPY"]
    else:
        spy_close = spy_raw["SPY"] if "SPY" in spy_raw.columns else spy_raw.iloc[:, 0]

    spy_ret = spy_close.pct_change().dropna()
    spy_ret.name = "spy_return"

    periods = ["train", "validation", "test", "full_span"]
    records = []

    daily_dfs = {}
    for p in ["train", "validation", "test"]:
        p_csv = results_path / f"{p}_daily.csv"
        if not p_csv.exists():
            raise FileNotFoundError(f"Daily portfolio results missing for period '{p}' at {p_csv}")
        df = pd.read_csv(p_csv, index_col=0, parse_dates=True)
        daily_dfs[p] = df

    daily_dfs["full_span"] = pd.concat([daily_dfs["train"], daily_dfs["validation"], daily_dfs["test"]])

    for p in periods:
        daily = daily_dfs[p]
        strat_ret = daily["return"].dropna()

        # Align on common dates
        merged = pd.concat([strat_ret, spy_ret], axis=1, join="inner").dropna()
        if len(merged) < 10:
            continue

        y = merged["return"].values
        x = merged["spy_return"].values
        X = sm.add_constant(x)

        # Newey-West HAC standard errors with 5 lags
        model = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

        alpha_daily = float(model.params[0])
        beta = float(model.params[1])
        t_stat_beta = float(model.tvalues[1])
        pval_beta = float(model.pvalues[1])
        r2 = float(model.rsquared)
        corr = float(np.corrcoef(x, y)[0, 1])

        records.append({
            "period": p,
            "trading_days": len(merged),
            "market_beta": round(beta, 4),
            "hac_tstat_5lags": round(t_stat_beta, 4),
            "p_value": round(pval_beta, 6),
            "r_squared": round(r2, 6),
            "correlation_spy": round(corr, 4),
            "annualized_alpha": round(alpha_daily * 252.0, 6),
        })

    return pd.DataFrame(records)


def compute_hedge_ratio_instability(
    prices: pd.DataFrame,
    hedge_params: pd.DataFrame,
    window: int = 252,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute rolling 252-day OLS hedge ratio and percentage deviation from frozen baseline.

    Parameters
    ----------
    prices : pd.DataFrame
        Full-span closing price panel.
    hedge_params : pd.DataFrame
        Frozen hedge parameters registry.
    window : int, default 252
        Rolling calibration window length.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        (summary_df, rolling_beta_time_series_df)
    """
    rolling_betas = {}
    summary_records = []
    n = len(prices)

    for _, row in hedge_params.iterrows():
        pair = str(row["pair"])
        leg_a = str(row["leg_a"])
        leg_b = str(row["leg_b"])
        frozen_beta = float(row["beta"])

        log_a = np.log(prices[leg_a].values)
        log_b = np.log(prices[leg_b].values)

        roll_beta_arr = np.full(n, np.nan, dtype=float)

        for i in range(window - 1, n):
            y_win = log_a[i - window + 1 : i + 1]
            x_win = log_b[i - window + 1 : i + 1]
            X = np.column_stack([np.ones_like(x_win), x_win])
            p, _, _, _ = np.linalg.lstsq(X, y_win, rcond=None)
            roll_beta_arr[i] = float(p[1])

        roll_series = pd.Series(roll_beta_arr, index=prices.index, name=pair)
        rolling_betas[pair] = roll_series

        valid_betas = roll_series.dropna()
        if not valid_betas.empty:
            mean_beta = float(valid_betas.mean())
            min_beta = float(valid_betas.min())
            max_beta = float(valid_betas.max())
            end_beta = float(valid_betas.iloc[-1])

            # Percentage deviation from frozen beta
            pct_devs = (valid_betas - frozen_beta) / abs(frozen_beta) * 100.0
            mean_abs_pct_dev = float(pct_devs.abs().mean())
            max_abs_pct_dev = float(pct_devs.abs().max())
            end_pct_dev = float((end_beta - frozen_beta) / abs(frozen_beta) * 100.0)

            summary_records.append({
                "pair": pair,
                "frozen_beta": round(frozen_beta, 6),
                "mean_rolling_beta": round(mean_beta, 6),
                "min_rolling_beta": round(min_beta, 6),
                "max_rolling_beta": round(max_beta, 6),
                "end_of_test_beta": round(end_beta, 6),
                "mean_abs_pct_deviation": round(mean_abs_pct_dev, 2),
                "max_abs_pct_deviation": round(max_abs_pct_dev, 2),
                "end_of_test_pct_deviation": round(end_pct_dev, 2),
            })

    summary_df = pd.DataFrame(summary_records)
    rolling_df = pd.DataFrame(rolling_betas, index=prices.index)
    return summary_df, rolling_df


def compute_cointegration_decay(
    prices: pd.DataFrame,
    hedge_params: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """Rerun Engle-Granger tests separately across train, validation, and test windows.

    Diagnostic only; does not alter model selection.
    """
    records = []
    periods = ["train", "validation", "test"]

    for period in periods:
        p_prices = slice_period(prices, period, cfg)
        for _, row in hedge_params.iterrows():
            pair = str(row["pair"])
            leg_a = str(row["leg_a"])
            leg_b = str(row["leg_b"])

            log_a = np.log(p_prices[leg_a])
            log_b = np.log(p_prices[leg_b])

            stat_ab, pval_ab, _ = engle_granger(log_a, log_b, trend="c")
            stat_ba, pval_ba, _ = engle_granger(log_b, log_a, trend="c")
            max_p = max(pval_ab, pval_ba)

            # Measure half-life on period-specific regression residuals
            X = np.column_stack([np.ones(len(log_b)), log_b.values])
            p_fit, _, _, _ = np.linalg.lstsq(X, log_a.values, rcond=None)
            spread_res = log_a.values - (p_fit[0] + p_fit[1] * log_b.values)
            hl = half_life(spread_res)

            records.append({
                "pair": pair,
                "period": period,
                "trading_days": len(p_prices),
                "stat_a_on_b": round(stat_ab, 4),
                "pval_a_on_b": round(pval_ab, 6),
                "stat_b_on_a": round(stat_ba, 4),
                "pval_b_on_a": round(pval_ba, 6),
                "bidirectional_max_pval": round(max_p, 6),
                "half_life_days": round(hl, 2),
                "is_cointegrated_5pct": bool(max_p < 0.05),
            })

    return pd.DataFrame(records)


def compute_structural_breaks(
    prices: pd.DataFrame,
    hedge_params: pd.DataFrame,
) -> pd.DataFrame:
    """Run OLS-residual CUSUM test (statsmodels breaks_cusumolsresid) over full 2018–2024 span.

    Null Hypothesis (H0): Parameter stability across the entire sample period.
    """
    records = []
    for _, row in hedge_params.iterrows():
        pair = str(row["pair"])
        leg_a = str(row["leg_a"])
        leg_b = str(row["leg_b"])

        log_a = np.log(prices[leg_a].values)
        log_b = np.log(prices[leg_b].values)

        # OLS regression across full span
        X = np.column_stack([np.ones_like(log_b), log_b])
        p_fit, _, _, _ = np.linalg.lstsq(X, log_a, rcond=None)
        residuals = log_a - (p_fit[0] + p_fit[1] * log_b)

        # CUSUM test with ddof=2 (constant and slope)
        sup_b, pval, crit = breaks_cusumolsresid(residuals, ddof=2)

        records.append({
            "pair": pair,
            "cusum_statistic": round(float(sup_b), 4),
            "p_value": round(float(pval), 6),
            "crit_1pct": round(float(crit[0][1] if isinstance(crit[0], (tuple, list)) else crit[0]), 4),
            "crit_5pct": round(float(crit[1][1] if isinstance(crit[1], (tuple, list)) else crit[1]), 4),
            "crit_10pct": round(float(crit[2][1] if isinstance(crit[2], (tuple, list)) else crit[2]), 4),
            "has_structural_break": bool(pval < 0.05),
        })

    return pd.DataFrame(records)


def extract_worst_trades(
    results_dir: Union[str, Path] = "reports/results",
    n_worst: int = 5,
    prices: Optional[pd.DataFrame] = None,
    hedge_params: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Extract and analyze the N worst trades by net P&L across all evaluation periods."""
    results_path = Path(results_dir)
    trade_frames = []

    for p in ["train", "validation", "test"]:
        t_file = results_path / f"{p}_trades.csv"
        if t_file.exists():
            df = pd.read_csv(t_file)
            df["period"] = p
            trade_frames.append(df)

    if not trade_frames:
        raise FileNotFoundError("No trade logs found in results directory.")

    all_trades = pd.concat(trade_frames, ignore_index=True)
    all_trades = all_trades.sort_values("net_pnl", ascending=True).reset_index(drop=True)
    worst_df = all_trades.head(n_worst).copy()

    # Pre-compute spreads and z-scores if full prices and hedge params are supplied
    z_dict = {}
    if prices is not None and hedge_params is not None:
        for _, row in hedge_params.iterrows():
            p_name = str(row["pair"])
            alpha = float(row["alpha"])
            beta = float(row["beta"])
            mu = float(row["res_mean_train"])
            sd = float(row["res_std_train"])
            leg_a = str(row["leg_a"])
            leg_b = str(row["leg_b"])

            spread = np.log(prices[leg_a]) - alpha - beta * np.log(prices[leg_b])
            z_dict[p_name] = (spread - mu) / sd

    details = []
    z_min_list = []
    z_max_list = []
    z_entry_list = []
    z_exit_list = []

    for rank, (_, row) in enumerate(worst_df.iterrows(), start=1):
        pair = str(row["pair"])
        entry_dt = pd.to_datetime(row["entry_date"])
        exit_dt = pd.to_datetime(row["exit_date"])
        direction = int(row["direction"])
        net_pnl = float(row["net_pnl"])
        days_held = int(row["holding_days"])
        exit_reason = str(row["exit_reason"])

        if pair in z_dict:
            z_full = z_dict[pair]
            trade_mask = (z_full.index >= entry_dt) & (z_full.index <= exit_dt)
            z_trade = z_full.loc[trade_mask]

            z_entry_val = float(z_trade.iloc[0]) if not z_trade.empty else np.nan
            z_exit_val = float(z_trade.iloc[-1]) if not z_trade.empty else np.nan
            z_min_val = float(z_trade.min()) if not z_trade.empty else np.nan
            z_max_val = float(z_trade.max()) if not z_trade.empty else np.nan

            # Path snippet extended 10 bars before entry and 5 bars after exit for visualization
            ext_mask = (z_full.index >= entry_dt - pd.Timedelta(days=15)) & (z_full.index <= exit_dt + pd.Timedelta(days=10))
            z_extended = z_full.loc[ext_mask]
        else:
            z_entry_val = z_exit_val = z_min_val = z_max_val = np.nan
            z_extended = pd.Series(dtype=float)

        z_entry_list.append(round(z_entry_val, 3) if not np.isnan(z_entry_val) else np.nan)
        z_exit_list.append(round(z_exit_val, 3) if not np.isnan(z_exit_val) else np.nan)
        z_min_list.append(round(z_min_val, 3) if not np.isnan(z_min_val) else np.nan)
        z_max_list.append(round(z_max_val, 3) if not np.isnan(z_max_val) else np.nan)

        details.append({
            "rank": rank,
            "period": row["period"],
            "pair": pair,
            "direction": direction,
            "entry_date": str(row["entry_date"]),
            "exit_date": str(row["exit_date"]),
            "holding_days": days_held,
            "exit_reason": exit_reason,
            "net_pnl": net_pnl,
            "gross_pnl": float(row["gross_pnl"]),
            "costs": float(row["costs"]),
            "z_extended": z_extended,
        })

    worst_df["rank"] = range(1, len(worst_df) + 1)
    worst_df["z_entry"] = z_entry_list
    worst_df["z_exit"] = z_exit_list
    worst_df["z_min"] = z_min_list
    worst_df["z_max"] = z_max_list

    cols = [
        "rank", "period", "pair", "direction", "entry_date", "exit_date",
        "holding_days", "exit_reason", "gross_pnl", "trade_cost", "borrow_cost",
        "costs", "net_pnl", "return_on_capital", "z_entry", "z_exit", "z_min", "z_max"
    ]
    present_cols = [c for c in cols if c in worst_df.columns]
    return worst_df[present_cols], details


def compute_subperiod_analysis(
    cfg: Config,
    results_dir: Union[str, Path] = "reports/results",
) -> pd.DataFrame:
    """Evaluate strategy performance across calendar years and defined stress regimes."""
    results_path = Path(results_dir)

    daily_frames = []
    trade_frames = []
    for p in ["train", "validation", "test"]:
        d_file = results_path / f"{p}_daily.csv"
        t_file = results_path / f"{p}_trades.csv"
        if d_file.exists():
            daily_frames.append(pd.read_csv(d_file, index_col=0, parse_dates=True))
        if t_file.exists():
            trade_frames.append(pd.read_csv(t_file))

    full_daily = pd.concat(daily_frames).sort_index()
    full_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    if not full_trades.empty:
        full_trades["entry_date"] = pd.to_datetime(full_trades["entry_date"])
        full_trades["exit_date"] = pd.to_datetime(full_trades["exit_date"])

    initial_capital = float(cfg.capital.initial_capital)

    windows = [
        # Calendar Years
        ("2018", "2018-01-01", "2018-12-31", "Calendar Year"),
        ("2019", "2019-01-01", "2019-12-31", "Calendar Year"),
        ("2020", "2020-01-01", "2020-12-31", "Calendar Year"),
        ("2021", "2021-01-01", "2021-12-31", "Calendar Year"),
        ("2022", "2022-01-01", "2022-12-31", "Calendar Year"),
        ("2023", "2023-01-01", "2023-12-31", "Calendar Year"),
        ("2024", "2024-01-01", "2024-12-31", "Calendar Year"),
        # Stressed Market Windows
        ("2020 Covid Crash", "2020-02-01", "2020-04-30", "Stress Window"),
        ("2022 Rate Hikes", "2022-01-01", "2022-12-31", "Stress Window"),
    ]

    records = []
    for name, start_str, end_str, category in windows:
        d_start = pd.to_datetime(start_str)
        d_end = pd.to_datetime(end_str)

        sub_daily = full_daily[(full_daily.index >= d_start) & (full_daily.index <= d_end)]
        if sub_daily.empty:
            continue

        n_days = len(sub_daily)
        gross_pnl = float(sub_daily["gross_pnl"].sum())
        trade_costs = float(sub_daily["trade_cost"].sum())
        borrow_costs = float(sub_daily["borrow_cost"].sum())
        total_costs = trade_costs + borrow_costs
        net_pnl = float(sub_daily["net_pnl"].sum())

        rets = sub_daily["return"].dropna()
        sharpe = compute_sharpe_ratio(rets, rf=0.0, annualization=252)

        # Equity tracking within window
        eq = initial_capital + sub_daily["net_pnl"].cumsum()
        cum_ret = (eq.iloc[-1] - initial_capital) / initial_capital
        cagr = compute_annualized_return(eq, initial_capital, annualization=252)
        max_dd, max_dd_dur, _ = compute_max_drawdown(eq)

        # Trades exiting within window
        if not full_trades.empty:
            sub_trades = full_trades[(full_trades["exit_date"] >= d_start) & (full_trades["exit_date"] <= d_end)]
            n_trades = len(sub_trades)
            win_rate = float((sub_trades["net_pnl"] > 0).sum() / n_trades) if n_trades > 0 else np.nan
        else:
            n_trades = 0
            win_rate = np.nan

        records.append({
            "subperiod_name": name,
            "category": category,
            "start_date": start_str,
            "end_date": end_str,
            "trading_days": n_days,
            "gross_pnl": round(gross_pnl, 2),
            "trade_costs": round(trade_costs, 2),
            "borrow_costs": round(borrow_costs, 2),
            "total_costs": round(total_costs, 2),
            "net_pnl": round(net_pnl, 2),
            "net_cagr": round(cagr, 6) if not np.isnan(cagr) else np.nan,
            "net_sharpe": round(sharpe, 4) if not np.isnan(sharpe) else np.nan,
            "max_drawdown": round(max_dd, 6),
            "n_trades": n_trades,
            "win_rate": round(win_rate, 4) if not np.isnan(win_rate) else np.nan,
        })

    return pd.DataFrame(records)
