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
