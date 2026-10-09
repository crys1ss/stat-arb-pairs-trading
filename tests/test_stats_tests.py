"""Unit tests for statistical hypothesis tests (ADF, KPSS wrappers)."""

import numpy as np
import pytest
from src.stats_tests import adf_test, kpss_test


def test_adf_fails_to_reject_on_seeded_random_walk():
    rng = np.random.default_rng(42)
    # Generate random walk: y_t = y_{t-1} + e_t
    n = 500
    innovations = rng.standard_normal(n)
    rw = np.cumsum(innovations)

    res = adf_test(rw, regression="c", autolag="AIC")
    assert res["error"] is None
    # On a random walk, ADF should fail to reject H0 (unit root exists) -> p-value > 0.05
    assert res["pvalue"] > 0.05
    assert not np.isnan(res["stat"])
    assert res["nobs"] > 400


def test_adf_rejects_on_seeded_stationary_ar1():
    rng = np.random.default_rng(42)
    # Generate AR(1) with phi = 0.5: stationary
    n = 500
    innovations = rng.standard_normal(n)
    ar1 = np.zeros(n)
    for t in range(1, n):
        ar1[t] = 0.5 * ar1[t - 1] + innovations[t]

    res = adf_test(ar1, regression="c", autolag="AIC")
    assert res["error"] is None
    # On stationary AR(1), ADF should reject H0 -> p-value < 0.05
    assert res["pvalue"] < 0.05
    assert res["stat"] < res["crit_values"]["5%"]


def test_adf_returns_nan_gracefully_on_constant_series():
    constant_series = np.full(100, 42.0)
    res = adf_test(constant_series)
    assert np.isnan(res["stat"])
    assert np.isnan(res["pvalue"])
    assert res["error"] == "constant_series_zero_variance"


def test_kpss_returns_nan_gracefully_on_constant_series():
    constant_series = np.full(100, 42.0)
    res = kpss_test(constant_series)
    assert np.isnan(res["stat"])
    assert np.isnan(res["pvalue"])
    assert res["error"] == "constant_series_zero_variance"


def test_kpss_pvalue_and_bounds():
    rng = np.random.default_rng(42)
    white_noise = rng.standard_normal(500)
    res = kpss_test(white_noise)
    assert res["error"] is None
    # For stationary white noise, KPSS should fail to reject H0 (p-value >= 0.05)
    assert res["pvalue"] >= 0.05
    # Statsmodels truncates KPSS p-values to [0.01, 0.10]
    assert 0.01 <= res["pvalue"] <= 0.10
