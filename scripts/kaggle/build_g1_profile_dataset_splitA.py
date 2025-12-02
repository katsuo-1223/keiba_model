# scripts/kaggle/build_g1_profile_dataset_splitA.py

from __future__ import annotations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# もともと jra_race_result_light を使っている想定
RACE_LIGHT_PATH = ROOT / "data" / "processed" / "kaggle" / "jra_race_result_light.csv"
OUT_PATH = ROOT / "data" / "processed" / "kaggle" / "g1_profile_train_splitA.csv"

# ★ 追加：既存の G1 ラベル＆スコア
LABEL_PATH = ROOT / "data" / "processed" / "kaggle" / "horse_g1_score.csv"

CUTOFF_DATE = "2010-12-31"

def main() -> None:
    print("[SplitA] build_g1_profile_dataset_splitA 開始")
    print(f"[INFO] input: {RACE_LIGHT_PATH}")
    print(f"[INFO] output: {OUT_PATH}")
    print(f"[INFO] cutoff: {CUTOFF_DATE}")

    df = pd.read_csv(RACE_LIGHT_PATH)

    # ★ ここが一番大事：2010-12-31 までで切る
    df["レース日付"] = pd.to_datetime(df["レース日付"])
    cutoff = pd.to_datetime(CUTOFF_DATE)
    df = df[df["レース日付"] <= cutoff].copy()

    # ▼ ここから先は、元の build_g1_profile_dataset.py の
    #    「馬単位で集約して g1_profile_train.csv を作っている処理」
    #    をほぼコピペで OK。
    # 例（イメージ）：
    #   - 出走数
    #   - 勝利数
    #   - 連対率
    #   - クラス別出走数
    #   - G1/G2/G3 出走数 など

    # 例: 馬名ごとの簡単な集約イメージ（本番は元スクリプトに合わせてください）
    agg = df.groupby("馬名").agg(
        races=("レースID", "nunique"),
        wins=("着順", lambda s: (s == 1).sum()),
        places=("着順", lambda s: (s <= 3).sum()),
        # TODO: 実際の特徴量定義は既存 build_g1_profile_dataset.py に合わせる
    ).reset_index()

    # 連対率など派生指標
    agg["win_rate"] = agg["wins"] / agg["races"]
    agg["place_rate"] = agg["places"] / agg["races"]

        # ここまでで agg は「馬名ごとの特徴量」になっている前提
    # 例: agg.columns = ["馬名", "races", "wins", "places", "win_rate", "place_rate", ...]

    # ★ 既存の horse_g1_score.csv からラベルを付与
    labels = pd.read_csv(LABEL_PATH)

    # 必要な列だけに絞る（列名は実ファイルに合わせて調整してください）
    # 例: ["馬名", "horse_is_g1_winner", "first_g1_win_date", "g1_score"]
    use_cols = [c for c in ["馬名", "horse_is_g1_winner"] if c in labels.columns]
    labels = labels[use_cols].drop_duplicates(subset=["馬名"])

    agg = agg.merge(labels, on="馬名", how="left")

    # ラベルが欠損している行（=ラベル不明の馬）は学習から外す
    before = len(agg)
    agg = agg.dropna(subset=["horse_is_g1_winner"]).copy()
    after = len(agg)
    print(f"[SplitA] ラベル欠損で削除: {before - after} / {before} 件")

    agg.to_csv(OUT_PATH, index=False)

    print(f"[SplitA] g1_profile_train_splitA.csv を保存しました: {OUT_PATH}")


if __name__ == "__main__":
    main()