#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Kaggle の JRA レース結果 CSV（日本語カラム）から、
必要なカラムだけを抽出して軽量ファイルを作成するスクリプト。

入力:
    data/raw/kaggle/19860105-20210731_race_result.csv （想定）

出力:
    data/processed/kaggle/jra_race_result_light.csv
    data/processed/kaggle/jra_race_result_light.parquet
"""

import argparse
import pathlib
import pandas as pd


# 抽出対象の日本語カラム名
USE_COLS = [
    "レースID",
    "レース日付",
    "競馬場コード",
    "競馬場名",
    "競争条件",
    "レース番号",
    "芝・ダート区分",
    "距離(m)",
    "天候",
    "馬場状態1",
    "馬場状態2",
    "着順",
    "着順注記",
    "枠番",
    "馬番",
    "馬名",
    "性別",
    "馬齢",
    "斤量",
    "騎手",
    "タイム",          # 文字列として保持
    "上り",
    "単勝",
    "人気",
    "馬体重",
    "場体重増減",
    "調教師",
    "賞金(万円)",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract necessary columns from JRA race result CSV (Japanese columns)."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/raw/kaggle/19860105-20210731_race_result.csv",
        help="入力CSVパス（デフォルト: data/raw/kaggle/19860105-20210731_race_result.csv）",
    )
    parser.add_argument(
        "--out-csv",
        type=str,
        default="data/processed/kaggle/jra_race_result_light.csv",
        help="出力する軽量CSVのパス",
    )
    parser.add_argument(
        "--out-parquet",
        type=str,
        default="data/processed/kaggle/jra_race_result_light.parquet",
        help="出力するParquetのパス",
    )
    return parser.parse_args()


def time_to_seconds(val):
    """
    'M:SS.S' 形式などのタイム文字列を秒(float)に変換する。
    例:
        '1:34.3' -> 94.3
        '59.8'   -> 59.8
    変換できない場合は pd.NA を返す。
    """
    if pd.isna(val):
        return pd.NA
    s = str(val).strip()
    if s == "" or s.lower() == "nan":
        return pd.NA

    # M:SS.S 形式
    if ":" in s:
        try:
            m_str, sec_str = s.split(":", 1)
            minutes = int(m_str)
            seconds = float(sec_str)
            return minutes * 60 + seconds
        except Exception:
            return pd.NA
    else:
        # 単に '59.8' などのケース
        try:
            return float(s)
        except Exception:
            return pd.NA


def main() -> None:
    args = parse_args()

    input_path = pathlib.Path(args.input)
    out_csv_path = pathlib.Path(args.out_csv)
    out_parquet_path = pathlib.Path(args.out_parquet)

    print(f"[LOAD] {input_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    df = pd.read_csv(input_path, usecols=USE_COLS)

    # ---- 型を整える ----

    # レース日付: '1986-06-07' 形式なので、format は指定せず自動判別に任せる
    if "レース日付" in df.columns:
        df["レース日付"] = pd.to_datetime(df["レース日付"], errors="coerce")

    # 数値にしておきたいカラム（タイムは別処理）
    numeric_cols = [
        "レース番号",
        "距離(m)",
        "着順",
        "枠番",
        "馬番",
        "馬齢",
        "斤量",
        "上り",
        "単勝",
        "人気",
        "馬体重",
        "場体重増減",
        "賞金(万円)",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # タイムを秒に変換したカラムを追加（元のタイム文字列も残す）
    if "タイム" in df.columns:
        df["タイム_秒"] = df["タイム"].apply(time_to_seconds)

    # 出力ディレクトリ作成
    out_csv_path.parent.mkdir(parents=True, exist_ok=True)
    out_parquet_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[SAVE] CSV -> {out_csv_path}")
    df.to_csv(out_csv_path, index=False)

    # pyarrow / fastparquet がない場合でも止まらないように try/except
    try:
        print(f"[SAVE] Parquet -> {out_parquet_path}")
        df.to_parquet(out_parquet_path, index=False)
    except ImportError as e:
        print("[WARN] Parquet 出力用のエンジン(pyarrow / fastparquet)が見つかりませんでした。")
        print("       CSV は出力済みです。Parquet も使いたい場合は pyarrow のインストールを検討してください。")
        print(f"       詳細: {e}")

    print("[DONE] 必要カラムのみを抽出した JRA レース結果ファイルを作成しました。")


if __name__ == "__main__":
    main()