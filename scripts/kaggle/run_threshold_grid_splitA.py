# scripts/kaggle/run_threshold_grid_splitA.py

from __future__ import annotations
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

BACKTEST_SCRIPT = ROOT / "scripts" / "kaggle" / "timeseries_backtest_win.py"

DATA_WITH_G1 = ROOT / "data" / "processed" / "kaggle" / "train_race_result_with_g1_splitA.csv"
DATA_WITHOUT_G1 = ROOT / "data" / "processed" / "kaggle" / "train_race_result_without_g1_splitA.csv"

OUTPUT_DIR = ROOT / "outputs" / "kaggle"
SUMMARY_PATH = OUTPUT_DIR / "roi_timeseries_summary.csv"
GRID_OUT_PATH = OUTPUT_DIR / "roi_threshold_grid_splitA.csv"


THRESHOLDS = [1.0, 1.5, 2.0, 2.5]


def run_backtest(data_path: Path, threshold: float) -> pd.DataFrame:
    """既存の timeseries_backtest_win.py を呼び出し、結果CSVを読み込む。"""
    print(f"[RUN] data={data_path.name}, threshold={threshold}")

    cmd = [
        sys.executable,
        str(BACKTEST_SCRIPT),
        "--data-path",
        str(data_path),
        "--output-dir",
        str(OUTPUT_DIR),
        "--threshold",
        str(threshold),
    ]
    subprocess.run(cmd, check=True)

    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(f"バックテスト結果が見つかりません: {SUMMARY_PATH}")

    df = pd.read_csv(SUMMARY_PATH)
    return df


def main() -> None:
    print("=== run_threshold_grid_splitA 開始 ===")
    print(f"[INFO] BACKTEST_SCRIPT: {BACKTEST_SCRIPT}")
    print(f"[INFO] OUTPUT_DIR     : {OUTPUT_DIR}")

    results = []

    # パターン1: g1_score_splitA あり
    for thr in THRESHOLDS:
        df = run_backtest(DATA_WITH_G1, thr)
        # SplitA だけに絞る
        df = df[df["split"] == "splitA"].copy()
        df["threshold"] = thr
        df["use_g1"] = True
        results.append(df)

    # パターン2: g1_score_splitA なし
    for thr in THRESHOLDS:
        df = run_backtest(DATA_WITHOUT_G1, thr)
        df = df[df["split"] == "splitA"].copy()
        df["threshold"] = thr
        df["use_g1"] = False
        results.append(df)

    all_df = pd.concat(results, ignore_index=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_df.to_csv(GRID_OUT_PATH, index=False)

    print(f"[DONE] まとめ結果を保存しました: {GRID_OUT_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()