"""Statistical hypothesis testing wrappers for unit root and stationarity diagnostics (ADF, KPSS)."""

from __future__ import annotations

import warnings
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tools.sm_exceptions import InterpolationWarning


def adf_test(
    series: Union[pd.Series, np.ndarray],
    regression: str = "c",
    autolag: str = "AIC",
) -> Dict[str, Any]:
    """Augmented Dickey-Fuller (ADF) unit root test wrapper.

    Null Hypothesis (H0):
        The series possesses a unit root (non-stationary).
    Alternative Hypothesis (H1):
        The series is stationary.

    Parameters
    ----------
    series : Union[pd.Series, np.ndarray]
        Time series to evaluate.
    regression : str, default "c"
        Constant term included ('c' for constant, 'ct' for constant and trend).
    autolag : str, default "AIC"
        Lag length selection criterion.

    Returns
    -------
    Dict[str, Any]
        Dictionary with keys:
        'stat': float, test statistic
        'pvalue': float, MacKinnon approximate p-value
        'lags': int, number of lags utilized
        'nobs': int, effective number of observations
        'crit_values': dict, critical values at 1%, 5%, 10%
        'error': Optional[str], failure reason if test could not be evaluated
    """
    clean_series = pd.Series(series).dropna().values
    if len(clean_series) < 10:
        return {
            "stat": float("nan"),
            "pvalue": float("nan"),
            "lags": 0,
            "nobs": len(clean_series),
            "crit_values": {},
            "error": "insufficient_observations",
        }

    # Detect zero variance / constant series
    if np.all(clean_series == clean_series[0]) or np.isclose(np.var(clean_series), 0.0):
        return {
            "stat": float("nan"),
            "pvalue": float("nan"),
            "lags": 0,
            "nobs": len(clean_series),
            "crit_values": {},
            "error": "constant_series_zero_variance",
        }

    try:
        res = adfuller(clean_series, regression=regression, autolag=autolag, result_object=False)
        return {
            "stat": float(res[0]),
            "pvalue": float(res[1]),
            "lags": int(res[2]),
            "nobs": int(res[3]),
            "crit_values": {k: float(v) for k, v in res[4].items()},
            "error": None,
        }
    except Exception as exc:
        return {
            "stat": float("nan"),
            "pvalue": float("nan"),
            "lags": 0,
            "nobs": len(clean_series),
            "crit_values": {},
            "error": str(exc),
        }


def kpss_test(
    series: Union[pd.Series, np.ndarray],
    regression: str = "c",
    nlags: str = "auto",
) -> Dict[str, Any]:
    """Kwiatkowski-Phillips-Schmidt-Shin (KPSS) stationarity test wrapper.

    Null Hypothesis (H0):
        The series is level-stationary (or trend-stationary if regression='ct').
    Alternative Hypothesis (H1):
        The series possesses a unit root (non-stationary).

    Note on p-value bounds:
        Statsmodels truncates KPSS asymptotic p-values to the interval [0.01, 0.10].
        P-values reported as 0.10 may be >= 0.10, and p-values reported as 0.01 may be <= 0.01.

    Parameters
    ----------
    series : Union[pd.Series, np.ndarray]
        Time series to evaluate.
    regression : str, default "c"
        'c' for level stationarity, 'ct' for trend stationarity.
    nlags : str, default "auto"
        Number of lags for Newey-West Bartlett kernel.

    Returns
    -------
    Dict[str, Any]
        Dictionary with keys:
        'stat': float, KPSS test statistic
        'pvalue': float, bounded p-value in [0.01, 0.10]
        'lags': int, lags utilized in covariance estimation
        'nobs': int, effective number of observations
        'crit_values': dict, critical values at 10%, 5%, 2.5%, 1%
        'error': Optional[str], failure reason if test could not be evaluated
    """
    clean_series = pd.Series(series).dropna().values
    if len(clean_series) < 10:
        return {
            "stat": float("nan"),
            "pvalue": float("nan"),
            "lags": 0,
            "nobs": len(clean_series),
            "crit_values": {},
            "error": "insufficient_observations",
        }

    if np.all(clean_series == clean_series[0]) or np.isclose(np.var(clean_series), 0.0):
        return {
            "stat": float("nan"),
            "pvalue": float("nan"),
            "lags": 0,
            "nobs": len(clean_series),
            "crit_values": {},
            "error": "constant_series_zero_variance",
        }

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InterpolationWarning)
            res = kpss(clean_series, regression=regression, nlags=nlags, result_object=False)
        return {
            "stat": float(res[0]),
            "pvalue": float(res[1]),
            "lags": int(res[2]),
            "nobs": len(clean_series),
            "crit_values": {k: float(v) for k, v in res[3].items()},
            "error": None,
        }
    except Exception as exc:
        return {
            "stat": float("nan"),
            "pvalue": float("nan"),
            "lags": 0,
            "nobs": len(clean_series),
            "crit_values": {},
            "error": str(exc),
        }
