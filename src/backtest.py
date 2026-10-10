"""Single-pair backtest simulation engine with explicit transaction costs and execution lag."""

from __future__ import annotations

from typing import Any, Dict, NamedTuple, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.config import Config, ExecutionConfig


class BacktestResult(NamedTuple):
    """Container for backtest simulation outputs."""

    daily: pd.DataFrame
    trades: pd.DataFrame


def compute_weights(beta: float) -> Tuple[float, float]:
    """Compute gross capital weights for legs A and B given frozen hedge ratio beta.

    Formulation:
        w_A = 1.0 / (1.0 + |beta|)
        w_B = -beta / (1.0 + |beta|)
        |w_A| + |w_B| = 1.0

    Parameters
    ----------
    beta : float
        Frozen training-period OLS hedge ratio.

    Returns
    -------
    Tuple[float, float]
        (w_A, w_B) where |w_A| + |w_B| == 1.0.
    """
    abs_beta = abs(beta)
    denom = 1.0 + abs_beta
    w_a = 1.0 / denom
    w_b = -beta / denom
    return w_a, w_b


def backtest_pair(
    price_a: Union[pd.Series, np.ndarray],
    price_b: Union[pd.Series, np.ndarray],
    signals: pd.DataFrame,
    beta: float,
    capital: float,
    cost_config: Union[ExecutionConfig, Config, Dict[str, Any]],
    pair_name: str = "pair",
    execution_lag: Optional[int] = None,
) -> BacktestResult:
    """Execute causal single-pair backtest simulation with realistic execution lag and costs.

    Execution Contract & Return Conventions:
    ----------------------------------------
    1. Execution Contract:
       Signals emitted by the signal generation state machine represent decisions made at
       market CLOSE on date t. To strictly preclude look-ahead bias, fills execute no earlier
       than close t + execution_lag, where execution_lag >= 1 trading day. Fills occur at
       the closing price of date t + execution_lag.

    2. Fixed Capital Base Convention:
       Pair daily returns are computed as `net_pnl / capital`, using a strictly fixed capital
       base throughout the simulation period. The capital base is not dynamically compounded
       or adjusted by accumulated P&L. This standard institutional methodology ensures
       stationary risk weighting and clean, unconfounded return attribution across pairs.

    3. Position Sizing & Share Count Invariant:
       At fill close, notional amounts are established:
           notional_A = capital * |w_A|
           notional_B = capital * |w_B|
       Fractional share counts are established at fill close:
           shares_A = direction * (notional_A / fill_price_A)
           shares_B = -direction * sgn(beta) * (notional_B / fill_price_B)
       Shares are held strictly fixed until position liquidation.

    4. P&L & Cost Accounting:
       - Gross P&L: sum over legs of shares * (P_t - P_{t-1}) for each day held. There is no
         P&L on or before the fill bar.
       - Trade Costs: (commission_bps + slippage_bps) / 1e4 * traded notional, per leg,
         charged once at entry and once at exit. Traded notional at entry is capital;
         at exit it is |shares_A| * P_exit_A + |shares_B| * P_exit_B.
       - Borrow Cost: (borrow_bps_annual / 1e4 / 252) * short notional for each day held,
         charged on the short leg's notional.
       - Force-close: Any position still open at the final bar of the period is liquidated
         at the last close with exit trade costs and exit_reason 'period_end'.

    Parameters
    ----------
    price_a : Union[pd.Series, np.ndarray]
        Adjusted close price series for dependent leg A.
    price_b : Union[pd.Series, np.ndarray]
        Adjusted close price series for independent leg B.
    signals : pd.DataFrame
        Signals DataFrame containing 'state', 'entry_flag', 'exit_flag', and 'exit_reason'.
    beta : float
        Frozen training-period OLS hedge ratio.
    capital : float
        Allocated pair capital in quote currency (e.g. 100,000.0).
    cost_config : Union[ExecutionConfig, Config, Dict[str, Any]]
        Configuration object or dict containing cost parameters.
    pair_name : str, default "pair"
        Pair identifier symbol (e.g. "BAC_PNC").
    execution_lag : Optional[int], default None
        Optional explicit override for execution lag in trading days (must be >= 1).

    Returns
    -------
    BacktestResult
        NamedTuple with two elements:
        - daily: pd.DataFrame with daily series (gross_pnl, trade_cost, borrow_cost, net_pnl, return, position, shares_a, shares_b)
        - trades: pd.DataFrame trade log table
    """
    if capital <= 0.0:
        raise ValueError(f"Capital must be strictly positive, got {capital}")

    # Extract execution and cost configuration
    if isinstance(cost_config, Config):
        cfg = cost_config.execution
        lag = execution_lag if execution_lag is not None else cfg.execution_lag
        comm_bps = cfg.commission_bps
        slip_bps = cfg.slippage_bps
        borrow_bps = cfg.borrow_bps_annual
    elif isinstance(cost_config, ExecutionConfig):
        lag = execution_lag if execution_lag is not None else cost_config.execution_lag
        comm_bps = cost_config.commission_bps
        slip_bps = cost_config.slippage_bps
        borrow_bps = cost_config.borrow_bps_annual
    elif isinstance(cost_config, dict):
        lag = execution_lag if execution_lag is not None else int(cost_config.get("execution_lag", 1))
        comm_bps = float(cost_config.get("commission_bps", 5.0))
        slip_bps = float(cost_config.get("slippage_bps", 5.0))
        borrow_bps = float(cost_config.get("borrow_bps_annual", 50.0))
    else:
        raise TypeError(f"Unsupported cost_config type: {type(cost_config)}")

    assert lag >= 1, f"execution_lag must be >= 1 to prevent look-ahead bias, got {lag}"

    # Align inputs onto common index
    if isinstance(price_a, pd.Series) and isinstance(price_b, pd.Series):
        common_idx = price_a.dropna().index.intersection(price_b.dropna().index).intersection(signals.index)
        p_a_series = price_a.loc[common_idx].astype(float)
        p_b_series = price_b.loc[common_idx].astype(float)
        sig_df = signals.loc[common_idx]
        dates = common_idx
    else:
        p_a_arr = np.asarray(price_a, dtype=float)
        p_b_arr = np.asarray(price_b, dtype=float)
        n_len = min(len(p_a_arr), len(p_b_arr), len(signals))
        dates = signals.index[:n_len] if hasattr(signals, "index") else pd.RangeIndex(n_len)
        p_a_series = pd.Series(p_a_arr[:n_len], index=dates)
        p_b_series = pd.Series(p_b_arr[:n_len], index=dates)
        sig_df = signals.iloc[:n_len]

    n = len(p_a_series)
    if n == 0:
        empty_daily = pd.DataFrame(
            columns=["gross_pnl", "trade_cost", "borrow_cost", "net_pnl", "return", "position", "shares_a", "shares_b"]
        )
        empty_trades = pd.DataFrame(
            columns=[
                "pair", "direction", "signal_date", "entry_date", "exit_signal_date", "exit_date",
                "holding_days", "entry_price_a", "entry_price_b", "exit_price_a", "exit_price_b",
                "shares_a", "shares_b", "gross_pnl", "trade_cost", "borrow_cost", "costs", "net_pnl",
                "return_on_capital", "exit_reason"
            ]
        )
        return BacktestResult(daily=empty_daily, trades=empty_trades)

    p_a_vals = p_a_series.values
    p_b_vals = p_b_series.values
    entry_flags = sig_df["entry_flag"].values
    exit_flags = sig_df["exit_flag"].values
    states = sig_df["state"].values
    exit_reasons = sig_df["exit_reason"].values if "exit_reason" in sig_df.columns else [None] * n

    # Compute static capital weights
    abs_beta = abs(beta)
    w_a_abs = 1.0 / (1.0 + abs_beta)
    w_b_abs = abs_beta / (1.0 + abs_beta)
    notional_a = capital * w_a_abs
    notional_b = capital * w_b_abs
    sgn_beta = 1.0 if beta >= 0.0 else -1.0

    trade_cost_rate = (comm_bps + slip_bps) / 10000.0
    daily_borrow_rate = (borrow_bps / 10000.0) / 252.0

    # Daily accounting arrays
    gross_pnl_arr = np.zeros(n, dtype=float)
    trade_cost_arr = np.zeros(n, dtype=float)
    borrow_cost_arr = np.zeros(n, dtype=float)
    net_pnl_arr = np.zeros(n, dtype=float)
    return_arr = np.zeros(n, dtype=float)
    position_arr = np.zeros(n, dtype=int)
    shares_a_arr = np.zeros(n, dtype=float)
    shares_b_arr = np.zeros(n, dtype=float)

    # Position tracking state
    in_pos = False
    curr_dir = 0
    curr_shares_a = 0.0
    curr_shares_b = 0.0
    curr_short_notional = 0.0
    curr_entry_idx = -1
    curr_sig_idx = -1
    curr_entry_p_a = 0.0
    curr_entry_p_b = 0.0
    curr_entry_cost = 0.0
    curr_trade_gross = 0.0
    curr_trade_borrow = 0.0

    # Pending execution state (due to execution_lag >= 1)
    pending_entry: Optional[Dict[str, Any]] = None
    pending_exit: Optional[Dict[str, Any]] = None

    trade_records = []

    for t in range(n):
        # -------------------------------------------------------------
        # 1. Accrue daily gross P&L and borrow cost from prior close
        # -------------------------------------------------------------
        if in_pos:
            # P&L accrued from holding position between close t-1 and close t
            pnl_a = curr_shares_a * (p_a_vals[t] - p_a_vals[t - 1])
            pnl_b = curr_shares_b * (p_b_vals[t] - p_b_vals[t - 1])
            day_gross = float(pnl_a + pnl_b)
            day_borrow = float(daily_borrow_rate * curr_short_notional)

            gross_pnl_arr[t] = day_gross
            borrow_cost_arr[t] = day_borrow
            curr_trade_gross += day_gross
            curr_trade_borrow += day_borrow

        # -------------------------------------------------------------
        # 2. Process fills at CLOSE of bar t
        # -------------------------------------------------------------
        # (a) Check if a scheduled exit fills at close t OR force-close at period end
        exit_now = False
        exit_reason_str = None
        exit_sig_date = None

        if in_pos:
            if pending_exit is not None and pending_exit["fill_idx"] == t:
                exit_now = True
                exit_reason_str = pending_exit["exit_reason"]
                exit_sig_date = dates[pending_exit["signal_idx"]]
                pending_exit = None
            elif t == n - 1:
                # Force-close open position on the final bar of the period
                exit_now = True
                if pending_exit is not None:
                    exit_reason_str = pending_exit["exit_reason"]
                    exit_sig_date = dates[pending_exit["signal_idx"]]
                    pending_exit = None
                else:
                    exit_reason_str = "period_end"
                    exit_sig_date = dates[t]

        if exit_now:
            # Liquidate position at close t
            exit_p_a = p_a_vals[t]
            exit_p_b = p_b_vals[t]
            exit_notional_a = abs(curr_shares_a) * exit_p_a
            exit_notional_b = abs(curr_shares_b) * exit_p_b
            exit_cost = float(trade_cost_rate * (exit_notional_a + exit_notional_b))

            trade_cost_arr[t] += exit_cost
            total_trade_costs = float(curr_entry_cost + exit_cost + curr_trade_borrow)
            net_trade_pnl = float(curr_trade_gross - total_trade_costs)
            trade_ret = float(net_trade_pnl / capital)
            holding_days = int(t - curr_entry_idx)

            trade_records.append({
                "pair": pair_name,
                "direction": curr_dir,
                "signal_date": dates[curr_sig_idx],
                "entry_date": dates[curr_entry_idx],
                "exit_signal_date": exit_sig_date,
                "exit_date": dates[t],
                "holding_days": holding_days,
                "entry_price_a": curr_entry_p_a,
                "entry_price_b": curr_entry_p_b,
                "exit_price_a": exit_p_a,
                "exit_price_b": exit_p_b,
                "shares_a": curr_shares_a,
                "shares_b": curr_shares_b,
                "gross_pnl": round(curr_trade_gross, 6),
                "trade_cost": round(curr_entry_cost + exit_cost, 6),
                "borrow_cost": round(curr_trade_borrow, 6),
                "costs": round(total_trade_costs, 6),
                "net_pnl": round(net_trade_pnl, 6),
                "return_on_capital": round(trade_ret, 8),
                "exit_reason": exit_reason_str,
            })

            in_pos = False
            curr_dir = 0
            curr_shares_a = 0.0
            curr_shares_b = 0.0
            curr_short_notional = 0.0

        # (b) Check if a scheduled entry fills at close t
        if not in_pos and pending_entry is not None and pending_entry["fill_idx"] == t:
            # Do not fill if on the very last bar without room to hold
            fill_p_a = p_a_vals[t]
            fill_p_b = p_b_vals[t]
            curr_dir = int(pending_entry["direction"])

            # Establish fractional share counts
            curr_shares_a = float(curr_dir * (notional_a / fill_p_a))
            curr_shares_b = float(-curr_dir * sgn_beta * (notional_b / fill_p_b))

            if curr_shares_a < 0.0:
                curr_short_notional = notional_a
            elif curr_shares_b < 0.0:
                curr_short_notional = notional_b
            else:
                curr_short_notional = 0.0

            # Entry trade cost charged once at entry
            entry_traded_notional = notional_a + notional_b  # exactly equals capital
            curr_entry_cost = float(trade_cost_rate * entry_traded_notional)
            trade_cost_arr[t] += curr_entry_cost

            in_pos = True
            curr_entry_idx = t
            curr_sig_idx = pending_entry["signal_idx"]
            curr_entry_p_a = fill_p_a
            curr_entry_p_b = fill_p_b
            curr_trade_gross = 0.0
            curr_trade_borrow = 0.0
            pending_entry = None

        # -------------------------------------------------------------
        # 3. Schedule new signals emitted at CLOSE of bar t
        # -------------------------------------------------------------
        if in_pos and pending_exit is None:
            if bool(exit_flags[t]):
                pending_exit = {
                    "fill_idx": t + lag,
                    "signal_idx": t,
                    "exit_reason": exit_reasons[t] if exit_reasons[t] is not None else "signal_exit",
                }
        elif not in_pos and pending_entry is None:
            if bool(entry_flags[t]):
                pending_entry = {
                    "fill_idx": t + lag,
                    "signal_idx": t,
                    "direction": states[t],
                }

        # -------------------------------------------------------------
        # 4. Finalize bar daily metrics
        # -------------------------------------------------------------
        net_pnl_arr[t] = gross_pnl_arr[t] - trade_cost_arr[t] - borrow_cost_arr[t]
        return_arr[t] = net_pnl_arr[t] / capital
        position_arr[t] = curr_dir if in_pos else 0
        shares_a_arr[t] = curr_shares_a if in_pos else 0.0
        shares_b_arr[t] = curr_shares_b if in_pos else 0.0

    daily_df = pd.DataFrame(
        {
            "gross_pnl": gross_pnl_arr,
            "trade_cost": trade_cost_arr,
            "borrow_cost": borrow_cost_arr,
            "net_pnl": net_pnl_arr,
            "return": return_arr,
            "position": position_arr,
            "shares_a": shares_a_arr,
            "shares_b": shares_b_arr,
        },
        index=dates,
    )

    trades_df = pd.DataFrame(
        trade_records,
        columns=[
            "pair", "direction", "signal_date", "entry_date", "exit_signal_date", "exit_date",
            "holding_days", "entry_price_a", "entry_price_b", "exit_price_a", "exit_price_b",
            "shares_a", "shares_b", "gross_pnl", "trade_cost", "borrow_cost", "costs", "net_pnl",
            "return_on_capital", "exit_reason"
        ],
    )

    return BacktestResult(daily=daily_df, trades=trades_df)


# Canonical alias
run_backtest = backtest_pair
