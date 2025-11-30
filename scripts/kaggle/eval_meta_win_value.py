# scripts/kaggle/eval_meta_win_value.py
"""
メタモデル（train_meta_win_model.py）の出力
data/processed/kaggle/win_meta_pred.csv を用いて、
期待値しきい値ごとの回収率を集計するスクリプト。

入力:
    data/processed/kaggle/win_meta_pred.csv
        - レースID, 馬番, レース日付, 競馬場コード, 競馬場名, 馬名
        - target_win (+ target_place あれば)
        - 単勝_倍率 or 単勝
        - pred_win_meta
        - expected_value_win_meta

出力:
    data/processed/kaggle/eval_meta_win_value_thresholds.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
META_PRED_PATH = ROOT / "data" / "processed" / "kaggle" / "win_meta_pred.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "eval_meta_win_value_thresholds.csv"


def main() -> None:
    print("=== eval_meta_win_value.py 実行開始 ===")
    print(f"[INFO] META_PRED_PATH: {META_PRED_PATH}")

    df = pd.read_csv(META_PRED_PATH)

    if "target_win" not in df.columns:
        raise KeyError("列 'target_win' が win_meta_pred.csv にありません。")

    if "expected_value_win_meta" not in df.columns:
        raise KeyError("列 'expected_value_win_meta' が win_meta_pred.csv にありません。")

    # オッズ列の決定
    if "単勝_倍率" in df.columns:
        odds_col = "単勝_倍率"
    elif "単勝" in df.columns:
        odds_col = "単勝"
    else:
        raise KeyError("列 '単勝_倍率' も '単勝' も見つかりません。オッズ列が必要です。")

    thresholds = [1.00, 1.05, 1.10, 1.20, 1.30, 1.50, 2.00]

    results = []

    for th in thresholds:
        df_th = df[df["expected_value_win_meta"] >= th]

        n_bets = len(df_th)
        if n_bets == 0:
            results.append(
                {
                    "threshold": th,
                    "n_bets": 0,
                    "n_hits": 0,
                    "hit_rate": 0.0,
                    "total_bet": 0,
                    "total_return": 0.0,
                    "roi": 0.0,
                }
            )
            continue

        n_hits = df_th["target_win"].sum()
        hit_rate = n_hits / n_bets

        total_bet = 100 * n_bets
        total_return = (df_th["target_win"] * df_th[odds_col] * 100).sum()

        roi = total_return / total_bet if total_bet > 0 else 0.0

        print(f"th={th:.2f}  bets={n_bets}  hit_rate={hit_rate:.3f}  roi={roi:.3f}")

        results.append(
            {
                "threshold": th,
                "n_bets": n_bets,
                "n_hits": int(n_hits),
                "hit_rate": hit_rate,
                "total_bet": int(total_bet),
                "total_return": float(total_return),
                "roi": roi,
            }
        )

    out_df = pd.DataFrame(results)
    out_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved: {OUTPUT_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()