# -*- coding: utf-8 -*-
"""
日本語マスター（月次CSV: race_master_jp_YYYYMM.csv）を読み込み、
英語整形して単一の master テーブル (data/raw/race_master.csv) を出力。

既定は 2024年 1..12 を対象。
将来は --year-from 2022 --year-to 2024 のように 3年分も一括処理可能。

オプション:
  --months 1,2,3     月をカンマ区切り指定（未指定なら 1..12）
  --strict           2/3歳・1/2勝・芝・距離1000〜1700 の厳密フィルタを最終段で適用
"""

from __future__ import annotations
import argparse
import glob
from pathlib import Path
from typing import List, Optional

import pandas as pd

RAW_DIR  = Path("data/raw")
OUT_CSV  = RAW_DIR / "race_master.csv"

VENUE_MAP = {
    "札幌": "SAPPORO","函館": "HAKODATE","福島": "FUKUSHIMA","新潟": "NIIGATA",
    "東京": "TOKYO","中山": "NAKAYAMA","中京": "CHUKYO","京都": "KYOTO",
    "阪神": "HANSHIN","小倉": "KOKURA",
}
SURFACE_MAP = {"芝": "TURF", "ダ": "DIRT", "ダート": "DIRT"}  # 念のため "ダ" も吸収
TRACK_COND_MAP = {"良": "Gd", "稍重": "Yld", "重": "Sft", "不良": "Hvy"}
WEATHER_MAP = {
    "晴": "Sunny", "晴れ": "Sunny",
    "曇": "Cloudy", "曇り": "Cloudy",
    "小雨": "LightRain", "雨": "Rain",
    "小雪": "LightSnow", "雪": "Snow",
}

# 出力列（英語ビューの最小セット）
EN_COLS = ["race_id","date","venue","surface_type","distance","weather","track_condition","num_horses","url_jp"]

def _parse_months_arg(arg: Optional[str]) -> Optional[List[int]]:
    if not arg:
        return None
    parts = []
    for tok in arg.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok:
            a, b = tok.split("-", 1)
            a, b = int(a), int(b)
            parts.extend(range(min(a,b), max(a,b)+1))
        else:
            parts.append(int(tok))
    # 重複や順序は気にしない（後段でユニーク化不要）
    return parts

def _load_monthlies(year_from: int, year_to: int, months: Optional[List[int]]) -> pd.DataFrame:
    paths = []
    if months is None:
        months = list(range(1, 13))

    for y in range(year_from, year_to + 1):
        for m in months:
            pat = RAW_DIR / f"race_master_jp_{y}{m:02d}.csv"
            if pat.exists() and pat.stat().st_size > 0:
                paths.append(str(pat))

    if not paths:
        print("[WARN] No monthly JP files were found. Pattern: data/raw/race_master_jp_YYYYMM.csv")
        return pd.DataFrame()

    frames = []
    for p in sorted(paths):
        try:
            df = pd.read_csv(p, dtype={"race_id": str})
            frames.append(df)
            print(f"[READ] {p} rows={len(df)}")
        except Exception as e:
            print(f"[WARN] failed to read {p}: {e}")

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    # 主キー重複は最初を優先（同一IDの月重複は基本起きない想定だが念のため）
    out = out.drop_duplicates("race_id")
    return out

