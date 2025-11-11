#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import pandas as pd
import numpy as np
from pathlib import Path

# 予測時点で使える安全なデフォルト特徴量（last3f等の事後値は含めない）
NUMERIC_COLS_DEFAULT = [
    "distance", "weight_carried", "body_weight", "pop_win", "odds_win"
]
CATEG_COLS_DEFAULT = [
    "going", "weather", "field", "turn"
]

# 列名候補（英語統一データ想定）
FINISH_CANDIDATES = ["FP", "finish", "placing", "pos", "rank", "fin_pos", "finish_pos"]
ODDS_CANDIDATES   = ["odds_win", "Odds", "odds"]
POP_CANDIDATES    = ["pop_win", "Pop", "popularity"]
SEXAGE_CANDIDATES = ["sex_age", "SexAge", "sexAge", "Sex/Age"]  # 例: 'C3','F2'等


def parse_sex_age(sa: str):
    if not isinstance(sa, str) or len(sa) == 0:
        return np.nan, np.nan
    sex = sa[0]
    digits = [c for c in sa if c.isdigit()]
    try:
        age = int(digits[0]) if digits else np.nan
    except Exception:
        age = np.nan
    return sex, age


def resolve_first_existing(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def build_features(df: pd.DataFrame, num_cols, cat_cols):
    # sex_age 抽出
    sexage_col = resolve_first_existing(df.columns, SEXAGE_CANDIDATES)
    if sexage_col:
        parsed = df[sexage_col].astype(str).fillna("").apply(parse_sex_age)
        df["sex"] = parsed.apply(lambda x: x[0])
        df["age"] = parsed.apply(lambda x: x[1])
    else:
        df["sex"], df["age"] = np.nan, np.nan

    # 型変換（数値列）
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # ワンホット（低頻度結合はしないシンプル版）
    one_hot_cols = []
    for c in cat_cols + ["sex"]:
        if c in df.columns:
            dummies = pd.get_dummies(df[c].astype("category"), prefix=c, dummy_na=True)
            df = pd.concat([df, dummies], axis=1)
            one_hot_cols.extend(list(dummies.columns))

    feature_cols = [c for c in (num_cols + ["age"] + one_hot_cols) if c in df.columns]
    return df, feature_cols


def split_by_race(df: pd.DataFrame, seed: int, train_ratio: float):
    race_ids = df["race_id"].dropna().astype(str).unique()
    rng = np.random.default_rng(seed)
    rng.shuffle(race_ids)
    n_train = int(len(race_ids) * train_ratio)
    train_rids = set(race_ids[:n_train])

    train_df = df[df["race_id"].astype(str).isin(train_rids)].copy()
    valid_df = df[~df["race_id"].astype(str).isin(train_rids)].copy()
    return train_df, valid_df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/processed/race_results_with_master.csv")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train-ratio", type=float, default=0.7)
    ap.add_argument("--numeric-cols", nargs="*", default=NUMERIC_COLS_DEFAULT)
    ap.add_argument("--categorical-cols", nargs="*", default=CATEG_COLS_DEFAULT)
    ap.add_argument("--target-col", default="FP", help="finish position column name")
    ap.add_argument("--limit-races", type=int, default=50, help="use first N races")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(in_path)

    # 列名のトリム
    df.columns = df.columns.str.strip()

    # race_id の存在確認
    if "race_id" not in df.columns:
        cand = [c for c in df.columns if "race_id" in c]
        if cand:
            df = df.rename(columns={cand[0]: "race_id"})
        else:
            raise ValueError("race_id column not found in input CSV.")

    # 着順列の解決（FP最優先）
    finish_col = args.target_col if args.target_col in df.columns else resolve_first_existing(df.columns, FINISH_CANDIDATES)
    if finish_col is None:
        raise ValueError(f"finish column not found. candidates={FINISH_CANDIDATES}, columns={list(df.columns)}")

    # オッズ/人気の英語→標準化
    if "odds_win" not in df.columns:
        oc = resolve_first_existing(df.columns, ODDS_CANDIDATES)
        if oc and oc != "odds_win":
            df = df.rename(columns={oc: "odds_win"})
    if "pop_win" not in df.columns:
        pc = resolve_first_existing(df.columns, POP_CANDIDATES)
        if pc and pc != "pop_win":
            df = df.rename(columns={pc: "pop_win"})

    # 対象レース（先頭Nユニークrace_id）
    race_order = df["race_id"].dropna().astype(str)
    first_races = list(dict.fromkeys(race_order))[: args.limit_races]
    df = df[df["race_id"].astype(str).isin(first_races)].copy()

    # 目的変数
    fin = pd.to_numeric(df[finish_col], errors="coerce")
    df["target_win"] = (fin == 1).astype(int)

    # 特徴量
    df, feature_cols = build_features(df, args.numeric_cols, args.categorical_cols)

    # 学習/検証分割
    train_df, valid_df = split_by_race(df, args.seed, args.train_ratio)

    # 出力
    meta = {
        "feature_cols": feature_cols,
        "target_col": "target_win",
        "finish_source_col": finish_col,
        "n_train": int(len(train_df)),
        "n_valid": int(len(valid_df)),
        "n_races": int(df["race_id"].astype(str).nunique()),
    }
    pd.Series(meta).to_json(out_dir / "train_meta.json")

    train_df.to_csv(out_dir / "train_dataset.csv", index=False)
    valid_df.to_csv(out_dir / "valid_dataset.csv", index=False)

    print("[build_train_dataset] finish_col:", finish_col)
    print("Saved:", out_dir / "train_dataset.csv", out_dir / "valid_dataset.csv")
    print("#features:", len(feature_cols))


if __name__ == "__main__":
    main()