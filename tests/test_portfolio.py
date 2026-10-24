"""Unit and accounting invariant tests for multi-pair portfolio aggregation."""

import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.portfolio import compute_turnover, run_portfolio


@pytest.fixture(scope="module")
def cfg():
    return load_config("configs/baseline.yaml")


@pytest.fixture(scope="module")
def train_result(cfg):
    return run_portfolio(cfg=cfg, period="train")


@pytest.fixture(scope="module")
def val_result(cfg):
    return run_portfolio(cfg=cfg, period="validation")


def test_accounting_invariant_ending_equity_equals_trade_net_pnl(train_result, val_result, cfg):
    """Invariant 1: ending equity - starting equity == sum of trade net P&L (tolerance 1e-8)."""
    for res in [train_result, val_result]:
        daily = res.daily
        trades = res.trades

        starting_capital = float(cfg.capital.initial_capital)
        ending_equity = float(daily["equity"].iloc[-1])
        equity_delta = ending_equity - starting_capital

        sum_trade_net_pnl = float(trades["net_pnl"].sum())

        np.testing.assert_allclose(
            equity_delta,
            sum_trade_net_pnl,
            rtol=1e-8,
            atol=1e-8,
            err_msg="Ending equity minus starting equity must equal the sum of trade net P&L.",
        )


def test_accounting_invariant_sum_per_pair_pnl_equals_portfolio_pnl(train_result, val_result):
    """Invariant 2: the sum of per-pair P&L equals portfolio P&L (tolerance 1e-8)."""
    for res in [train_result, val_result]:
        daily = res.daily
        pair_results = res.pair_results

        # Check total period sum
        pair_total_net = sum(float(b_res.daily["net_pnl"].sum()) for b_res in pair_results.values())
        port_total_net = float(daily["net_pnl"].sum())
        np.testing.assert_allclose(
            pair_total_net,
            port_total_net,
            rtol=1e-8,
            atol=1e-8,
            err_msg="Sum of pair total net P&Ls must equal portfolio total net P&L.",
        )

        # Check day-by-day vector sum
        pnl_cols = [c for c in daily.columns if c.startswith("pnl_")]
        assert len(pnl_cols) == len(pair_results)
        daily_pair_sum = daily[pnl_cols].sum(axis=1).values
        port_daily_net = daily["net_pnl"].values

        np.testing.assert_allclose(
            daily_pair_sum,
            port_daily_net,
            rtol=1e-8,
            atol=1e-8,
            err_msg="Sum of daily pair P&Ls must equal portfolio daily net P&L on every bar.",
        )


def test_accounting_invariant_gross_minus_net_equals_trade_costs_plus_borrow(train_result, val_result):
    """Invariant 3: gross P&L - net P&L == total trade costs + borrow costs (tolerance 1e-8)."""
    for res in [train_result, val_result]:
        daily = res.daily
        gross = daily["gross_pnl"].values
        net = daily["net_pnl"].values
        trade_cost = daily["trade_cost"].values
        borrow_cost = daily["borrow_cost"].values

        cost_diff = gross - net
        expected_costs = trade_cost + borrow_cost

        np.testing.assert_allclose(
            cost_diff,
            expected_costs,
            rtol=1e-8,
            atol=1e-8,
            err_msg="Gross minus net P&L must equal trade costs plus borrow costs.",
        )


def test_accounting_invariant_compounding_returns_reproduces_equity(train_result, val_result, cfg):
    """Invariant 4: compounding the return series reproduces the equity curve (tolerance 1e-8)."""
    for res in [train_result, val_result]:
        daily = res.daily
        initial_capital = float(cfg.capital.initial_capital)
        returns = daily["return"].values
        equity_actual = daily["equity"].values

        # Compounding: equity_t = initial_capital * prod_{s=0}^t (1 + r_s)
        equity_reconstructed = initial_capital * np.cumprod(1.0 + returns)

        np.testing.assert_allclose(
            equity_reconstructed,
            equity_actual,
            rtol=1e-8,
            atol=1e-8,
            err_msg="Compounding the return series must strictly reproduce the equity curve.",
        )


def test_turnover_formula_consistency(train_result, val_result):
    """Verify annualized turnover calculation matches formula."""
    for res in [train_result, val_result]:
        daily = res.daily
        trades = res.trades
        turnover = res.turnover

        avg_equity = float(daily["equity"].mean())
        entry_notional = (trades["shares_a"].abs() * trades["entry_price_a"] + trades["shares_b"].abs() * trades["entry_price_b"]).sum()
        exit_notional = (trades["shares_a"].abs() * trades["exit_price_a"] + trades["shares_b"].abs() * trades["exit_price_b"]).sum()
        expected_turnover = float((entry_notional + exit_notional) / avg_equity * (252.0 / len(daily)))

        assert pytest.approx(turnover, rel=1e-6) == expected_turnover


def test_test_period_locked_raises_permission_error(cfg):
    """Ensure accessing locked test period raises PermissionError."""
    assert cfg.dates.unlock_test is False
    with pytest.raises(PermissionError, match="strictly locked"):
        run_portfolio(cfg=cfg, period="test")


def test_exposure_and_open_pairs_tracking(train_result, val_result):
    """Verify gross exposure is non-negative and open pairs count is within bounds."""
    for res in [train_result, val_result]:
        daily = res.daily
        k_pairs = len(res.pair_results)

        assert (daily["gross_exposure"] >= 0.0).all()
        assert (daily["open_pairs"] >= 0).all()
        assert (daily["open_pairs"] <= k_pairs).all()
        assert (daily["gross_leverage"] >= 0.0).all()


def test_run_portfolio_rolling_60_with_prices_passed(cfg):
    """Verify rolling_60 baseline executes without UnboundLocalError when prices DataFrame is passed."""
    import copy

    dates = pd.date_range("2020-01-01", periods=80, freq="B")
    np.random.seed(42)
    prices = pd.DataFrame(
        {
            "A": 100.0 + np.cumsum(np.random.randn(80)),
            "B": 100.0 + np.cumsum(np.random.randn(80)),
        },
        index=dates,
    )
    hedge_df = pd.DataFrame(
        [
            {
                "pair": "A_B",
                "leg_a": "A",
                "leg_b": "B",
                "alpha": 0.0,
                "beta": 1.0,
                "res_mean_train": 0.0,
                "res_std_train": 1.0,
            }
        ]
    )

    from dataclasses import replace

    cfg_rolling = replace(cfg, signals=replace(cfg.signals, z_score_baseline="rolling_60"))

    res = run_portfolio(cfg=cfg_rolling, period="train", prices=prices, hedge_params=hedge_df)
    assert res is not None
    assert (res.daily["open_pairs"].iloc[:60] == 0).all()
    assert (res.pair_results["A_B"].daily["position"].iloc[:60] == 0).all()
