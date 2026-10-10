"""Unit tests for candidate pairs screening, Engle-Granger cointegration, half-life estimation, and Holm correction."""

import numpy as np
import pytest
from src.config import UniverseConfig
from src.pairs import candidate_pairs, engle_granger, half_life, holm


def test_pairs_generated_within_sectors_only():
    universe = UniverseConfig(
        banks=["JPM", "BAC", "WFC"],
        energy=["XOM", "CVX"],
        staples=["KO", "PEP"],
    )
    pairs = candidate_pairs(universe)

    # banks: 3 choose 2 = 3
    # energy: 2 choose 2 = 1
    # staples: 2 choose 2 = 1
    # Total = 5
    assert len(pairs) == 5

    for leg_a, leg_b, sector in pairs:
        assert leg_a < leg_b  # Deterministic alphabetical ordering
        if sector == "banks":
            assert leg_a in universe.banks and leg_b in universe.banks
        elif sector == "energy":
            assert leg_a in universe.energy and leg_b in universe.energy
        elif sector == "staples":
            assert leg_a in universe.staples and leg_b in universe.staples


def test_holm_step_down_on_known_p_values():
    # Known 4 hypothesis p-values
    # Hand calculation:
    # m = 4, alpha = 0.05
    # Raw p: [0.01, 0.04, 0.005, 0.20]
    # Sorted:
    # i=0: p=0.005 -> adj = 4 * 0.005 = 0.02 (< 0.05 -> reject)
    # i=1: p=0.010 -> adj = max(0.02, 3 * 0.01) = 0.03 (< 0.05 -> reject)
    # i=2: p=0.040 -> adj = max(0.03, 2 * 0.04) = 0.08 (>= 0.05 -> fail)
    # i=3: p=0.200 -> adj = max(0.08, 1 * 0.20) = 0.20 (>= 0.05 -> fail)
    #
    # Final adjusted p in original order:
    # 0.01  -> 0.03
    # 0.04  -> 0.08
    # 0.005 -> 0.02
    # 0.20  -> 0.20
    # Rejections: [True, False, True, False]
    p_vals = [0.01, 0.04, 0.005, 0.20]
    reject, p_adj = holm(p_vals, alpha=0.05)

    expected_adj = np.array([0.03, 0.08, 0.02, 0.20])
    expected_reject = np.array([True, False, True, False])

    np.testing.assert_allclose(p_adj, expected_adj, atol=1e-5)
    np.testing.assert_array_equal(reject, expected_reject)


def test_engle_granger_synthetic_cointegration():
    rng = np.random.default_rng(42)
    n = 600

    # Common stochastic trend (I(1) random walk)
    trend = np.cumsum(rng.standard_normal(n))

    # Cointegrated pair: y_t = 1.5 * x_t + stationary noise
    x = trend + 0.2 * rng.standard_normal(n)
    y = 1.5 * trend + 0.2 * rng.standard_normal(n)

    stat, pval, crit = engle_granger(y, x)
    # Engle-Granger should reject H0 (no cointegration) strongly
    assert pval < 0.01
    assert stat < crit["1%"]


def test_engle_granger_independent_random_walks():
    rng = np.random.default_rng(42)
    n = 600

    # Two independent random walks
    rw1 = np.cumsum(rng.standard_normal(n))
    rw2 = np.cumsum(rng.standard_normal(n))

    stat, pval, crit = engle_granger(rw1, rw2)
    # Should fail to reject H0 (no cointegration)
    assert pval > 0.05


def test_half_life_estimation_on_known_ar1():
    # Continuous AR(1): s_t = lambda * s_{t-1} + e_t
    # gamma = lambda - 1
    # half_life = -ln(2) / gamma
    # If lambda = 0.90, gamma = -0.10 -> half_life = -ln(2) / (-0.10) ~= 6.9315 trading days
    rng = np.random.default_rng(42)
    n = 10000
    e = rng.standard_normal(n)
    s = np.zeros(n)
    lam = 0.90
    for t in range(1, n):
        s[t] = lam * s[t - 1] + e[t]

    hl = half_life(s)
    expected_hl = -np.log(2.0) / (lam - 1.0)
    # Should match closely with high sample size
    assert pytest.approx(hl, rel=0.08) == expected_hl
