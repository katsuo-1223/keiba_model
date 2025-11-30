import pandas as pd
import numpy as np

def calc_roi(df):
    if len(df) == 0:
        return 0
    total_bet = 100 * len(df)
    total_return = (df["target_win"] * df["単勝_倍率"] * 100).sum()
    return total_return / total_bet

def main():
    df = pd.read_csv("data/processed/kaggle/lgbm_win_pred_calibrated.csv")
    df["EV"] = df["calibrated_win"] * df["単勝_倍率"]

    odds_bins = [0, 2, 3, 5, 10, 20, 50, 100]
    pop_bins  = [0, 3, 6, 10, 18]

    df["odds_bin"] = pd.cut(df["単勝_倍率"], bins=odds_bins)
    df["pop_bin"]  = pd.cut(df["人気"], bins=pop_bins)

    results = []

    for o in df["odds_bin"].unique():
        for p in df["pop_bin"].unique():
            sub = df[(df["odds_bin"] == o) & (df["pop_bin"] == p) & (df["EV"] >= 1.0)]
            roi = calc_roi(sub)
            results.append([o, p, len(sub), roi])

    out = pd.DataFrame(results, columns=["odds_bin", "pop_bin", "bets", "roi"])
    print(out)

    out.to_csv("data/processed/kaggle/roi_by_odds_pop.csv", index=False)
    print("\nSaved roi_by_odds_pop.csv")

if __name__ == "__main__":
    main()