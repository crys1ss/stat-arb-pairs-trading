"""Unit tests for data validation, clean panel construction, and period slicing using deterministic fixtures."""

import numpy as np
import pandas as pd
import pytest

from src.config import Config, DatesConfig, UniverseConfig, ScreeningConfig, SignalsConfig, ExecutionConfig, CapitalConfig
from src.data import slice_period
from src.validation import (
    build_clean_panel,
    check_abnormal_returns,
    check_calendar_alignment,
    check_duplicate_dates,
    check_missing_values,
    check_monotonic_index,
    check_non_positive_prices,
)


@pytest.fixture
def mock_config() -> Config:
    return Config(
        universe=UniverseConfig(banks=["JPM", "BAC"], energy=["XOM", "CVX"], staples=["KO", "PEP"]),
        dates=DatesConfig(
            download_start="2020-01-01",
            download_end="2024-12-31",
            train_start="2020-01-01",
            train_end="2021-12-31",
            validation_start="2022-01-01",
            validation_end="2022-12-31",
            test_start="2023-01-01",
            test_end="2024-12-31",
            unlock_test=False,
        ),
        screening=ScreeningConfig(
            within_sector_only=True,
            trend="c",
            bidirectional_max_pvalue=True,
            alpha=0.05,
            min_half_life_days=1.0,
            max_half_life_days=60.0,
            dependent_leg_policy="alphabetical_first",
        ),
        signals=SignalsConfig(entry_z=2.0, exit_z=0.5, max_hold_days=30),
        execution=ExecutionConfig(
            execution_lag=1,
            commission_bps=5.0,
            slippage_bps=5.0,
            borrow_bps_annual=50.0,
        ),
        capital=CapitalConfig(initial_capital=1000000.0, risk_free_rate=0.0, annualization=252),
        seed=42,
    )


def test_duplicate_date_detection():
    dates = pd.to_datetime(["2021-01-04", "2021-01-05", "2021-01-05", "2021-01-06"])
    df = pd.DataFrame({"A": [10.0, 11.0, 11.5, 12.0]}, index=dates)

    dups = check_duplicate_dates(df)
    assert len(dups) == 1
    assert dups[0] == pd.Timestamp("2021-01-05")
    assert check_monotonic_index(df) is False


def test_nans_not_forward_filled():
    dates = pd.date_range("2021-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "A": [100.0, np.nan, np.nan, 105.0, 106.0],
            "B": [50.0, 51.0, 52.0, 53.0, np.nan],
        },
        index=dates,
    )

    clean_panel, missing_log = build_clean_panel(df)

    # Invariant: NaNs MUST be preserved, never forward filled or manufactured
    assert pd.isna(clean_panel.loc["2021-01-02", "A"])
    assert pd.isna(clean_panel.loc["2021-01-03", "A"])
    assert clean_panel.loc["2021-01-04", "A"] == 105.0
    assert pd.isna(clean_panel.loc["2021-01-05", "B"])

    assert len(missing_log) == 3
    assert set(missing_log["ticker"]) == {"A", "B"}


def test_abnormal_return_flagging():
    dates = pd.date_range("2021-01-01", periods=4, freq="D")
    # A has standard 2% move then 35% jump
    df = pd.DataFrame(
        {
            "A": [100.0, 102.0, 145.0, 146.0],
            "B": [50.0, 51.0, 50.5, 51.0],
        },
        index=dates,
    )

    flagged = check_abnormal_returns(df, threshold=0.25)
    assert len(flagged) == 1
    assert flagged.iloc[0]["ticker"] == "A"
    assert flagged.iloc[0]["price_prev"] == 102.0
    assert flagged.iloc[0]["price_curr"] == 145.0
    assert flagged.iloc[0]["log_return"] > 0.25

    # Invariant: underlying data is untouched
    assert df.loc["2021-01-03", "A"] == 145.0


def test_calendar_alignment():
    dates = pd.date_range("2021-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "A": [10.0, 11.0, 12.0, 13.0],
            "B": [20.0, np.nan, 22.0, 23.0],
        },
        index=dates,
    )

    align_df = check_calendar_alignment(df)
    row_a = align_df[align_df["ticker"] == "A"].iloc[0]
    row_b = align_df[align_df["ticker"] == "B"].iloc[0]

    assert row_a["union_trading_days"] == 4
    assert row_a["days_present"] == 4
    assert row_a["days_missing"] == 0

    assert row_b["union_trading_days"] == 4
    assert row_b["days_present"] == 3
    assert row_b["days_missing"] == 1


def test_non_positive_prices():
    dates = pd.date_range("2021-01-01", periods=3, freq="D")
    df = pd.DataFrame({"A": [10.0, 0.0, 12.0], "B": [20.0, -1.5, 22.0]}, index=dates)
    counts = check_non_positive_prices(df)
    assert counts["A"] == 1
    assert counts["B"] == 1


def test_slice_period_refuses_test_when_locked(mock_config: Config):
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    df = pd.DataFrame({"A": np.arange(len(dates))}, index=dates)

    assert mock_config.dates.unlock_test is False
    with pytest.raises(PermissionError, match="strictly locked"):
        slice_period(df, "test", mock_config)


def test_slice_period_train_and_validation(mock_config: Config):
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    df = pd.DataFrame({"A": np.arange(len(dates))}, index=dates)

    train_slice = slice_period(df, "train", mock_config)
    assert train_slice.index.min() >= pd.Timestamp("2020-01-01")
    assert train_slice.index.max() <= pd.Timestamp("2021-12-31")

    val_slice = slice_period(df, "validation", mock_config)
    assert val_slice.index.min() >= pd.Timestamp("2022-01-01")
    assert val_slice.index.max() <= pd.Timestamp("2022-12-31")


def test_slice_period_allows_test_when_unlocked(mock_config: Config):
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    df = pd.DataFrame({"A": np.arange(len(dates))}, index=dates)

    # Dynamically unlock test for this test
    unlocked_dates = DatesConfig(
        download_start=mock_config.dates.download_start,
        download_end=mock_config.dates.download_end,
        train_start=mock_config.dates.train_start,
        train_end=mock_config.dates.train_end,
        validation_start=mock_config.dates.validation_start,
        validation_end=mock_config.dates.validation_end,
        test_start=mock_config.dates.test_start,
        test_end=mock_config.dates.test_end,
        unlock_test=True,
    )
    unlocked_cfg = Config(
        universe=mock_config.universe,
        dates=unlocked_dates,
        screening=mock_config.screening,
        signals=mock_config.signals,
        execution=mock_config.execution,
        capital=mock_config.capital,
        seed=mock_config.seed,
    )

    test_slice = slice_period(df, "test", unlocked_cfg)
    assert test_slice.index.min() >= pd.Timestamp("2023-01-01")
    assert test_slice.index.max() <= pd.Timestamp("2024-12-31")
