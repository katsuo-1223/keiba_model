#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EDA for Target Encoding features:
- Input : data/processed/train_with_target_encoding.csv
- Output: data/processed/eda_te/*
  - hist_{col}.png              : ヒストグラム
  - deciles_{col}.csv           : デシル別の実勝率/件数
  - topN_{col}.csv              : TE上位Nカテゴリ（元カテゴリ別の平均TE/件数/実勝率）
  - summary_overview.csv        : 主要統計のまとめ
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

INPUT_PATH = "data/processed/train_with_target_encoding.csv"
OUT_DIR = Path("data/processed/eda_te")
TE_COLUMNS = ["jockey_te", "horse_id_te", "trainer_te"]      # 存在するものだけ使う
RAW_COLUMNS = ["jockey", "horse_id", "trainer"]              # 対応する元カテゴリ名
TARGET_COL = "target_win"
TOPN = 20  # 上位カテゴリ出力件数


def ensure_cols(df: pd.DataFrame, cols):
    """存在する列のみ返す"""
    return [c for c in cols if c in df.columns]


def plot_hist(series: pd.Series, title: str, out_path: Path, bins: int = 30):
    plt.figure(figsize=(7, 4))
    plt.hist(series.dropna().values, bins=bins)
    plt.title(title)
    plt.xlabel("Target-Encoded Value")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def decile_table(df: pd.DataFrame, te_col: str, target_col: str) -> pd.DataFrame:
    """TEをデシル分割し、各ビンの実勝率/件数を集計"""
    d = df[[te_col, target_col]].dropna().copy()
    # 0~1に寄ることが多いので、同順位の扱いも考慮してqcut失敗時はcutで代替
    try:
        d["decile"] = pd.qcut(d[te_col], q=10, labels=False, duplicates="drop")
    except ValueError:
        d["decile"] = pd.cut(d[te_col], bins=10, labels=False, include_lowest=True)

    tab = d.groupby("decile").agg(
        n=("target_win", "size"),
        win_rate=("target_win", "mean"),
        te_min=(te_col, "min"),
        te_max=(te_col, "max"),
        te_mean=(te_col, "mean"),
    ).reset_index()
    tab = tab.sort_values("decile")
    return tab


def topn_by_category(df: pd.DataFrame, cat_col: str, te_col: str, target_col: str, n: int) -> pd.DataFrame:
    """元カテゴリ（例: jockey）ごとに平均TEと実勝率を出し、上位Nを返す"""
    d = df[[cat_col, te_col, target_col]].dropna(subset=[cat_col]).copy()
    agg = d.groupby(cat_col).agg(
        count=(target_col, "size"),
        te_mean=(te_col, "mean"),
        win_rate=(target_col, "mean"),
    ).reset_index()
    # 件数が極端に少ないカテゴリでのノイズを抑制（任意で閾値調整）
    agg = agg.sort_values(["te_mean", "count"], ascending=[False, False]).head(n)
    return agg


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INPUT_PATH)
    df.columns = df.columns.str.strip()

    # 対象列の存在チェック
    te_cols = ensure_cols(df, TE_COLUMNS)
    raw_cols = ensure_cols(df, RAW_COLUMNS)

    if TARGET_COL not in df.columns:
        raise ValueError(f"'{TARGET_COL}' is required in {INPUT_PATH}")

    # 概要サマリー
    summary_rows = []
    for col in te_cols:
        s = df[col]
        summary_rows.append({
            "feature": col,
            "count_nonnull": int(s.notna().sum()),
            "mean": float(s.mean()),
            "std": float(s.std(ddof=0)),
            "min": float(s.min()),
            "p25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "p75": float(s.quantile(0.75)),
            "max": float(s.max()),
        })
        # ヒスト
        plot_hist(s, f"Histogram of {col}", OUT_DIR / f"hist_{col}.png")

        # デシルテーブル
        dec = decile_table(df, col, TARGET_COL)
        dec.to_csv(OUT_DIR / f"deciles_{col}.csv", index=False)

    if summary_rows:
        pd.DataFrame(summary_rows).to_csv(OUT_DIR / "summary_overview.csv", index=False)

    # 元カテゴリ別のTopN（例えば jockey_te と jockey の組）
    pairs = [("jockey", "jockey_te"), ("horse_id", "horse_id_te"), ("trainer", "trainer_te")]
    for raw_col, te_col in pairs:
        if raw_col in raw_cols and te_col in te_cols:
            topn = topn_by_category(df, raw_col, te_col, TARGET_COL, TOPN)
            topn.to_csv(OUT_DIR / f"topN_{raw_col}.csv", index=False)

    print("✅ EDA outputs saved under:", OUT_DIR)


if __name__ == "__main__":
    main()