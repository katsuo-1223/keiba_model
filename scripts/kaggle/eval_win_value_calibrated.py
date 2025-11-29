"""
キャリブレーション後の ROI を評価する
"""

import pandas as pd

df = pd.read_csv("data/processed/kaggle/lgbm_win_pred_calibrated.csv")

thresholds = [1.0, 1.05, 1.1, 1.2, 1.3, 1.5, 2.0]

for th in thresholds:
    sub = df[df["calibrated_ev"] >= th]

    bets = len(sub)
    hits = sub["target_win"].sum()

    if bets == 0:
        roi = 0
    else:
        total_bet = 100 * bets
        total_return = (sub["target_win"] * sub["単勝"] * 100).sum()
        roi = total_return / total_bet

    print(f"th={th:.2f}  bets={bets}  hit_rate={hits/bets if bets>0 else 0:.3f}  roi={roi:.3f}")