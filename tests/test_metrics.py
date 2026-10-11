"""Unit tests for performance metrics, risk measures, drawdown, and trade statistics."""

import math
import numpy as np
import pandas as pd
import pytest

from src.metrics import (
    compute_annualized_return,
    compute_annualized_volatility,
    compute_cumulative_return,
    compute_drawdown_series,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_trade_metrics,
    compute_turnover,
)


def test_drawdown_on_known_series():
    # Known price/equity series:
    # Day 0: 100.0 (Peak: 100, DD: 0.0)
    # Day 1: 110.0 (Peak: 110, DD: 0.0)
    # Day 2:  99.0 (Peak: 110, DD: (99 - 110)/110 = -0.10)
    # Day 3: 104.5 (Peak: 110, DD: (104.5 - 110)/110 = -0.05)
    # Day 4:  88.0 (Peak: 110, DD: (88 - 110)/110 = -0.20)
    # Day 5: 120.0 (Peak: 120, DD: 0.0)
    equity = pd.Series([100.0, 110.0, 99.0, 104.5, 88.0, 120.0])

    dd_series = compute_drawdown_series(equity)
    expected_dd = pd.Series([0.0, 0.0, -0.10, -0.05, -0.20, 0.0], name="drawdown")
    np.testing.assert_allclose(dd_series.values, expected_dd.values, atol=1e-10)

    max_dd, max_dur, _ = compute_max_drawdown(equity)
    # Max drawdown is 20% (0.20)
    assert pytest.approx(max_dd) == 0.20
    # Longest drawdown duration is 3 days (Day 2, 3, 4)
    assert max_dur == 3


def test_sharpe_on_known_returns():
    # Known return series:
    # returns = [0.01, -0.005, 0.015, -0.002, 0.008]
    rets = pd.Series([0.01, -0.005, 0.015, -0.002, 0.008])
    mean_r = float(rets.mean())
    std_r = float(rets.std(ddof=1))

    # Hand calculation: (mean / std) * sqrt(252)
    expected_sharpe = (mean_r / std_r) * math.sqrt(252)

    sharpe = compute_sharpe_ratio(rets, rf=0.0, annualization=252)
    assert pytest.approx(sharpe, rel=1e-8) == expected_sharpe

    # Test with non-zero risk-free rate
    rf = 0.02
    daily_rf = rf / 252.0
    expected_sharpe_rf = ((mean_r - daily_rf) / std_r) * math.sqrt(252)
    assert pytest.approx(compute_sharpe_ratio(rets, rf=rf, annualization=252), rel=1e-8) == expected_sharpe_rf

    # Zero-volatility case must return NaN, never inf
    zero_vol_rets = pd.Series([0.01, 0.01, 0.01, 0.01])
    nan_sharpe = compute_sharpe_ratio(zero_vol_rets, rf=0.0)
    assert math.isnan(nan_sharpe)
    assert not math.isinf(nan_sharpe)


def test_annualization_consistency_between_returns_and_equity():
    # Construct an equity curve over 504 trading days (exactly 2 years)
    # Starting equity: 1,000,000; Ending equity: 1,210,000 (+21.0% cumulative)
    n_days = 504
    initial_cap = 1_000_000.0
    ending_cap = 1_210_000.0

    # Geometric CAGR = (1,210,000 / 1,000,000) ** (252 / 504) - 1 = (1.21) ** 0.5 - 1 = 1.10 - 1 = 0.10 (10.0%)
    linear_eq = pd.Series(np.linspace(initial_cap, ending_cap, n_days))

    cum_ret = compute_cumulative_return(linear_eq, initial_capital=initial_cap)
    cagr = compute_annualized_return(linear_eq, initial_capital=initial_cap, annualization=252)

    assert pytest.approx(cum_ret) == 0.21
    assert pytest.approx(cagr) == 0.10

    # Mathematical consistency: (1 + CAGR) ** (N / 252) - 1 == cumulative return
    reconstructed_cum_ret = ((1.0 + cagr) ** (n_days / 252.0)) - 1.0
    assert pytest.approx(reconstructed_cum_ret, rel=1e-10) == cum_ret


def test_zero_trade_case():
    # Empty trades DataFrame
    empty_trades = pd.DataFrame(
        columns=[
            "pair", "direction", "signal_date", "entry_date", "exit_signal_date", "exit_date",
            "holding_days", "entry_price_a", "entry_price_b", "exit_price_a", "exit_price_b",
            "shares_a", "shares_b", "gross_pnl", "trade_cost", "borrow_cost", "costs", "net_pnl",
            "return_on_capital", "exit_reason"
        ]
    )

    stats = compute_trade_metrics(empty_trades)

    # Must return 0 for trade count, and strictly NaN for averages/rates (never inf)
    assert stats["n_trades"] == 0
    assert stats["n_wins"] == 0
    assert stats["n_losses"] == 0
    assert math.isnan(stats["win_rate"])
    assert math.isnan(stats["mean_trade_return"])
    assert math.isnan(stats["median_trade_return"])
    assert math.isnan(stats["mean_holding_days"])
    assert math.isnan(stats["max_holding_days"])
    assert math.isnan(stats["profit_factor"])

    # No inf values
    for k, v in stats.items():
        if isinstance(v, float):
            assert not math.isinf(v)

    # Turnover on empty trades must return 0.0
    dummy_daily = pd.DataFrame({"equity": [100_000.0, 100_000.0]})
    assert compute_turnover(empty_trades, dummy_daily) == 0.0


def test_volatility_zero_or_trivial():
    # Single observation return series
    single_ret = pd.Series([0.01])
    assert math.isnan(compute_annualized_volatility(single_ret))

    # Identical returns (zero variance)
    const_rets = pd.Series([0.005, 0.005, 0.005])
    vol = compute_annualized_volatility(const_rets)
    assert math.isnan(vol)
    assert not math.isinf(vol)
