# scripts/kaggle/eval_win_value_thresholds.py

import pandas as pd


def main():
    df = pd.read_csv("data/processed/kaggle/lgbm_win_pred.csv")

    # 列名をそろえる（すでにこの名前で出している想定）
    df = df.rename(columns={
        "単勝_倍率": "odds_mult",
        "expected_value_win": "expected_value",
    })

    thresholds = [1.00, 1.05, 1.10, 1.20, 1.30, 1.50, 2.00]

    results = []

    for th in thresholds:
        df_th = df[df["expected_value"] >= th]

        n_bets = len(df_th)
        if n_bets == 0:
            results.append({
                "threshold": th,
                "n_bets": 0,
                "n_hits": 0,
                "hit_rate": 0,
                "total_bet": 0,
                "total_return": 0,
                "roi": 0,
            })
            continue

        n_hits = df_th["target_win"].sum()
        hit_rate = n_hits / n_bets

        total_bet = 100 * n_bets
        total_return = (df_th["target_win"] * df_th["odds_mult"] * 100).sum()

        roi = total_return / total_bet if total_bet > 0 else 0

        print(f"th={th:.2f}  bets={n_bets}  hit_rate={hit_rate:.3f}  roi={roi:.3f}")

        results.append({
            "threshold": th,
            "n_bets": n_bets,
            "n_hits": int(n_hits),
            "hit_rate": hit_rate,
            "total_bet": total_bet,
            "total_return": float(total_return),
            "roi": roi,
        })

    out_df = pd.DataFrame(results)
    out_df.to_csv("data/processed/kaggle/eval_win_value_thresholds.csv", index=False)
    print("\nSaved: data/processed/kaggle/eval_win_value_thresholds.csv")


if __name__ == "__main__":
    main()