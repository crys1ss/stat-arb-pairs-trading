# Equity Price Data Acquisition and Validation Guide

This directory manages the storage, local caching, and provenance tracking of daily equity price data.

## Universe and Specifications
- **Sectors**: Banking (6 tickers), Energy (6 tickers), Consumer Staples (6 tickers).
- **Date Range**: 2018-01-01 to 2024-12-31 (download window).
- **Adjusted Prices**: Retrieved using Yahoo Finance via `yfinance` with `auto_adjust=True`. Splits and cash dividends are folded directly into the adjusted prices.
- **Missing Data Policy**: Strictly **NO forward-filling** and **NO back-filling**. Missing observations remain `NaN`. Downstream pair screening and backtesting modules drop timestamps where either leg of a pair has missing data.

## Directory Structure
- `data/raw/prices.parquet`: Raw downloaded OHLCV multi-ticker panel from Yahoo Finance (git-ignored).
- `data/raw/metadata.json`: Download provenance metadata (UTC retrieval timestamp, library versions, tickers, date range, observation counts).
- `data/processed/close.parquet`: Clean adjusted close price panel aligned across the union trading calendar (git-ignored).

## How to Acquire and Refresh Data
To download and validate the dataset using the configuration settings:
```bash
python scripts/fetch_data.py
```

To force a refresh from Yahoo Finance, bypassing the local parquet cache:
```bash
python scripts/fetch_data.py --refresh
```

## Data Source & Terms of Use
Market data is obtained from Yahoo Finance for non-commercial, personal academic research and educational evaluation purposes only. No proprietary or commercial redistribution is implied. Users must comply with Yahoo Finance Terms of Service.
