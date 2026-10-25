"""
Compare baseline vs 20-day cooldown on the 2022 validation period strictly.

Saves comparison to reports/results/cooldown_validation_comparison.csv.
Adheres strictly to the protocol: does not evaluate on test set, does not touch frozen files.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import load_config
from src.portfolio import run_portfolio
from src.metrics import compute_portfolio_metrics, compute_turnover


def run_cooldown_validation_comparison():
    print("Running Baseline vs Cooldown Comparison on 2022 Validation Period...")

    # 1. Run baseline (cooldown_days = 0)
    cfg_base = load_config("configs/baseline.yaml")
    res_base = run_portfolio(cfg=cfg_base, period="validation")
    hedge_df = pd.read_csv("reports/results/hedge_params.csv")
    pairs = hedge_df["pair"].tolist()
    initial_cap = float(cfg_base.capital.initial_capital)
    pair_cap = initial_cap / float(len(pairs))

    turnover_base = compute_turnover(res_base.trades, res_base.daily, annualization=cfg_base.capital.annualization)
    metrics_base = compute_portfolio_metrics(
        daily_df=res_base.daily,
        trades_df=res_base.trades,
        initial_capital=initial_cap,
        pair_capital=pair_cap,
        pairs=pairs,
        turnover=turnover_base,
        period_name="validation",
        annualization=cfg_base.capital.annualization,
    )

    # 2. Run cooldown (cooldown_days = 20)
    cfg_cool = load_config("configs/cooldown_validation.yaml")
    res_cool = run_portfolio(cfg=cfg_cool, period="validation")

    turnover_cool = compute_turnover(res_cool.trades, res_cool.daily, annualization=cfg_cool.capital.annualization)
    metrics_cool = compute_portfolio_metrics(
        daily_df=res_cool.daily,
        trades_df=res_cool.trades,
        initial_capital=initial_cap,
        pair_capital=pair_cap,
        pairs=pairs,
        turnover=turnover_cool,
        period_name="validation",
        annualization=cfg_cool.capital.annualization,
    )

    # 3. Assemble comparison rows
    net_base = metrics_base["performance_comparison"]["net"]
    gross_base = metrics_base["performance_comparison"]["gross"]
    trade_base = metrics_base["trade_statistics"]
    cost_base = metrics_base["costs"]

    net_cool = metrics_cool["performance_comparison"]["net"]
    gross_cool = metrics_cool["performance_comparison"]["gross"]
    trade_cool = metrics_cool["trade_statistics"]
    cost_cool = metrics_cool["costs"]

    summary_rows = [
        {
            "metric": "Net P&L ($)",
            "baseline_val_0d": round(net_base["total_pnl"], 2),
            "cooldown_val_20d": round(net_cool["total_pnl"], 2),
            "difference": round(net_cool["total_pnl"] - net_base["total_pnl"], 2),
        },
        {
            "metric": "Gross P&L ($)",
            "baseline_val_0d": round(gross_base["total_pnl"], 2),
            "cooldown_val_20d": round(gross_cool["total_pnl"], 2),
            "difference": round(gross_cool["total_pnl"] - gross_base["total_pnl"], 2),
        },
        {
            "metric": "Total Friction / Costs ($)",
            "baseline_val_0d": round(cost_base["total_all_costs"], 2),
            "cooldown_val_20d": round(cost_cool["total_all_costs"], 2),
            "difference": round(cost_cool["total_all_costs"] - cost_base["total_all_costs"], 2),
        },
        {
            "metric": "Net Sharpe Ratio",
            "baseline_val_0d": round(net_base["sharpe_ratio_rf_0"], 4),
            "cooldown_val_20d": round(net_cool["sharpe_ratio_rf_0"], 4),
            "difference": round(net_cool["sharpe_ratio_rf_0"] - net_base["sharpe_ratio_rf_0"], 4),
        },
        {
            "metric": "Number of Trades",
            "baseline_val_0d": trade_base["n_trades"],
            "cooldown_val_20d": trade_cool["n_trades"],
            "difference": trade_cool["n_trades"] - trade_base["n_trades"],
        },
        {
            "metric": "Win Rate (%)",
            "baseline_val_0d": round(trade_base["win_rate"] * 100, 2),
            "cooldown_val_20d": round(trade_cool["win_rate"] * 100, 2),
            "difference": round((trade_cool["win_rate"] - trade_base["win_rate"]) * 100, 2),
        },
        {
            "metric": "Max Drawdown (%)",
            "baseline_val_0d": round(net_base["max_drawdown"] * 100, 2),
            "cooldown_val_20d": round(net_cool["max_drawdown"] * 100, 2),
            "difference": round((net_cool["max_drawdown"] - net_base["max_drawdown"]) * 100, 2),
        },
    ]

    # Per-pair P&L comparison
    for pair in pairs:
        base_pnl = res_base.trades[res_base.trades["pair"] == pair]["net_pnl"].sum() if len(res_base.trades) > 0 else 0.0
        cool_pnl = res_cool.trades[res_cool.trades["pair"] == pair]["net_pnl"].sum() if len(res_cool.trades) > 0 else 0.0
        summary_rows.append(
            {
                "metric": f"Pair Net P&L: {pair} ($)",
                "baseline_val_0d": round(base_pnl, 2),
                "cooldown_val_20d": round(cool_pnl, 2),
                "difference": round(cool_pnl - base_pnl, 2),
            }
        )

    df_comp = pd.DataFrame(summary_rows)
    out_path = Path("reports/results/cooldown_validation_comparison.csv")
    df_comp.to_csv(out_path, index=False)
    print(f"\nSaved comparison to {out_path}:")
    print(df_comp.to_string(index=False))

    return df_comp


if __name__ == "__main__":
    run_cooldown_validation_comparison()
