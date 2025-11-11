#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Add target encoding (mean win rate per category)
Output a new file train_with_target_encoding.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path


INPUT_PATH = "data/processed/race_results_with_master.csv"
OUTPUT_PATH = "data/processed/train_with_target_encoding.csv"

# 勝率を計算する対象カテゴリ
TARGET_COLS = ["jockey", "horse_id", "trainer"]
FINISH_COL = "FP"


def main():
    in_path = Path(INPUT_PATH)
    out_path = Path(OUTPUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)
    df.columns = df.columns.str.strip()

    if FINISH_COL not in df.columns:
        raise ValueError(f"'{FINISH_COL}' column not found in input CSV.")

    # 目的変数（着順1位なら1）
    df["target_win"] = (df[FINISH_COL] == 1).astype(int)

    # 実際に存在するカテゴリ列だけを使う
    use_cols = [c for c in TARGET_COLS if c in df.columns]
    print(f"Target encoding for: {use_cols}")

    for col in use_cols:
        mean_map = df.groupby(col)["target_win"].mean()
        df[f"{col}_te"] = df[col].map(mean_map)
        print(f"  {col}: created {col}_te (unique {len(mean_map)})")

    # 欠損（新規カテゴリ）を全体平均で補完
    global_mean = df["target_win"].mean()
    for col in use_cols:
        df[f"{col}_te"] = df[f"{col}_te"].fillna(global_mean)

    # 出力（必要な列＋target encoding列）
    te_cols = [f"{c}_te" for c in use_cols]
    out_cols = [FINISH_COL, "target_win"] + use_cols + te_cols
    out_cols = [c for c in out_cols if c in df.columns]

    df[out_cols].to_csv(out_path, index=False)
    print(f"\n✅ Saved target encoding file to: {out_path}")
    print(f"Columns: {out_cols}")
    print(f"Rows: {len(df)}")


if __name__ == "__main__":
    main()