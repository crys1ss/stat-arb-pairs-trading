"""Unit tests for configuration loading, typing, and validation invariants."""

import pytest
from pathlib import Path
from src.config import (
    load_config,
    Config,
    UniverseConfig,
    DatesConfig,
    ScreeningConfig,
    SignalsConfig,
    ExecutionConfig,
    CapitalConfig,
)


@pytest.fixture
def baseline_config_path() -> Path:
    # Resolve relative to repo root
    return Path(__file__).resolve().parent.parent / "configs" / "baseline.yaml"


def test_baseline_config_loads_and_validates(baseline_config_path: Path):
    cfg = load_config(baseline_config_path)
    assert isinstance(cfg, Config)
    assert len(cfg.universe.banks) == 6
    assert len(cfg.universe.energy) == 6
    assert len(cfg.universe.staples) == 6
    assert len(cfg.universe.all_tickers) == 18
    assert cfg.dates.unlock_test is False
    assert cfg.execution.execution_lag == 1
    assert cfg.signals.exit_z < cfg.signals.entry_z


def test_dates_ordering_and_non_overlap(baseline_config_path: Path):
    cfg = load_config(baseline_config_path)
    # Check that train ends before validation starts
    assert cfg.dates.train_start <= cfg.dates.train_end
    assert cfg.dates.train_end < cfg.dates.validation_start
    assert cfg.dates.validation_start <= cfg.dates.validation_end
    assert cfg.dates.validation_end < cfg.dates.test_start
    assert cfg.dates.test_start <= cfg.dates.test_end


def test_overlapping_dates_raise_error():
    # Train and validation overlap
    dates_cfg = DatesConfig(
        download_start="2018-01-01",
        download_end="2024-12-31",
        train_start="2018-01-01",
        train_end="2022-01-15",
        validation_start="2022-01-01",
        validation_end="2022-12-31",
        test_start="2023-01-01",
        test_end="2024-12-31",
    )
    with pytest.raises(ValueError, match="must not overlap"):
        dates_cfg.validate()


def test_inverted_date_order_raises_error():
    dates_cfg = DatesConfig(
        download_start="2018-01-01",
        download_end="2024-12-31",
        train_start="2021-12-31",
        train_end="2018-01-01",
        validation_start="2022-01-01",
        validation_end="2022-12-31",
        test_start="2023-01-01",
        test_end="2024-12-31",
    )
    with pytest.raises(ValueError, match="cannot be after"):
        dates_cfg.validate()


def test_threshold_validation_exit_less_than_entry():
    # Valid
    sig_cfg = SignalsConfig(entry_z=2.0, exit_z=0.5, max_hold_days=30)
    sig_cfg.validate()

    # Invalid: exit >= entry
    with pytest.raises(ValueError, match="must be strictly less than"):
        SignalsConfig(entry_z=2.0, exit_z=2.5, max_hold_days=30).validate()

    with pytest.raises(ValueError, match="must be strictly less than"):
        SignalsConfig(entry_z=2.0, exit_z=2.0, max_hold_days=30).validate()


def test_execution_lag_prevent_lookahead():
    with pytest.raises(ValueError, match="execution_lag must be >= 1"):
        ExecutionConfig(
            execution_lag=0,
            commission_bps=5.0,
            slippage_bps=5.0,
            borrow_bps_annual=50.0,
        ).validate()
