"""Visualization and publication-ready charting module using Matplotlib."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Union

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_normalized_prices_by_sector(
    df: pd.DataFrame,
    sector_map: Dict[str, str],
    out_path: Union[str, Path],
) -> Path:
    """Plot normalized price series (base = 100 at start of period) partitioned by sector.

    Parameters
    ----------
    df : pd.DataFrame
        Price panel indexed by DatetimeIndex.
    sector_map : Dict[str, str]
        Mapping from ticker symbol to sector name.
    out_path : Union[str, Path]
        Output path for the generated figure PNG.

    Returns
    -------
    Path
        Resolved destination path of saved figure.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    sectors = ["banks", "energy", "staples"]
    fig, axes = plt.subplots(len(sectors), 1, figsize=(12, 10), sharex=True)

    for ax, sector in zip(axes, sectors):
        sector_tickers = [t for t in df.columns if sector_map.get(t) == sector]
        for ticker in sector_tickers:
            series = df[ticker].dropna()
            if not series.empty:
                normalized = (series / series.iloc[0]) * 100.0
                ax.plot(normalized.index, normalized.values, label=ticker, linewidth=1.2)

        ax.set_title(f"Sector: {sector.capitalize()} (Base = 100)", fontsize=11, fontweight="bold")
        ax.set_ylabel("Normalized Price", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", ncol=6, fontsize=8, framealpha=0.8)

    axes[-1].set_xlabel("Date", fontsize=10)
    fig.suptitle("Normalized Adjusted Prices by Sector (Training Period 2018–2021)", fontsize=13, fontweight="bold", y=0.99)
    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_log_prices_by_sector(
    df: pd.DataFrame,
    sector_map: Dict[str, str],
    out_path: Union[str, Path],
) -> Path:
    """Plot natural log prices partitioned by sector.

    Parameters
    ----------
    df : pd.DataFrame
        Price panel indexed by DatetimeIndex.
    sector_map : Dict[str, str]
        Mapping from ticker symbol to sector name.
    out_path : Union[str, Path]
        Output path for the generated figure PNG.

    Returns
    -------
    Path
        Resolved destination path of saved figure.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    sectors = ["banks", "energy", "staples"]
    fig, axes = plt.subplots(len(sectors), 1, figsize=(12, 10), sharex=True)

    for ax, sector in zip(axes, sectors):
        sector_tickers = [t for t in df.columns if sector_map.get(t) == sector]
        for ticker in sector_tickers:
            series = df[ticker].dropna()
            if not series.empty:
                log_price = np.log(series)
                ax.plot(log_price.index, log_price.values, label=ticker, linewidth=1.2)

        ax.set_title(f"Sector: {sector.capitalize()} (Log Prices)", fontsize=11, fontweight="bold")
        ax.set_ylabel("ln(Price)", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", ncol=6, fontsize=8, framealpha=0.8)

    axes[-1].set_xlabel("Date", fontsize=10)
    fig.suptitle("Log Price Trajectories by Sector (Training Period 2018–2021)", fontsize=13, fontweight="bold", y=0.99)
    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_correlation_heatmap(
    corr_matrix: pd.DataFrame,
    out_path: Union[str, Path],
    caption: Optional[str] = (
        "Note: Correlation is not cointegration. Highly correlated pairs may drift apart permanently,\n"
        "while cointegration requires a stationary spread (mean-reverting equilibrium)."
    ),
) -> Path:
    """Generate and save a publication-quality correlation heatmap for daily returns.

    Parameters
    ----------
    corr_matrix : pd.DataFrame
        Pairwise correlation matrix.
    out_path : Union[str, Path]
        Output path for the generated figure PNG.
    caption : Optional[str]
        Explanatory footnote regarding correlation vs. cointegration.

    Returns
    -------
    Path
        Resolved destination path of saved figure.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11, 9))
    cax = ax.imshow(corr_matrix.values, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    cbar = fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Pearson Correlation", fontsize=9)

    tickers = list(corr_matrix.columns)
    ax.set_xticks(np.arange(len(tickers)))
    ax.set_yticks(np.arange(len(tickers)))
    ax.set_xticklabels(tickers, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(tickers, fontsize=8)

    # Annotate numeric values for readability
    for i in range(len(tickers)):
        for j in range(len(tickers)):
            val = corr_matrix.iloc[i, j]
            color = "white" if abs(val) > 0.55 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=6.5)

    ax.set_title("Daily Return Correlation Matrix (Training Period 2018–2021)", fontsize=12, fontweight="bold", pad=12)

    if caption:
        fig.text(0.5, 0.01, caption, ha="center", fontsize=8, fontstyle="italic", color="#333333")

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_pair_prices(
    prices: pd.DataFrame,
    leg_a: str,
    leg_b: str,
    split_date: Union[str, pd.Timestamp],
    out_path: Union[str, Path],
) -> Path:
    """Plot adjusted and log prices for a specific pair with shaded period boundaries.

    Parameters
    ----------
    prices : pd.DataFrame
        Price DataFrame containing leg_a and leg_b.
    leg_a : str
        Ticker symbol for leg A.
    leg_b : str
        Ticker symbol for leg B.
    split_date : Union[str, pd.Timestamp]
        Boundary between training and validation periods.
    out_path : Union[str, Path]
        Path to save output PNG.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    split_dt = pd.Timestamp(split_date)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)

    # Subplot 1: Adjusted prices
    ax1.plot(prices.index, prices[leg_a], label=f"{leg_a} (Adj Close)", color="#1f77b4", linewidth=1.2)
    ax1.plot(prices.index, prices[leg_b], label=f"{leg_b} (Adj Close)", color="#ff7f0e", linewidth=1.2)
    ax1.set_title(f"Adjusted Prices: {leg_a} vs. {leg_b}", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Price ($)", fontsize=9)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Subplot 2: Log prices
    ax2.plot(prices.index, np.log(prices[leg_a]), label=f"ln({leg_a})", color="#1f77b4", linewidth=1.2)
    ax2.plot(prices.index, np.log(prices[leg_b]), label=f"ln({leg_b})", color="#ff7f0e", linewidth=1.2)
    ax2.set_title(f"Log Prices: ln({leg_a}) vs. ln({leg_b})", fontsize=11, fontweight="bold")
    ax2.set_ylabel("ln(Price)", fontsize=9)
    ax2.set_xlabel("Date", fontsize=10)
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, linestyle="--", alpha=0.5)

    # Shade training vs validation periods
    for ax in (ax1, ax2):
        ax.axvspan(prices.index.min(), split_dt, color="#2ca02c", alpha=0.08, label="Train Period" if ax == ax1 else "")
        ax.axvspan(split_dt, prices.index.max(), color="#d62728", alpha=0.08, label="Validation Period" if ax == ax1 else "")
        ax.axvline(split_dt, color="#333333", linestyle=":", linewidth=1.0)

    fig.suptitle(f"Price Dynamics: {leg_a} / {leg_b} (Train 2018–2021 | Validation 2022)", fontsize=12, fontweight="bold", y=0.99)
    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_pair_spread(
    spread: pd.Series,
    mu_train: float,
    sd_train: float,
    entry_z: float,
    exit_z: float,
    split_date: Union[str, pd.Timestamp],
    out_path: Union[str, Path],
    pair_name: str = "Pair Spread",
) -> Path:
    """Plot spread trajectory with frozen training mean, entry bands, and exit bands with shaded periods.

    Parameters
    ----------
    spread : pd.Series
        Constructed spread series across train and validation.
    mu_train : float
        Frozen training-period spread mean.
    sd_train : float
        Frozen training-period spread standard deviation.
    entry_z : float
        Entry threshold in standard deviations (e.g. 2.0).
    exit_z : float
        Exit threshold in standard deviations (e.g. 0.5).
    split_date : Union[str, pd.Timestamp]
        Boundary between training and validation periods.
    out_path : Union[str, Path]
        Path to save output PNG.
    pair_name : str
        Display title for the pair.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    split_dt = pd.Timestamp(split_date)

    fig, ax = plt.subplots(figsize=(12, 5.5))

    # Plot spread
    ax.plot(spread.index, spread.values, color="#1f77b4", linewidth=1.2, label="Spread $s_t$")

    # Mean line
    ax.axhline(mu_train, color="#333333", linestyle="-", linewidth=1.2, label=f"Train Mean ({mu_train:.4f})")

    # Entry bands
    ax.axhline(mu_train + entry_z * sd_train, color="#d62728", linestyle="--", linewidth=1.0, label=f"+{entry_z}σ Entry")
    ax.axhline(mu_train - entry_z * sd_train, color="#2ca02c", linestyle="--", linewidth=1.0, label=f"-{entry_z}σ Entry")

    # Exit bands
    ax.axhline(mu_train + exit_z * sd_train, color="#ff7f0e", linestyle=":", linewidth=1.0, label=f"+{exit_z}σ Exit")
    ax.axhline(mu_train - exit_z * sd_train, color="#ff7f0e", linestyle=":", linewidth=1.0, label=f"-{exit_z}σ Exit")

    # Shaded periods
    ax.axvspan(spread.index.min(), split_dt, color="#2ca02c", alpha=0.07, label="Train (2018–2021)")
    ax.axvspan(split_dt, spread.index.max(), color="#d62728", alpha=0.07, label="Validation (2022)")
    ax.axvline(split_dt, color="#333333", linestyle=":", linewidth=1.2)

    ax.set_title(f"{pair_name}: Spread Trajectory and Frozen Calibration Bands", fontsize=11, fontweight="bold")
    ax.set_ylabel(r"Spread $s_t = \ln(P_A) - \hat{\alpha} - \hat{\beta}\ln(P_B)$", fontsize=9)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", ncol=4, fontsize=8, framealpha=0.85)

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_rolling_betas(
    rolling_beta_df: pd.DataFrame,
    frozen_betas: Dict[str, float],
    split_date: Union[str, pd.Timestamp],
    out_path: Union[str, Path],
) -> Path:
    """Plot rolling 252-day OLS hedge ratio betas against frozen baseline betas across train and validation.

    Parameters
    ----------
    rolling_beta_df : pd.DataFrame
        DataFrame where columns are pair names and values are 252-day rolling betas.
    frozen_betas : Dict[str, float]
        Dictionary mapping pair name to frozen training-period beta.
    split_date : Union[str, pd.Timestamp]
        Train/validation split date.
    out_path : Union[str, Path]
        Path to save output PNG.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    split_dt = pd.Timestamp(split_date)

    pairs = list(rolling_beta_df.columns)
    fig, axes = plt.subplots(len(pairs), 1, figsize=(12, 2.5 * len(pairs)), sharex=True)
    if len(pairs) == 1:
        axes = [axes]

    for ax, pair in zip(axes, pairs):
        series = rolling_beta_df[pair].dropna()
        frozen_b = frozen_betas.get(pair, np.nan)

        ax.plot(series.index, series.values, label=f"Rolling 252d β ({pair})", color="#1f77b4", linewidth=1.3)
        ax.axhline(frozen_b, color="#d62728", linestyle="--", linewidth=1.2, label=f"Frozen Train β ({frozen_b:.4f})")

        ax.axvspan(series.index.min(), split_dt, color="#2ca02c", alpha=0.07)
        ax.axvspan(split_dt, series.index.max(), color="#d62728", alpha=0.07)
        ax.axvline(split_dt, color="#333333", linestyle=":", linewidth=1.0)

        ax.set_title(f"Hedge Ratio Stability: {pair}", fontsize=10, fontweight="bold")
        ax.set_ylabel("β", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", fontsize=8, ncol=2)

    axes[-1].set_xlabel("Date", fontsize=10)
    fig.suptitle("Diagnostic: Rolling 252-Day OLS Hedge Ratio vs. Frozen Baseline (Train & Validation)", fontsize=12, fontweight="bold", y=0.99)
    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file
