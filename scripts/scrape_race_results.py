#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_race_results.py (v4: EN-site aware, encoding-safe)

Key points:
- Accepts EN URLs in --from-list (e.g., https://en.netkeiba.com/db/race/202406010107/)
- --site en|jp (default: en) controls which site to FETCH results from
- From-list robust scan (any column): extracts 12-digit race_id from jp/en URLs or plain IDs
- Discovery fallback still uses JP monthly list (stable filters). If you want EN-only flow,
  provide EN URLs via --from-list.
- Encoding-safe I/O, Excel friendly (default utf-8-sig)
- FP is horse number (3rd column)

Usage (EN site end-to-end from list):
  python scripts/scrape_race_results.py \
    --from-list data/raw/race_urls_2024_en.csv \
    --year-start 2024 --year-end 2024 \
    --months 1-12 \
    --site en \
    --output data/raw/race_results.csv

Multi-year (results fetch from EN):
  --year-start 2022 --year-end 2024 --site en
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------- Config ----------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.8,ja;q=0.6",
}

LIST_URL_TEMPLATE = (
    "https://db.netkeiba.com/?pid=race_list"
    "&track[]=1"
    "&start_year={y}&start_mon={m}&end_year={y}&end_mon={m}"
    "{venues}"
    "{barei}"
    "{grade}"
    "&kyori_min={dmin}&kyori_max={dmax}"
    "&sort=date"
    "&list=100"
)

VENUE_CODES = ["01","02","03","04","05","06","07","08","09","10"]
AGE_TO_BAREI = {"2": "11", "3": "12"}
WIN_CLASS_TO_GRADE = {"1": "6", "2": "7"}

RESULT_PAGE_URL_JP = "https://db.netkeiba.com/race/{race_id}/"
RESULT_PAGE_URL_EN = "https://en.netkeiba.com/db/race/{race_id}/"

REQUEST_TIMEOUT = 20
RETRY = 3
SLEEP_BASE = (0.8, 1.8)

# Race ID extraction
RID_12_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
RID_IN_URL_JP_RE = re.compile(r"/race/(\d{12})/")
RID_IN_URL_EN_RE = re.compile(r"/db/race/(\d{12})/")
HORSE_IN_URL_RE = re.compile(r"/horse/(\d+)/")

# Whitespace normalization
WS_RE = re.compile(r"\s+")

# -------------------- Utilities ---------------------

def _sleep():
    time.sleep(random.uniform(*SLEEP_BASE))

def _get(url: str) -> requests.Response:
    last_exc = None
    for i in range(RETRY):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if r.encoding is None or r.encoding.lower() in ("iso-8859-1", "ascii", "us-ascii"):
                r.encoding = r.apparent_encoding or "utf-8"
            if not r.encoding:
                r.encoding = "utf-8"
            if r.status_code == 200:
                return r
        except Exception as e:
            last_exc = e
        _sleep()
    if last_exc:
        raise last_exc
    r.raise_for_status()
    return r

def ensure_dir(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)

def sanitize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\xa0", " ").replace("\u3000", " ")
    s = WS_RE.sub(" ", s)
    return s.strip()

# -------------------- Discovery (JP list only) ---------------------

def build_list_url(y: int, m: int, venues: List[str], ages: List[str], win_classes: List[str], dmin: int, dmax: int) -> str:
    venues_q = "".join([f"&jyo[]={v}" for v in venues])
    barei_q = "".join([f"&barei[]={AGE_TO_BAREI[a]}" for a in ages if a in AGE_TO_BAREI])
    grade_q = "".join([f"&grade[]={WIN_CLASS_TO_GRADE[c]}" for c in win_classes if c in WIN_CLASS_TO_GRADE])
    return LIST_URL_TEMPLATE.format(y=y, m=m, venues=venues_q, barei=barei_q, grade=grade_q, dmin=dmin, dmax=dmax)

