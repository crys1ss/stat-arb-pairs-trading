"""Unit tests for single-pair backtest simulation engine with explicit execution lag and costs."""

import numpy as np
import pandas as pd
import pytest

from src.backtest import BacktestResult, backtest_pair, compute_weights
from src.config import ExecutionConfig


def test_weights_computation():
    # Test beta = 1.0: weights are 0.5 and -0.5, gross sum = 1.0
    w_a, w_b = compute_weights(1.0)
    assert pytest.approx(w_a) == 0.5
    assert pytest.approx(w_b) == -0.5
    assert pytest.approx(abs(w_a) + abs(w_b)) == 1.0

    # Test beta = 0.5: w_A = 1 / 1.5 = 2/3, w_B = -0.5 / 1.5 = -1/3
    w_a, w_b = compute_weights(0.5)
    assert pytest.approx(w_a) == 2.0 / 3.0
    assert pytest.approx(w_b) == -1.0 / 3.0
    assert pytest.approx(abs(w_a) + abs(w_b)) == 1.0


def test_fill_happens_at_t_plus_one_not_t():
    # 4-day price path: signal at t=0, fill must happen at t=1 with execution_lag=1
    dates = pd.date_range("2021-01-01", periods=4, freq="B")
    p_a = pd.Series([100.0, 102.0, 104.0, 106.0], index=dates)
    p_b = pd.Series([50.0, 51.0, 52.0, 53.0], index=dates)

    sig_df = pd.DataFrame(
        {
            "z": [-2.2, -1.0, 0.0, 0.5],
            "state": [1, 1, 0, 0],
            "entry_flag": [True, False, False, False],
            "exit_flag": [False, False, True, False],
            "exit_reason": [None, None, "mean_revert", None],
        },
        index=dates,
    )

    cost_cfg = {
        "execution_lag": 1,
        "commission_bps": 5.0,
        "slippage_bps": 5.0,
        "borrow_bps_annual": 50.0,
    }

    res = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg)
    daily = res.daily

    # On signal bar t=0: strictly NO fill, NO position, NO trade cost, NO gross P&L
    assert daily.loc[dates[0], "position"] == 0
    assert daily.loc[dates[0], "trade_cost"] == 0.0
    assert daily.loc[dates[0], "gross_pnl"] == 0.0
    assert daily.loc[dates[0], "shares_a"] == 0.0

    # On fill bar t=1: fill executes at close 1
    assert daily.loc[dates[1], "position"] == 1
    assert daily.loc[dates[1], "trade_cost"] > 0.0
    assert daily.loc[dates[1], "gross_pnl"] == 0.0  # No P&L on or before fill bar
    assert daily.loc[dates[1], "shares_a"] > 0.0

    # Test lag assertion: execution_lag < 1 must raise AssertionError
    with pytest.raises(AssertionError):
        backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg, execution_lag=0)


