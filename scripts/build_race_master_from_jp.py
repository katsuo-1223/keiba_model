# -*- coding: utf-8 -*-
"""
JPレース一覧（race_list）を主ソースにマスター生成。
一覧が0件のときは race_id を拾って JP詳細ページでフォールバック取得。
出力:
- data/raw/race_master_jp_YYYYMM.csv  (JP原本・月次)
- data/raw/race_master.csv            (英語整形 + upsert、統合)

対象条件（厳密フィルタ）:
- 芝（surface_jp == "芝"）
- 距離 1000〜1700m
- 年齢：2歳 or 3歳（"以上"は除外）
- クラス：1勝 or 2勝
"""

from __future__ import annotations
import re
import time
from pathlib import Path
from typing import Optional, List

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ========= 設定 =========
OUT_DIR = Path("data/raw")
OUT_DIR.mkdir(parents=True, exist_ok=True)

LIST_URL_TMPL = (
    "https://db.netkeiba.com/?pid=race_list"
    "&track[]={track}"
    "&start_year={year}&start_mon={mon}"
    "&end_year={year}&end_mon={mon}"
    "&jyo[]=01&jyo[]=02&jyo[]=03&jyo[]=04&jyo[]=05"
    "&jyo[]=06&jyo[]=07&jyo[]=08&jyo[]=09&jyo[]=10"
    "&barei[]=11&barei[]=12"  # 2歳=11, 3歳=12（※サイトの検索パラメータ）
    "&grade[]=6&grade[]=7"    # 1勝=6, 2勝=7
    "&kyori_min={dmin}&kyori_max={dmax}"
    "&sort=date"
    "&list=100"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

VENUE_MAP_JP_TO_EN = {
    "札幌":"SAPPORO","函館":"HAKODATE","福島":"FUKUSHIMA","新潟":"NIIGATA",
    "東京":"TOKYO","中山":"NAKAYAMA","中京":"CHUKYO","京都":"KYOTO",
    "阪神":"HANSHIN","小倉":"KOKURA",
}
SURFACE_MAP_JP_TO_EN = {"芝":"TURF","ダ":"DIRT","ダート":"DIRT"}
TRACK_COND_JP_TO_EN = {"良":"Gd","稍重":"Yld","重":"Sft","不良":"Hvy"}
WEATHER_JP_TO_EN = {
    "晴":"Sunny","晴れ":"Sunny",
    "曇":"Cloudy","曇り":"Cloudy",
    "雨":"Rainy","小雨":"Light Rain",
    "雪":"Snowy","小雪":"Light Snow",
}

# ========= 正規表現 =========
RID_IN_HREF_RE = re.compile(r"/race/(\d{12})/")
DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
VENUE_RE = re.compile(r"(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)")
SURFACE_RE = re.compile(r"(芝|ダ|ダート)[^\d]{0,5}(\d{3,4})m")
TRACK_COND_RE = re.compile(r"(良|稍重|重|不良)")
WEATHER_RE = re.compile(r"(天候[:：]?\s*)?(晴れ?|曇り?|雨|小雨|雪|小雪)")

# 年齢（2/3歳のみ、"以上"は除外）
AGE_EXACT_RE = re.compile(r'(?<!\d)([23])歳(?!以上)')
AGE_OR_OLDER_RE = re.compile(r'([2-9])歳以上')  # 除外検知用
# クラス（1勝/2勝）
CLASS_RE = re.compile(r'([12])勝(?:クラス)?')

# ========= HTTPセッション =========
_session = None
def _get_session():
    global _session
    if _session is not None:
        return _session
    s = requests.Session()
    try:
        retry = Retry(
            total=3, backoff_factor=0.6,
            status_forcelist=[429,500,502,503,504],
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
    except TypeError:
        retry = Retry(
            total=3, backoff_factor=0.6,
            status_forcelist=[429,500,502,503,504],
            method_whitelist=frozenset(["GET"]),
        )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter); s.mount("http://", adapter)
    s.headers.update(HEADERS)

    # Cookieウォームアップ（ブロック緩和）
    try:
        s.get("https://db.netkeiba.com/?pid=race_top", timeout=(5,15))
    except Exception:
        pass

    _session = s
    return s

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")

def fetch(url, sleep=0.2, timeout=20, referer=None):
    time.sleep(sleep)
    s = _get_session()
    headers = {}
    if referer:
        headers["Referer"] = referer
    resp = s.get(url, headers=headers, timeout=(5, timeout))
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text

# ========= 共通: 厳密フィルタ =========
def _apply_strict_filter(df: pd.DataFrame) -> pd.DataFrame:
    """芝/距離/年齢(2or3歳)/クラス(1勝or2勝) で厳密に絞る。欠損は除外。"""
    if df.empty:
        return df
    mask = (
        df["surface_jp"].isin(["芝"]) &
        df["distance"].between(1000, 1700, inclusive="both") &
        df["age_exact"].isin([2, 3]) &
        df["race_class_jp"].isin(["1勝", "2勝"])
    )
    return df[mask].drop_duplicates("race_id").reset_index(drop=True)

# ========= 一覧パース =========
def parse_race_list_page(html: str) -> pd.DataFrame:
    soup = _soup(html)
    table = soup.select_one("table.race_table_01")
    if table is None:
        # デバッグ保存
        dbg = OUT_DIR / "debug_race_list_latest.html"
        with open(dbg, "w", encoding="utf-8") as f:
            f.write(html)
        return pd.DataFrame()

    rows = []
    for tr in table.select("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue

        # date & venue
        date_text = tds[0].get_text(strip=True)
        date, venue = None, None
        m = DATE_RE.search(date_text)
        if m:
            y, mo, d = m.groups()
            date = "%04d-%02d-%02d" % (int(y), int(mo), int(d))
        m2 = VENUE_RE.search(date_text)
        if m2:
            venue = m2.group(1)

        # race_id
        a = tds[1].find("a", href=True)
        if not a:
            continue
        m3 = RID_IN_HREF_RE.search(a["href"])
        if not m3:
            continue
        rid = m3.group(1)
        race_name = a.get_text(strip=True)

        # 条件ブロック
        cond_text = tds[2].get_text(" ", strip=True)
        surface, distance, track_cond, weather = None, None, None, None
        age_exact, race_class_jp = None, None

        m4 = SURFACE_RE.search(cond_text)
        if m4:
            surface = m4.group(1)
            distance = int(m4.group(2))

        m5 = TRACK_COND_RE.search(cond_text)
        if m5:
            track_cond = m5.group(1)

        m6 = WEATHER_RE.search(cond_text)
        if m6:
            weather = m6.group(2) if m6.group(2) else m6.group(0)

        # 年齢（2/3歳のみ、"以上"は除外）
        if AGE_EXACT_RE.search(cond_text) and not AGE_OR_OLDER_RE.search(cond_text):
            age_exact = int(AGE_EXACT_RE.search(cond_text).group(1))

        # クラス（1勝/2勝）
        mc = CLASS_RE.search(cond_text)
        if mc:
            race_class_jp = f"{mc.group(1)}勝"

        rows.append({
            "race_id": rid,
            "date": date,
            "venue_jp": venue,
            "surface_jp": surface,
            "distance": distance,
            "track_condition_jp": track_cond,
            "weather_jp": weather,
            "age_exact": age_exact,
            "race_class_jp": race_class_jp,
            "url_jp": f"https://db.netkeiba.com/race/{rid}/",
            "race_name": race_name,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return _apply_strict_filter(df)

# ========= JP詳細ページ（フォールバック用） =========
def parse_jp_detail_by_rid(race_id: str) -> dict:
    """JP詳細ページから各項目を抽出（確実だが1件1リクエスト）"""
    url = f"https://db.netkeiba.com/race/{race_id}/"
    html = fetch(url, referer="https://db.netkeiba.com/?pid=race_top", timeout=20)
    soup = _soup(html)
    text = soup.get_text(" ", strip=True)

    # date
    date = None
    m = DATE_RE.search(text)
    if m:
        y, mo, d = m.groups()
        date = "%04d-%02d-%02d" % (int(y), int(mo), int(d))

    # venue
    venue = None
    m2 = VENUE_RE.search(text)
    if m2:
        venue = m2.group(1)

    # weather
    weather = None
    m6 = WEATHER_RE.search(text)
    if m6:
        weather = m6.group(2) if m6.group(2) else m6.group(0)

    # surface / distance
    surface, distance = None, None
    m4 = SURFACE_RE.search(text)
    if m4:
        surface = m4.group(1)
        distance = int(m4.group(2))

    # track_condition
    track_cond = None
    m5 = TRACK_COND_RE.search(text)
    if m5:
        track_cond = m5.group(1)

    # 年齢（2/3歳のみ、"以上"は除外）
    age_exact = None
    if AGE_EXACT_RE.search(text) and not AGE_OR_OLDER_RE.search(text):
        age_exact = int(AGE_EXACT_RE.search(text).group(1))

    # クラス（1勝/2勝）
    race_class_jp = None
    mc = CLASS_RE.search(text)
    if mc:
        race_class_jp = f"{mc.group(1)}勝"

    # race_name（任意）
    race_name = None
    a = soup.select_one('a[href*="/race/{}/"]'.format(race_id))
    if a:
        race_name = a.get_text(strip=True)

    return {
        "race_id": race_id,
        "date": date,
        "venue_jp": venue,
        "surface_jp": surface,
        "distance": distance,
        "track_condition_jp": track_cond,
        "weather_jp": weather,
        "age_exact": age_exact,
        "race_class_jp": race_class_jp,
        "url_jp": url,
        "race_name": race_name,
    }

def fallback_from_list_html(html: str) -> pd.DataFrame:
    """一覧HTMLから race_id 群だけ抽出し、JP詳細で埋めるフォールバック"""
    rids = list(dict.fromkeys(RID_IN_HREF_RE.findall(html)))  # 順序保持で重複除去
    rows = []
    for i, rid in enumerate(rids, 1):
        try:
            print(f"[FALLBACK] ({i}/{len(rids)}) {rid}")
            rows.append(parse_jp_detail_by_rid(rid))
        except Exception as e:
            print(f"[FALLBACK ERR] {rid}: {e}")
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return _apply_strict_filter(df)

# ========= 変換 / マージ =========
def normalize_to_en(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["venue"] = df["venue_jp"].map(VENUE_MAP_JP_TO_EN)
    df["surface_type"] = df["surface_jp"].replace(SURFACE_MAP_JP_TO_EN)
    df["track_condition"] = df["track_condition_jp"].replace(TRACK_COND_JP_TO_EN)
    df["weather"] = df["weather_jp"].replace(WEATHER_JP_TO_EN)
    return df

def coalesce_by_race_id(df: pd.DataFrame) -> pd.DataFrame:
    key = "race_id"
    cols = [c for c in df.columns if c != key]
    def first_notna(s: pd.Series):
        idx = s.first_valid_index()
        return s.loc[idx] if idx is not None else pd.NA
    agg_map = {c: ("max" if c == "num_horses" else first_notna) for c in cols}
    return df.groupby(key, as_index=False).agg(agg_map)

def merge_num_horses(df: pd.DataFrame) -> pd.DataFrame:
    results_csv = OUT_DIR / "race_results.csv"
    if results_csv.exists():
        res = pd.read_csv(results_csv, dtype={"race_id": str})
        num = res["race_id"].astype(str).value_counts().rename_axis("race_id").reset_index(name="num_horses")
        df = df.merge(num, how="left", on="race_id")
        print("[JP] merged num_horses from race_results.csv")
    else:
        df["num_horses"] = None
    return df

# ========= 月次ビルド =========
def build_race_master_jp(year: int, mon: int, track: int = 1, dmin: int = 1000, dmax: int = 1700) -> pd.DataFrame:
    url = LIST_URL_TMPL.format(year=year, mon=mon, track=track, dmin=dmin, dmax=dmax)
    print("[GET]", url)
    html = fetch(url, referer="https://db.netkeiba.com/?pid=race_top")
    print("[PARSE] race_list...")
    df = parse_race_list_page(html)

    if df.empty:
        print("[WARN] race_list parsed 0 rows. Falling back to detail scraping...")
        df = fallback_from_list_html(html)

    if df.empty:
        dbg = OUT_DIR / "debug_race_list_latest.html"
        with open(dbg, "w", encoding="utf-8") as f:
            f.write(html)
        raise RuntimeError("Parsed 0 rows (even after fallback). Debug saved: %s" % dbg)

    out_path = OUT_DIR / f"race_master_jp_{year}{mon:02d}.csv"
    df.to_csv(out_path, index=False)
    print(f"[JP] wrote {out_path} ({len(df)} rows)")
    return df

# ========= 英語整形（列セット統一） =========
_EN_COLS = ["race_id","date","venue","surface_type","distance","weather","track_condition","num_horses","url_jp"]

def to_en_view(jp_df: pd.DataFrame) -> pd.DataFrame:
    jp_df = merge_num_horses(jp_df)
    en_df = normalize_to_en(jp_df)
    en_df = en_df.reindex(columns=_EN_COLS)
    return en_df

# ========= バッチ実行（年範囲 × 月範囲） =========
def run_batch(
    year_from: int,
    year_to: int,
    months: Optional[List[int]] = None,
    track: int = 1,
    dmin: int = 1000,
    dmax: int = 1700,
    resume: bool = True,            # 既存CSVがあればスキップ
    write_master_each: bool = False # 月ごとに英語マスターへupsertするか（Falseなら最後に一括）
):
    if months is None:
        months = list(range(1, 12 + 1))

    en_frames = []  # 一括upsert用

    for y in range(year_from, year_to + 1):
        for m in months:
            jp_csv = OUT_DIR / f"race_master_jp_{y}{m:02d}.csv"
            if resume and jp_csv.exists() and jp_csv.stat().st_size > 100:
                print(f"[SKIP] {jp_csv.name} already exists")
                # 再利用して英語化
                try:
                    jp_df = pd.read_csv(jp_csv, dtype={"race_id": str})
                    # 念のため、厳密フィルタをもう一度適用（過去のCSVに混入があれば除去）
                    required_cols = {"surface_jp","distance","age_exact","race_class_jp"}
                    if required_cols.issubset(set(jp_df.columns)):
                        jp_df = _apply_strict_filter(jp_df)
                    en_df = to_en_view(jp_df)
                    if write_master_each:
                        _upsert_master(en_df)
                    else:
                        en_frames.append(en_df)
                except Exception as e:
                    print(f"[WARN] failed to reuse {jp_csv.name}: {e}")
                continue

            try:
                jp_df = build_race_master_jp(y, m, track, dmin, dmax)
                en_df = to_en_view(jp_df)
                if write_master_each:
                    _upsert_master(en_df)
                else:
                    en_frames.append(en_df)
            except Exception as e:
                print(f"[ERROR] {y}-{m:02d}: {e}")

    if not write_master_each and en_frames:
        new_en = pd.concat(en_frames, ignore_index=True, sort=False)
        _upsert_master(new_en)

def _upsert_master(en_df: pd.DataFrame):
    master_csv = OUT_DIR / "race_master.csv"
    if master_csv.exists():
        old = pd.read_csv(master_csv, dtype={"race_id": str})
        merged = pd.concat([old, en_df], ignore_index=True, sort=False)
    else:
        merged = en_df
    merged = coalesce_by_race_id(merged)
    merged.to_csv(master_csv, index=False)
    print("[EN] upsert -> %s (%d rows)" % (master_csv, len(merged)))

# ========= 互換 main（単月実行） =========
def main(year=2024, mon=1, track=1, dmin=1000, dmax=1700):
    jp_df = build_race_master_jp(year, mon, track, dmin, dmax)
    en_df = to_en_view(jp_df)
    _upsert_master(en_df)

# ========= エントリポイント =========
if __name__ == "__main__":
    # 使い方例:
    # 1) 2024年 全月（逐次upsert: True だと途中停止でも master が最新に）
    # run_batch(2024, 2024, resume=True, write_master_each=True)
    #
    # 2) 2022〜2024年（3年分）を一括upsertで更新
    # run_batch(2022, 2024, resume=True, write_master_each=False)
    #
    # デフォルト: 2024年 全月、一括upsert（既存JPは再利用）
    run_batch(
        year_from=2024,
        year_to=2024,
        months=None,           # None=1..12
        track=1,               # 芝
        dmin=1000, dmax=1700,
        resume=True,           # 既存JP CSVはスキップして再利用
        write_master_each=False
    )