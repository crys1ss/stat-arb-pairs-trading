"""Signal generation state machine and spread z-score thresholding module."""

from __future__ import annotations

from typing import Optional, Union
import numpy as np
import pandas as pd


def generate_signals(
    z: Union[pd.Series, np.ndarray],
    entry_z: float,
    exit_z: float,
    max_hold_days: int,
    stop_z: Optional[float] = None,
    close_at_end: bool = False,
    cooldown_days: int = 0,
) -> pd.DataFrame:
    """Generate deterministic, causal pairs-trading signals via a state machine.

    Execution Contract:
    -------------------
    Signals emitted by this function represent decisions made at market CLOSE on date t.
    To strictly preclude look-ahead bias, the backtesting engine must apply fills no earlier
    than close t + execution_lag (where execution_lag >= 1 trading day).

    State Machine Rules:
    --------------------
    1. When flat (state == 0):
       - If cooldown_remaining > 0: decrement counter and remain flat (no entries).
       - If z_t >= entry_z: enter short spread (state -> -1).
       - If z_t <= -entry_z: enter long spread (state -> +1).
       - A NaN z_t precludes any new entry.
    2. When holding long spread (state == +1):
       - Mean reversion: exit when z_t >= -exit_z (covers convergence and crossing zero).
       - Max hold duration: exit when days_held >= max_hold_days.
       - Stop loss: exit when stop_z is provided and |z_t| >= stop_z.
       - A NaN z_t means the existing position is held unless max_hold is reached.
       - Period end: forced exit at final bar if close_at_end=True.
    3. When holding short spread (state == -1):
       - Mean reversion: exit when z_t <= exit_z (covers convergence and crossing zero).
       - Max hold duration: exit when days_held >= max_hold_days.
       - Stop loss: exit when stop_z is provided and |z_t| >= stop_z.
       - A NaN z_t means the existing position is held unless max_hold is reached.
       - Period end: forced exit at final bar if close_at_end=True.
    4. Sequencing invariants:
       - No re-entry on the same bar as an exit.
       - No overlapping positions.
       - Pure causality: state at bar t depends strictly on z[0..t].
       - If exit reason is 'max_hold' or 'stop', cooldown_days blocks entries for that many bars.

    Parameters
    ----------
    z : Union[pd.Series, np.ndarray]
        Normalized spread z-score time series.
    entry_z : float
        Statistical divergence entry threshold in standard deviations (e.g. 2.0).
    exit_z : float
        Mean-reversion exit threshold in standard deviations (e.g. 0.5).
    max_hold_days : int
        Maximum holding period in trading days before forced time-based exit.
    stop_z : Optional[float], default None
        Optional divergence stop-loss threshold in standard deviations.
    close_at_end : bool, default False
        Whether to liquidate open positions on the final bar with reason 'period_end'.
        Default is False to strictly preserve truncation causality across arbitrary sub-periods.
    cooldown_days : int, default 0
        Number of bars to block new entries after a 'max_hold' or 'stop' exit.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed like z with columns:
        - 'z': original z-score
        - 'state': integer state (+1 long spread, -1 short spread, 0 flat)
        - 'entry_flag': bool, True on bars where a new position is initiated
        - 'exit_flag': bool, True on bars where an existing position is liquidated
        - 'exit_reason': Optional[str] ('mean_revert', 'max_hold', 'stop', 'period_end', or None)
        - 'days_held': int, count of trading days current position has been held
    """
    if isinstance(z, pd.Series):
        z_vals = z.values
        index = z.index
    else:
        z_vals = np.asarray(z, dtype=float)
        index = pd.RangeIndex(len(z_vals))

    n = len(z_vals)
    state_arr = np.zeros(n, dtype=int)
    entry_flag_arr = np.zeros(n, dtype=bool)
    exit_flag_arr = np.zeros(n, dtype=bool)
    exit_reason_arr = [None] * n
    days_held_arr = np.zeros(n, dtype=int)

    current_state = 0
    days_held = 0
    cooldown_remaining = 0

    for t in range(n):
        zt = z_vals[t]
        is_nan = np.isnan(zt)

        if current_state == 0:
            # We are currently FLAT
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
                state_arr[t] = 0
                days_held_arr[t] = 0
                continue

            if not is_nan:
                if zt >= entry_z:
                    # Enter short spread
                    current_state = -1
                    days_held = 1
                    state_arr[t] = -1
                    entry_flag_arr[t] = True
                    days_held_arr[t] = 1
                elif zt <= -entry_z:
                    # Enter long spread
                    current_state = 1
                    days_held = 1
                    state_arr[t] = 1
                    entry_flag_arr[t] = True
                    days_held_arr[t] = 1
                else:
                    state_arr[t] = 0
                    days_held_arr[t] = 0
            else:
                # NaN while flat -> remain flat
                state_arr[t] = 0
                days_held_arr[t] = 0

        else:
            # We are currently in a POSITION (+1 or -1)
            days_held += 1
            exit_triggered = False
            reason: Optional[str] = None

            if not is_nan:
                # Check stop loss first if configured
                if stop_z is not None and abs(zt) >= stop_z:
                    exit_triggered = True
                    reason = "stop"

                # Check mean reversion
                elif current_state == 1 and zt >= -exit_z:
                    exit_triggered = True
                    reason = "mean_revert"
                elif current_state == -1 and zt <= exit_z:
                    exit_triggered = True
                    reason = "mean_revert"

                # Check max hold days
                elif days_held >= max_hold_days:
                    exit_triggered = True
                    reason = "max_hold"

                # Check period end if enabled
                elif close_at_end and t == n - 1:
                    exit_triggered = True
                    reason = "period_end"

            else:
                # NaN z while in position: hold unless max hold days elapsed or period end
                if days_held >= max_hold_days:
                    exit_triggered = True
                    reason = "max_hold"
                elif close_at_end and t == n - 1:
                    exit_triggered = True
                    reason = "period_end"

            if exit_triggered:
                exit_flag_arr[t] = True
                exit_reason_arr[t] = reason
                days_held_arr[t] = days_held
                state_arr[t] = 0
                # Reset state to flat; strictly no re-entry on exit bar
                current_state = 0
                days_held = 0
                if reason in ("max_hold", "stop") and cooldown_days > 0:
                    cooldown_remaining = cooldown_days
            else:
                state_arr[t] = current_state
                days_held_arr[t] = days_held

    return pd.DataFrame(
        {
            "z": z_vals,
            "state": state_arr,
            "entry_flag": entry_flag_arr,
            "exit_flag": exit_flag_arr,
            "exit_reason": exit_reason_arr,
            "days_held": days_held_arr,
        },
        index=index,
    )