def test_pnl_and_costs_match_hand_calculation():
    # 5-day tiny hand-computed price path
    # Dates: Day 0, Day 1, Day 2, Day 3, Day 4
    dates = pd.date_range("2021-01-01", periods=5, freq="B")
    p_a = pd.Series([100.0, 100.0, 105.0, 110.0, 110.0], index=dates)
    p_b = pd.Series([50.0, 50.0, 52.0, 48.0, 50.0], index=dates)

    # Signal: enter long spread at t=0, exit signal at t=2
    sig_df = pd.DataFrame(
        {
            "z": [-2.5, -1.8, 0.2, 0.4, 0.5],
            "state": [1, 1, 0, 0, 0],
            "entry_flag": [True, False, False, False, False],
            "exit_flag": [False, False, True, False, False],
            "exit_reason": [None, None, "mean_revert", None, None],
        },
        index=dates,
    )

    # capital = 100,000, beta = 1.0 -> notional_A = 50,000, notional_B = 50,000
    # commission_bps = 5.0, slippage_bps = 5.0 -> trade cost rate = 10 bps = 0.0010
    # borrow_bps_annual = 50.4 -> daily borrow rate = 50.4 / 10000 / 252 = 0.000002
    # Short leg B notional = 50,000 -> daily borrow cost = 0.000002 * 50,000 = 0.10
    cost_cfg = {
        "execution_lag": 1,
        "commission_bps": 5.0,
        "slippage_bps": 5.0,
        "borrow_bps_annual": 50.4,
    }

    res = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg, pair_name="TEST_PAIR")
    daily = res.daily
    trades = res.trades

    # Day 0: Signal emitted, no fill
    assert daily.loc[dates[0], "gross_pnl"] == 0.0
    assert daily.loc[dates[0], "trade_cost"] == 0.0
    assert daily.loc[dates[0], "borrow_cost"] == 0.0
    assert daily.loc[dates[0], "net_pnl"] == 0.0

    # Day 1: Entry fills at close 1
    # shares_A = 50,000 / 100 = +500; shares_B = -50,000 / 50 = -1000
    # Traded notional = 500*100 + 1000*50 = 100,000; entry cost = 0.0010 * 100,000 = 100.0
    assert daily.loc[dates[1], "gross_pnl"] == 0.0
    assert pytest.approx(daily.loc[dates[1], "trade_cost"]) == 100.0
    assert daily.loc[dates[1], "borrow_cost"] == 0.0
    assert pytest.approx(daily.loc[dates[1], "net_pnl"]) == -100.0

    # Day 2: Held day 1 to 2; exit signal emitted at close 2
    # Delta P_A = 105 - 100 = 5; Delta P_B = 52 - 50 = 2
    # Gross P&L = 500 * 5 + (-1000) * 2 = 2500 - 2000 = 500.0
    # Borrow cost = 1.00; trade cost = 0.0
    assert pytest.approx(daily.loc[dates[2], "gross_pnl"]) == 500.0
    assert daily.loc[dates[2], "trade_cost"] == 0.0
    assert pytest.approx(daily.loc[dates[2], "borrow_cost"]) == 1.00
    assert pytest.approx(daily.loc[dates[2], "net_pnl"]) == 499.00

    # Day 3: Exit fills at close 3
    # Delta P_A = 110 - 105 = 5; Delta P_B = 48 - 52 = -4
    # Gross P&L = 500 * 5 + (-1000) * (-4) = 2500 + 4000 = 6500.0
    # Borrow cost = 1.00
    # Exit notional = 500 * 110 + 1000 * 48 = 55,000 + 48,000 = 103,000
    # Exit trade cost = 0.0010 * 103,000 = 103.0
    assert pytest.approx(daily.loc[dates[3], "gross_pnl"]) == 6500.0
    assert pytest.approx(daily.loc[dates[3], "trade_cost"]) == 103.0
    assert pytest.approx(daily.loc[dates[3], "borrow_cost"]) == 1.00
    assert pytest.approx(daily.loc[dates[3], "net_pnl"]) == 6500.0 - 103.0 - 1.00

    # Day 4: Flat
    assert daily.loc[dates[4], "gross_pnl"] == 0.0
    assert daily.loc[dates[4], "trade_cost"] == 0.0
    assert daily.loc[dates[4], "borrow_cost"] == 0.0
    assert daily.loc[dates[4], "net_pnl"] == 0.0

    # Trade log assertions
    assert len(trades) == 1
    tr = trades.iloc[0]
    assert tr["pair"] == "TEST_PAIR"
    assert tr["direction"] == 1
    assert tr["holding_days"] == 2
    assert tr["entry_date"] == dates[1]
    assert tr["exit_date"] == dates[3]
    assert pytest.approx(tr["entry_price_a"]) == 100.0
    assert pytest.approx(tr["entry_price_b"]) == 50.0
    assert pytest.approx(tr["exit_price_a"]) == 110.0
    assert pytest.approx(tr["exit_price_b"]) == 48.0
    assert pytest.approx(tr["gross_pnl"]) == 7000.0
    assert pytest.approx(tr["trade_cost"]) == 203.0
    assert pytest.approx(tr["borrow_cost"]) == 2.00
    assert pytest.approx(tr["costs"]) == 205.00
    assert pytest.approx(tr["net_pnl"]) == 6795.00
    assert pytest.approx(tr["return_on_capital"]) == 6795.00 / 100_000.0
    assert tr["exit_reason"] == "mean_revert"


