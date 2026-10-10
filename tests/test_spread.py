"""Unit tests for hedge ratio estimation, spread construction, and z-score calculations."""

import numpy as np
import pandas as pd
import pytest

from src.pairs import construct_spread, fit_hedge, zscore


def test_spread_reproduces_constructed_residual():
    # Generate prices with known relationship: ln(A) = 0.50 + 1.25 * ln(B) + eps
    n = 100
    dates = pd.date_range("2021-01-01", periods=n, freq="B")
    log_b = np.linspace(3.0, 4.0, n)
    known_alpha = 0.50
    known_beta = 1.25
    known_eps = np.sin(np.linspace(0, 3 * np.pi, n)) * 0.05
    log_a = known_alpha + known_beta * log_b + known_eps

    prices = pd.DataFrame({
        "A": np.exp(log_a),
        "B": np.exp(log_b),
    }, index=dates)

    params = {"alpha": known_alpha, "beta": known_beta}
    spread = construct_spread(prices, params, leg_a="A", leg_b="B")

    # Invariant: constructed spread exactly matches known_eps
    np.testing.assert_allclose(spread.values, known_eps, atol=1e-10)


def test_no_lookahead_fit_hedge_frozen():
    # Invariant: changing post-training data has ZERO impact on training parameters
    n_train = 100
    dates_train = pd.date_range("2018-01-01", periods=n_train, freq="B")
    rng = np.random.default_rng(42)

    log_b_train = 3.0 + rng.standard_normal(n_train) * 0.1
    log_a_train = 0.2 + 0.8 * log_b_train + rng.standard_normal(n_train) * 0.02

    # Initial fit on training
    hedge_params_1 = fit_hedge(log_a_train, log_b_train)

    # Post-training modification: imagine post-training prices spike by 500%
    log_b_post = np.array([10.0, 15.0, 20.0])
    log_a_post = np.array([50.0, 60.0, 70.0])

    # Re-evaluate fitting ONLY on the training arrays
    hedge_params_2 = fit_hedge(log_a_train, log_b_train)

    assert hedge_params_1["alpha"] == hedge_params_2["alpha"]
    assert hedge_params_1["beta"] == hedge_params_2["beta"]
    assert hedge_params_1["r_squared"] == hedge_params_2["r_squared"]


def test_zscore_uses_frozen_training_statistics_not_full_sample():
    # Create two regimes: training regime with mu=0, sd=1, post-regime with mean shift to 5
    s_train = np.array([-1.0, 0.0, 1.0])
    s_post = np.array([4.0, 5.0, 6.0])
    s_full = np.concatenate([s_train, s_post])

    mu_train = float(np.mean(s_train))  # 0.0
    sd_train = float(np.std(s_train, ddof=1))  # 1.0

    z_full = zscore(s_full, mu_train=mu_train, sd_train=sd_train)

    # Expected: z_full[3] is (4.0 - 0.0) / 1.0 = 4.0
    # NOT normalized using full sample mean (~2.33) and full sample std (~2.94)
    expected_z = (s_full - mu_train) / sd_train
    np.testing.assert_allclose(z_full.values, expected_z, atol=1e-10)
    assert z_full.iloc[3] == pytest.approx(4.0)


def test_zscore_invalid_sd_raises_value_error():
    spread = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="strictly positive"):
        zscore(spread, mu_train=0.0, sd_train=0.0)
