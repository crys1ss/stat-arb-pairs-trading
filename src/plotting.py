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


def plot_signals_with_markers(
    z_series: pd.Series,
    signals_df: pd.DataFrame,
    entry_z: float,
    exit_z: float,
    split_date: Union[str, pd.Timestamp],
    out_path: Union[str, Path],
    pair_name: str = "Pair",
) -> Path:
    """Plot spread z-score trajectory with explicit entry and exit trade markers.

    Parameters
    ----------
    z_series : pd.Series
        Normalized z-score series.
    signals_df : pd.DataFrame
        Signals DataFrame containing 'entry_flag', 'exit_flag', 'state', and 'exit_reason'.
    entry_z : float
        Statistical divergence entry threshold (e.g. 2.0).
    exit_z : float
        Mean-reversion exit threshold (e.g. 0.5).
    split_date : Union[str, pd.Timestamp]
        Train/validation boundary date.
    out_path : Union[str, Path]
        Destination PNG path.
    pair_name : str
        Display title for the pair.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    split_dt = pd.Timestamp(split_date)

    fig, ax = plt.subplots(figsize=(12, 5.5))

    # Plot z-score curve
    ax.plot(z_series.index, z_series.values, color="#1f77b4", linewidth=1.1, label="Z-Score $z_t$")

    # Threshold horizontal reference lines
    ax.axhline(0.0, color="#333333", linestyle="-", linewidth=0.8, alpha=0.7)
    ax.axhline(entry_z, color="#d62728", linestyle="--", linewidth=1.0, label=f"+{entry_z}σ Short Entry")
    ax.axhline(-entry_z, color="#2ca02c", linestyle="--", linewidth=1.0, label=f"-{entry_z}σ Long Entry")
    ax.axhline(exit_z, color="#ff7f0e", linestyle=":", linewidth=1.0, label=f"±{exit_z}σ Exit Bands")
    ax.axhline(-exit_z, color="#ff7f0e", linestyle=":", linewidth=1.0)

    # Shaded periods
    ax.axvspan(z_series.index.min(), split_dt, color="#2ca02c", alpha=0.07, label="Train (2018–2021)")
    ax.axvspan(split_dt, z_series.index.max(), color="#d62728", alpha=0.07, label="Validation (2022)")
    ax.axvline(split_dt, color="#333333", linestyle=":", linewidth=1.2)

    # Entry markers
    long_entries = signals_df[(signals_df["entry_flag"]) & (signals_df["state"] == 1)]
    short_entries = signals_df[(signals_df["entry_flag"]) & (signals_df["state"] == -1)]
    exits = signals_df[signals_df["exit_flag"]]

    if not long_entries.empty:
        ax.scatter(
            long_entries.index,
            z_series.loc[long_entries.index],
            color="#2ca02c",
            marker="^",
            s=80,
            zorder=5,
            label=f"Long Spread Entry (n={len(long_entries)})",
        )

    if not short_entries.empty:
        ax.scatter(
            short_entries.index,
            z_series.loc[short_entries.index],
            color="#d62728",
            marker="v",
            s=80,
            zorder=5,
            label=f"Short Spread Entry (n={len(short_entries)})",
        )

    if not exits.empty:
        ax.scatter(
            exits.index,
            z_series.loc[exits.index],
            color="#333333",
            marker="x",
            s=70,
            linewidth=1.8,
            zorder=5,
            label=f"Exit Signal (n={len(exits)})",
        )

    ax.set_title(f"{pair_name}: Z-Score Signal State Machine (Train & Validation)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Normalized Spread Z-Score", fontsize=9)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", ncol=3, fontsize=8, framealpha=0.85)

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_gross_vs_net_equity(
    daily_df: pd.DataFrame,
    initial_capital: float,
    out_path: Union[str, Path],
    title: str = "Portfolio Equity Curve: Gross vs. Net of Friction",
) -> Path:
    """Plot cumulative gross equity curve alongside net equity curve with shaded cost wedge.

    Parameters
    ----------
    daily_df : pd.DataFrame
        Daily portfolio DataFrame containing 'equity' and 'gross_pnl'.
    initial_capital : float
        Starting equity base.
    out_path : Union[str, Path]
        Output path for the generated PNG.
    title : str
        Figure title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    dates = pd.to_datetime(daily_df.index)
    net_eq = daily_df["equity"].values
    gross_eq = (initial_capital + daily_df["gross_pnl"].cumsum()).values

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(dates, gross_eq / 1000.0, label="Gross Equity (Zero Friction)", color="#1f77b4", linewidth=1.5)
    ax.plot(dates, net_eq / 1000.0, label="Net Equity (After Commissions, Slippage & Borrow)", color="#2ca02c", linewidth=1.6)

    # Shade the friction wedge between gross and net
    ax.fill_between(dates, net_eq / 1000.0, gross_eq / 1000.0, color="#d62728", alpha=0.15, label="Cumulative Transaction & Borrow Costs")

    # Baseline capital horizontal line
    ax.axhline(initial_capital / 1000.0, color="#666666", linestyle="--", linewidth=1.0, alpha=0.8, label=f"Initial Capital (${initial_capital:,.0f})")

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("Portfolio Equity ($k)", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_drawdown(
    equity_series: pd.Series,
    out_path: Union[str, Path],
    title: str = "Portfolio Underwater Drawdown Curve",
) -> Path:
    """Plot underwater drawdown curve with shaded area.

    Parameters
    ----------
    equity_series : pd.Series
        Equity curve time series.
    out_path : Union[str, Path]
        Output path for PNG.
    title : str
        Figure title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    dates = pd.to_datetime(equity_series.index)
    peak = equity_series.cummax()
    dd = ((equity_series - peak) / peak) * 100.0  # percentage

    max_dd = abs(float(dd.min()))

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(dates, dd.values, color="#d62728", linewidth=1.2, label=f"Drawdown (Max: -{max_dd:.2f}%)")
    ax.fill_between(dates, dd.values, 0.0, color="#d62728", alpha=0.25)
    ax.axhline(0.0, color="#333333", linestyle="-", linewidth=0.8)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("Underwater Drawdown (%)", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.9)

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_per_pair_pnl(
    per_pair_df: pd.DataFrame,
    out_path: Union[str, Path],
    title: str = "Per-Pair Net P&L Contribution",
) -> Path:
    """Generate bar chart of per-pair net P&L with positive/negative color formatting.

    Parameters
    ----------
    per_pair_df : pd.DataFrame
        Table containing 'pair' and 'net_pnl' columns.
    out_path : Union[str, Path]
        Output path for PNG.
    title : str
        Figure title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))

    pairs = per_pair_df["pair"].tolist()
    pnls = per_pair_df["net_pnl"].tolist()
    colors = ["#2ca02c" if p >= 0 else "#d62728" for p in pnls]

    bars = ax.bar(pairs, pnls, color=colors, width=0.55, edgecolor="#333333", linewidth=0.8)

    # Value annotations on bars
    for bar, val in zip(bars, pnls):
        y_pos = bar.get_height()
        offset = max(abs(val) * 0.03, 1000.0)
        va = "bottom" if val >= 0 else "top"
        text_y = y_pos + offset if val >= 0 else y_pos - offset
        ax.text(bar.get_x() + bar.get_width() / 2.0, text_y, f"${val:,.0f}", ha="center", va=va, fontsize=8.5, fontweight="bold")

    ax.axhline(0.0, color="#333333", linestyle="-", linewidth=1.0)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Net P&L ($)", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_trade_distributions(
    trades_df: pd.DataFrame,
    out_path: Union[str, Path],
    title: str = "Distribution of Trade Returns and Holding Periods",
) -> Path:
    """Plot dual histograms showing trade return distribution and holding period duration.

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade log containing 'return_on_capital' and 'holding_days'.
    out_path : Union[str, Path]
        Output path for PNG.
    title : str
        Figure title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    if not trades_df.empty:
        rets = trades_df["return_on_capital"] * 100.0  # Percentage return on pair capital
        holds = trades_df["holding_days"]

        # 1. Trade returns histogram
        n_bins_ret = min(15, max(5, len(rets) // 2))
        ax1.hist(rets, bins=n_bins_ret, color="#1f77b4", edgecolor="#333333", alpha=0.75)
        ax1.axvline(0.0, color="#d62728", linestyle="--", linewidth=1.2, label="Zero P&L")
        mean_ret = rets.mean()
        ax1.axvline(mean_ret, color="#2ca02c", linestyle="-", linewidth=1.2, label=f"Mean ({mean_ret:+.2f}%)")
        ax1.set_title("Trade Return Distribution (% on Pair Capital)", fontsize=10, fontweight="bold")
        ax1.set_xlabel("Trade Return (%)", fontsize=9)
        ax1.set_ylabel("Frequency", fontsize=9)
        ax1.legend(loc="upper left", fontsize=8)
        ax1.grid(True, linestyle="--", alpha=0.5)

        # 2. Holding period histogram
        n_bins_hold = min(15, max(5, int(holds.max() - holds.min() + 1)))
        ax2.hist(holds, bins=n_bins_hold, color="#ff7f0e", edgecolor="#333333", alpha=0.75)
        mean_hold = holds.mean()
        ax2.axvline(mean_hold, color="#333333", linestyle="-", linewidth=1.2, label=f"Mean ({mean_hold:.1f} days)")
        ax2.set_title("Holding Period Distribution (Trading Days)", fontsize=10, fontweight="bold")
        ax2.set_xlabel("Holding Period (Days)", fontsize=9)
        ax2.set_ylabel("Frequency", fontsize=9)
        ax2.legend(loc="upper right", fontsize=8)
        ax2.grid(True, linestyle="--", alpha=0.5)
    else:
        ax1.text(0.5, 0.5, "No Trades", ha="center", va="center")
        ax2.text(0.5, 0.5, "No Trades", ha="center", va="center")

    fig.suptitle(title, fontsize=12, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def compute_chained_equity(
    train_daily_df: pd.DataFrame,
    val_daily_df: pd.DataFrame,
    test_daily_df: Optional[pd.DataFrame] = None,
    initial_capital: float = 1000000.0,
    method: str = "compounded",
) -> pd.Series:
    """Compute continuous chained net equity series across train, validation, and test periods.

    Chaining Methodology
    --------------------
    1. 'compounded' (Default / Standard):
       Concatenates the daily net percentage returns r_t = net_pnl_t / equity_{t-1} across
       train, validation, and test periods, compounding continuously from initial capital C_0:
           Equity_t = C_0 * prod_{tau=1}^t (1 + r_tau)
       This ensures seamless multi-period returns matching portfolio reinvestment dynamics.
    2. 'additive':
       Concatenates daily net P&L across all periods and accumulates from initial capital:
           Equity_t = C_0 + sum_{tau=1}^t net_pnl_tau
       This represents a fixed nominal dollar allocation convention ($200k/pair per period).

    Parameters
    ----------
    train_daily_df : pd.DataFrame
        Daily metrics for train period containing 'return', 'net_pnl', 'equity'.
    val_daily_df : pd.DataFrame
        Daily metrics for validation period.
    test_daily_df : Optional[pd.DataFrame]
        Daily metrics for test period (if evaluated).
    initial_capital : float
        Starting portfolio capital base.
    method : str
        'compounded' or 'additive'.

    Returns
    -------
    pd.Series
        Chained net equity series indexed by DatetimeIndex.
    """
    dfs = [train_daily_df, val_daily_df]
    if test_daily_df is not None and not test_daily_df.empty:
        dfs.append(test_daily_df)

    if method == "compounded":
        all_rets = pd.concat([df["return"] for df in dfs])
        all_rets.index = pd.to_datetime(all_rets.index)
        all_rets = all_rets.sort_index()
        chained = initial_capital * (1.0 + all_rets).cumprod()
    elif method == "additive":
        all_pnl = pd.concat([df["net_pnl"] for df in dfs])
        all_pnl.index = pd.to_datetime(all_pnl.index)
        all_pnl = all_pnl.sort_index()
        chained = initial_capital + all_pnl.cumsum()
    else:
        raise ValueError(f"Unknown chaining method: {method}. Choose 'compounded' or 'additive'.")

    chained.name = "chained_equity"
    return chained


def plot_chained_equity(
    train_daily_df: pd.DataFrame,
    val_daily_df: pd.DataFrame,
    test_daily_df: Optional[pd.DataFrame],
    out_path: Union[str, Path],
    initial_capital: float = 1000000.0,
    chaining_method: str = "compounded",
    title: str = "Multi-Period Chained Portfolio Net Equity (2018–2024)",
) -> Path:
    """Plot full historical net equity curve chaining train, validation, and test periods.

    Shades each distinct evaluation period and includes formal documentation of the chaining
    methodology directly on the chart and in the metadata.

    Parameters
    ----------
    train_daily_df : pd.DataFrame
        Train period daily portfolio DataFrame.
    val_daily_df : pd.DataFrame
        Validation period daily portfolio DataFrame.
    test_daily_df : Optional[pd.DataFrame]
        Test period daily portfolio DataFrame (if available).
    out_path : Union[str, Path]
        Destination PNG path.
    initial_capital : float
        Starting capital.
    chaining_method : str
        'compounded' or 'additive'.
    title : str
        Figure title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    chained = compute_chained_equity(
        train_daily_df=train_daily_df,
        val_daily_df=val_daily_df,
        test_daily_df=test_daily_df,
        initial_capital=initial_capital,
        method=chaining_method,
    )

    t_dates = pd.to_datetime(train_daily_df.index)
    v_dates = pd.to_datetime(val_daily_df.index)
    has_test = test_daily_df is not None and not test_daily_df.empty
    if has_test:
        te_dates = pd.to_datetime(test_daily_df.index)

    fig, ax = plt.subplots(figsize=(13, 6.5))

    # Plot full chained equity
    ax.plot(chained.index, chained.values / 1000.0, color="#1f77b4", linewidth=1.6, label="Chained Net Equity", zorder=4)

    # Shaded periods
    # Train
    ax.axvspan(t_dates.min(), t_dates.max(), color="#2ca02c", alpha=0.10, label="Train Period (2018–2021)")
    # Validation
    ax.axvspan(v_dates.min(), v_dates.max(), color="#ff7f0e", alpha=0.12, label="Validation Period (2022)")
    # Test
    if has_test:
        ax.axvspan(te_dates.min(), te_dates.max(), color="#9467bd", alpha=0.12, label="Test Period (2023–2024, Out-of-Sample)")

    # Boundary dividers
    ax.axvline(t_dates.max(), color="#333333", linestyle="--", linewidth=1.1, alpha=0.8)
    if has_test:
        ax.axvline(v_dates.max(), color="#333333", linestyle="--", linewidth=1.1, alpha=0.8)

    # Initial capital baseline
    ax.axhline(initial_capital / 1000.0, color="#666666", linestyle=":", linewidth=1.0, alpha=0.8, label=f"Initial Capital (${initial_capital:,.0f})")

    # Annotate period endings
    train_end_eq = chained.loc[t_dates.max()]
    val_end_eq = chained.loc[v_dates.max()]
    ax.scatter([t_dates.max()], [train_end_eq / 1000.0], color="#2ca02c", s=40, zorder=5)
    ax.annotate(
        f"Train End: ${train_end_eq:,.0f}",
        xy=(t_dates.max(), train_end_eq / 1000.0),
        xytext=(-70, 15),
        textcoords="offset points",
        fontsize=8.5,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#2ca02c", lw=1.0),
    )

    ax.scatter([v_dates.max()], [val_end_eq / 1000.0], color="#ff7f0e", s=40, zorder=5)
    ax.annotate(
        f"Val End: ${val_end_eq:,.0f}",
        xy=(v_dates.max(), val_end_eq / 1000.0),
        xytext=(-60, -25),
        textcoords="offset points",
        fontsize=8.5,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#ff7f0e", lw=1.0),
    )

    if has_test:
        test_end_eq = chained.loc[te_dates.max()]
        ax.scatter([te_dates.max()], [test_end_eq / 1000.0], color="#9467bd", s=40, zorder=5)
        ax.annotate(
            f"Test End: ${test_end_eq:,.0f}",
            xy=(te_dates.max(), test_end_eq / 1000.0),
            xytext=(-70, 15),
            textcoords="offset points",
            fontsize=8.5,
            fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#9467bd", lw=1.0),
        )

    # Documentation box describing chaining mechanism
    doc_text = (
        "Chaining Methodology:\n"
        "• Concatenated daily net returns r_t across periods.\n"
        "• Compounded continuously: E_t = E_0 × ∏(1 + r_t).\n"
        "• Train: 1,008 days | Val: 251 days | Test: 501 days."
    )
    ax.text(
        0.02,
        0.04,
        doc_text,
        transform=ax.transAxes,
        fontsize=8.0,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#cccccc", alpha=0.9),
    )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Portfolio Net Equity ($k)", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_full_span_drawdown(
    chained_equity_series: pd.Series,
    train_end_date: Union[str, pd.Timestamp],
    val_end_date: Union[str, pd.Timestamp],
    out_path: Union[str, Path],
    title: str = "Full-Span Portfolio Underwater Drawdown (2018–2024)",
) -> Path:
    """Plot underwater drawdown curve across the full chained historical span (2018–2024).

    Parameters
    ----------
    chained_equity_series : pd.Series
        Chained net equity time series.
    train_end_date : Union[str, pd.Timestamp]
        Calendar end date of training period.
    val_end_date : Union[str, pd.Timestamp]
        Calendar end date of validation period.
    out_path : Union[str, Path]
        Destination PNG path.
    title : str
        Figure title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    dates = pd.to_datetime(chained_equity_series.index)
    peak = chained_equity_series.cummax()
    dd = ((chained_equity_series - peak) / peak) * 100.0  # percentage

    max_dd = abs(float(dd.min()))
    max_dd_date = dd.idxmin()

    t_end = pd.Timestamp(train_end_date)
    v_end = pd.Timestamp(val_end_date)

    fig, ax = plt.subplots(figsize=(13, 5.5))

    # Plot drawdown curve
    ax.plot(dates, dd.values, color="#d62728", linewidth=1.3, label=f"Underwater Drawdown (Max: -{max_dd:.2f}%)")
    ax.fill_between(dates, dd.values, 0.0, color="#d62728", alpha=0.22)
    ax.axhline(0.0, color="#333333", linestyle="-", linewidth=0.8)

    # Shaded periods
    ax.axvspan(dates.min(), t_end, color="#2ca02c", alpha=0.08, label="Train Period (2018–2021)")
    ax.axvspan(t_end, v_end, color="#ff7f0e", alpha=0.10, label="Validation Period (2022)")
    ax.axvspan(v_end, dates.max(), color="#9467bd", alpha=0.10, label="Test Period (2023–2024)")

    # Divider lines
    ax.axvline(t_end, color="#333333", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.axvline(v_end, color="#333333", linestyle="--", linewidth=1.0, alpha=0.7)

    # Annotate max drawdown
    ax.scatter([max_dd_date], [dd.loc[max_dd_date]], color="#800000", s=60, zorder=6)
    ax.annotate(
        f"Max DD: -{max_dd:.2f}%\n({pd.Timestamp(max_dd_date).strftime('%Y-%m-%d')})",
        xy=(max_dd_date, dd.loc[max_dd_date]),
        xytext=(30, -25),
        textcoords="offset points",
        fontsize=8.5,
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#800000", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#ffe6e6", edgecolor="#d62728", alpha=0.9),
    )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Underwater Drawdown (%)", fontsize=10)
    ax.set_xlabel("Date", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower left", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file


def plot_test_zscore_signals(
    z_series_dict: Dict[str, pd.Series],
    signals_df_dict: Dict[str, pd.DataFrame],
    entry_z: float,
    exit_z: float,
    out_path: Union[str, Path],
    title: str = "Test Period Z-Score Trajectory and Trade Signals (2023–2024)",
) -> Path:
    """Generate multi-panel figure displaying test period z-scores and trade signals for all pairs.

    Parameters
    ----------
    z_series_dict : Dict[str, pd.Series]
        Mapping from pair name to test period z-score series.
    signals_df_dict : Dict[str, pd.DataFrame]
        Mapping from pair name to test period signals DataFrame.
    entry_z : float
        Entry threshold (e.g. 2.0).
    exit_z : float
        Exit threshold (e.g. 0.5).
    out_path : Union[str, Path]
        Destination PNG path.
    title : str
        Figure super title.
    """
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    pairs = list(z_series_dict.keys())
    n_pairs = len(pairs)

    fig, axes = plt.subplots(n_pairs, 1, figsize=(13, 2.5 * n_pairs), sharex=True)
    if n_pairs == 1:
        axes = [axes]

    for ax, pair in zip(axes, pairs):
        z_series = z_series_dict[pair]
        signals_df = signals_df_dict[pair]

        ax.plot(z_series.index, z_series.values, color="#1f77b4", linewidth=1.1, label="$z_t$")
        ax.axhline(0.0, color="#333333", linestyle="-", linewidth=0.7, alpha=0.7)
        ax.axhline(entry_z, color="#d62728", linestyle="--", linewidth=0.9, label=f"+{entry_z}σ")
        ax.axhline(-entry_z, color="#2ca02c", linestyle="--", linewidth=0.9, label=f"-{entry_z}σ")
        ax.axhline(exit_z, color="#ff7f0e", linestyle=":", linewidth=0.8)
        ax.axhline(-exit_z, color="#ff7f0e", linestyle=":", linewidth=0.8)

        # Plot trade markers
        long_entries = signals_df[(signals_df["entry_flag"]) & (signals_df["state"] == 1)]
        short_entries = signals_df[(signals_df["entry_flag"]) & (signals_df["state"] == -1)]
        exits = signals_df[signals_df["exit_flag"]]

        if not long_entries.empty:
            ax.scatter(long_entries.index, z_series.loc[long_entries.index], color="#2ca02c", marker="^", s=60, zorder=5, label="Long")
        if not short_entries.empty:
            ax.scatter(short_entries.index, z_series.loc[short_entries.index], color="#d62728", marker="v", s=60, zorder=5, label="Short")
        if not exits.empty:
            ax.scatter(exits.index, z_series.loc[exits.index], color="#333333", marker="x", s=50, linewidth=1.5, zorder=5, label="Exit")

        ax.set_title(f"{pair} (Test Period: {len(long_entries) + len(short_entries)} entries, {len(exits)} exits)", fontsize=9.5, fontweight="bold")
        ax.set_ylabel("z-score", fontsize=8.5)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="upper right", ncol=6, fontsize=7.5, framealpha=0.8)

    axes[-1].set_xlabel("Date", fontsize=9.5)
    fig.suptitle(title, fontsize=12, fontweight="bold", y=0.995)
    plt.tight_layout()
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_file