def test_costs_charged_exactly_once_at_entry_and_exit():
    dates = pd.date_range("2021-01-01", periods=6, freq="B")
    p_a = pd.Series([100.0, 100.0, 102.0, 103.0, 104.0, 104.0], index=dates)
    p_b = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0, 50.0], index=dates)

    # Signal: entry at t=0 (fills t=1), exit signal at t=3 (fills t=4)
    sig_df = pd.DataFrame(
        {
            "z": [-2.2, -1.5, -1.0, 0.3, 0.0, 0.0],
            "state": [1, 1, 1, 0, 0, 0],
            "entry_flag": [True, False, False, False, False, False],
            "exit_flag": [False, False, False, True, False, False],
            "exit_reason": [None, None, None, "mean_revert", None, None],
        },
        index=dates,
    )

    cost_cfg = {"execution_lag": 1, "commission_bps": 5.0, "slippage_bps": 5.0, "borrow_bps_annual": 50.0}
    res = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg)
    daily = res.daily

    # Non-zero trade cost must occur ONLY on entry fill (t=1) and exit fill (t=4)
    trade_cost_bars = daily.index[daily["trade_cost"] > 0].tolist()
    assert trade_cost_bars == [dates[1], dates[4]]

    # Zero trade cost on all other bars (t=0, 2, 3, 5)
    assert daily.loc[dates[0], "trade_cost"] == 0.0
    assert daily.loc[dates[2], "trade_cost"] == 0.0
    assert daily.loc[dates[3], "trade_cost"] == 0.0
    assert daily.loc[dates[5], "trade_cost"] == 0.0


def test_borrow_accrual_is_correct():
    dates = pd.date_range("2021-01-01", periods=5, freq="B")
    p_a = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0], index=dates)
    p_b = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0], index=dates)

    # Signal: entry at t=0 (fills t=1), held through t=2, t=3, exit fills at t=4
    sig_df = pd.DataFrame(
        {
            "z": [-2.5, -2.0, -1.5, 0.2, 0.0],
            "state": [1, 1, 1, 0, 0],
            "entry_flag": [True, False, False, False, False],
            "exit_flag": [False, False, False, True, False],
            "exit_reason": [None, None, None, "mean_revert", None],
        },
        index=dates,
    )

    # capital = 100,000, beta = 1.0 -> short notional = 50,000
    # borrow_bps_annual = 252.0 -> daily borrow rate = 252 / 10000 / 252 = 1 / 10000 = 0.0001
    # daily borrow cost = 0.0001 * 50,000 = 5.0 per day held
    cost_cfg = {"execution_lag": 1, "commission_bps": 0.0, "slippage_bps": 0.0, "borrow_bps_annual": 252.0}
    res = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg)
    daily = res.daily
    trades = res.trades

    # Day 0: flat, no borrow
    assert daily.loc[dates[0], "borrow_cost"] == 0.0
    # Day 1: fill day, no prior overnight hold, no borrow
    assert daily.loc[dates[1], "borrow_cost"] == 0.0
    # Day 2: held day 1 to 2 -> 5.0
    assert pytest.approx(daily.loc[dates[2], "borrow_cost"]) == 5.0
    # Day 3: held day 2 to 3 -> 5.0
    assert pytest.approx(daily.loc[dates[3], "borrow_cost"]) == 5.0
    # Day 4: held day 3 to 4, liquidated at close -> 5.0
    assert pytest.approx(daily.loc[dates[4], "borrow_cost"]) == 5.0

    # Total trade borrow cost = 15.0 across 3 holding days
    assert len(trades) == 1
    assert trades.iloc[0]["holding_days"] == 3
    assert pytest.approx(trades.iloc[0]["borrow_cost"]) == 15.0


def test_zero_trades_give_zero_pnl_and_zero_costs():
    dates = pd.date_range("2021-01-01", periods=5, freq="B")
    p_a = pd.Series([100.0, 102.0, 104.0, 101.0, 103.0], index=dates)
    p_b = pd.Series([50.0, 51.0, 49.0, 52.0, 50.0], index=dates)

    # Flat throughout: 0 entries, 0 exits
    sig_df = pd.DataFrame(
        {
            "z": [0.1, 0.2, -0.3, 0.4, -0.1],
            "state": [0, 0, 0, 0, 0],
            "entry_flag": [False, False, False, False, False],
            "exit_flag": [False, False, False, False, False],
            "exit_reason": [None, None, None, None, None],
        },
        index=dates,
    )

    cost_cfg = {"execution_lag": 1, "commission_bps": 5.0, "slippage_bps": 5.0, "borrow_bps_annual": 50.0}
    res = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg)

    assert len(res.trades) == 0
    assert (res.daily["gross_pnl"] == 0.0).all()
    assert (res.daily["trade_cost"] == 0.0).all()
    assert (res.daily["borrow_cost"] == 0.0).all()
    assert (res.daily["net_pnl"] == 0.0).all()
    assert (res.daily["return"] == 0.0).all()


