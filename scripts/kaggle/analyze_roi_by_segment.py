import pandas as pd

def calc_roi(df):
    if len(df) == 0:
        return 0
    total_bet = 100 * len(df)
    total_return = (df["target_win"] * df["単勝_倍率"] * 100).sum()
    return total_return / total_bet

def main():
    df = pd.read_csv("data/processed/kaggle/lgbm_win_pred_calibrated.csv")
    df["EV"] = df["calibrated_win"] * df["単勝_倍率"]

    # 距離カテゴリ（build_train_race_result_basic_with_prev.py と揃える）
    def distance_bin(x):
        if x < 1400: return "短距離"
        if x < 1900: return "マイル〜中距離"
        if x < 2500: return "中距離〜長距離"
        return "長距離"

    df["距離帯"] = df["距離(m)"].apply(distance_bin)

    # クラス（完全一致ではなく contains で分類）
    def class_bin(x):
        if "新馬" in x: return "新馬"
        if "未勝利" in x: return "未勝利"
        if "1勝" in x: return "1勝"
        if "2勝" in x: return "2勝"
        if "3勝" in x: return "3勝"
        if "G" in x: return "重賞"
        return "その他"

    df["クラス帯"] = df["競争条件"].astype(str).apply(class_bin)

    # 頭数
    # レースID で group して頭数を取る
    headcount = df.groupby("レースID")["馬番"].count()
    df = df.merge(headcount.rename("頭数"), on="レースID")

    # 分類
    df["頭数帯"] = pd.cut(df["頭数"], bins=[0, 8, 13, 20], labels=["少頭数", "中頭数", "多頭数"])

    results = []
    for d in df["距離帯"].unique():
        for c in df["クラス帯"].unique():
            for h in df["頭数帯"].unique():
                sub = df[(df["距離帯"] == d) &
                         (df["クラス帯"] == c) &
                         (df["頭数帯"] == h) &
                         (df["EV"] >= 1.0)]
                roi = calc_roi(sub)
                results.append([d, c, h, len(sub), roi])

    out = pd.DataFrame(results, columns=["距離帯", "クラス帯", "頭数帯", "bets", "roi"])
    print(out)
    out.to_csv("data/processed/kaggle/roi_by_segment.csv", index=False)

if __name__ == "__main__":
    main()