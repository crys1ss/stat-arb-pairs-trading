"""Data acquisition, caching, and chronological slicing module."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import yfinance as yf

from src.config import Config

logger = logging.getLogger(__name__)


def download_prices(
    cfg: Config,
    refresh: bool = False,
    raw_dir: Union[str, Path] = "data/raw",
    tickers: Optional[List[str]] = None,
    filename: str = "prices.parquet",
) -> pd.DataFrame:
    """Download daily equity price history via Yahoo Finance (yfinance) with local caching.

    Note on corporate actions:
        Splits and cash dividends are folded directly into the adjusted prices via
        yfinance's `auto_adjust=True` parameter.

    Parameters
    ----------
    cfg : Config
        Validated pipeline configuration dataclass.
    refresh : bool, default False
        If True, ignores cached files and forces a fresh download from Yahoo Finance.
    raw_dir : Union[str, Path], default "data/raw"
        Directory where raw prices parquet and metadata json are persisted.
    tickers : Optional[List[str]], default None
        Specific tickers to download. If None, defaults to cfg.universe.all_tickers.
    filename : str, default "prices.parquet"
        Destination parquet filename within raw_dir.

    Returns
    -------
    pd.DataFrame
        Downloaded price panel. If multiple tickers are fetched, columns are MultiIndex
        or ticker-indexed Close prices.

    Raises
    ------
    RuntimeError
        If download fails after retry attempt or returns empty data.
    """
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    parquet_file = raw_path / filename
    metadata_file = raw_path / ("metadata.json" if filename == "prices.parquet" else f"{Path(filename).stem}_metadata.json")

    if not refresh and parquet_file.is_file():
        logger.info(f"Loading cached price data from {parquet_file}")
        return pd.read_parquet(parquet_file)

    target_tickers: List[str] = tickers if tickers is not None else cfg.universe.all_tickers
    start_date: str = cfg.dates.download_start
    # yfinance end date is exclusive; add buffer or pass as specified
    end_date: str = cfg.dates.download_end

    logger.info(
        f"Downloading price history for {len(target_tickers)} tickers from {start_date} to {end_date} (refresh={refresh})"
    )


    download_attempts = 0
    max_attempts = 2
    raw_data: Optional[pd.DataFrame] = None
    last_error: Optional[Exception] = None

    while download_attempts < max_attempts:
        download_attempts += 1
        try:
            # auto_adjust=True folds splits and dividends into adjusted prices
            # threads=False prevents SQLite database locks in yfinance internal caching
            df = yf.download(
                tickers=target_tickers,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                group_by="column",
                progress=False,
                threads=False,
            )

            if df is not None and not df.empty:
                raw_data = df
                break
            else:
                raise ValueError("Downloaded DataFrame is empty.")
        except Exception as exc:
            last_error = exc
            logger.warning(
                f"Download attempt {download_attempts}/{max_attempts} failed: {exc}"
            )

    if raw_data is None or raw_data.empty:
        raise RuntimeError(
            f"Failed to download price data from yfinance after {max_attempts} attempts. "
            f"Underlying error: {last_error}"
        )

    # Normalize datetime index to tz-naive UTC midnight
    if isinstance(raw_data.index, pd.DatetimeIndex):
        if raw_data.index.tz is not None:
            raw_data.index = raw_data.index.tz_localize(None)
        raw_data.index = raw_data.index.normalize()

    # Cache raw DataFrame to parquet
    raw_data.to_parquet(parquet_file)

    # Compute row counts per ticker for metadata provenance
    rows_per_ticker: Dict[str, int] = {}
    if isinstance(raw_data.columns, pd.MultiIndex):
        if "Close" in raw_data.columns.levels[0]:
            close_subset = raw_data["Close"]
            for t in target_tickers:
                rows_per_ticker[t] = int(close_subset[t].dropna().shape[0]) if t in close_subset.columns else 0
        else:
            for t in target_tickers:
                rows_per_ticker[t] = int(raw_data.xs(t, axis=1, level=1).dropna().shape[0]) if t in raw_data.columns.levels[1] else 0
    else:
        for t in target_tickers:
            rows_per_ticker[t] = int(raw_data[t].dropna().shape[0]) if t in raw_data.columns else 0

    metadata: Dict[str, Any] = {
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "yfinance_version": getattr(yf, "__version__", "unknown"),
        "tickers": target_tickers,
        "requested_range": {
            "start": start_date,
            "end": end_date,
        },
        "rows_per_ticker": rows_per_ticker,
    }

    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Price data cached to {parquet_file} with metadata in {metadata_file}")
    return raw_data


def slice_period(
    df: pd.DataFrame,
    name: str,
    cfg: Config,
) -> pd.DataFrame:
    """Extract a strictly bounded chronological slice of data for train, validation, or test.

    Enforces that test period data remains strictly inaccessible unless `cfg.dates.unlock_test`
    is explicitly set to True.

    Parameters
    ----------
    df : pd.DataFrame
        Price or return panel indexed by DatetimeIndex.
    name : str
        Period identifier: 'train', 'validation', or 'test'.
    cfg : Config
        Validated configuration dataclass.

    Returns
    -------
    pd.DataFrame
        Sliced subset of the DataFrame.

    Raises
    ------
    PermissionError
        If 'test' period is requested while `cfg.dates.unlock_test` is False.
    ValueError
        If an unrecognized period name is passed or index is not DatetimeIndex.
    """
    valid_names = {"train", "validation", "test"}
    if name not in valid_names:
        raise ValueError(f"Unknown period name: '{name}'. Must be one of {valid_names}.")

    if name == "test" and not cfg.dates.unlock_test:
        raise PermissionError(
            "Access to the out-of-sample 'test' period is strictly locked until the Day 10 freeze. "
            "Set `cfg.dates.unlock_test = True` only after all model decisions have been frozen."
        )

    if name == "train":
        start_str = cfg.dates.train_start
        end_str = cfg.dates.train_end
    elif name == "validation":
        start_str = cfg.dates.validation_start
        end_str = cfg.dates.validation_end
    else:  # test
        start_str = cfg.dates.test_start
        end_str = cfg.dates.test_end

    start_dt = pd.to_datetime(start_str)
    end_dt = pd.to_datetime(end_str)

    if not isinstance(df.index, pd.DatetimeIndex):
        # Attempt conversion
        df_copy = df.copy()
        df_copy.index = pd.to_datetime(df_copy.index)
        sliced = df_copy.loc[(df_copy.index >= start_dt) & (df_copy.index <= end_dt)]
        return sliced

    return df.loc[(df.index >= start_dt) & (df.index <= end_dt)].copy()
