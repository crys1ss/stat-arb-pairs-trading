"""Configuration management and typed validation for the pairs-trading pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass(frozen=True)
class UniverseConfig:
    banks: List[str]
    energy: List[str]
    staples: List[str]

    @property
    def all_tickers(self) -> List[str]:
        """Return a sorted, unique list of all tickers in the universe."""
        return sorted(list(set(self.banks + self.energy + self.staples)))

    @property
    def sector_map(self) -> Dict[str, str]:
        """Mapping from ticker symbol to sector name."""
        mapping: Dict[str, str] = {}
        for ticker in self.banks:
            mapping[ticker] = "banks"
        for ticker in self.energy:
            mapping[ticker] = "energy"
        for ticker in self.staples:
            mapping[ticker] = "staples"
        return mapping


@dataclass(frozen=True)
class DatesConfig:
    download_start: str
    download_end: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    test_start: str
    test_end: str
    unlock_test: bool = False

    def validate(self) -> None:
        """Validate chronological ordering and non-overlapping period boundaries."""
        d_start = date.fromisoformat(self.download_start)
        d_end = date.fromisoformat(self.download_end)
        tr_start = date.fromisoformat(self.train_start)
        tr_end = date.fromisoformat(self.train_end)
        va_start = date.fromisoformat(self.validation_start)
        va_end = date.fromisoformat(self.validation_end)
        te_start = date.fromisoformat(self.test_start)
        te_end = date.fromisoformat(self.test_end)

        if tr_start > tr_end:
            raise ValueError(f"train_start ({tr_start}) cannot be after train_end ({tr_end})")
        if va_start > va_end:
            raise ValueError(f"validation_start ({va_start}) cannot be after validation_end ({va_end})")
        if te_start > te_end:
            raise ValueError(f"test_start ({te_start}) cannot be after test_end ({te_end})")

        # Strict chronological ordering and non-overlap
        if tr_end >= va_start:
            raise ValueError(
                f"Training and validation periods must not overlap: train_end ({tr_end}) >= validation_start ({va_start})"
            )
        if va_end >= te_start:
            raise ValueError(
                f"Validation and test periods must not overlap: validation_end ({va_end}) >= test_start ({te_start})"
            )

        # Bounds within download window
        if d_start > tr_start or d_end < te_end:
            raise ValueError(
                f"Download range ({d_start} to {d_end}) must cover full period ({tr_start} to {te_end})"
            )


@dataclass(frozen=True)
class ScreeningConfig:
    within_sector_only: bool
    trend: str
    bidirectional_max_pvalue: bool
    alpha: float
    min_half_life_days: float
    max_half_life_days: float
    dependent_leg_policy: str

    def validate(self) -> None:
        if self.alpha <= 0.0 or self.alpha >= 1.0:
            raise ValueError(f"Significance level alpha must be in (0, 1), got {self.alpha}")
        if self.min_half_life_days <= 0.0:
            raise ValueError(f"min_half_life_days must be positive, got {self.min_half_life_days}")
        if self.min_half_life_days >= self.max_half_life_days:
            raise ValueError(
                f"min_half_life_days ({self.min_half_life_days}) must be strictly less than "
                f"max_half_life_days ({self.max_half_life_days})"
            )


@dataclass(frozen=True)
class SignalsConfig:
    entry_z: float
    exit_z: float
    max_hold_days: int
    stop_z: Optional[float] = None
    z_score_baseline: str = "training_fixed"
    cooldown_days: int = 0

    def validate(self) -> None:
        if self.entry_z <= 0.0:
            raise ValueError(f"entry_z must be positive, got {self.entry_z}")
        if self.exit_z < 0.0:
            raise ValueError(f"exit_z must be non-negative, got {self.exit_z}")
        if self.exit_z >= self.entry_z:
            raise ValueError(
                f"exit_z ({self.exit_z}) must be strictly less than entry_z ({self.entry_z})"
            )
        if self.max_hold_days <= 0:
            raise ValueError(f"max_hold_days must be positive, got {self.max_hold_days}")
        if self.cooldown_days < 0:
            raise ValueError(
                f"cooldown_days must be non-negative, got {self.cooldown_days}"
            )
        if self.stop_z is not None and self.stop_z <= self.entry_z:
            raise ValueError(
                f"stop_z ({self.stop_z}) must be strictly greater than entry_z ({self.entry_z})"
            )


@dataclass(frozen=True)
class ExecutionConfig:
    execution_lag: int
    commission_bps: float
    slippage_bps: float
    borrow_bps_annual: float

    def validate(self) -> None:
        if self.execution_lag < 1:
            raise ValueError(f"execution_lag must be >= 1 to prevent look-ahead bias, got {self.execution_lag}")
        if self.commission_bps < 0.0 or self.slippage_bps < 0.0 or self.borrow_bps_annual < 0.0:
            raise ValueError("Cost parameters cannot be negative")


@dataclass(frozen=True)
class CapitalConfig:
    initial_capital: float
    risk_free_rate: float
    annualization: int

    def validate(self) -> None:
        if self.initial_capital <= 0.0:
            raise ValueError(f"initial_capital must be positive, got {self.initial_capital}")
        if self.annualization <= 0:
            raise ValueError(f"annualization days must be positive, got {self.annualization}")


@dataclass(frozen=True)
class Config:
    universe: UniverseConfig
    dates: DatesConfig
    screening: ScreeningConfig
    signals: SignalsConfig
    execution: ExecutionConfig
    capital: CapitalConfig
    seed: int

    def validate(self) -> None:
        """Run validation across all configuration sub-domains."""
        self.dates.validate()
        self.screening.validate()
        self.signals.validate()
        self.execution.validate()
        self.capital.validate()


def load_config(config_path: str | Path = "configs/baseline.yaml") -> Config:
    """Load, parse, and validate YAML configuration file into a typed Config dataclass."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path.resolve()}")

    with open(path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f)

    cfg = Config(
        universe=UniverseConfig(**data["universe"]),
        dates=DatesConfig(**data["dates"]),
        screening=ScreeningConfig(**data["screening"]),
        signals=SignalsConfig(**data["signals"]),
        execution=ExecutionConfig(**data["execution"]),
        capital=CapitalConfig(**data["capital"]),
        seed=int(data.get("seed", 42)),
    )
    cfg.validate()
    return cfg


if __name__ == "__main__":
    # Smoke-test CLI execution
    import pprint
    cfg = load_config()
    print("Configuration loaded and validated successfully:")
    pprint.pprint(cfg)
