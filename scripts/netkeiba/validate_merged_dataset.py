#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate merged dataset schema & quality.
"""
import sys, pandas as pd, numpy as np, re
from pathlib import Path

IN_PATH = Path("data/processed/race_results_with_master.csv")

def main():
    df = pd.read_csv(IN_PATH, encoding="utf-8-sig")
    ok = True

    # 1) 必須列
    required = ["race_id","FP","odds","distance"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print("[NG] missing columns:", missing); ok = False

    # 2) ヘッダ混入の検出
    if "FP" in df.columns:
        bad = df["FP"].astype(str).str.fullmatch(r"FP", case=False, na=False).sum()
        if bad:
            print(f"[NG] header-like rows detected in FP: {bad}"); ok = False

    # 3) オッズが小数(=少なくとも1つは小数点を含む or 小数値の存在)
    odds = pd.to_numeric(df["odds"], errors="coerce")
    if odds.isna().all():
        print("[NG] odds all NA"); ok = False
    else:
        has_decimal = any((x % 1) > 0 for x in odds.dropna().head(50))
        if not has_decimal:
            print("[NG] odds seems integer-only (lost decimals?)"); ok = False

    # 4) race_id の重複キー検査（race_id+horse_name+jockey+time で重複が少ないこと）
    keys = ["race_id","horse_name","jockey","time"]
    keys = [k for k in keys if k in df.columns]
    if keys:
        dup = df.duplicated(subset=keys).sum()
        if dup:
            print(f"[WARN] duplicate rows on {keys}: {dup}")

    print("[OK]" if ok else "[NG]")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())