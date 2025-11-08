#!/usr/bin/env python3
"""
merge_results_with_master.py (lean version)

Inputs are **English-only CSVs** with consistent schemas.
- Merge `race_results.csv` (per-horse rows) and `race_master.csv` (per-race rows) on `race_id`.
- Compute `num_horses` per race **from results** as `max(FP)` and attach to master before merging.
- No JP/EN normalization or fuzzy schema handling.

Usage:
    python scripts/merge_results_with_master.py \
      --results data/raw/race_results.csv \
      --master  data/raw/race_master.csv \
      --output  data/processed/race_results_with_master.csv \
      --join    inner

Notes:
- Expects columns: results -> [race_id, FP, ...], master -> [race_id, ...]
- `--join` can be `inner` (default) or `left` (results-kept left join).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List

import pandas as pd

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
LOG_FMT = "[%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
logger = logging.getLogger("merge")

# ------------------------------------------------------------
# Core
# ------------------------------------------------------------

def run(
    results_path: Path,
    master_path: Path,
    output_path: Path,
    join_how: str = "inner",
) -> None:
    # 1) Load
    logger.info("Reading results: %s", results_path)
    results = pd.read_csv(results_path)
    logger.info("Reading master : %s", master_path)
    master = pd.read_csv(master_path)

    # 2) Validate minimal schema
    for name, df, need in [
        ("results", results, ["race_id", "FP"]),
        ("master", master, ["race_id"]),
    ]:
        missing = [c for c in need if c not in df.columns]
        if missing:
            raise KeyError(f"{name}: missing required columns: {missing}")

    # Ensure race_id as string to avoid dtype mismatches
    results["race_id"] = results["race_id"].astype(str)
    master["race_id"] = master["race_id"].astype(str)

    # 3) num_horses from results (max FP per race)
    logger.info("Calculating num_horses from results (max FP per race_id)")
    num_horses_df = (
        results.groupby("race_id")["FP"]
        .max()
        .rename("num_horses")
        .reset_index()
    )
    # Prefer integer dtype if clean
    try:
        num_horses_df["num_horses"] = pd.to_numeric(num_horses_df["num_horses"], errors="raise").astype("Int64")
    except Exception:
        num_horses_df["num_horses"] = pd.to_numeric(num_horses_df["num_horses"], errors="coerce").astype("Int64")

    master = master.merge(num_horses_df, on="race_id", how="left")
    logger.info("num_horses annotated on master (non-null: %d)", master["num_horses"].notna().sum())

    # 4) Merge results x master
    logger.info("Merging on race_id (how=%s)", join_how)
    merged = results.merge(master, on="race_id", how=join_how, suffixes=("_res", "_mst"))

    # 5) Optional nice ordering if common fields exist
    pref = [
        "race_id", "date", "race_name", "course", "surface", "distance", "weather", "going",
        "num_horses",  # newly added
        "horse_id", "horse_name", "rank", "FP", "pop", "odds", "time", "last3f", "weight",
    ]
    cols_exist = [c for c in pref if c in merged.columns]
    others = [c for c in merged.columns if c not in cols_exist]
    merged = merged[cols_exist + others]

    # Stable sort if keys available
    sort_keys = [c for c in ["date", "race_id", "rank", "FP"] if c in merged.columns]
    if sort_keys:
        merged = merged.sort_values(sort_keys).reset_index(drop=True)

    # 6) Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    logger.info("Saved: %s (rows=%d, cols=%d)", output_path, merged.shape[0], merged.shape[1])


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge race results with master and compute num_horses from FP")
    p.add_argument("--results", type=Path, required=True, help="path to race_results.csv")
    p.add_argument("--master", type=Path, required=True, help="path to race_master.csv")
    p.add_argument("--output", type=Path, required=True, help="output CSV path")
    p.add_argument("--join", choices=["inner", "left"], default="inner")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
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