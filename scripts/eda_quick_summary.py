#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EDA quick summary (EN-only merged data)
- Input : data/processed/race_results_with_master.csv
- Output: data/processed/eda_* と plot_*.png
"""

import re, numpy as np, pandas as pd, matplotlib.pyplot as plt
from pathlib import Path

IN_PATH = Path("data/processed/race_results_with_master.csv")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def to_float(x):
    try: return float(str(x).replace(",", "").strip())
    except: return np.nan

def parse_distance(v):
    m = re.search(r"(\d{3,4})", str(v)); return float(m.group(1)) if m else np.nan

def parse_last3f(v):
    s = str(v).strip().replace(",", "")
    try: return float(s)
    except: return np.nan

def parse_body_weight(v):
    m = re.search(r"(-?\d{3})(?:\(|$)", str(v)); return float(m.group(1)) if m else np.nan

def main():
    df = pd.read_csv(IN_PATH, encoding="utf-8-sig")
    work = df.copy()

    # ヘッダー混入の最終防御
    if "FP" in work.columns:
        bad = work["FP"].astype(str).str.fullmatch(r"FP", case=False, na=False)
        work = work[~bad].copy()

    work["finish_pos"] = pd.to_numeric(work.get("FP"), errors="coerce").astype("Int64")
    work["odds"] = pd.to_numeric(work.get("odds"), errors="coerce")
    if work["odds"].isna().mean() > 0.5:
        work["odds"] = work["odds"].apply(to_float)

    # popularity が無ければオッズ昇順で推定
    if "popularity" in work.columns:
        pop = pd.to_numeric(work["popularity"], errors="coerce")
    else:
        pop = np.nan
    if pd.isna(pop).mean() > 0.4:
        work["popularity"] = work.groupby("race_id")["odds"].rank(method="min", ascending=True)
    else:
        work["popularity"] = pop

    # 距離/上り/馬体重
    if "distance" in work.columns:
        work["distance_m"] = work["distance"].apply(parse_distance)
    else:
        work["distance_m"] = np.nan
    work["last3f_num"] = work.get("last3f", np.nan).apply(parse_last3f)

    if "horse_weight" in work.columns:
        work["horse_weight_kg"] = work["horse_weight"].apply(parse_body_weight)
    else:
        work["horse_weight_kg"] = np.nan

    valid = work.dropna(subset=["finish_pos","odds","distance_m"]).copy()
    valid["win"]  = (valid["finish_pos"]==1).astype(int)
    valid["top3"] = (valid["finish_pos"]<=3).astype(int)
    valid["bet"]  = 100.0
    valid["ret"]  = np.where(valid["win"]==1, valid["odds"]*100.0, 0.0)

    # ビン
    valid["dist_bin"] = pd.cut(valid["distance_m"],
                               bins=[0,1200,1400,1600,1800,10000],
                               labels=["<=1200","1201-1400","1401-1600","1601-1800","1801+"],
                               include_lowest=True)

    def pop_bucket(p):
        if pd.isna(p): return np.nan
        p = int(np.floor(p))
        return "1" if p==1 else "2" if p==2 else "3" if p==3 else "4-5" if 4<=p<=5 else "6-9" if 6<=p<=9 else "10+"
    valid["pop_bucket"] = valid["popularity"].apply(pop_bucket)

    # 集計
    pop_summ = valid.groupby("pop_bucket").agg(
        n=("finish_pos","size"),
        win_rate=("win","mean"),
        top3_rate=("top3","mean"),
        avg_odds=("odds","mean"),
        total_bet=("bet","sum"),
        total_ret=("ret","sum")
    ).reset_index().sort_values("pop_bucket")
    if len(pop_summ):
        pop_summ["win_rate"] = (pop_summ["win_rate"]*100).round(1)
        pop_summ["top3_rate"] = (pop_summ["top3_rate"]*100).round(1)
        pop_summ["avg_odds"]  = pop_summ["avg_odds"].round(2)
        pop_summ["roi_pct"]   = (pop_summ["total_ret"]/pop_summ["total_bet"]*100).round(1)

    dist_summ = valid.groupby("dist_bin").agg(
        n=("finish_pos","size"),
        avg_last3f=("last3f_num","mean"),
        win_rate=("win","mean"),
        top3_rate=("top3","mean")
    ).reset_index()
    if len(dist_summ):
        dist_summ["win_rate"]   = (dist_summ["win_rate"]*100).round(1)
        dist_summ["top3_rate"]  = (dist_summ["top3_rate"]*100).round(1)
        dist_summ["avg_last3f"] = dist_summ["avg_last3f"].round(2)

    # 保存
    pop_summ.to_csv(OUT_DIR/"eda_popularity_summary.csv", index=False)
    dist_summ.to_csv(OUT_DIR/"eda_distance_summary.csv", index=False)
    valid[["race_id","finish_pos","popularity","odds","distance_m","last3f_num","horse_weight_kg","dist_bin"]].head(200)\
        .to_csv(OUT_DIR/"eda_valid_preview.csv", index=False)

    # 図
    plt.figure()
    plt.scatter(valid["popularity"], valid["finish_pos"], alpha=0.4)
    plt.gca().invert_yaxis()
    plt.xlabel("Popularity (1=favorite)"); plt.ylabel("Finish Position"); plt.title("Popularity vs Finish Position")
    plt.savefig(OUT_DIR/"plot_popularity_vs_finish.png", bbox_inches="tight"); plt.close()

    plt.figure()
    plt.scatter(valid["odds"], valid["finish_pos"], alpha=0.4)
    plt.gca().invert_yaxis()
    plt.xlabel("Win Odds"); plt.ylabel("Finish Position"); plt.title("Odds vs Finish Position")
    plt.savefig(OUT_DIR/"plot_odds_vs_finish.png", bbox_inches="tight"); plt.close()

    print("[OK] EDA files written under", OUT_DIR)

if __name__ == "__main__":
    main()