def discover_race_ids(year_start: int, year_end: int, months: List[int], venues: List[str], ages: List[str], win_classes: List[str], dmin: int, dmax: int) -> List[str]:
    rids: List[str] = []
    for y in range(year_start, year_end + 1):
        for m in months:
            url = build_list_url(y, m, venues, ages, win_classes, dmin, dmax)
            print(f"[INFO] Discover: {url}")
            r = _get(url)
            soup = BeautifulSoup(r.text, "lxml")
            month_ids = []
            for a in soup.find_all("a", href=True):
                mobj = RID_IN_URL_JP_RE.search(a["href"])
                if mobj:
                    month_ids.append(mobj.group(1))
            seen = set()
            month_ids = [x for x in month_ids if not (x in seen or seen.add(x))]
            print(f"[INFO]  -> found {len(month_ids)} race_ids for {y}-{m:02d}")
            rids.extend(month_ids)
            _sleep()
    seen = set()
    rids = [x for x in rids if not (x in seen or seen.add(x))]
    return rids

# -------------------- From-list extraction ---------------------

def read_csv_any_encoding(path: Path) -> pd.DataFrame:
    encodings = ("utf-8", "utf-8-sig", "cp932", "euc-jp")
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:
            last_err = e
    raise last_err if last_err else RuntimeError(f"Failed to read {path}")

def extract_race_ids_from_df(df: pd.DataFrame) -> List[str]:
    rids: List[str] = []
    for col in df.columns:
        series = df[col].astype(str).fillna("")
        for v in series:
            m = RID_12_RE.search(v)
            if m:
                rids.append(m.group(1)); continue
            m = RID_IN_URL_JP_RE.search(v)
            if m:
                rids.append(m.group(1)); continue
            m = RID_IN_URL_EN_RE.search(v)
            if m:
                rids.append(m.group(1)); continue
    seen = set()
    return [x for x in rids if not (x in seen or seen.add(x))]

def collect_race_ids_from_lists(list_paths: List[Path]) -> List[str]:
    all_ids: List[str] = []
    for p in list_paths:
        try:
            df = read_csv_any_encoding(p)
        except Exception as e:
            print(f"[WARN] read fail {p}: {e}")
            continue
        ids_ = extract_race_ids_from_df(df)
        print(f"[INFO] Extracted {len(ids_)} ids from {p.name}")
        all_ids.extend(ids_)
    seen = set()
    return [x for x in all_ids if not (x in seen or seen.add(x))]

# -------------------- Parse result page (JP/EN tolerant) ---------------------

