#!/usr/bin/env python3
"""
merge_results_with_master.py (fixed)

目的:
- results（1頭ごとの結果）と master（レースごとの情報）を race_id で結合
- FP の最大値から num_horses を算出し master に付与
- **単勝オッズ(odds)の小数を確実に保持**（整数化や文字列化で欠落させない）
- race_id は両側で str に統一

使い方:
    python scripts/merge_results_with_master.py \
      --results data/raw/race_results.csv \
      --master  data/raw/race_master.csv \
      --output  data/processed/race_results_with_master.csv \
      --join    inner

注意:
- 既に結合後CSVで odds が人気に置換されている場合は復元できません。
  必ず **raw の race_results.csv（小数オッズ入り）** から再マージしてください。
"""

import argparse
import sys
import logging
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
LOG_FMT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
logger = logging.getLogger("merge_fixed")

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
def to_float_safe(x) -> Optional[float]:
    """
    小数オッズを安全に抽出して float 化。
    - カンマ除去
    - 文字列混入でも正規表現で数値部分だけ抽出
    - 抽出できない場合は NaN
    """
    s = str(x).strip().replace(",", "")
    if s == "" or s.lower() in {"nan", "none"}:
        return np.nan
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return np.nan
    try:
        return float(m.group(0))
    except Exception:
        return np.nan

def read_results(path: Path) -> pd.DataFrame:
    logger.info("Reading results: %s", path)
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")

    # -------------------------------
    # ① 不正な「ヘッダー行」を除去
    # -------------------------------
    # 代表的なヘッダー単語が FP や Odds に混入している行を排除
    bad_mask = (
        df["FP"].astype(str).str.contains("FP", case=False, na=False)
        | df["odds"].astype(str).str.contains("Odds", case=False, na=False)
        | df["horse_name"].astype(str).str.contains("Horse", case=False, na=False)
    )
    before = len(df)
    df = df[~bad_mask].copy()
    after = len(df)
    if before != after:
        logger.warning(f"Removed {before - after} header-like rows from results.")

    # race_id を str に
    if "race_id" in df.columns:
        df["race_id"] = df["race_id"].astype(str)

    # FP は Int64（nullable int）
    if "FP" in df.columns:
        df["FP"] = pd.to_numeric(df["FP"], errors="coerce").astype("Int64")

    # -------------------------------
    # ② odds を小数保持で float 化
    # -------------------------------
    if "odds" in df.columns:
        df["odds"] = df["odds"].apply(to_float_safe).astype(float)

    return df

def read_master(path: Path) -> pd.DataFrame:
    logger.info("Reading master: %s", path)
    df = pd.read_csv(path, dtype={"race_id": str}, encoding="utf-8-sig")
    if "race_id" in df.columns:
        df["race_id"] = df["race_id"].astype(str)
    return df

# ------------------------------------------------------------
# Core
# ------------------------------------------------------------
def run(
    results_path: Path,
    master_path: Path,
    output_path: Path,
    join_how: str = "inner",
) -> None:
    results = read_results(results_path)
    master = read_master(master_path)

    # 1) num_horses を results から付与（FP の最大値）
    if "FP" in results.columns:
        logger.info("Calculating num_horses from results (max FP per race_id)")
        num_horses_df = (
            results.groupby("race_id")["FP"]
            .max()
            .rename("num_horses")
            .reset_index()
        )
        # nullable int にしておく
        num_horses_df["num_horses"] = pd.to_numeric(
            num_horses_df["num_horses"], errors="coerce"
        ).astype("Int64")
        master = master.merge(num_horses_df, on="race_id", how="left")
        logger.info("num_horses annotated on master (non-null: %d)", master["num_horses"].notna().sum())

    # 2) 結合
    logger.info("Merging on race_id (how=%s)", join_how)
    merged = results.merge(master, on="race_id", how=join_how, suffixes=("_res", "_mst"))

    # 3) 列の並び（存在するものだけ並べる）
    pref = [
        "race_id", "date", "race_name", "course", "surface", "distance", "weather", "going",
        "num_horses",
        "horse_id", "horse_name", "rank", "FP", "pop", "odds", "time", "last3f", "weight",
    ]
    cols_exist = [c for c in pref if c in merged.columns]
    others = [c for c in merged.columns if c not in cols_exist]
    merged = merged[cols_exist + others]

    # 4) odds の先頭サンプルをログ（小数保持の健全性チェック用）
    if "odds" in merged.columns:
        sample = merged["odds"].dropna().astype(float).head(10).tolist()
        logger.info("Sample odds (should contain decimals if present in raw): %s", sample)

    # 5) 書き出し（float_format 未指定 → 保存値を丸めない）
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info("Wrote merged CSV: %s (rows=%d, cols=%d)", output_path, merged.shape[0], merged.shape[1])

# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, type=Path, help="Path to race_results.csv (raw; odds keeps decimals)")
    ap.add_argument("--master", required=True, type=Path, help="Path to race_master.csv")
    ap.add_argument("--output", required=True, type=Path, help="Path to write merged CSV")
    ap.add_argument("--join", default="inner", choices=["inner", "left", "right", "outer"], help="Pandas merge how")
    return ap

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        run(
            results_path=args.results,
            master_path=args.master,
            output_path=args.output,
            join_how=args.join,
        )
        return 0
    except Exception as e:
        logger.exception("Failed to merge: %s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())