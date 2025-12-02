# scripts/kaggle/make_train_without_g1.py

from __future__ import annotations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

WITH_G1_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_with_g1_splitA.csv"
WITHOUT_G1_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_without_g1_splitA.csv"


def main() -> None:
    print("=== make_train_without_g1 開始 ===")
    print(f"[INFO] 入力: {WITH_G1_PATH}")

    if not WITH_G1_PATH.exists():
        raise FileNotFoundError(f"入力ファイルがありません: {WITH_G1_PATH}")

    df = pd.read_csv(WITH_G1_PATH)

    if "g1_score_splitA" not in df.columns:
        print("[WARN] g1_score_splitA 列が見つからないので、そのままコピーします。")
        df.to_csv(WITHOUT_G1_PATH, index=False)
        print(f"[INFO] 出力: {WITHOUT_G1_PATH}")
        return

    df = df.drop(columns=["g1_score_splitA"])
    df.to_csv(WITHOUT_G1_PATH, index=False)

    print(f"[INFO] g1_score_splitA を削除して保存しました: {WITHOUT_G1_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()