"""Unit tests for failure analysis, market exposure, and structural break diagnostics."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.config import load_config
from src.failure_analysis import (
    compute_cointegration_decay,
    compute_hedge_ratio_instability,
    compute_market_exposure,
    compute_structural_breaks,
    compute_subperiod_analysis,
    extract_worst_trades,
)


@pytest.fixture(scope="module")
def cfg():
    return load_config("configs/test_run.yaml")


@pytest.fixture(scope="module")
def prices():
    p_file = Path("data/processed/close.parquet")
    return pd.read_parquet(p_file)


@pytest.fixture(scope="module")
def hedge_params():
    h_file = Path("reports/results/hedge_params.csv")
    return pd.read_csv(h_file)


def test_market_exposure_regression(cfg):
    """Verify market beta regression runs across periods with valid HAC statistics."""
    res_df = compute_market_exposure(cfg=cfg, results_dir="reports/results", raw_dir="data/raw")
    assert not res_df.empty
    assert set(res_df["period"]).issuperset({"train", "validation", "test", "full_span"})
    # Verify market neutrality: strategy beta is low (|beta| < 0.2 across all periods)
    assert (res_df["market_beta"].abs() < 0.20).all()
    assert res_df["hac_tstat_5lags"].notna().all()


def test_hedge_ratio_instability_calculation(prices, hedge_params):
    """Verify rolling beta instability calculation and percentage deviation."""
    summary_df, rolling_df = compute_hedge_ratio_instability(prices, hedge_params, window=252)
    assert len(summary_df) == len(hedge_params)
    assert set(summary_df["pair"]) == set(hedge_params["pair"])
    assert (summary_df["mean_abs_pct_deviation"] >= 0.0).all()
    assert rolling_df.shape[0] == len(prices)


def test_cointegration_decay_evaluation(prices, hedge_params, cfg):
    """Verify cointegration decay diagnostics cover train, validation, and test windows."""
    coint_df = compute_cointegration_decay(prices, hedge_params, cfg)
    assert len(coint_df) == len(hedge_params) * 3
    assert set(coint_df["period"]) == {"train", "validation", "test"}
    assert (coint_df["bidirectional_max_pval"] >= 0.0).all()
    assert (coint_df["bidirectional_max_pval"] <= 1.0).all()


def test_structural_breaks_cusum(prices, hedge_params):
    """Verify OLS-residual CUSUM test returns valid statistics and critical thresholds."""
    breaks_df = compute_structural_breaks(prices, hedge_params)
    assert len(breaks_df) == len(hedge_params)
    assert (breaks_df["cusum_statistic"] > 0.0).all()
    assert (breaks_df["p_value"] >= 0.0).all()
    assert (breaks_df["p_value"] <= 1.0).all()
    assert "has_structural_break" in breaks_df.columns


def test_worst_trades_extraction(prices, hedge_params):
    """Verify extraction of 5 worst trades sorted by net P&L ascending."""
    worst_df, details = extract_worst_trades("reports/results", n_worst=5, prices=prices, hedge_params=hedge_params)
    assert len(worst_df) == 5
    assert len(details) == 5
    # Must be sorted ascending by net P&L
    pnl_vals = worst_df["net_pnl"].values
    assert (np.diff(pnl_vals) >= 0).all()
    assert (worst_df["net_pnl"] < 0).all()


def test_subperiod_analysis_coverage(cfg):
    """Verify subperiod analysis covers calendar years and stress windows."""
    sub_df = compute_subperiod_analysis(cfg, results_dir="reports/results")
    assert not sub_df.empty
    names = set(sub_df["subperiod_name"])
    assert {"2018", "2019", "2020", "2021", "2022", "2023", "2024"}.issubset(names)
    assert "2020 Covid Crash" in names
    assert "2022 Rate Hikes" in names
