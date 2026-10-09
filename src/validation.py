"""Data validation, missing value inspection, anomaly flagging, and clean panel construction module."""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def check_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Report missing (NaN) count and missing percentage for each ticker column."""
    total_rows = len(df)
    records = []
    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        pct_missing = (n_missing / total_rows * 100.0) if total_rows > 0 else 0.0
        records.append({
            "ticker": str(col),
            "total_rows": total_rows,
            "missing_count": n_missing,
            "missing_pct": round(pct_missing, 4),
        })
    return pd.DataFrame(records)


def check_duplicate_dates(df: pd.DataFrame) -> List[pd.Timestamp]:
    """Identify duplicate timestamps present in the DataFrame index."""
    idx = df.index
    duplicates = idx[idx.duplicated()].unique().tolist()
    return duplicates


def check_non_positive_prices(df: pd.DataFrame) -> Dict[str, int]:
    """Count non-positive (<= 0) price values per ticker."""
    counts: Dict[str, int] = {}
    for col in df.columns:
        valid_prices = df[col].dropna()
        non_positive = int((valid_prices <= 0).sum())
        counts[str(col)] = non_positive
    return counts


def check_monotonic_index(df: pd.DataFrame) -> bool:
    """Check if the DataFrame index is strictly monotonic increasing."""
    return bool(df.index.is_monotonic_increasing and not df.index.has_duplicates)


def check_abnormal_returns(
    df: pd.DataFrame,
    threshold: float = 0.25,
) -> pd.DataFrame:
    """Flag daily absolute log returns exceeding the threshold (e.g., |r| > 25%).

    Rules:
        Flag anomalous returns for audit purposes; NEVER silently alter or remove them.

    Parameters
    ----------
    df : pd.DataFrame
        Daily price panel.
    threshold : float, default 0.25
        Absolute daily log return cutoff for flagging.

    Returns
    -------
    pd.DataFrame
        Table of flagged events with columns: ['date', 'ticker', 'price_prev', 'price_curr', 'log_return'].
    """
    flagged = []
    for col in df.columns:
        series = df[col].dropna()
        if len(series) < 2:
            continue
        log_rets = np.log(series / series.shift(1))
        abnormal = log_rets[np.abs(log_rets) > threshold]
        for dt, ret in abnormal.items():
            loc = series.index.get_loc(dt)
            prev_price = series.iloc[loc - 1] if isinstance(loc, int) and loc > 0 else np.nan
            flagged.append({
                "date": dt,
                "ticker": str(col),
                "price_prev": float(prev_price),
                "price_curr": float(series.loc[dt]),
                "log_return": round(float(ret), 6),
            })
    return pd.DataFrame(flagged)


def check_date_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """Report the first and last valid observation date and total valid observations per ticker."""
    records = []
    for col in df.columns:
        valid_series = df[col].dropna()
        if valid_series.empty:
            records.append({
                "ticker": str(col),
                "first_valid_date": None,
                "last_valid_date": None,
                "valid_count": 0,
            })
        else:
            records.append({
                "ticker": str(col),
                "first_valid_date": str(valid_series.index.min().date()),
                "last_valid_date": str(valid_series.index.max().date()),
                "valid_count": int(valid_series.shape[0]),
            })
    return pd.DataFrame(records)


def check_calendar_alignment(df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate calendar alignment relative to the union trading calendar.

    The union trading calendar consists of all trading days where at least one
    ticker in the universe recorded a price observation.

    Returns
    -------
    pd.DataFrame
        Summary table showing union trading days, days present, and missing days per ticker.
    """
    union_dates = df.dropna(how="all").index.unique()
    total_union_days = len(union_dates)

    records = []
    for col in df.columns:
        present_days = int(df[col].dropna().shape[0])
        missing_days = total_union_days - present_days
        records.append({
            "ticker": str(col),
            "union_trading_days": total_union_days,
            "days_present": present_days,
            "days_missing": missing_days,
            "coverage_pct": round((present_days / total_union_days * 100.0) if total_union_days > 0 else 0.0, 4),
        })
    return pd.DataFrame(records)


def build_clean_panel(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Construct an aligned clean daily price panel adhering strictly to missing data policies.

    Missing-Data Policy:
        NO forward-filling and NO back-filling. Missing values are preserved as NaN.
        Pair-level statistical analysis and backtest simulation later drop dates
        where either leg of a specific candidate pair is missing.

    Parameters
    ----------
    df : pd.DataFrame
        Raw downloaded DataFrame (may have MultiIndex columns e.g. from yfinance).

    Returns
    -------
    clean_panel : pd.DataFrame
        Aligned price panel indexed by unique, sorted DatetimeIndex with ticker columns.
    dropped_or_missing_log : pd.DataFrame
        Log of every missing observation across the union trading calendar.
    """
    # Extract Close series if MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.levels[0]:
            close_panel = df["Close"].copy()
        else:
            # Try second level or fallback
            close_panel = df.copy()
    else:
        close_panel = df.copy()

    # Ensure index is DatetimeIndex
    if not isinstance(close_panel.index, pd.DatetimeIndex):
        close_panel.index = pd.to_datetime(close_panel.index)

    # Normalize to tz-naive midnight
    if close_panel.index.tz is not None:
        close_panel.index = close_panel.index.tz_localize(None)
    close_panel.index = close_panel.index.normalize()

    # Deduplicate index if any duplicate dates exist, keeping first
    if close_panel.index.has_duplicates:
        close_panel = close_panel.loc[~close_panel.index.duplicated(keep="first")]

    # Sort chronologically
    close_panel = close_panel.sort_index()

    # Define union trading calendar: dates where at least one ticker has a valid non-NaN price
    union_idx = close_panel.dropna(how="all").index
    clean_panel = close_panel.reindex(union_idx)

    # Build log of missing observations
    missing_records = []
    for col in clean_panel.columns:
        nan_dates = clean_panel.index[clean_panel[col].isna()]
        for dt in nan_dates:
            missing_records.append({
                "date": dt,
                "ticker": str(col),
                "issue": "missing_price_on_union_day",
            })

    missing_log = pd.DataFrame(missing_records)
    if missing_log.empty:
        missing_log = pd.DataFrame(columns=["date", "ticker", "issue"])

    return clean_panel, missing_log
