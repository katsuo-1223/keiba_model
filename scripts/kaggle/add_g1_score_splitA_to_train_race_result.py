from __future__ import annotations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

RACE_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_basic_with_g1.csv"
SCORE_PATH = ROOT / "data" / "processed" / "kaggle" / "horse_g1_score_splitA.csv"
OUT_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_with_g1_splitA.csv"


def main() -> None:
    print("=== add_g1_score_splitA_to_train_race_result 開始 ===")
    print(f"[INFO] RACE_PATH : {RACE_PATH}")
    print(f"[INFO] SCORE_PATH: {SCORE_PATH}")

    race_df = pd.read_csv(RACE_PATH)
    score_df = pd.read_csv(SCORE_PATH)

    if "馬名" not in race_df.columns:
        raise KeyError("race_df に '馬名' 列がありません")
    if "馬名" not in score_df.columns:
        raise KeyError("score_df に '馬名' 列がありません")

    merged = race_df.merge(score_df, on="馬名", how="left")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUT_PATH, index=False)
    print(f"[INFO] 出力: {OUT_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()