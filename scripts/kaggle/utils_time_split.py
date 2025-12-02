# scripts/kaggle/utils_time_split.py

from __future__ import annotations

import pandas as pd


def add_race_date(df: pd.DataFrame, date_col: str = "レース日付") -> pd.DataFrame:
    """
    レース日付を datetime 型に変換して返すユーティリティ。

    - 文字列 'YYYY-MM-DD' でも
    - すでに datetime 型でも

    pd.to_datetime で安全に変換する。
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df


def split_by_date(
    df: pd.DataFrame,
    date_col: str,
    train_end: str,
    test_start: str,
    test_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    日付で train / test に分割する。

    - train: ～ train_end
    - test : test_start ～ test_end

    いずれも 'YYYY-MM-DD' 形式の文字列で指定する。
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    train_end_dt = pd.to_datetime(train_end)
    test_start_dt = pd.to_datetime(test_start)
    test_end_dt = pd.to_datetime(test_end)

    train_df = df[df[date_col] <= train_end_dt].copy()
    test_df = df[(df[date_col] >= test_start_dt) & (df[date_col] <= test_end_dt)].copy()

    return train_df, test_df