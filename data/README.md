# Data Storage and Acquisition Guide

This directory holds local caches of equity price data acquired for the research project.

## Directory Structure
- `data/raw/`: Raw adjusted daily prices fetched via `yfinance` stored in Parquet format, accompanied by download provenance metadata (`metadata.json`). (Git-ignored).
- `data/processed/`: Aligned, validated clean price panel (`close.parquet`). (Git-ignored).

## Reproduction & Terms of Use
Data will be fetched on Day 2 via `python scripts/fetch_data.py`.
Market data is obtained from Yahoo Finance for educational and research evaluation purposes only.
