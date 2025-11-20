#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EDA: Feature importance & correlation analysis
Use all race_results_with_master.csv to identify features affecting FP==1
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import matplotlib.pyplot as plt
from pathlib import Path

# === Config ===
INPUT_PATH = "data/processed/race_results_with_master.csv"
OUTPUT_DIR = "data/processed/eda/"
TARGET_COL = "FP"  # finish position

# 手動で使えそうな特徴量候補
CANDIDATE_COLS = [
    "distance", "going", "weather", "field", "turn",
    "weight_carried", "body_weight", "odds_win", "pop_win",
    "sex_age", "horse", "jockey", "trainer", "frame", "horse_no"
]


def parse_sex_age(sa):
    if not isinstance(sa, str) or len(sa) == 0:
        return np.nan, np.nan
    sex = sa[0]
    digits = [c for c in sa if c.isdigit()]
    age = int(digits[0]) if digits else np.nan
    return sex, age


def main():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(INPUT_PATH)
    df.columns = df.columns.str.strip()

    # === 目的変数 ===
    df["target_win"] = (df[TARGET_COL] == 1).astype(int)

    # === sex, age分離 ===
    if "sex_age" in df.columns:
        parsed = df["sex_age"].astype(str).apply(parse_sex_age)
        df["sex"] = parsed.apply(lambda x: x[0])
        df["age"] = parsed.apply(lambda x: x[1])

    # === 特徴量候補抽出 ===
    cols = [c for c in CANDIDATE_COLS if c in df.columns]
    df = df[cols + ["target_win"]].copy()

    # === カテゴリ変数の自動判別 ===
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in cols if c not in num_cols]

    # one-hotエンコード（多すぎる騎手・馬はfrequency encoding）
    freq_limit = 30
    for c in cat_cols:
        n_unique = df[c].nunique()
        if n_unique > freq_limit:
            counts = df[c].value_counts()
            df[c + "_freq"] = df[c].map(counts)
        else:
            dummies = pd.get_dummies(df[c], prefix=c, dummy_na=True)
            df = pd.concat([df, dummies], axis=1)
    df = df.drop(columns=cat_cols)

    # 欠損処理
    df = df.fillna(0)

    X = df.drop(columns=["target_win"])
    y = df["target_win"]

    # === LightGBMで簡易重要度分析 ===
    model = lgb.LGBMClassifier(
        objective="binary", n_estimators=400, learning_rate=0.05, num_leaves=63, random_state=42
    )
    model.fit(X, y)

    importance = pd.DataFrame({
        "feature": X.columns,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    importance.to_csv(Path(OUTPUT_DIR) / "feature_importance.csv", index=False)

    # === 可視化 ===
    topn = importance.head(20)
    plt.figure(figsize=(8, 6))
    plt.barh(topn["feature"], topn["importance"])
    plt.gca().invert_yaxis()
    plt.title("Feature Importance (All races)")
    plt.tight_layout()
    plt.savefig(Path(OUTPUT_DIR) / "feature_importance.png", dpi=150)

    # === 相関確認（数値列のみ） ===
    corr = df[num_cols + ["target_win"]].corr()["target_win"].sort_values(ascending=False)
    corr.to_csv(Path(OUTPUT_DIR) / "corr_with_target.csv")

    print("Saved importance & correlation results to:", OUTPUT_DIR)
    print("\nTop correlated numeric features:")
    print(corr.head(10))
    print("\nTop important model features:")
    print(topn.head(10))


if __name__ == "__main__":
    main()