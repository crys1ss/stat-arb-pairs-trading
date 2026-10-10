"""Multi-pair portfolio aggregation, exposure tracking, and accounting validation module."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union
import numpy as np
import pandas as pd

from src.backtest import BacktestResult, backtest_pair
from src.config import Config, load_config
from src.data import slice_period
from src.pairs import construct_spread, zscore
from src.signals import generate_signals


class PortfolioResult(NamedTuple):
    """Container for portfolio simulation outputs."""

    daily: pd.DataFrame
    trades: pd.DataFrame
    pair_results: Dict[str, BacktestResult]
    turnover: float


def compute_turnover(trades_df: pd.DataFrame, daily_df: pd.DataFrame, annualization: int = 252) -> float:
    """Compute annualized portfolio turnover.

    Turnover formulation:
        Turnover = (total_traded_notional / average_equity) * (252 / T)

    Parameters
    ----------
    trades_df : pd.DataFrame
        Trade log DataFrame containing entry and exit prices and share quantities.
    daily_df : pd.DataFrame
        Daily portfolio DataFrame containing 'equity'.
    annualization : int, default 252
        Trading days per year.

    Returns
    -------
    float
        Annualized turnover ratio.
    """
    if trades_df.empty or daily_df.empty:
        return 0.0

    avg_equity = float(daily_df["equity"].mean())
    if avg_equity <= 0.0:
        return 0.0

    t_days = len(daily_df)
    if t_days == 0:
        return 0.0

    # Traded notional = entry notional + exit notional per trade
    entry_notional = (
        trades_df["shares_a"].abs() * trades_df["entry_price_a"]
        + trades_df["shares_b"].abs() * trades_df["entry_price_b"]
    ).sum()
    exit_notional = (
        trades_df["shares_a"].abs() * trades_df["exit_price_a"]
        + trades_df["shares_b"].abs() * trades_df["exit_price_b"]
    ).sum()
    total_traded_notional = float(entry_notional + exit_notional)

    annualized_turnover = (total_traded_notional / avg_equity) * (annualization / t_days)
    return float(annualized_turnover)


def run_portfolio(
    cfg: Config,
    period: str,
    prices: Optional[pd.DataFrame] = None,
    hedge_params: Optional[pd.DataFrame] = None,
    results_dir: Union[str, Path] = "reports/results",
) -> PortfolioResult:
    """Execute multi-pair portfolio backtest with exact capital splitting and accounting aggregation.

    Accounting Protocol & Contract:
    -------------------------------
    1. Capital Allocation:
       Total initial capital `cfg.capital.initial_capital` is split equally across all K selected pairs
       at the start of the period (`pair_capital = initial_capital / K`).
       Unused cash earns the risk-free rate (assumed 0.0).

    2. Equity & Return Accounting:
       Equity accumulates strictly via daily net P&L:
           equity_t = initial_capital + cumsum(portfolio_net_pnl)_t
       Daily portfolio return is evaluated relative to prior-close equity:
           return_t = net_pnl_t / equity_{t-1}   (with equity_{-1} = initial_capital)
       This guarantees that compounding (1 + return_t) strictly reproduces equity_t.

    3. Exposure & Position Tracking:
       For each pair k at close t:
           exposure_A = shares_A * P_A,t
           exposure_B = shares_B * P_B,t
           gross_exposure = |exposure_A| + |exposure_B|
           net_exposure = exposure_A + exposure_B
       Portfolio tracks aggregate gross exposure, net exposure, active open pair count,
       and each individual pair's daily net P&L contribution.

    Parameters
    ----------
    cfg : Config
        Validated configuration dataclass.
    period : str
        Period to simulate: 'train', 'validation', or 'test'.
    prices : Optional[pd.DataFrame], default None
        Optional pre-loaded/pre-sliced prices DataFrame. If None, loaded from data cache.
    hedge_params : Optional[pd.DataFrame], default None
        Optional pre-loaded hedge parameters DataFrame. If None, loaded from reports/results.
    results_dir : Union[str, Path], default "reports/results"
        Directory containing hedge_params.csv.

    Returns
    -------
    PortfolioResult
        NamedTuple with (daily, trades, pair_results, turnover).
    """
    # 1. Enforce period permissions and obtain prices
    if period == "test" and not cfg.dates.unlock_test:
        raise PermissionError(
            "Access to the out-of-sample 'test' period is strictly locked until the Day 10 freeze. "
            "Set `cfg.dates.unlock_test = True` only after all model decisions have been frozen."
        )

    if prices is None:
        data_file = Path("data/processed/close.parquet")
        if not data_file.exists():
            raise FileNotFoundError(f"Clean price panel missing at {data_file}. Run data pipeline first.")
        full_prices = pd.read_parquet(data_file)
        period_prices = slice_period(full_prices, period, cfg)
    else:
        # If user passed custom prices (e.g. in tests), ensure it is sliced or used as-is
        period_prices = prices.copy()

    # 2. Obtain selected pairs and frozen hedge parameters
    if hedge_params is None:
        hedge_path = Path(results_dir) / "hedge_params.csv"
        if not hedge_path.exists():
            raise FileNotFoundError(f"Hedge parameters missing at {hedge_path}. Run screening/calibration first.")
        hedge_df = pd.read_csv(hedge_path)
    else:
        hedge_df = hedge_params.copy()

    k_pairs = len(hedge_df)
    if k_pairs == 0:
        raise ValueError("Selected pairs list is empty. Cannot run portfolio simulation.")

    initial_capital = float(cfg.capital.initial_capital)
    pair_capital = initial_capital / float(k_pairs)

    dates = period_prices.index
    n_days = len(dates)

    pair_results: Dict[str, BacktestResult] = {}
    pair_daily_dict: Dict[str, pd.DataFrame] = {}
    all_trade_records: List[pd.DataFrame] = []

    # 3. Simulate each individual pair backtest
    for _, row in hedge_df.iterrows():
        pair_name = str(row["pair"])
        leg_a = str(row["leg_a"])
        leg_b = str(row["leg_b"])
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        mu_train = float(row["res_mean_train"])
        sd_train = float(row["res_std_train"])

        params = {"alpha": alpha, "beta": beta, "leg_a": leg_a, "leg_b": leg_b}

        # Construct spread and normalized z-score using strictly frozen training statistics
        spread = construct_spread(period_prices, params)
        z = zscore(spread, mu_train=mu_train, sd_train=sd_train)

        # Generate signals via state machine
        sig_df = generate_signals(
            z=z,
            entry_z=cfg.signals.entry_z,
            exit_z=cfg.signals.exit_z,
            max_hold_days=cfg.signals.max_hold_days,
            stop_z=cfg.signals.stop_z,
            close_at_end=False,  # Causal signal generation; period-end liquidation handled by backtest engine
        )

        # Run single-pair backtest simulation
        b_res = backtest_pair(
            price_a=period_prices[leg_a],
            price_b=period_prices[leg_b],
            signals=sig_df,
            beta=beta,
            capital=pair_capital,
            cost_config=cfg.execution,
            pair_name=pair_name,
        )

        pair_results[pair_name] = b_res
        pair_daily_dict[pair_name] = b_res.daily
        if not b_res.trades.empty:
            all_trade_records.append(b_res.trades)

    # 4. Aggregate across all pairs on common timeline
    port_gross_pnl = np.zeros(n_days, dtype=float)
    port_trade_cost = np.zeros(n_days, dtype=float)
    port_borrow_cost = np.zeros(n_days, dtype=float)
    port_net_pnl = np.zeros(n_days, dtype=float)

    port_gross_exposure = np.zeros(n_days, dtype=float)
    port_net_exposure = np.zeros(n_days, dtype=float)
    port_open_pairs = np.zeros(n_days, dtype=int)

    pair_contrib_data: Dict[str, np.ndarray] = {}
    pair_exposure_data: Dict[str, np.ndarray] = {}

    for pair_name, p_daily in pair_daily_dict.items():
        # Align onto common dates index
        p_d = p_daily.reindex(dates, fill_value=0.0)

        p_gross = p_d["gross_pnl"].values
        p_trade_cost = p_d["trade_cost"].values
        p_borrow_cost = p_d["borrow_cost"].values
        p_net = p_d["net_pnl"].values

        port_gross_pnl += p_gross
        port_trade_cost += p_trade_cost
        port_borrow_cost += p_borrow_cost
        port_net_pnl += p_net

        pair_contrib_data[f"pnl_{pair_name}"] = p_net

        # Compute pair dollar exposures at close t
        row_params = hedge_df[hedge_df["pair"] == pair_name].iloc[0]
        leg_a = str(row_params["leg_a"])
        leg_b = str(row_params["leg_b"])

        sh_a = p_d["shares_a"].values
        sh_b = p_d["shares_b"].values
        p_a = period_prices[leg_a].values
        p_b = period_prices[leg_b].values

        exp_a = sh_a * p_a
        exp_b = sh_b * p_b
        pair_gross_exp = np.abs(exp_a) + np.abs(exp_b)
        pair_net_exp = exp_a + exp_b

        port_gross_exposure += pair_gross_exp
        port_net_exposure += pair_net_exp
        port_open_pairs += (p_d["position"].values != 0).astype(int)

        pair_exposure_data[f"exposure_{pair_name}"] = pair_gross_exp

    # 5. Compute equity and compounding returns
    # Equity_t = initial_capital + cumsum(portfolio_net_pnl)_t
    equity_arr = initial_capital + np.cumsum(port_net_pnl)

    # Return_t = net_pnl_t / equity_{t-1}
    return_arr = np.zeros(n_days, dtype=float)
    for t in range(n_days):
        prev_equity = initial_capital if t == 0 else equity_arr[t - 1]
        return_arr[t] = port_net_pnl[t] / prev_equity if prev_equity > 0.0 else 0.0

    # Leverage ratios
    gross_leverage = np.where(equity_arr > 0.0, port_gross_exposure / equity_arr, 0.0)
    net_leverage = np.where(equity_arr > 0.0, port_net_exposure / equity_arr, 0.0)

    # Assemble comprehensive daily DataFrame
    daily_dict: Dict[str, Any] = {
        "gross_pnl": port_gross_pnl,
        "trade_cost": port_trade_cost,
        "borrow_cost": port_borrow_cost,
        "net_pnl": port_net_pnl,
        "equity": equity_arr,
        "return": return_arr,
        "gross_exposure": port_gross_exposure,
        "net_exposure": port_net_exposure,
        "gross_leverage": gross_leverage,
        "net_leverage": net_leverage,
        "open_pairs": port_open_pairs,
    }

    # Add individual pair contributions and exposures
    daily_dict.update(pair_contrib_data)
    daily_dict.update(pair_exposure_data)

    portfolio_daily_df = pd.DataFrame(daily_dict, index=dates)

    # Assemble combined trade log
    if all_trade_records:
        portfolio_trades_df = pd.concat(all_trade_records, ignore_index=True)
        # Sort chronologically by entry_date, then exit_date
        portfolio_trades_df = portfolio_trades_df.sort_values(["entry_date", "exit_date"]).reset_index(drop=True)
    else:
        portfolio_trades_df = pd.DataFrame(
            columns=[
                "pair", "direction", "signal_date", "entry_date", "exit_signal_date", "exit_date",
                "holding_days", "entry_price_a", "entry_price_b", "exit_price_a", "exit_price_b",
                "shares_a", "shares_b", "gross_pnl", "trade_cost", "borrow_cost", "costs", "net_pnl",
                "return_on_capital", "exit_reason"
            ]
        )

    # 6. Compute annualized portfolio turnover
    turnover_val = compute_turnover(portfolio_trades_df, portfolio_daily_df, annualization=cfg.capital.annualization)

    return PortfolioResult(
        daily=portfolio_daily_df,
        trades=portfolio_trades_df,
        pair_results=pair_results,
        turnover=turnover_val,
    )
