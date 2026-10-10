"""Candidate-pair screening, Engle-Granger cointegration, Holm correction, and hedge estimation module."""

from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import coint

from src.config import Config, UniverseConfig


def candidate_pairs(universe: UniverseConfig) -> List[Tuple[str, str, str]]:
    """Generate all unique within-sector candidate pairs.

    Parameters
    ----------
    universe : UniverseConfig
        Universe configuration containing sectoral ticker lists.

    Returns
    -------
    List[Tuple[str, str, str]]
        List of (leg_A, leg_B, sector) tuples where leg_A is alphabetically first.
    """
    pairs: List[Tuple[str, str, str]] = []
    sector_buckets = [
        ("banks", universe.banks),
        ("energy", universe.energy),
        ("staples", universe.staples),
    ]

    for sector, tickers in sector_buckets:
        sorted_tickers = sorted(tickers)
        for a, b in itertools.combinations(sorted_tickers, 2):
            # Deterministic ordering: alphabetically first ticker is leg A
            pairs.append((a, b, sector))

    return pairs


def engle_granger(
    y: Union[pd.Series, np.ndarray],
    x: Union[pd.Series, np.ndarray],
    trend: str = "c",
) -> Tuple[float, float, Dict[str, float]]:
    """Execute Engle-Granger two-step cointegration test.

    Null Hypothesis (H0):
        The two series are not cointegrated (residuals possess a unit root).
    Alternative Hypothesis (H1):
        The series are cointegrated.

    Parameters
    ----------
    y : Union[pd.Series, np.ndarray]
        Dependent price/log-price series.
    x : Union[pd.Series, np.ndarray]
        Independent price/log-price series.
    trend : str, default "c"
        Trend included in cointegrating equation ('c' for constant).

    Returns
    -------
    Tuple[float, float, Dict[str, float]]
        (test_statistic, p_value, critical_values_dict)
    """
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float)

    # Filter out NaNs if any
    valid_mask = ~(np.isnan(y_arr) | np.isnan(x_arr))
    y_arr = y_arr[valid_mask]
    x_arr = x_arr[valid_mask]

    score, pvalue, crit_val = coint(y_arr, x_arr, trend=trend)
    crit_dict = {"1%": float(crit_val[0]), "5%": float(crit_val[1]), "10%": float(crit_val[2])}
    return float(score), float(pvalue), crit_dict


def half_life(spread: Union[pd.Series, np.ndarray]) -> float:
    """Estimate mean-reversion half-life (in trading days) from an AR(1) spread regression.

    Model:
        Delta spread_t = gamma * spread_{t-1} + mu + epsilon_t
        where gamma = lambda - 1.

    Half-life:
        -ln(2) / gamma, for gamma < 0.

    Parameters
    ----------
    spread : Union[pd.Series, np.ndarray]
        Residual spread time series.

    Returns
    -------
    float
        Half-life in trading days. Returns NaN if gamma >= 0 (non-mean-reverting).
    """
    s = pd.Series(spread).dropna().values
    if len(s) < 10:
        return float("nan")

    delta_s = np.diff(s)
    lag_s = s[:-1]

    # OLS of delta_s on lag_s with constant: delta_s = gamma * lag_s + mu
    x_mat = np.column_stack([lag_s, np.ones_like(lag_s)])
    try:
        params, residuals, rank, s_vals = np.linalg.lstsq(x_mat, delta_s, rcond=None)
        gamma = params[0]
        if gamma < 0.0:
            hl = -np.log(2.0) / gamma
            return float(hl)
        else:
            return float("nan")
    except Exception:
        return float("nan")


