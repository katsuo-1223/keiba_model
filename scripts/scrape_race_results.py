#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_race_results.py (v6, EN-only / header-safe version)

目的:
- 英語版 Netkeiba (https://en.netkeiba.com/db/race/XXXX/) からレース結果を安全にスクレイピングし、
  列ズレ・ヘッダ混入のないCSVを生成する。

特徴:
- <th>の見出しから列→キーをマッピングし、<td>のみで本文行を抽出（列位置に依存しない）
- データ中にヘッダ行（"FP / PP / Horse / A&S / ..." 等）が再登場しても自動スキップ
- 馬IDは <a href="/horse/XXXX/"> から抽出
- 出力は固定カラム順 (UTF-8-SIG)
"""

from __future__ import annotations
import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

import requests
import pandas as pd
from bs4 import BeautifulSoup

# ----------------------------------------------------
# Logging
# ----------------------------------------------------
LOG_FMT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
logger = logging.getLogger("scrape_results_en")

# ----------------------------------------------------
# Constants
# ----------------------------------------------------
RESULT_PAGE_URL_EN = "https://en.netkeiba.com/db/race/{race_id}/"
RID_12_RE = re.compile(r"\b(\d{12})\b")
RID_IN_URL_EN_RE = re.compile(r"/db/race/(\d{12})")
HORSE_IN_URL_RE = re.compile(r"/horse/(\d+)/")

# ----------------------------------------------------
# Utilities
# ----------------------------------------------------
def fetch_html(url: str, timeout: int = 20, tries: int = 3, sleep_sec: float = 0.8) -> str:
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and r.text:
                return r.text
            last_err = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last_err = e
        time.sleep(sleep_sec)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")

def extract_race_ids_from_df(df: pd.DataFrame) -> List[str]:
    rids: List[str] = []
    for col in df.columns:
        series = df[col].astype(str).fillna("")
        for v in series:
            m = RID_12_RE.search(v)
            if m:
                rids.append(m.group(1))
                continue
            m = RID_IN_URL_EN_RE.search(v)
            if m:
                rids.append(m.group(1))
                continue
    # 重複除去
    seen = set()
    out: List[str] = []
    for rid in rids:
        if rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out

def _norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _en_header_to_key(header_text: str) -> Optional[str]:
    """ENテーブルの<th>文字列を正規化キーに変換"""
    h = _norm(header_text).lower()
    if h in {"pos", "position", "fp"}:   return "FP"
    if h in {"pp"}:                      return "PP"
    if h in {"horse"}:                   return "horse_name"
    if h in {"a&s", "a & s"}:            return "sex_age"
    if h in {"wgt.(kg)", "wgt (kg)"}:    return "weight"
    if h in {"jockey"}:                  return "jockey"
    if h in {"ft", "time"}:              return "time"
    if h in {"l3f", "last3f"}:           return "last3f"
    if h in {"odds"}:                    return "odds"
    if h in {"fav", "pop"}:              return "popularity"
    if h in {"horse wgt.(kg)", "horse wgt (kg)"}: return "horse_weight"
    return None

# ----------------------------------------------------
# Parser (EN only)
# ----------------------------------------------------
def parse_en_race_results_table(html: str, race_id: str) -> List[Dict[str, str]]:
    """
    ENサイトの結果テーブルを安全にパースする。
    - <th>を見出しとしてマッピング、<td>のみをデータとして抽出
    - ヘッダ行再登場をスキップ
    """
    soup = BeautifulSoup(html, "lxml")

    table = soup.find("table", id="db_h_race_results")
    if not table:
        table = soup.find("table")
    if not table:
        return []

    # ヘッダ <th>
    header_tr = None
    for tr in table.find_all("tr"):
        ths = tr.find_all("th")
        if ths and len(ths) >= 3:
            header_tr = tr
            break
    if not header_tr:
        return []

    header_cells = [_norm(th.get_text(strip=True)) for th in header_tr.find_all("th")]
    col_to_key: Dict[int, str] = {}
    for idx, htxt in enumerate(header_cells):
        k = _en_header_to_key(htxt)
        if k:
            col_to_key[idx] = k
    if not col_to_key:
        return []

    # データ <tr>
    tb = table.find("tbody")
    body_trs = tb.find_all("tr") if tb else [tr for tr in table.find_all("tr") if not tr.find("th")]

    header_tokens = {"FP","PP","Horse","A&S","Wgt.(kg)","Jockey","FT","Odds","Fav","Horse Wgt.(kg)"}
    rows: List[Dict[str, str]] = []

    for tr in body_trs:
        tds = tr.find_all("td")
        if not tds:
            continue

        # 行全体にヘッダ語が含まれる場合はスキップ
        row_text = " ".join(td.get_text(strip=True) for td in tds)
        if any(tok in row_text for tok in header_tokens):
            continue

        data: Dict[str, str] = {}
        for idx, td in enumerate(tds):
            if idx not in col_to_key:
                continue
            key = col_to_key[idx]
            val = td.get_text(strip=True)

            if key == "horse_name":
                horse_id = ""
                a = td.find("a", href=True)
                if a:
                    m = HORSE_IN_URL_RE.search(a["href"])
                    if m:
                        horse_id = m.group(1)
                data["horse_id"] = horse_id

            data[key] = val

        # 有効行チェック
        if not any(k in data for k in ("FP","horse_name")):
            continue

        data["race_id"] = str(race_id)
        for k in ("FP","PP","horse_name","horse_id","sex_age","weight","jockey",
                  "time","last3f","odds","popularity","horse_weight"):
            data.setdefault(k, "")
        rows.append(data)

    return rows

# ----------------------------------------------------
# CLI
# ----------------------------------------------------
def build_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--from-list", type=Path, required=True,
                   help="CSV/TSV/TXT with race URLs or 12-digit race_ids")
    p.add_argument("--output", type=Path, required=True,
                   help="Output CSV path")
    p.add_argument("--encoding", type=str, default="utf-8-sig",
                   help="Output encoding (default: utf-8-sig)")
    p.add_argument("--sleep", type=float, default=0.8,
                   help="Sleep seconds between requests")
    p.add_argument("--limit", type=int, default=0,
                   help="Optional limit for debugging (0 = no limit)")
    return p.parse_args()

def read_any_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx",".xls"}:
        return pd.read_excel(path)
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.read_csv(path, sep="\t")

def ensure_columns_order(df: pd.DataFrame) -> pd.DataFrame:
    pref = ["race_id","FP","PP","horse_name","horse_id","sex_age","weight",
            "jockey","time","last3f","odds","popularity","horse_weight"]
    for c in pref:
        if c not in df.columns:
            df[c] = ""
    others = [c for c in df.columns if c not in pref]
    return df[pref + others]

# ----------------------------------------------------
# Main
# ----------------------------------------------------
def main() -> int:
    args = build_args()
    src_df = read_any_table(args.from_list)
    rids = extract_race_ids_from_df(src_df)
    if args.limit and args.limit > 0:
        rids = rids[:args.limit]
    if not rids:
        logger.error("No race_id found in: %s", args.from_list)
        return 2

    logger.info("Targets: %d races", len(rids))
    rows_all: List[Dict[str, str]] = []

    for i, rid in enumerate(rids, 1):
        url = RESULT_PAGE_URL_EN.format(race_id=rid)
        try:
            html = fetch_html(url)
            rows = parse_en_race_results_table(html, rid)
            if not rows:
                logger.warning("No rows parsed: race_id=%s", rid)
            rows_all.extend(rows)
        except Exception as e:
            logger.warning("Failed to parse race_id=%s: %s", rid, e)
        time.sleep(args.sleep)
        if i % 50 == 0:
            logger.info("Progress: %d / %d", i, len(rids))

    if not rows_all:
        logger.error("No results parsed at all.")
        return 3

    out_df = pd.DataFrame(rows_all)
    out_df = ensure_columns_order(out_df)
    before = len(out_df)
    out_df = out_df.drop_duplicates(subset=["race_id","horse_name","jockey","time"], keep="first")
    logger.info("Dedup: %d -> %d", before, len(out_df))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False, encoding=args.encoding)
    logger.info("Wrote: %s (rows=%d, cols=%d)", args.output, out_df.shape[0], out_df.shape[1])
    return 0

if __name__ == "__main__":
    sys.exit(main())