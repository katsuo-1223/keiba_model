#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Summarize number of races and win counts per horse_id and jockey.
Input : data/processed/race_results_with_master.csv
Output:
  - data/processed/stats_horse.csv
  - data/processed/stats_jockey.csv
"""

import pandas as pd
from pathlib import Path

INPUT = "data/processed/race_results_with_master.csv"
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# === Load ===
df = pd.read_csv(INPUT)
df.columns = df.columns.str.strip()

# Detect columns automatically
fp_col = None
for c in df.columns:
    if c.lower() in ["fp", "finish", "fin_pos", "finish_position"]:
        fp_col = c
        break
if fp_col is None:
    raise ValueError("No finish position column (e.g., FP) found.")

# Convert to numeric if needed
df[fp_col] = pd.to_numeric(df[fp_col], errors="coerce")

# === Horse stats ===
if "horse_id" in df.columns:
    horse_stats = (
        df.groupby("horse_id")
        .agg(
            n_races=(fp_col, "count"),
            n_wins=(fp_col, lambda x: (x == 1).sum()),
        )
        .reset_index()
    )
    horse_stats["win_rate"] = (horse_stats["n_wins"] / horse_stats["n_races"]).round(3)
    horse_stats = horse_stats.sort_values("n_races", ascending=False)
    horse_stats.to_csv(OUT_DIR / "stats_horse.csv", index=False)
    print(f"✅ Saved horse stats: {OUT_DIR / 'stats_horse.csv'}")

# === Jockey stats ===
jockey_col = "jockey" if "jockey" in df.columns else None
if jockey_col:
    jockey_stats = (
        df.groupby(jockey_col)
        .agg(
            n_races=(fp_col, "count"),
            n_wins=(fp_col, lambda x: (x == 1).sum()),
        )
        .reset_index()
    )
    jockey_stats["win_rate"] = (jockey_stats["n_wins"] / jockey_stats["n_races"]).round(3)
    jockey_stats = jockey_stats.sort_values("n_races", ascending=False)
    jockey_stats.to_csv(OUT_DIR / "stats_jockey.csv", index=False)
    print(f"✅ Saved jockey stats: {OUT_DIR / 'stats_jockey.csv'}")

print("\nTop 5 horses:")
print(horse_stats.head())

print("\nTop 5 jockeys:")
print(jockey_stats.head())