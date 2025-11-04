# scripts/fetch_race_results_from_list.py
from __future__ import annotations
import re
import time
from pathlib import Path
from typing import List, Dict
from io import StringIO

import pandas as pd
import requests

INPUT_CSV = "data/raw/race_urls_jan2024_cleaned.csv"
OUT_DIR = Path("data/raw")
OUT_CSV = OUT_DIR / "race_results.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 列名の正規化（en / jp どちらでもOK）
COLMAP: Dict[str, str] = {
    # 日本語
    "着順": "finish",
    "枠番": "bracket",
    "馬番": "num",
    "馬名": "horse",
    "性齢": "sex_age",
    "斤量": "weight_carried",
    "騎手": "jockey",
    "タイム": "time",
    "着差": "margin",
    "通過": "passing",
    "上り": "last3f",
    "単勝": "win_odds",
    "人気": "pop",
    "馬体重": "horse_weight",
    "調教師": "trainer",
    # 英語
    "Fin": "finish",
    "Finish": "finish",
    "Br": "bracket",
    "No.": "num",
    "Horse": "horse",
    "Sex/Age": "sex_age",
    "Weight": "weight_carried",
    "Jockey": "jockey",
    "Time": "time",
    "Margin": "margin",
    "Passing": "passing",
    "Last 3F": "last3f",
    "Win odds": "win_odds",
    "Pop": "pop",
    "Horse weight": "horse_weight",
    "Trainer": "trainer",
}

def extract_race_id(url: str) -> str | None:
    """URL中の最後の12桁を race_id として抽出。"""
    if not isinstance(url, str):
        return None
    m = re.findall(r"(\d{12})", url)
    return m[-1] if m else None

def choose_result_table(tables: List[pd.DataFrame]) -> pd.DataFrame:
    """候補テーブルの中から結果表らしいものを選択。"""
    cand = []
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        joined = " ".join(cols)
        if (("着順" in joined and "馬名" in joined) or
            ("Horse" in joined and ("Fin" in joined or "Finish" in joined))):
            cand.append(t)
    if cand:
        return cand[0]
    return max(tables, key=lambda df: df.shape[1])

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [COLMAP.get(str(c).strip(), str(c).strip()) for c in df.columns]

    # 稀に1行目がヘッダ化している崩れ対策（軽め）
    if 0 in df.index:
        row0 = [str(x) for x in df.iloc[0].tolist()]
        if any(x in COLMAP for x in row0) or ("Horse" in "".join(row0)) or ("馬名" in "".join(row0)):
            df = df.iloc[1:].reset_index(drop=True)

    # 型整形（落ちないように寛容）
    for c in ["finish", "bracket", "num", "pop"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "win_odds" in df.columns:
        df["win_odds"] = pd.to_numeric(df["win_odds"], errors="coerce")

    # 性齢 → sex, age
    if "sex_age" in df.columns:
        sex_age = df["sex_age"].astype(str)
        m = sex_age.str.extract(r"([牡牝セ騙MF])\s*[-/]?\s*(\d+)")
        df["sex"] = m[0]
        df["age"] = pd.to_numeric(m[1], errors="coerce")

    # 馬体重 "(486(+4))" → 数値に分解
    if "horse_weight" in df.columns:
        hw = df["horse_weight"].astype(str)
        m = hw.str.extract(r"(\d+)\s*\(([-+]\d+)\)")
        df["horse_weight_kg"] = pd.to_numeric(m[0], errors="coerce")
        df["weight_diff"] = pd.to_numeric(m[1], errors="coerce")

    return df

def fetch_one(url: str, sleep_sec: float = 0.8, timeout: int = 25) -> pd.DataFrame:
    """レース結果1ページ分を取得して正規化。"""
    time.sleep(sleep_sec)
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    tables = pd.read_html(StringIO(r.text))
    if not tables:
        raise ValueError("No tables found")

    df = choose_result_table(tables)
    df = normalize_columns(df)

    # race_id を先頭、url を末尾へ
    rid = extract_race_id(url) or ""
    df.insert(0, "race_id", rid)
    df["url"] = url  # 末尾に自動追加（後で列順を整える）

    return df

def read_urls_from_csv(path: str) -> List[str]:
    """列名が不定でも、セル中の http* をURLとして抽出。"""
    df = pd.read_csv(path)
    for cand in ["Race URL", "race_url", "url"]:
        if cand in df.columns:
            urls = df[cand].dropna().astype(str).tolist()
            return [u.strip() for u in urls if u.startswith("http")]
    urls = []
    for col in df.columns:
        urls.extend([str(x).strip() for x in df[col].dropna().astype(str) if x.startswith("http")])
    return sorted(set(urls))

def stable_col_order(df: pd.DataFrame) -> pd.DataFrame:
    """race_id を最左、url を最右に配置する列順へ整列。"""
    cols = list(df.columns)
    # 先頭: race_id
    if "race_id" in cols:
        cols.remove("race_id")
        cols = ["race_id"] + cols
    # 最後: url
    if "url" in cols:
        cols.remove("url")
        cols = cols + ["url"]
    return df.reindex(columns=cols)

def upsert_to_out_csv(new_df: pd.DataFrame, out_csv: Path) -> None:
    """既存CSVに追記（同一レース・同一馬番の重複を除去）。"""
    new_df = stable_col_order(new_df)

    if out_csv.exists():
        old = pd.read_csv(out_csv)
        # 列揃え（新旧で差があっても union で合わせる）
        all_cols = list(dict.fromkeys(list(old.columns) + list(new_df.columns)))
        old = old.reindex(columns=all_cols)
        new_df = new_df.reindex(columns=all_cols)

        merged = pd.concat([old, new_df], ignore_index=True)
        subset = ["race_id", "num"] if "num" in merged.columns else ["race_id", "horse", "jockey"]
        merged = merged.drop_duplicates(subset=subset, keep="last")
        merged.to_csv(out_csv, index=False)
    else:
        new_df.to_csv(out_csv, index=False)

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    urls = read_urls_from_csv(INPUT_CSV)
    if not urls:
        raise SystemExit(f"No URLs found in {INPUT_CSV}")

    errors = []
    batch_rows = []

    for url in urls:
        try:
            df = fetch_one(url)
            batch_rows.append(df)
            print(f"[OK] fetched: {url}")
        except Exception as e:
            print(f"[ERR] {url} : {e}")
            rid = extract_race_id(url)
            errors.append({"url": url, "race_id": rid, "error": str(e)})

    if batch_rows:
        batch_df = pd.concat(batch_rows, ignore_index=True, sort=False)
        upsert_to_out_csv(batch_df, OUT_CSV)
        print(f"\n✅ Appended to {OUT_CSV}")

    if errors:
        err_df = pd.DataFrame(errors)
        err_path = OUT_DIR / "fetch_errors.csv"
        err_df.to_csv(err_path, index=False)
        print(f"Completed with errors. See: {err_path}")
    else:
        print("Completed successfully.")

if __name__ == "__main__":
    main()