def translate_master(df: pd.DataFrame) -> pd.DataFrame:
    """JP→EN 正規化（列名ゆらぎにも対応）。"""
    if df.empty:
        return df.copy()

    df = df.copy()

    # 列名ゆらぎ吸収
    rename_map = {
        "場所": "venue",
        "venue_jp": "venue",
        "surface_jp": "surface_type",
        "track_condition_jp": "track_condition",
        "track_condision_jp": "track_condition",  # タイポ対策
        "天候": "weather",
        "weather_jp": "weather",
    }
    df.rename(columns=rename_map, inplace=True)

    # venue
    if "venue" in df.columns:
        df["venue"] = df["venue"].map(VENUE_MAP).fillna(df["venue"])

    # surface_type
    if "surface_type" in df.columns:
        df["surface_type"] = df["surface_type"].map(SURFACE_MAP).fillna(df["surface_type"])

    # track_condition
    if "track_condition" in df.columns:
        df["track_condition"] = df["track_condition"].map(TRACK_COND_MAP).fillna(df["track_condition"])

    # weather
    if "weather" in df.columns:
        df["weather"] = df["weather"].replace(WEATHER_MAP)

    # num_horses が無い場合は作っておく（前段で結合しない構成でも壊れないように）
    if "num_horses" not in df.columns:
        df["num_horses"] = pd.NA

    # URL 列は名称が違うケースを吸収
    if "url_jp" not in df.columns:
        for cand in ["jp_url", "race_url", "race_url_jp", "url"]:
            if cand in df.columns:
                df.rename(columns={cand: "url_jp"}, inplace=True)
                break
    if "url_jp" not in df.columns:
        df["url_jp"] = pd.NA

    # 出力列を固定順に
    for c in EN_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df[EN_COLS].copy()

def _apply_strict_filter_if_requested(df: pd.DataFrame, strict: bool) -> pd.DataFrame:
    """必要なら最終段で厳密フィルタ（2/3歳・1/2勝・芝・距離 1000-1700）。"""
    if not strict or df.empty:
        return df

    # 前段の JP ファイルに依存する列（age_exact / race_class_jp / surface_jp / distance）が
    # 失われている場合に備え、元の列名が残っていればそれを参照する。
    # translate 前の列を保持している想定であれば、ここで再フィルタ可。
    # なければ EN ビューから判定可能な条件（surface_type / distance）だけ適用。
    have_jp_filter_cols = all(c in df.columns for c in ["surface_type", "distance"])
    if not have_jp_filter_cols:
        return df

    mask = (df["surface_type"] == "TURF") & df["distance"].between(1000, 1700, inclusive="both")
    # age / class は EN ビューには無いので、JP列が残っていればさらに掛ける
    age_col, class_col = None, None
    for c in ["age_exact", "age", "age_jp"]:
        if c in df.columns:
            age_col = c; break
    for c in ["race_class_jp", "race_class"]:
        if c in df.columns:
            class_col = c; break

    if age_col is not None:
        mask &= df[age_col].isin([2, 3])
    if class_col is not None:
        mask &= df[class_col].astype(str).isin(["1勝","2勝","1WIN","2WIN"])

    filtered = df[mask].copy()
    filtered = filtered.drop_duplicates("race_id")
    print(f"[STRICT] filtered {len(df)} -> {len(filtered)} rows")
    return filtered

def main():
    parser = argparse.ArgumentParser(description="Translate JP monthly masters to single EN master CSV.")
    parser.add_argument("--year-from", type=int, default=2024)
    parser.add_argument("--year-to", type=int, default=2024)
    parser.add_argument("--months", type=str, default=None, help="例: '1-12' or '1,2,3'")
    parser.add_argument("--strict", action="store_true", help="2/3歳・1/2勝・芝・距離1000-1700の厳密フィルタを適用")
    parser.add_argument("--out", type=str, default=str(OUT_CSV))
    args = parser.parse_args()

    months = _parse_months_arg(args.months)
    df_jp = _load_monthlies(args.year_from, args.year_to, months)

    if df_jp.empty:
        print("[WARN] No input rows. Nothing to write.")
        return

    print("📄 読み込んだ列（サンプル）:", df_jp.columns.tolist()[:25])
    df_en = translate_master(df_jp)
    df_en = _apply_strict_filter_if_requested(df_en, args.strict)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_en.to_csv(out_path, index=False)
    print(f"✅ wrote {out_path}, rows={len(df_en)}")

if __name__ == "__main__":
    main()