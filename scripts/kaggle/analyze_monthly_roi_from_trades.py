# scripts/kaggle/analyze_monthly_roi_from_trades.py

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
TRADES_PATH = ROOT / "outputs" / "kaggle" / "trades_splitA_meta_thr1.5.csv"


def main() -> None:
    print("=== analyze_monthly_roi_from_trades.py ===")
    print(f"[INFO] TRADES_PATH: {TRADES_PATH}")

    if not TRADES_PATH.exists():
        raise FileNotFoundError(f"トレードログが見つかりません: {TRADES_PATH}")

    df = pd.read_csv(TRADES_PATH)

    # 型の整形
    df["レース日付"] = pd.to_datetime(df["レース日付"])
    if "payout" not in df.columns:
        # 念のため、payout がなければ再計算
        df["payout"] = np.where(df["target_win"] == 1, df["単勝"] * 100.0, 0.0)

    df["month"] = df["レース日付"].dt.to_period("M")

    monthly = (
        df.groupby("month")
        .agg(
            bets=("payout", "size"),
            returns=("payout", "sum"),
        )
        .reset_index()
    )
    monthly["roi"] = monthly["returns"] / (monthly["bets"] * 100.0)

    print("\n--- 月次ROI ---")
    print(monthly)

    # 保存もしておく
    out_path = TRADES_PATH.with_name(TRADES_PATH.stem + "_monthly_roi.csv")
    monthly.to_csv(out_path, index=False)
    print(f"\n[INFO] Saved monthly ROI to: {out_path}")

    # 概要統計（標準偏差・平均など）
    mean_roi = monthly["roi"].mean()
    std_roi = monthly["roi"].std()
    min_roi = monthly["roi"].min()
    max_roi = monthly["roi"].max()

    print("\n--- ROI summary ---")
    print(f"mean ROI : {mean_roi:.3f}")
    print(f"std  ROI : {std_roi:.3f}")
    print(f"min  ROI : {min_roi:.3f}")
    print(f"max  ROI : {max_roi:.3f}")


if __name__ == "__main__":
    main()