def parse_results_page(html: str, race_id: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    table = (
        soup.find("table", id="race_table_01")
        or soup.find("table", class_="race_table_01")
        or soup.find("table", class_="db_h_race_results")
        or soup.find("table")
    )
    if not table:
        return []

    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all(["td","th"])
        if len(tds) < 8:
            continue
        head0 = tds[0].get_text(strip=True)
        if head0 in ("", "着順", "着順 ", "Pos", "Position"):
            continue

        def txt(i, default=""):
            if i >= len(tds):
                return default
            return sanitize_text(tds[i].get_text(strip=True))

        horse_id = ""
        for a in tr.find_all("a", href=True):
            m = HORSE_IN_URL_RE.search(a["href"])
            if m:
                horse_id = m.group(1)
                break

        row = {
            "race_id": race_id,
            "rank": txt(0),
            "FP": txt(2),
            "horse_name": txt(3),
            "horse_id": horse_id,
            "sex_age": txt(4),
            "weight": txt(5),
            "jockey": txt(6),
            "time": txt(7),
            "last3f": txt(11) if len(tds) > 11 else "",
            "odds": txt(12) if len(tds) > 12 else "",
            "pop": txt(13) if len(tds) > 13 else "",
        }
        rows.append(row)
    return rows

# -------------------- Writing results ---------------------

def load_done_ids(out_path: Path) -> set:
    if not out_path.exists():
        return set()
    try:
        df = pd.read_csv(out_path, usecols=["race_id"])
        return set(df["race_id"].astype(str).unique().tolist())
    except Exception:
        return set()

def scrape_results_for_ids(race_ids: List[str], out_path: Path, site: str, encoding: str):
    ensure_dir(out_path)
    done_ids = load_done_ids(out_path)
    new_count = 0

    url_tpl = RESULT_PAGE_URL_EN if site == "en" else RESULT_PAGE_URL_JP

    write_header = not out_path.exists()
    with out_path.open("a", newline="", encoding=encoding) as f:
        writer = None
        for rid in race_ids:
            rid = str(rid)
            if rid in done_ids:
                continue
            url = url_tpl.format(race_id=rid)
            try:
                r = _get(url)
            except Exception as e:
                print(f"[WARN] GET failed {url}: {e}")
                _sleep()
                continue

            rows = parse_results_page(r.text, rid)
            if not rows:
                print(f"[WARN] Parse produced 0 rows for {rid} ({site})")
                _sleep()
                continue

            if writer is None:
                fieldnames = list(rows[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                    write_header = False

            for row in rows:
                row = {k: sanitize_text(v) for k, v in row.items()}
                writer.writerow(row)
            f.flush()
            done_ids.add(rid)
            new_count += 1
            _sleep()

    print(f"[INFO] Scraped {new_count} races. (Per-horse rows written per race)")

# -------------------- CLI ---------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape race results (v4: EN-site aware, encoding-safe, robust list scan + discovery fallback)")
    p.add_argument("--from-list", nargs="*", help="race URL list CSV(s); any column ok; 12-digit ids or jp/en race URLs")
    p.add_argument("--year-start", type=int, required=True, help="start year (e.g., 2024)")
    p.add_argument("--year-end", type=int, required=True, help="end year (e.g., 2024)")
    p.add_argument("--months", type=str, default="1-12", help="months like '1-12' or '1,2,3'")
    p.add_argument("--site", choices=["en","jp"], default="en", help="which site to fetch results pages from")
    p.add_argument("--output", type=Path, required=True, help="output CSV path")
    p.add_argument("--encoding", type=str, default="utf-8-sig", help="output CSV encoding (utf-8-sig|utf-8|cp932|euc-jp)")

    # Discovery filters (JP list only)
    p.add_argument("--venues", type=str, default=",".join(VENUE_CODES), help="comma list of jyo codes 01..10")
    p.add_argument("--age", type=str, default="2,3", help="comma ages like '2,3' (mapped to barei=11,12)")
    p.add_argument("--win-class", type=str, default="1,2", help="comma win classes like '1,2' (mapped to grade=6,7)")
    p.add_argument("--dist-min", type=int, default=1000)
    p.add_argument("--dist-max", type=int, default=1700)
    return p.parse_args()

def parse_months(s: str) -> List[int]:
    s = s.strip()
    if "-" in s:
        a,b = s.split("-",1)
        return list(range(int(a), int(b)+1))
    return [int(x) for x in s.split(",") if x.strip()]

def main() -> int:
    args = parse_args()
    months = parse_months(args.months)

    race_ids: List[str] = []
    if args.from_list:
        print(f"[INFO] Using list files: {args.from_list}")
        list_paths = [Path(p) for p in args.from_list]
        race_ids = collect_race_ids_from_lists(list_paths)

    if not race_ids:
        print("[INFO] No ids found from list; falling back to discovery mode (JP list)")
        venues = [v for v in args.venues.split(",") if v in VENUE_CODES]
        ages = [a for a in args.age.split(",") if a in AGE_TO_BAREI]
        win_classes = [c for c in args.win_class.split(",") if c in WIN_CLASS_TO_GRADE]
        race_ids = discover_race_ids(args.year_start, args.year_end, months, venues, ages, win_classes, args.dist_min, args.dist_max)

    seen = set()
    race_ids = [x for x in race_ids if not (x in seen or seen.add(x))]
    print(f"[INFO] Target race_ids: {len(race_ids)}")

    scrape_results_for_ids(race_ids, args.output, site=args.site, encoding=args.encoding)
    print(f"[INFO] Done -> {args.output}")
    return 0

if __name__ == "__main__":
    sys.exit(main())