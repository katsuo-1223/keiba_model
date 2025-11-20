#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import pandas as pd
import numpy as np
from pathlib import Path


def simulate_roi(df: pd.DataFrame, thr: float = 1.0):
    # 条件: EV_return = p_win * odds_win > thr（既定=1.0）
    d = df.copy()
    d["odds_win"] = pd.to_numeric(d["odds_win"], errors="coerce")
    d = d.dropna(subset=["p_win", "odds_win"])  # 必須列

    d["ev_return"] = d["p_win"] * d["odds_win"]
    bets = d[d["ev_return"] > thr].copy()

    if bets.empty:
        return {"n_bets": 0, "stake": 0.0, "return": 0.0, "roi": np.nan}

    bets["stake"] = 1.0
    bets["hit_return"] = np.where(bets["FP"] == 1, bets["odds_win"], 0.0) \
        if "FP" in bets.columns else np.where(bets["fin_pos"] == 1, bets["odds_win"], 0.0)

    stake = bets["stake"].sum()
    ret = bets["hit_return"].sum()
    roi = ret / stake if stake > 0 else np.nan
    return {"n_bets": int(len(bets)), "stake": float(stake), "return": float(ret), "roi": float(roi)}


def per_race_topk(df: pd.DataFrame, k: int = 1):
    # 各レースで EV_return 上位kにベット
    d = df.copy()
    d["odds_win"] = pd.to_numeric(d["odds_win"], errors="coerce")
    d = d.dropna(subset=["p_win", "odds_win"])  # 必須
    d["ev_return"] = d["p_win"] * d["odds_win"]

    bets = (
        d.sort_values(["race_id", "ev_return"], ascending=[True, False])
        .groupby("race_id")
        .head(k)
    )

    bets["stake"] = 1.0
    bets["hit_return"] = np.where(bets["FP"] == 1, bets["odds_win"], 0.0) \
        if "FP" in bets.columns else np.where(bets["fin_pos"] == 1, bets["odds_win"], 0.0)

    stake = bets["stake"].sum()
    ret = bets["hit_return"].sum()
    roi = ret / stake if stake > 0 else np.nan
    return {"n_races": int(bets["race_id"].nunique()), "k": k, "stake": float(stake), "return": float(ret), "roi": float(roi)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/processed")
    ap.add_argument("--thr", type=float, default=1.0)
    ap.add_argument("--k", type=int, default=1)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    valid = pd.read_csv(data_dir / "valid_with_pred.csv")

    summary_thr = simulate_roi(valid, thr=args.thr)
    summary_topk = per_race_topk(valid, k=args.k)

    print("=== Threshold rule (EV_return > {:.2f}) ===".format(args.thr))
    for k, v in summary_thr.items():
        print(f"{k}: {v}")

    print("\n=== Per-race Top-{} by EV_return ===".format(args.k))
    for k, v in summary_topk.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()