def test_force_close_at_period_end():
    dates = pd.date_range("2021-01-01", periods=5, freq="B")
    p_a = pd.Series([100.0, 100.0, 105.0, 108.0, 110.0], index=dates)
    p_b = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0], index=dates)

    # Signal: entry at t=0 (fills t=1), no exit signal emitted through period end (t=4)
    sig_df = pd.DataFrame(
        {
            "z": [-2.2, -1.9, -1.8, -1.7, -1.6],
            "state": [1, 1, 1, 1, 1],
            "entry_flag": [True, False, False, False, False],
            "exit_flag": [False, False, False, False, False],
            "exit_reason": [None, None, None, None, None],
        },
        index=dates,
    )

    cost_cfg = {"execution_lag": 1, "commission_bps": 5.0, "slippage_bps": 5.0, "borrow_bps_annual": 50.0}
    res = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg)
    trades = res.trades
    daily = res.daily

    # Must force-close on final bar t=4
    assert len(trades) == 1
    tr = trades.iloc[0]
    assert tr["exit_reason"] == "period_end"
    assert tr["entry_date"] == dates[1]
    assert tr["exit_date"] == dates[4]
    assert tr["holding_days"] == 3

    # Exit trade cost charged at period end
    assert daily.loc[dates[4], "trade_cost"] > 0.0
    assert pytest.approx(tr["exit_price_a"]) == 110.0
    assert pytest.approx(tr["exit_price_b"]) == 50.0


def test_lag_2_shifts_fills_by_exactly_one_more_bar():
    # 7-day path to test lag 1 vs lag 2
    dates = pd.date_range("2021-01-01", periods=7, freq="B")
    p_a = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0], index=dates)
    p_b = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0], index=dates)

    # Signal: entry at t=0, exit signal at t=3
    sig_df = pd.DataFrame(
        {
            "z": [-2.2, -1.8, -1.5, 0.4, 0.2, 0.0, 0.0],
            "state": [1, 1, 1, 0, 0, 0, 0],
            "entry_flag": [True, False, False, False, False, False, False],
            "exit_flag": [False, False, False, True, False, False, False],
            "exit_reason": [None, None, None, "mean_revert", None, None, None],
        },
        index=dates,
    )

    cost_cfg = {"commission_bps": 5.0, "slippage_bps": 5.0, "borrow_bps_annual": 50.0}

    # Run with lag = 1
    res_lag1 = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg, execution_lag=1)
    # Run with lag = 2
    res_lag2 = backtest_pair(p_a, p_b, sig_df, beta=1.0, capital=100_000.0, cost_config=cost_cfg, execution_lag=2)

    tr_lag1 = res_lag1.trades.iloc[0]
    tr_lag2 = res_lag2.trades.iloc[0]

    # With lag=1: entry fills at dates[1], exit fills at dates[4]
    assert tr_lag1["entry_date"] == dates[1]
    assert tr_lag1["exit_date"] == dates[4]

    # With lag=2: entry fills at dates[2] (+1 bar), exit fills at dates[5] (+1 bar)
    assert tr_lag2["entry_date"] == dates[2]
    assert tr_lag2["exit_date"] == dates[5]

    # Verify daily execution flags
    # Lag 1: trade cost on dates[1] and dates[4]
    assert res_lag1.daily.loc[dates[1], "trade_cost"] > 0.0
    assert res_lag1.daily.loc[dates[4], "trade_cost"] > 0.0

    # Lag 2: trade cost shifted by exactly +1 bar to dates[2] and dates[5]
    assert res_lag2.daily.loc[dates[1], "trade_cost"] == 0.0
    assert res_lag2.daily.loc[dates[2], "trade_cost"] > 0.0
    assert res_lag2.daily.loc[dates[4], "trade_cost"] == 0.0
    assert res_lag2.daily.loc[dates[5], "trade_cost"] > 0.0
