"""Portfolio performance metrics, risk measures, drawdown, and trade statistics module."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


def compute_turnover(trades_df: pd.DataFrame, daily_df: pd.DataFrame, annualization: int = 252) -> float:
    """Compute annualized portfolio turnover.

    Turnover formulation:
        Turnover = (total_traded_notional / average_equity) * (annualization / T)

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade log DataFrame containing entry and exit prices and share quantities.
    daily_df : pd.DataFrame
        Daily portfolio DataFrame containing 'equity'.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    float
        Annualized turnover ratio. Returns NaN if zero days or non-positive equity.
    """
    if trades_df.empty or daily_df.empty:
        return 0.0

    avg_equity = float(daily_df["equity"].mean())
    if avg_equity <= 0.0 or math.isnan(avg_equity):
        return float("nan")

    t_days = len(daily_df)
    if t_days == 0:
        return float("nan")

    # Traded notional = entry notional + exit notional per trade
    entry_notional = (
        trades_df["shares_a"].abs() * trades_df["entry_price_a"]
        + trades_df["shares_b"].abs() * trades_df["entry_price_b"]
    ).sum()
    exit_notional = (
        trades_df["shares_a"].abs() * trades_df["exit_price_a"]
        + trades_df["shares_b"].abs() * trades_df["exit_price_b"]
    ).sum()
    total_traded_notional = float(entry_notional + exit_notional)

    annualized_turnover = (total_traded_notional / avg_equity) * (annualization / t_days)
    return float(annualized_turnover)


def compute_cumulative_return(equity: pd.Series, initial_capital: float) -> float:
    """Compute cumulative portfolio return over the period.

    Parameters
    ----------
    equity : pd.Series
        Equity curve time series.
    initial_capital : float
        Starting portfolio capital.

    Returns
    -------
    float
        Cumulative return as a decimal fraction, or NaN if invalid.
    """
    if equity.empty or initial_capital <= 0.0:
        return float("nan")
    ending_equity = float(equity.iloc[-1])
    return (ending_equity - initial_capital) / initial_capital


def compute_annualized_return(
    equity: pd.Series,
    initial_capital: float,
    annualization: int = 252,
) -> float:
    """Compute geometric compound annualized growth rate (CAGR).

    Formulation:
        (ending_equity / initial_capital) ** (annualization / N) - 1.0

    Parameters
    ----------
    equity : pd.Series
        Equity curve time series.
    initial_capital : float
        Starting portfolio capital.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    float
        Geometric annualized return, or NaN if invalid/zero periods.
    """
    n_days = len(equity)
    if n_days == 0 or initial_capital <= 0.0:
        return float("nan")

    ending_equity = float(equity.iloc[-1])
    if ending_equity <= 0.0:
        return float("nan")

    cum_ratio = ending_equity / initial_capital
    if cum_ratio <= 0.0:
        return float("nan")

    return float(cum_ratio ** (annualization / n_days) - 1.0)


def compute_annualized_volatility(
    returns: pd.Series,
    annualization: int = 252,
) -> float:
    """Compute sample annualized volatility of daily returns.

    Formulation:
        std(returns, ddof=1) * sqrt(annualization)

    Parameters
    ----------
    returns : pd.Series
        Daily portfolio return series.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    float
        Annualized volatility. Returns NaN for zero-volatility or fewer than 2 bars.
    """
    clean_rets = returns.dropna()
    if len(clean_rets) < 2:
        return float("nan")

    std_val = float(clean_rets.std(ddof=1))
    if std_val <= 0.0 or math.isnan(std_val):
        return float("nan")

    return float(std_val * math.sqrt(annualization))


def compute_sharpe_ratio(
    returns: pd.Series,
    rf: float = 0.0,
    annualization: int = 252,
) -> float:
    """Compute annualized Sharpe ratio under explicit benchmark risk-free rate assumption (rf = 0.0).

    Formulation:
        (mean(returns) - (rf / annualization)) / std(returns, ddof=1) * sqrt(annualization)

    Parameters
    ----------
    returns : pd.Series
        Daily portfolio return series.
    rf : float, default 0.0
        Annualized risk-free rate.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    float
        Annualized Sharpe ratio. Returns NaN if volatility is zero or returns series is trivial.
    """
    clean_rets = returns.dropna()
    if len(clean_rets) < 2:
        return float("nan")

    std_val = float(clean_rets.std(ddof=1))
    if std_val <= 0.0 or math.isnan(std_val):
        return float("nan")

    daily_rf = rf / float(annualization)
    mean_excess = float(clean_rets.mean() - daily_rf)
    sharpe = (mean_excess / std_val) * math.sqrt(annualization)

    if math.isinf(sharpe):
        return float("nan")
    return float(sharpe)


def compute_drawdown_series(equity: pd.Series) -> pd.Series:
    """Calculate the continuous underwater drawdown series from cumulative equity peaks.

    Formulation:
        peak_t = max_{s <= t} equity_s
        drawdown_t = (equity_t - peak_t) / peak_t <= 0.0

    Parameters
    ----------
    equity : pd.Series
        Equity curve series.

    Returns
    -------
    pd.Series
        Drawdown series as non-positive decimal fraction.
    """
    if equity.empty:
        return pd.Series(dtype=float)
    peak = equity.cummax()
    dd = (equity - peak) / peak
    dd.name = "drawdown"
    return dd


def compute_max_drawdown(equity: pd.Series) -> Tuple[float, int, pd.Series]:
    """Calculate maximum drawdown magnitude, maximum drawdown duration in trading days, and the drawdown curve.

    Parameters
    ----------
    equity : pd.Series
        Equity curve series.

    Returns
    -------
    Tuple[float, int, pd.Series]
        (max_drawdown_fraction, max_duration_days, drawdown_series)
        max_drawdown is reported as a non-negative decimal fraction (e.g. 0.045 for 4.5% drawdown).
    """
    if equity.empty:
        return 0.0, 0, pd.Series(dtype=float)

    dd_series = compute_drawdown_series(equity)
    max_dd = float(abs(dd_series.min())) if not dd_series.empty else 0.0

    # Calculate maximum drawdown duration (consecutive days below previous high water mark)
    peak = equity.cummax()
    max_duration = 0
    curr_duration = 0

    for eq, pk in zip(equity.values, peak.values):
        if eq < pk:
            curr_duration += 1
            if curr_duration > max_duration:
                max_duration = curr_duration
        else:
            curr_duration = 0

    return max_dd, max_duration, dd_series


def compute_trade_metrics(trades_df: pd.DataFrame) -> Dict[str, Any]:
    """Compute trade-level summary statistics.

    Zero-trade cases strictly return NaN, never inf.

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade log DataFrame containing 'net_pnl', 'return_on_capital', and 'holding_days'.

    Returns
    -------
    Dict[str, Any]
        Dictionary of trade performance statistics.
    """
    n_trades = len(trades_df)
    if n_trades == 0:
        return {
            "n_trades": 0,
            "win_rate": float("nan"),
            "n_wins": 0,
            "n_losses": 0,
            "mean_trade_return": float("nan"),
            "median_trade_return": float("nan"),
            "mean_holding_days": float("nan"),
            "max_holding_days": float("nan"),
            "profit_factor": float("nan"),
        }

    net_pnls = trades_df["net_pnl"].values
    trade_rets = trades_df["return_on_capital"].values
    holding_days = trades_df["holding_days"].values

    wins = net_pnls > 0.0
    losses = net_pnls < 0.0
    n_wins = int(np.sum(wins))
    n_losses = int(np.sum(losses))
    win_rate = float(n_wins / n_trades)

    gross_gains = float(np.sum(net_pnls[wins])) if n_wins > 0 else 0.0
    gross_losses = float(abs(np.sum(net_pnls[losses]))) if n_losses > 0 else 0.0

    if gross_losses > 0.0:
        profit_factor = gross_gains / gross_losses
    elif gross_gains > 0.0:
        profit_factor = float("nan")  # Undefined without losses, return NaN not inf
    else:
        profit_factor = float("nan")

    return {
        "n_trades": n_trades,
        "win_rate": win_rate,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "mean_trade_return": float(np.mean(trade_rets)),
        "median_trade_return": float(np.median(trade_rets)),
        "mean_holding_days": float(np.mean(holding_days)),
        "max_holding_days": int(np.max(holding_days)),
        "profit_factor": profit_factor,
    }


def compute_concentration_metrics(pair_pnls: Dict[str, float]) -> Dict[str, Any]:
    """Compute each pair's share of absolute P&L and the Herfindahl-Hirschman Index (HHI).

    Parameters
    ----------
    pair_pnls : Dict[str, float]
        Dictionary mapping pair name to its net P&L.

    Returns
    -------
    Dict[str, Any]
        Dictionary containing per-pair absolute P&L shares and portfolio HHI.
    """
    if not pair_pnls:
        return {"pnl_shares": {}, "hhi": float("nan")}

    abs_pnls = {k: abs(v) for k, v in pair_pnls.items()}
    total_abs = sum(abs_pnls.values())

    if total_abs <= 0.0:
        shares = {k: 0.0 for k in pair_pnls}
        return {"pnl_shares": shares, "hhi": float("nan")}

    shares = {k: float(v / total_abs) for k, v in abs_pnls.items()}
    hhi = float(sum(s ** 2 for s in shares.values()))

    return {
        "pnl_shares": shares,
        "hhi": hhi,
    }


def compute_per_pair_table(
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    pair_capital: float,
    pairs: Sequence[str],
    annualization: int = 252,
) -> pd.DataFrame:
    """Generate per-pair performance summary table.

    Parameters
    ----------
    daily_df : pd.DataFrame
        Portfolio daily DataFrame with columns 'pnl_{pair}'.
    trades_df : pd.DataFrame
        Trade log DataFrame with 'pair' column.
    pair_capital : float
        Capital allocated to each pair.
    pairs : Sequence[str]
        List of selected pair names.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    pd.DataFrame
        Table indexed by pair symbol.
    """
    records = []

    # Calculate overall total absolute net P&L across all pairs for share calculation
    all_pair_pnls = {}
    for p in pairs:
        col = f"pnl_{p}"
        all_pair_pnls[p] = float(daily_df[col].sum()) if col in daily_df.columns else 0.0

    total_abs_pnl = sum(abs(v) for v in all_pair_pnls.values())

    for p in pairs:
        p_trades = trades_df[trades_df["pair"] == p] if not trades_df.empty else pd.DataFrame()
        n_tr = len(p_trades)

        col = f"pnl_{p}"
        p_daily_net = daily_df[col] if col in daily_df.columns else pd.Series(0.0, index=daily_df.index)
        net_pnl = float(p_daily_net.sum())

        if n_tr > 0:
            gross_pnl = float(p_trades["gross_pnl"].sum())
            trade_cost = float(p_trades["trade_cost"].sum())
            borrow_cost = float(p_trades["borrow_cost"].sum())
            win_rate = float((p_trades["net_pnl"] > 0).mean())
            mean_hold = float(p_trades["holding_days"].mean())
        else:
            gross_pnl = 0.0
            trade_cost = 0.0
            borrow_cost = 0.0
            win_rate = float("nan")
            mean_hold = float("nan")

        pair_ret_series = p_daily_net / pair_capital
        sharpe = compute_sharpe_ratio(pair_ret_series, rf=0.0, annualization=annualization)

        # Pair equity curve for drawdown calculation
        pair_equity = pair_capital + p_daily_net.cumsum()
        max_dd, _, _ = compute_max_drawdown(pair_equity)

        pnl_share = float(abs(net_pnl) / total_abs_pnl) if total_abs_pnl > 0.0 else float("nan")

        records.append({
            "pair": p,
            "n_trades": n_tr,
            "win_rate": round(win_rate, 4) if not math.isnan(win_rate) else float("nan"),
            "gross_pnl": round(gross_pnl, 2),
            "trade_cost": round(trade_cost, 2),
            "borrow_cost": round(borrow_cost, 2),
            "net_pnl": round(net_pnl, 2),
            "return_on_pair_capital": round(net_pnl / pair_capital, 6),
            "sharpe_ratio": round(sharpe, 4) if not math.isnan(sharpe) else float("nan"),
            "max_drawdown": round(max_dd, 4),
            "mean_holding_days": round(mean_hold, 1) if not math.isnan(mean_hold) else float("nan"),
            "pnl_share_abs": round(pnl_share, 4) if not math.isnan(pnl_share) else float("nan"),
        })

    return pd.DataFrame(records)


def compute_by_year_table(
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    initial_capital: float,
    annualization: int = 252,
) -> pd.DataFrame:
    """Generate calendar year breakdown table of returns, risk, and costs.

    Parameters
    ----------
    daily_df : pd.DataFrame
        Daily portfolio DataFrame indexed by DatetimeIndex.
    trades_df : pd.DataFrame
        Portfolio trades DataFrame.
    initial_capital : float
        Starting portfolio capital.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    pd.DataFrame
        Annual performance summary table.
    """
    if daily_df.empty:
        return pd.DataFrame()

    daily_copy = daily_df.copy()
    if not isinstance(daily_copy.index, pd.DatetimeIndex):
        daily_copy.index = pd.to_datetime(daily_copy.index)

    years = sorted(list(daily_copy.index.year.unique()))
    records = []

    for yr in years:
        sub_daily = daily_copy[daily_copy.index.year == yr]
        if sub_daily.empty:
            continue

        gross_pnl = float(sub_daily["gross_pnl"].sum())
        trade_cost = float(sub_daily["trade_cost"].sum())
        borrow_cost = float(sub_daily["borrow_cost"].sum())
        net_pnl = float(sub_daily["net_pnl"].sum())

        start_eq = float(sub_daily["equity"].iloc[0] - sub_daily["net_pnl"].iloc[0])
        end_eq = float(sub_daily["equity"].iloc[-1])
        yr_return = float((end_eq - start_eq) / start_eq) if start_eq > 0.0 else 0.0

        ann_vol = compute_annualized_volatility(sub_daily["return"], annualization=annualization)
        sharpe = compute_sharpe_ratio(sub_daily["return"], rf=0.0, annualization=annualization)
        max_dd, _, _ = compute_max_drawdown(sub_daily["equity"])

        # Count trades that exited in this calendar year
        if not trades_df.empty and "exit_date" in trades_df.columns:
            exit_dates = pd.to_datetime(trades_df["exit_date"])
            yr_trades = trades_df[exit_dates.dt.year == yr]
            n_tr = len(yr_trades)
        else:
            n_tr = 0

        # Annualized turnover for the year
        yr_turnover = compute_turnover(yr_trades if n_tr > 0 else pd.DataFrame(), sub_daily, annualization=annualization)

        records.append({
            "year": int(yr),
            "trading_days": len(sub_daily),
            "gross_pnl": round(gross_pnl, 2),
            "trade_cost": round(trade_cost, 2),
            "borrow_cost": round(borrow_cost, 2),
            "net_pnl": round(net_pnl, 2),
            "return": round(yr_return, 6),
            "annualized_volatility": round(ann_vol, 4) if not math.isnan(ann_vol) else float("nan"),
            "sharpe_ratio": round(sharpe, 4) if not math.isnan(sharpe) else float("nan"),
            "max_drawdown": round(max_dd, 4),
            "n_trades": n_tr,
            "turnover": round(yr_turnover, 2),
        })

    return pd.DataFrame(records)


def compute_portfolio_metrics(
    daily_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    initial_capital: float,
    pair_capital: float,
    pairs: Sequence[str],
    turnover: float,
    period_name: str = "",
    annualization: int = 252,
) -> Dict[str, Any]:
    """Compute comprehensive portfolio performance metrics with gross and net side by side.

    Zero-trade and zero-volatility cases return NaN, never inf.

    Parameters
    ----------
    daily_df : pd.DataFrame
        Daily portfolio DataFrame.
    trades_df : pd.DataFrame
        Trade log DataFrame.
    initial_capital : float
        Initial total portfolio equity base.
    pair_capital : float
        Capital allocated per pair.
    pairs : Sequence[str]
        List of selected pairs.
    turnover : float
        Annualized portfolio turnover.
    period_name : str, default ""
        Name of backtest period (e.g. "train", "validation").
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    Dict[str, Any]
        Dictionary structured with gross and net side by side.
    """
    # 1. Net metrics
    net_equity = daily_df["equity"]
    net_rets = daily_df["return"]
    cum_ret_net = compute_cumulative_return(net_equity, initial_capital)
    cagr_net = compute_annualized_return(net_equity, initial_capital, annualization=annualization)
    vol_net = compute_annualized_volatility(net_rets, annualization=annualization)
    sharpe_net = compute_sharpe_ratio(net_rets, rf=0.0, annualization=annualization)
    max_dd_net, max_dd_dur_net, _ = compute_max_drawdown(net_equity)
    total_net_pnl = float(daily_df["net_pnl"].sum())

    # 2. Gross metrics (hypothetical zero-friction world)
    # Gross equity curve = initial_capital + cumsum(gross_pnl)
    gross_equity = initial_capital + daily_df["gross_pnl"].cumsum()
    gross_rets = np.zeros(len(daily_df), dtype=float)
    for t in range(len(daily_df)):
        prev_eq = initial_capital if t == 0 else gross_equity.iloc[t - 1]
        gross_rets[t] = daily_df["gross_pnl"].iloc[t] / prev_eq if prev_eq > 0.0 else 0.0
    gross_ret_series = pd.Series(gross_rets, index=daily_df.index)

    cum_ret_gross = compute_cumulative_return(gross_equity, initial_capital)
    cagr_gross = compute_annualized_return(gross_equity, initial_capital, annualization=annualization)
    vol_gross = compute_annualized_volatility(gross_ret_series, annualization=annualization)
    sharpe_gross = compute_sharpe_ratio(gross_ret_series, rf=0.0, annualization=annualization)
    max_dd_gross, max_dd_dur_gross, _ = compute_max_drawdown(gross_equity)
    total_gross_pnl = float(daily_df["gross_pnl"].sum())

    # 3. Cost breakdown
    total_trade_cost = float(daily_df["trade_cost"].sum())
    total_borrow_cost = float(daily_df["borrow_cost"].sum())
    total_costs = total_trade_cost + total_borrow_cost
    cost_drag_pnl_pct = (total_costs / total_gross_pnl) if total_gross_pnl > 0.0 else float("nan")

    # 4. Trade statistics
    trade_stats = compute_trade_metrics(trades_df)

    # 5. Market exposure & presence
    pct_days_in_market = float((daily_df["open_pairs"] > 0).mean()) if not daily_df.empty else 0.0
    avg_gross_exp = float(daily_df["gross_exposure"].mean()) if not daily_df.empty else 0.0
    avg_gross_lev = float(daily_df["gross_leverage"].mean()) if not daily_df.empty else 0.0
    avg_net_exp = float(daily_df["net_exposure"].mean()) if not daily_df.empty else 0.0
    avg_open_pairs = float(daily_df["open_pairs"].mean()) if not daily_df.empty else 0.0

    # 6. Concentration & HHI
    pair_pnls = {}
    for p in pairs:
        col = f"pnl_{p}"
        pair_pnls[p] = float(daily_df[col].sum()) if col in daily_df.columns else 0.0
    conc_stats = compute_concentration_metrics(pair_pnls)

    metrics_dict = {
        "period": period_name,
        "initial_capital": float(initial_capital),
        "ending_equity": float(net_equity.iloc[-1]) if not net_equity.empty else initial_capital,
        "risk_free_rate_assumed": 0.0,
        "trading_days": len(daily_df),
        "annualization_days": annualization,
        "performance_comparison": {
            "gross": {
                "total_pnl": round(total_gross_pnl, 2),
                "cumulative_return": round(cum_ret_gross, 6),
                "annualized_return_cagr": round(cagr_gross, 6) if not math.isnan(cagr_gross) else float("nan"),
                "annualized_volatility": round(vol_gross, 6) if not math.isnan(vol_gross) else float("nan"),
                "sharpe_ratio_rf_0": round(sharpe_gross, 4) if not math.isnan(sharpe_gross) else float("nan"),
                "max_drawdown": round(max_dd_gross, 6),
                "max_drawdown_duration_days": int(max_dd_dur_gross),
            },
            "net": {
                "total_pnl": round(total_net_pnl, 2),
                "cumulative_return": round(cum_ret_net, 6),
                "annualized_return_cagr": round(cagr_net, 6) if not math.isnan(cagr_net) else float("nan"),
                "annualized_volatility": round(vol_net, 6) if not math.isnan(vol_net) else float("nan"),
                "sharpe_ratio_rf_0": round(sharpe_net, 4) if not math.isnan(sharpe_net) else float("nan"),
                "max_drawdown": round(max_dd_net, 6),
                "max_drawdown_duration_days": int(max_dd_dur_net),
            },
        },
        "costs": {
            "total_trade_costs": round(total_trade_cost, 2),
            "total_borrow_costs": round(total_borrow_cost, 2),
            "total_all_costs": round(total_costs, 2),
            "cost_drag_on_gross_pnl": round(cost_drag_pnl_pct, 4) if not math.isnan(cost_drag_pnl_pct) else float("nan"),
        },
        "trade_statistics": trade_stats,
        "market_exposure": {
            "percentage_days_in_market": round(pct_days_in_market, 4),
            "average_gross_exposure": round(avg_gross_exp, 2),
            "average_gross_leverage": round(avg_gross_lev, 4),
            "average_net_exposure": round(avg_net_exp, 2),
            "average_open_pairs": round(avg_open_pairs, 2),
            "annualized_turnover": round(turnover, 2),
        },
        "concentration": conc_stats,
    }

    return metrics_dict
