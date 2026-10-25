"""Export research pipeline results to site/data JSON files for the website and replay."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT_DIR / "reports" / "results"
DATA_DIR = ROOT_DIR / "data" / "processed"
SITE_DATA_DIR = ROOT_DIR / "site" / "data"


def load_hedge_params() -> pd.DataFrame:
    path = RESULTS_DIR / "hedge_params.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return pd.read_csv(path)


def export_periods() -> list[dict]:
    breakeven_df = pd.read_csv(RESULTS_DIR / "sensitivity_breakeven.csv").set_index("period")
    periods_meta = [
        ("train", "Train", "2018 to 2021"),
        ("validation", "Validation", "2022"),
        ("test", "Test", "2023 to 2024"),
    ]

    records = []
    for period_key, name, span in periods_meta:
        metrics_file = RESULTS_DIR / f"{period_key}_metrics.json"
        with open(metrics_file, "r", encoding="utf-8") as f:
            m = json.load(f)

        gross_pnl = float(m["performance_comparison"]["gross"]["total_pnl"])
        costs = float(m["costs"]["total_all_costs"])
        net_pnl = float(m["performance_comparison"]["net"]["total_pnl"])
        cost_drag = round(costs / gross_pnl, 4) if gross_pnl > 0 else round(m["costs"]["cost_drag_on_gross_pnl"], 4)
        bk_bps = float(breakeven_df.loc[period_key, "breakeven_cost_per_side_bps"])

        records.append({
            "period": period_key,
            "name": name,
            "span": span,
            "days": int(m["trading_days"]),
            "ending_equity": round(float(m["ending_equity"]), 2),
            "net_pnl": round(net_pnl, 2),
            "gross_pnl": round(gross_pnl, 2),
            "costs": round(costs, 2),
            "cost_drag": cost_drag,
            "cum_return": round(float(m["performance_comparison"]["net"]["cumulative_return"]), 5),
            "cagr": round(float(m["performance_comparison"]["net"]["annualized_return_cagr"]), 5),
            "sharpe": round(float(m["performance_comparison"]["net"]["sharpe_ratio_rf_0"]), 4),
            "max_drawdown": round(float(m["performance_comparison"]["net"]["max_drawdown"]), 5),
            "trades": int(m["trade_statistics"]["n_trades"]),
            "win_rate": round(float(m["trade_statistics"]["win_rate"]), 4),
            "breakeven_bps": round(bk_bps, 2),
        })
    return records


def export_pairs(hedge_df: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in hedge_df.iterrows():
        records.append({
            "pair": str(row["pair"]),
            "leg_a": str(row["leg_a"]),
            "leg_b": str(row["leg_b"]),
            "sector": str(row["sector"]),
            "beta": round(float(row["beta"]), 4),
            "alpha": round(float(row["alpha"]), 6),
            "half_life_days": round(float(row["half_life_train"]), 1),
            "weight_a": round(float(row["weight_a"]), 4),
            "weight_b": round(float(row["weight_b"]), 4),
            "sd_train": round(float(row["res_std_train"]), 5),
        })
    return records


def export_cost_curve() -> list[dict]:
    df = pd.read_csv(RESULTS_DIR / "sensitivity_costs.csv")
    sub = df[(df["borrow_bps_annual"] == 50.0) & (df["cost_per_side_bps"].isin([0.0, 5.0, 10.0, 20.0]))]
    records = []
    for _, row in sub.iterrows():
        records.append({
            "period": str(row["period"]),
            "cost_per_side_bps": float(row["cost_per_side_bps"]),
            "net_pnl": round(float(row["net_pnl"]), 2),
        })
    return records


def export_entry_exit() -> list[dict]:
    df = pd.read_csv(RESULTS_DIR / "sensitivity_entry_exit.csv")
    records = []
    for _, row in df.iterrows():
        records.append({
            "period": str(row["period"]),
            "entry_z": float(row["entry_z"]),
            "exit_z": float(row["exit_z"]),
            "net_pnl": round(float(row["net_pnl"]), 2),
            "net_sharpe": round(float(row["net_sharpe"]), 4),
            "trades": int(row["n_trades"]),
        })
    return records


def export_trades() -> list[dict]:
    records = []
    for period in ["train", "validation", "test"]:
        csv_file = RESULTS_DIR / f"{period}_trades.csv"
        df = pd.read_csv(csv_file)
        for _, row in df.iterrows():
            pair = str(row["pair"])
            entry_date = str(row["entry_date"])
            records.append({
                "trade_id": f"{period}-{pair}-{entry_date}",
                "period": period,
                "pair": pair,
                "direction": int(row["direction"]),
                "signal_date": str(row["signal_date"]),
                "entry_date": entry_date,
                "exit_signal_date": str(row["exit_signal_date"]),
                "exit_date": str(row["exit_date"]),
                "holding_days": int(row["holding_days"]),
                "gross_pnl": round(float(row["gross_pnl"]), 2),
                "costs": round(float(row["costs"]), 2),
                "net_pnl": round(float(row["net_pnl"]), 2),
                "exit_reason": str(row["exit_reason"]),
            })
    return records


def export_daily(hedge_df: pd.DataFrame, close_df: pd.DataFrame) -> list[dict]:
    # Precompute z-scores for all 5 pairs across the whole date range
    z_series_dict = {}
    for _, row in hedge_df.iterrows():
        pair = str(row["pair"])
        leg_a = str(row["leg_a"])
        leg_b = str(row["leg_b"])
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        mu = float(row["res_mean_train"])
        sd = float(row["res_std_train"])

        spread = np.log(close_df[leg_a]) - alpha - beta * np.log(close_df[leg_b])
        z = (spread - mu) / sd
        z_series_dict[pair] = z

    records = []
    pairs_list = list(hedge_df["pair"])

    for period in ["train", "validation", "test"]:
        daily_csv = RESULTS_DIR / f"{period}_daily.csv"
        df = pd.read_csv(daily_csv)

        # Reconstruct gross equity
        gross_pnl = df["gross_pnl"].values
        gross_equity_arr = 1000000.0 + np.cumsum(gross_pnl)

        # Compute drawdown from peak equity
        equity_arr = df["equity"].values
        cum_peak = np.maximum.accumulate(equity_arr)
        drawdown_arr = np.where(cum_peak > 0, (equity_arr - cum_peak) / cum_peak, 0.0)

        for step, (_, row) in enumerate(df.iterrows()):
            d_str = str(row["Date"])
            eq = round(float(row["equity"]), 2)
            g_eq = round(float(gross_equity_arr[step]), 2)
            dd = round(float(drawdown_arr[step]), 5)

            item = {
                "period": period,
                "date": d_str,
                "step": step,
                "equity": eq,
                "gross_equity": g_eq,
                "drawdown": dd,
                "open_pairs": int(row["open_pairs"]),
            }

            for p in pairs_list:
                z_val = round(float(z_series_dict[p].loc[d_str]), 3)
                pnl_val = round(float(row[f"pnl_{p}"]), 2)
                item[f"z_{p}"] = z_val
                item[f"pnl_{p}"] = pnl_val

            records.append(item)
    return records


def export_prices(hedge_df: pd.DataFrame, close_df: pd.DataFrame) -> dict:
    # All 8 unique tickers
    tickers = sorted(list(set(hedge_df["leg_a"].tolist() + hedge_df["leg_b"].tolist())))
    
    pairs_meta = []
    for _, row in hedge_df.iterrows():
        pairs_meta.append({
            "pair": str(row["pair"]),
            "leg_a": str(row["leg_a"]),
            "leg_b": str(row["leg_b"]),
            "sector": str(row["sector"]),
            "alpha": float(row["alpha"]),
            "beta": float(row["beta"]),
            "mu_train": float(row["res_mean_train"]),
            "sd_train": float(row["res_std_train"]),
            "weight_a": float(row["weight_a"]),
            "weight_b": float(row["weight_b"]),
            "half_life_days": float(row["half_life_train"]),
        })

    periods_data = {}
    for period in ["train", "validation", "test"]:
        daily_csv = RESULTS_DIR / f"{period}_daily.csv"
        df = pd.read_csv(daily_csv)
        period_dates = df["Date"].tolist()

        close_slice = close_df.loc[period_dates, tickers]
        prices_by_ticker = {
            t: [round(float(v), 4) for v in close_slice[t].values]
            for t in tickers
        }

        periods_data[period] = {
            "dates": period_dates,
            "prices": prices_by_ticker,
        }

    return {
        "tickers": tickers,
        "pairs": pairs_meta,
        "periods": periods_data,
    }


def main():
    print("Running export_site_data.py...")
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    hedge_df = load_hedge_params()
    close_df = pd.read_parquet(DATA_DIR / "close.parquet")

    # 1. Export periods.json
    periods = export_periods()
    with open(SITE_DATA_DIR / "periods.json", "w", encoding="utf-8") as f:
        json.dump(periods, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'periods.json'} ({len(periods)} periods)")

    # 2. Export pairs.json
    pairs = export_pairs(hedge_df)
    with open(SITE_DATA_DIR / "pairs.json", "w", encoding="utf-8") as f:
        json.dump(pairs, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'pairs.json'} ({len(pairs)} pairs)")

    # 3. Export cost_curve.json
    cost_curve = export_cost_curve()
    with open(SITE_DATA_DIR / "cost_curve.json", "w", encoding="utf-8") as f:
        json.dump(cost_curve, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'cost_curve.json'} ({len(cost_curve)} items)")

    # 4. Export entry_exit.json
    entry_exit = export_entry_exit()
    with open(SITE_DATA_DIR / "entry_exit.json", "w", encoding="utf-8") as f:
        json.dump(entry_exit, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'entry_exit.json'} ({len(entry_exit)} items)")

    # 5. Export trades.json
    trades = export_trades()
    with open(SITE_DATA_DIR / "trades.json", "w", encoding="utf-8") as f:
        json.dump(trades, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'trades.json'} ({len(trades)} trades)")

    # 6. Export daily.json
    daily = export_daily(hedge_df, close_df)
    with open(SITE_DATA_DIR / "daily.json", "w", encoding="utf-8") as f:
        json.dump(daily, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'daily.json'} ({len(daily)} days)")

    # 7. Export prices.json
    prices = export_prices(hedge_df, close_df)
    with open(SITE_DATA_DIR / "prices.json", "w", encoding="utf-8") as f:
        json.dump(prices, f, separators=(",", ":"))
    print(f"  Wrote {SITE_DATA_DIR / 'prices.json'}")

    # 8. Integrity Assertions
    print("\nVerifying integrity assertions:")
    for p in periods:
        p_name = p["period"]
        p_trades = [t for t in trades if t["period"] == p_name]
        trade_net_sum = round(sum(t["net_pnl"] for t in p_trades), 2)
        period_net_pnl = round(p["net_pnl"], 2)
        diff = round(abs(trade_net_sum - period_net_pnl), 2)
        print(f"  Period '{p_name}': sum(trades.net_pnl) = {trade_net_sum:.2f}, periods.json net_pnl = {period_net_pnl:.2f}, diff = {diff:.2f}")
        assert diff <= 1.0, f"Trade net P&L sum {trade_net_sum} does not match period net P&L {period_net_pnl} (diff {diff})"

    print("\n[PASS] All integrity assertions passed successfully!")


if __name__ == "__main__":
    main()