def holm(p_values: Sequence[float], alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
    """Holm-Bonferroni step-down multiple hypothesis testing correction.

    Parameters
    ----------
    p_values : Sequence[float]
        Vector of raw p-values.
    alpha : float, default 0.05
        Family-wise error rate significance threshold.

    Returns
    -------
    reject : np.ndarray
        Boolean array indicating rejected null hypotheses (passing significance).
    p_adj : np.ndarray
        Monotonically adjusted p-values.
    """
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    if m == 0:
        return np.array([], dtype=bool), np.array([], dtype=float)

    sort_order = np.argsort(p)
    sorted_p = p[sort_order]

    # Step-down adjusted p-values: p_adj(i) = max_{k <= i} min(1.0, (m - k + 1) * p(k))
    adj_sorted = np.empty(m, dtype=float)
    cum_max = 0.0
    for i in range(m):
        raw_adj = (m - i) * sorted_p[i]
        bounded = min(1.0, max(0.0, raw_adj))
        cum_max = max(cum_max, bounded)
        adj_sorted[i] = cum_max

    # Invert sorted order back to original input indexing
    p_adj = np.empty(m, dtype=float)
    p_adj[sort_order] = adj_sorted

    reject = p_adj < alpha
    return reject, p_adj


def fit_hedge(
    logA: Union[pd.Series, np.ndarray],
    logB: Union[pd.Series, np.ndarray],
) -> Dict[str, float]:
    """Fit OLS hedge regression on training log prices: log(P_A) = alpha + beta * log(P_B) + eps.

    Parameters
    ----------
    logA : Union[pd.Series, np.ndarray]
        Log prices of dependent ticker A.
    logB : Union[pd.Series, np.ndarray]
        Log prices of independent ticker B.

    Returns
    -------
    Dict[str, float]
        Dictionary with fitted alpha, beta, residual mean, residual std, and R^2.
    """
    y = np.asarray(logA, dtype=float)
    x = np.asarray(logB, dtype=float)

    valid = ~(np.isnan(y) | np.isnan(x))
    y = y[valid]
    x = x[valid]

    # OLS: y = alpha + beta * x
    X = np.column_stack([np.ones_like(x), x])
    params, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    alpha = float(params[0])
    beta = float(params[1])

    y_pred = alpha + beta * x
    residuals = y - y_pred

    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r_squared = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    return {
        "alpha": alpha,
        "beta": beta,
        "res_mean": float(np.mean(residuals)),
        "res_std": float(np.std(residuals, ddof=1)),
        "r_squared": r_squared,
    }


def construct_spread(
    prices: pd.DataFrame,
    params: Dict[str, Any],
    leg_a: Optional[str] = None,
    leg_b: Optional[str] = None,
) -> pd.Series:
    """Construct spread series using strictly frozen alpha and beta parameters.

    spread_t = ln(P_A,t) - alpha - beta * ln(P_B,t)

    Parameters
    ----------
    prices : pd.DataFrame
        DataFrame with price columns for leg_a and leg_b.
    params : Dict[str, Any]
        Pre-fitted parameters containing 'alpha', 'beta', and optionally 'leg_a', 'leg_b'.
    leg_a : Optional[str]
        Ticker symbol for dependent leg A (optional if present in params).
    leg_b : Optional[str]
        Ticker symbol for independent leg B (optional if present in params).

    Returns
    -------
    pd.Series
        Constructed spread time series.
    """
    a = leg_a if leg_a is not None else params.get("leg_a")
    b = leg_b if leg_b is not None else params.get("leg_b")
    if not a or not b:
        raise ValueError("leg_a and leg_b must be provided either as arguments or inside params dict")

    log_a = np.log(prices[a])
    log_b = np.log(prices[b])
    alpha = float(params["alpha"])
    beta = float(params["beta"])
    spread = log_a - alpha - beta * log_b
    spread.name = f"{a}_{b}_spread"
    return spread


def zscore(
    spread: Union[pd.Series, np.ndarray],
    mu_train: float,
    sd_train: float,
) -> pd.Series:
    """Calculate spread z-score using strictly frozen training period mean and standard deviation.

    z_t = (spread_t - mu_train) / sd_train

    Parameters
    ----------
    spread : Union[pd.Series, np.ndarray]
        Spread series.
    mu_train : float
        Frozen training-period spread mean.
    sd_train : float
        Frozen training-period spread standard deviation.

    Returns
    -------
    pd.Series
        Normalized z-score series.
    """
    s = pd.Series(spread)
    if sd_train <= 0.0 or np.isnan(sd_train):
        raise ValueError(f"sd_train must be strictly positive, got {sd_train}")
    z = (s - mu_train) / sd_train
    z.name = f"{s.name}_zscore" if s.name else "zscore"
    return z


def screen_pairs(
    train_prices: pd.DataFrame,
    cfg: Config,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Execute candidate-pair screening with Engle-Granger and Holm multiple testing correction.

    Parameters
    ----------
    train_prices : pd.DataFrame
        Clean price panel sliced strictly to the training period.
    cfg : Config
        Pipeline configuration dataclass.

    Returns
    -------
    screening_df : pd.DataFrame
        Table of all candidate pairs evaluated with statistics, p-values, and half-lives.
    selected_df : pd.DataFrame
        Frozen table of pairs passing screening (or pre-registered exploratory fallback).
    """
    # Invariant assertion: every date must reside within the training window
    train_start = pd.Timestamp(cfg.dates.train_start)
    train_end = pd.Timestamp(cfg.dates.train_end)
    assert train_prices.index.min() >= train_start, (
        f"train_prices index min {train_prices.index.min()} precedes train_start {train_start}"
    )
    assert train_prices.index.max() <= train_end, (
        f"train_prices index max {train_prices.index.max()} exceeds train_end {train_end}"
    )

    candidates = candidate_pairs(cfg.universe)
    log_prices = np.log(train_prices)
    daily_rets = log_prices.diff().dropna()

    results: List[Dict[str, Any]] = []

    for leg_a, leg_b, sector in candidates:
        s_a = log_prices[leg_a].dropna()
        s_b = log_prices[leg_b].dropna()
        common_idx = s_a.index.intersection(s_b.index)
        y = s_a.loc[common_idx]
        x = s_b.loc[common_idx]

        # 1. Pearson return correlation on training data
        ret_a = daily_rets[leg_a].loc[common_idx.intersection(daily_rets.index)]
        ret_b = daily_rets[leg_b].loc[common_idx.intersection(daily_rets.index)]
        corr = float(ret_a.corr(ret_b))

        # 2. Engle-Granger test in both regression orderings
        stat_ab, p_ab, crit_ab = engle_granger(y, x, trend=cfg.screening.trend)
        stat_ba, p_ba, crit_ba = engle_granger(x, y, trend=cfg.screening.trend)

        # Conservative bidirectional rule: pair p-value is the maximum of the two orderings
        raw_p = max(p_ab, p_ba)

        # 3. Fit hedge on training: log(A) = alpha + beta * log(B)
        hedge = fit_hedge(y, x)
        spread_res = y - (hedge["alpha"] + hedge["beta"] * x)
        hl = half_life(spread_res)

        results.append({
            "pair": f"{leg_a}_{leg_b}",
            "leg_a": leg_a,
            "leg_b": leg_b,
            "sector": sector,
            "correlation": round(corr, 4),
            "stat_ab": round(stat_ab, 4),
            "p_ab": round(p_ab, 6),
            "stat_ba": round(stat_ba, 4),
            "p_ba": round(p_ba, 6),
            "raw_p": round(raw_p, 6),
            "alpha": round(hedge["alpha"], 6),
            "beta": round(hedge["beta"], 6),
            "r_squared": round(hedge["r_squared"], 4),
            "half_life_days": round(hl, 2) if not np.isnan(hl) else float("nan"),
        })

    screening_df = pd.DataFrame(results)

    # 4. Apply Holm multiple testing correction across all candidate pairs
    raw_p_values = screening_df["raw_p"].values
    reject, holm_p = holm(raw_p_values, alpha=cfg.screening.alpha)

    # Cross-check our Holm implementation against statsmodels multipletests
    sm_reject, sm_holm_p, _, _ = multipletests(raw_p_values, alpha=cfg.screening.alpha, method="holm")
    np.testing.assert_allclose(holm_p, sm_holm_p, rtol=1e-5, atol=1e-5)
    np.testing.assert_array_equal(reject, sm_reject)

    screening_df["holm_p"] = np.round(holm_p, 6)

    # Screening criteria:
    # 1. Holm adjusted p-value < alpha (0.05)
    # 2. Half-life between [min_half_life, max_half_life]
    min_hl = cfg.screening.min_half_life_days
    max_hl = cfg.screening.max_half_life_days

    hl_mask = (screening_df["half_life_days"] >= min_hl) & (screening_df["half_life_days"] <= max_hl)
    coint_mask = screening_df["holm_p"] < cfg.screening.alpha
    screening_df["passes_screening"] = coint_mask & hl_mask
    screening_df["is_exploratory"] = False

    passed_pairs = screening_df[screening_df["passes_screening"]].copy()

    # Pre-registered fallback check:
    if len(passed_pairs) == 0:
        # Pre-registered fallback in PROGRESS.md decisions log:
        # Select 5 lowest raw p-value pairs that pass the half-life filter.
        candidates_with_valid_hl = screening_df[hl_mask].sort_values("raw_p")
        selected_df = candidates_with_valid_hl.head(5).copy()
        selected_df["is_exploratory"] = True
    else:
        selected_df = passed_pairs.copy()

    return screening_df, selected_df
