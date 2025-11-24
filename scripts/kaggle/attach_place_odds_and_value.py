# scripts/kaggle/attach_place_odds_and_value.py
"""
複勝オッズ（横持ちCSV）を縦持ちに変換し、
LightGBM の複勝予測結果に結合して期待値列を追加するスクリプト。

入力:
    - data/processed/kaggle/lgbm_place_pred.csv
        レースID, 馬番, pred_place など
    - data/raw/kaggle/19860105-20210731_odds.csv  (★あなたの複勝オッズ横持ちCSV)

出力:
    - data/processed/kaggle/lgbm_place_with_odds.csv
        レースID, 馬番, pred_place, 複勝オッズ, expected_value など
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

PRED_PATH = ROOT / "data" / "processed" / "kaggle" / "lgbm_place_pred.csv"
ODDS_WIDE_PATH = ROOT / "data" / "raw" / "kaggle" / "19860105-20210731_odds.csv"  # ★実際のファイル名に合わせてください
OUTPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "lgbm_place_with_odds.csv"


def load_predictions(path: Path) -> pd.DataFrame:
    print(f"[load_predictions] {path}")
    df = pd.read_csv(path)
    print(f"[load_predictions] {df.shape[0]:,} 行")
    return df


def load_odds_wide(path: Path) -> pd.DataFrame:
    print(f"[load_odds_wide] {path}")
    df = pd.read_csv(path)
    print(f"[load_odds_wide] {df.shape[0]:,} 行, {df.shape[1]} 列")
    return df


def odds_wide_to_long_place(df_wide: pd.DataFrame) -> pd.DataFrame:
    """
    横持ちオッズを「レースID, 馬番, 複勝オッズ」の縦持ちに変換する。
    期待する列名の例:
        複勝1_馬番, 複勝2_馬番, ..., 複勝5_馬番
        複勝1_オッズ, 複勝2_オッズ, ..., 複勝5_オッズ
    """
    rows = []

    max_n = 5  # 複勝1〜5 まである前提（足りない分は NaN でOK）

    for idx, row in df_wide.iterrows():
        race_id = row["レースID"]
        for n in range(1, max_n + 1):
            horse_col = f"複勝{n}_馬番"
            odds_col = f"複勝{n}_オッズ"

            if horse_col not in df_wide.columns or odds_col not in df_wide.columns:
                continue

            horse_no = row[horse_col]
            odds = row[odds_col]

            # 欠損や空欄はスキップ
            if pd.isna(horse_no) or pd.isna(odds):
                continue

            rows.append(
                {
                    "レースID": race_id,
                    "馬番": int(horse_no),
                    "複勝オッズ": float(odds),
                }
            )

    df_long = pd.DataFrame(rows)
    print(f"[odds_wide_to_long_place] 変換後: {df_long.shape[0]:,} 行")
    return df_long


def main() -> None:
    print("=== attach_place_odds_and_value.py 実行開始 ===")
    print(f"[INFO] PRED_PATH:       {PRED_PATH}")
    print(f"[INFO] ODDS_WIDE_PATH:  {ODDS_WIDE_PATH}")

    # 予測結果 & オッズ横持ちを読み込み
    df_pred = load_predictions(PRED_PATH)
    df_odds_wide = load_odds_wide(ODDS_WIDE_PATH)

    # レースID を文字列にそろえる
    df_pred["レースID"] = df_pred["レースID"].astype(str)
    df_odds_wide["レースID"] = df_odds_wide["レースID"].astype(str)

    # ★ 予測に存在するレースIDだけにオッズを絞る ★
    pred_ids = set(df_pred["レースID"].unique())
    df_odds_wide = df_odds_wide[df_odds_wide["レースID"].isin(pred_ids)]

    print(f"[filter race] 予測期間に含まれるレースのみ: {df_odds_wide.shape[0]:,} 行")

    # 横持ち → 縦持ち（レースID, 馬番, 複勝オッズ）
    df_place_odds = odds_wide_to_long_place(df_odds_wide)

    # 型合わせ（mergeキー）
    df_place_odds["レースID"] = df_place_odds["レースID"].astype(str)
    df_place_odds["馬番"] = df_place_odds["馬番"].astype(int)
    df_pred["馬番"] = df_pred["馬番"].astype(int)

    # レースID & 馬番 で結合（left join）
    df_merged = pd.merge(
        df_pred,
        df_place_odds,
        on=["レースID", "馬番"],
        how="left",
    )

    print(f"[merge] 結合後: {df_merged.shape[0]:,} 行")

    # 複勝オッズがない行を除外
    df_merged = df_merged.dropna(subset=["複勝オッズ"])
    print(f"[filter] 複勝オッズあり: {df_merged.shape[0]:,} 行")

    # === ★ ここを “倍率に変換して期待値1基準” に修正 ===
    df_merged["複勝オッズ_倍率"] = df_merged["複勝オッズ"] / 100.0

    df_merged["expected_value"] = (
        df_merged["pred_place"] * df_merged["複勝オッズ_倍率"]
    )
    # ===============================================

    # 保存
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_merged.to_csv(OUTPUT_PATH, index=False)
    print(f"[save] 保存完了: {OUTPUT_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()