"""Sensitivity and robustness analysis engine for pairs-trading research.

Evaluates strategy stability across:
1. Entry and exit z-score thresholds
2. Friction costs (commissions, slippage, borrow fees) and break-even interpolation
3. Maximum holding horizons
4. Execution lag
5. Alternative causal rolling z-score estimation

All outputs are strictly labeled "sensitivity, not selection".
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.config import Config, load_config
from src.metrics import compute_portfolio_metrics
from src.portfolio import run_portfolio

LABEL_SENSITIVITY = "sensitivity, not selection"


def extract_summary_record(
    period: str,
    variant_category: str,
    variant_params: Dict[str, Any],
    cfg_run: Config,
    res: Any,
) -> Dict[str, Any]:
    """Extract standard performance metrics from portfolio result for sensitivity logging."""
    p_metrics = compute_portfolio_metrics(
        daily_df=res.daily,
        trades_df=res.trades,
        initial_capital=float(cfg_run.capital.initial_capital),
        pair_capital=float(cfg_run.capital.initial_capital) / float(len(res.pair_results)),
        pairs=list(res.pair_results.keys()),
        turnover=res.turnover,
        period_name=period,
        annualization=int(cfg_run.capital.annualization),
    )

    gross_comp = p_metrics["performance_comparison"]["gross"]
    net_comp = p_metrics["performance_comparison"]["net"]
    costs = p_metrics["costs"]
    trades = p_metrics["trade_statistics"]
    exposure = p_metrics["market_exposure"]

    record = {
        "period": period,
        "variant_category": variant_category,
        "label": LABEL_SENSITIVITY,
        **variant_params,
        "gross_pnl": round(gross_comp["total_pnl"], 2),
        "net_pnl": round(net_comp["total_pnl"], 2),
        "gross_sharpe": round(gross_comp["sharpe_ratio_rf_0"], 4) if not np.isnan(gross_comp["sharpe_ratio_rf_0"]) else np.nan,
        "net_sharpe": round(net_comp["sharpe_ratio_rf_0"], 4) if not np.isnan(net_comp["sharpe_ratio_rf_0"]) else np.nan,
        "net_cagr": round(net_comp["annualized_return_cagr"], 6),
        "net_max_drawdown": round(net_comp["max_drawdown"], 6),
        "max_drawdown_duration_days": net_comp["max_drawdown_duration_days"],
        "trade_costs": round(costs["total_trade_costs"], 2),
        "borrow_costs": round(costs["total_borrow_costs"], 2),
        "total_costs": round(costs["total_all_costs"], 2),
        "n_trades": trades["n_trades"],
        "win_rate": round(trades["win_rate"], 4) if not np.isnan(trades["win_rate"]) else np.nan,
        "mean_holding_days": round(trades["mean_holding_days"], 2) if not np.isnan(trades["mean_holding_days"]) else np.nan,
        "annualized_turnover": round(exposure["annualized_turnover"], 2),
    }
    return record


def run_entry_exit_grid(
    base_cfg: Config,
    periods: List[str] = ["train", "validation", "test"],
    entry_grid: List[float] = [1.5, 2.0, 2.5],
    exit_grid: List[float] = [0.0, 0.5, 1.0],
) -> pd.DataFrame:
    """Run 3x3 entry/exit z-score grid across specified periods at baseline costs."""
    records = []
    for period in periods:
        for entry_z in entry_grid:
            for exit_z in exit_grid:
                if exit_z >= entry_z:
                    continue  # Invalid state machine config
                cfg_run = replace(
                    base_cfg,
                    signals=replace(base_cfg.signals, entry_z=entry_z, exit_z=exit_z),
                    dates=replace(base_cfg.dates, unlock_test=True),
                )
                res = run_portfolio(cfg=cfg_run, period=period)
                rec = extract_summary_record(
                    period=period,
                    variant_category="entry_exit_grid",
                    variant_params={"entry_z": entry_z, "exit_z": exit_z},
                    cfg_run=cfg_run,
                    res=res,
                )
                records.append(rec)
    return pd.DataFrame(records)


def run_cost_grid(
    base_cfg: Config,
    periods: List[str] = ["train", "validation", "test"],
    cost_per_side_grid: List[float] = [0.0, 5.0, 10.0, 20.0],
    borrow_grid: List[float] = [0.0, 50.0, 200.0],
) -> pd.DataFrame:
    """Run friction cost grid across specified periods at baseline parameters."""
    records = []
    for period in periods:
        for cost_bps in cost_per_side_grid:
            for borrow_bps in borrow_grid:
                # Split cost per side equally between commission and slippage
                cfg_run = replace(
                    base_cfg,
                    execution=replace(
                        base_cfg.execution,
                        commission_bps=cost_bps / 2.0,
                        slippage_bps=cost_bps / 2.0,
                        borrow_bps_annual=borrow_bps,
                    ),
                    dates=replace(base_cfg.dates, unlock_test=True),
                )
                res = run_portfolio(cfg=cfg_run, period=period)
                rec = extract_summary_record(
                    period=period,
                    variant_category="cost_grid",
                    variant_params={
                        "cost_per_side_bps": cost_bps,
                        "borrow_bps_annual": borrow_bps,
                    },
                    cfg_run=cfg_run,
                    res=res,
                )
                records.append(rec)
    return pd.DataFrame(records)


def run_max_hold_grid(
    base_cfg: Config,
    periods: List[str] = ["train", "validation", "test"],
    max_hold_grid: List[int] = [15, 30, 60],
) -> pd.DataFrame:
    """Run maximum holding horizon grid across specified periods at baseline parameters."""
    records = []
    for period in periods:
        for mhd in max_hold_grid:
            cfg_run = replace(
                base_cfg,
                signals=replace(base_cfg.signals, max_hold_days=mhd),
                dates=replace(base_cfg.dates, unlock_test=True),
            )
            res = run_portfolio(cfg=cfg_run, period=period)
            rec = extract_summary_record(
                period=period,
                variant_category="max_hold_horizon",
                variant_params={"max_hold_days": mhd},
                cfg_run=cfg_run,
                res=res,
            )
            records.append(rec)
    return pd.DataFrame(records)


def run_execution_lag_grid(
    base_cfg: Config,
    periods: List[str] = ["train", "validation", "test"],
    lags: List[int] = [1, 2],
) -> pd.DataFrame:
    """Run execution lag sensitivity across specified periods at baseline parameters."""
    records = []
    for period in periods:
        for lag in lags:
            cfg_run = replace(
                base_cfg,
                execution=replace(base_cfg.execution, execution_lag=lag),
                dates=replace(base_cfg.dates, unlock_test=True),
            )
            res = run_portfolio(cfg=cfg_run, period=period)
            rec = extract_summary_record(
                period=period,
                variant_category="execution_lag",
                variant_params={"execution_lag": lag},
                cfg_run=cfg_run,
                res=res,
            )
            records.append(rec)
    return pd.DataFrame(records)


def run_rolling_zscore_comparison(
    base_cfg: Config,
    periods: List[str] = ["train", "validation", "test"],
) -> pd.DataFrame:
    """Compare baseline training-fixed z-score against alternative causal 60-day rolling z-score."""
    records = []
    methods = [("training_fixed", "Fixed In-Sample Mean & Std"), ("rolling_60", "Rolling 60d Mean & Std (Lag 1)")]
    for period in periods:
        for method_key, method_name in methods:
            cfg_run = replace(
                base_cfg,
                signals=replace(base_cfg.signals, z_score_baseline=method_key),
                dates=replace(base_cfg.dates, unlock_test=True),
            )
            res = run_portfolio(cfg=cfg_run, period=period)
            rec = extract_summary_record(
                period=period,
                variant_category="zscore_methodology",
                variant_params={"zscore_method": method_key, "zscore_description": method_name},
                cfg_run=cfg_run,
                res=res,
            )
            records.append(rec)
    return pd.DataFrame(records)


def compute_breakeven_costs(
    cost_df: pd.DataFrame,
    baseline_borrow_bps: float = 50.0,
) -> pd.DataFrame:
    """Compute break-even transaction cost in bps per period via linear interpolation/regression.

    Finds the exact cost per side per leg (bps) at which Net P&L reaches $0.00.
    """
    records = []
    periods = cost_df["period"].unique()

    for period in periods:
        sub = cost_df[(cost_df["period"] == period) & (cost_df["borrow_bps_annual"] == baseline_borrow_bps)].sort_values("cost_per_side_bps")
        if sub.empty:
            continue

        c_vals = sub["cost_per_side_bps"].values
        pnl_vals = sub["net_pnl"].values

        # Linear regression fit: NetPnL = a + b * Cost
        # Net P&L is mathematically linear in trade cost per side for fixed trades
        poly = np.polyfit(c_vals, pnl_vals, deg=1)
        b, a = poly[0], poly[1]  # NetPnL = b * Cost + a

        if abs(b) > 1e-9:
            breakeven_bps = -a / b
        else:
            breakeven_bps = np.nan

        gross_pnl = float(sub["gross_pnl"].iloc[0])
        borrow_costs = float(sub["borrow_costs"].iloc[0])
        baseline_net_pnl = float(sub[sub["cost_per_side_bps"] == 10.0]["net_pnl"].iloc[0]) if (sub["cost_per_side_bps"] == 10.0).any() else np.nan

        status = "Profitable at baseline" if baseline_net_pnl > 0 else "Unprofitable at baseline (Friction Dominated)"

        records.append({
            "period": period,
            "label": LABEL_SENSITIVITY,
            "borrow_bps_annual": baseline_borrow_bps,
            "breakeven_cost_per_side_bps": round(float(breakeven_bps), 2),
            "baseline_cost_per_side_bps": 10.0,
            "baseline_net_pnl": baseline_net_pnl,
            "gross_pnl": gross_pnl,
            "borrow_costs": borrow_costs,
            "status": status,
            "notes": f"Linear interpolation zero-crossing; Net P&L = {b:.2f} * Cost + {a:.2f}",
        })

    return pd.DataFrame(records)
