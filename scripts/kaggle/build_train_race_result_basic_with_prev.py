# scripts/kaggle/build_train_race_result_basic_with_prev.py
"""
Kaggle JRA 元CSV（日本語カラム）から
train_race_result_basic.csv を再構築しつつ、

- 騎手情報
- 上がり3F & 上がり順位
- 通過4角（脚質の簡易指標）
- 前走着順
- 前走上がり3F
- 前走上がり順位
- 前走通過4角
- 前走距離
- 前走クラス（競争条件）

などの前走特徴量を追加するスクリプト。

入力:
    data/raw/kaggle/race_result.csv  （★あなたの元CSVのパスに変更してください）

出力:
    data/processed/kaggle/train_race_result_basic.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

# ★★ ここをあなたの元データのファイル名に合わせて修正してください ★★
RAW_RESULT_PATH = ROOT / "data" / "raw" / "kaggle" / "19860105-20210731_race_result.csv"

OUTPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_basic.csv"


def load_raw_result(path: Path) -> pd.DataFrame:
    print(f"[load_raw_result] {path}")
    df = pd.read_csv(path)
    print(f"[load_raw_result] {df.shape[0]:,} 行, {df.shape[1]} 列")
    return df

def ensure_condition_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    元CSV側の「競争条件」列を df['競争条件'] にそろえる。

    - 列名が「競走条件」など微妙に違う場合も拾う
    - 「条件」を含む列があれば、それを公式な '競争条件' としてコピーする
    """
    if "競争条件" in df.columns:
        # すでに存在していれば何もしない
        return df

    # 「条件」を含む列をゆるく探索
    cand = [c for c in df.columns if "条件" in str(c)]
    if cand:
        print(f"[INFO] 条件カラムを '{cand[0]}' から '競争条件' にマッピングします")
        df["競争条件"] = df[cand[0]]
    else:
        print("[WARN] '競争条件' 系の列が見つかりませんでした（条件特徴は NaN のままになります）")

    return df


def build_basic_columns(df: pd.DataFrame) -> pd.DataFrame:
    # 日付を datetime に
    df["レース日付"] = pd.to_datetime(df["レース日付"])

    # 上がり3F
    if "上り" in df.columns:
        df["上がり3F"] = pd.to_numeric(df["上り"], errors="coerce")
    else:
        df["上がり3F"] = np.nan

    # 芝/ダート
    df["芝・ダート区分_芝"] = (df["芝・ダート区分"] == "芝").astype(int)

    # 馬場状態
    df["馬場状態1_稍重"] = (df["馬場状態1"] == "稍重").astype(int)
    df["馬場状態1_良"] = (df["馬場状態1"] == "良").astype(int)
    df["馬場状態1_重"] = (df["馬場状態1"] == "重").astype(int)

    # 目的変数
    df["target_win"] = (df["着順"] == 1).astype(int)
    df["target_place"] = (df["着順"] <= 3).astype(int)

    return df


def add_agari_rank(df: pd.DataFrame) -> pd.DataFrame:
    """
    レースごとに上がり3Fの順位を計算（小さいほど速い）。
    """
    df["上がり3F"] = pd.to_numeric(df["上がり3F"], errors="coerce")

    df["上がり順位"] = (
        df.groupby("レースID")["上がり3F"]
        .rank(method="min")  # 同タイムは同順位
        .astype("float32")
    )

    return df


def extract_4th_corner(df: pd.DataFrame) -> pd.DataFrame:
    """
    4コーナー位置を数値で抽出して「通過4角」として持つ。

    4コーナー列は 例:
        '7' , '7-8', '12' などを想定
    """
    def parse_corner(val):
        if pd.isna(val):
            return np.nan
        s = str(val)
        # "7-8" みたいな場合は先頭だけ
        s = s.replace(" ", "").split("-")[0]
        try:
            return float(s)
        except ValueError:
            return np.nan

    if "4コーナー" in df.columns:
        df["通過4角"] = df["4コーナー"].apply(parse_corner).astype("float32")
    else:
        df["通過4角"] = np.nan

    return df


def add_prev_race_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    馬ごとに時系列順（レース日付 + レース番号）に並べて、
    1走前の情報を shift して前走特徴量を追加。
    """
    sort_keys = ["馬名", "レース日付"]
    if "レース番号" in df.columns:
        sort_keys.append("レース番号")

    df = df.sort_values(sort_keys).copy()

    group = df.groupby("馬名")

    df["前走_着順"] = group["着順"].shift(1)
    df["前走_上がり3F"] = group["上がり3F"].shift(1)
    df["前走_上がり順位"] = group["上がり順位"].shift(1)
    df["前走_通過4角"] = group["通過4角"].shift(1)
    df["前走_距離(m)"] = group["距離(m)"].shift(1)

    if "競争条件" in df.columns:
        df["前走_クラス"] = group["競争条件"].shift(1)
    else:
        df["前走_クラス"] = np.nan

    df["前走_レースID"] = group["レースID"].shift(1)
    df["前走_レース日付"] = group["レース日付"].shift(1)

    return df


def add_jockey_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    騎手ごとに時系列順（レース日付 + レース番号）に並べて、
    それまでの通算成績を特徴量として追加する。

    - 騎手_通算騎乗数
    - 騎手_通算勝利数
    - 騎手_通算連対数（ここでは target_place=1 を「馬券圏内」とみなす）
    - 騎手_通算勝率
    - 騎手_通算連対率
    """
    sort_keys = ["騎手", "レース日付"]
    if "レース番号" in df.columns:
        sort_keys.append("レース番号")

    df = df.sort_values(sort_keys).copy()

    g = df.groupby("騎手")

    # そのレースより前の騎乗数 = 累積件数（0,1,2,...）
    df["騎手_通算騎乗数"] = g.cumcount()

    # まず「1レース前までの勝ち・連対フラグ」を作る
    df["_prev_win"] = g["target_win"].shift(1).fillna(0)
    df["_prev_place"] = g["target_place"].shift(1).fillna(0)

    # それを累積して通算勝利数・通算連対数にする
    df["騎手_通算勝利数"] = g["_prev_win"].cumsum()
    df["騎手_通算連対数"] = g["_prev_place"].cumsum()

    # 勝率・連対率（騎乗数0のときは0で埋める）
    denom = df["騎手_通算騎乗数"].replace(0, np.nan)
    df["騎手_通算勝率"] = (df["騎手_通算勝利数"] / denom).fillna(0.0)
    df["騎手_通算連対率"] = (df["騎手_通算連対数"] / denom).fillna(0.0)

    # 一時列は削除
    df = df.drop(columns=["_prev_win", "_prev_place"])

    return df


def add_group_jockey_stats(
    df: pd.DataFrame,
    group_cols: list[str],
    prefix: str,
) -> pd.DataFrame:
    """
    group_cols で指定した条件ごとに騎手の通算成績を作る。
    例: group_cols = ["騎手", "距離帯"]
        prefix = "騎手距離"

    追加される列:
        {prefix}_通算騎乗数
        {prefix}_通算勝利数
        {prefix}_通算連対数
        {prefix}_通算勝率
        {prefix}_通算連対率
    """
    df = df.copy()

    # 時系列順に並べる
    sort_keys = group_cols + ["レース日付"]
    if "レース番号" in df.columns:
        sort_keys.append("レース番号")
    df = df.sort_values(sort_keys)

    g = df.groupby(group_cols)

    col_n = f"{prefix}_通算騎乗数"
    col_w = f"{prefix}_通算勝利数"
    col_p = f"{prefix}_通算連対数"
    col_wr = f"{prefix}_通算勝率"
    col_pr = f"{prefix}_通算連対率"

    df[col_n] = g.cumcount()

    df["_prev_win_grp"] = g["target_win"].shift(1).fillna(0)
    df["_prev_place_grp"] = g["target_place"].shift(1).fillna(0)

    df[col_w] = g["_prev_win_grp"].cumsum()
    df[col_p] = g["_prev_place_grp"].cumsum()

    denom = df[col_n].replace(0, np.nan)
    df[col_wr] = (df[col_w] / denom).fillna(0.0)
    df[col_pr] = (df[col_p] / denom).fillna(0.0)

    df = df.drop(columns=["_prev_win_grp", "_prev_place_grp"])

    return df


def get_distance_bin(x: float) -> str:
    if x < 1400:
        return "短距離"
    elif x < 1900:
        return "マイル〜中距離"
    elif x < 2500:
        return "中距離〜長距離"
    else:
        return "長距離"

def add_horse_stats(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["馬名", "レース日付", "レース番号"]).copy()
    g = df.groupby("馬名")

    df["馬_通算出走数"] = g.cumcount()

    df["_prev_win_h"] = g["target_win"].shift(1).fillna(0)
    df["_prev_place_h"] = g["target_place"].shift(1).fillna(0)

    df["馬_通算勝利数"] = g["_prev_win_h"].cumsum()
    df["馬_通算連対数"] = g["_prev_place_h"].cumsum()

    denom = df["馬_通算出走数"].replace(0, np.nan)
    df["馬_通算勝率"] = (df["馬_通算勝利数"] / denom).fillna(0.0)
    df["馬_通算連対率"] = (df["馬_通算連対数"] / denom).fillna(0.0)

    df = df.drop(columns=["_prev_win_h", "_prev_place_h"])

    return df


def add_group_horse_stats(df: pd.DataFrame, group_cols: list[str], prefix: str) -> pd.DataFrame:
    df = df.copy()
    sort_keys = group_cols + ["レース日付"]
    if "レース番号" in df.columns:
        sort_keys.append("レース番号")
    df = df.sort_values(sort_keys)

    g = df.groupby(group_cols)

    col_n = f"{prefix}_通算出走数"
    col_w = f"{prefix}_通算勝利数"
    col_p = f"{prefix}_通算連対数"
    col_wr = f"{prefix}_通算勝率"
    col_pr = f"{prefix}_通算連対率"

    df[col_n] = g.cumcount()
    df["_prev_win_hg"] = g["target_win"].shift(1).fillna(0)
    df["_prev_place_hg"] = g["target_place"].shift(1).fillna(0)

    df[col_w] = g["_prev_win_hg"].cumsum()
    df[col_p] = g["_prev_place_hg"].cumsum()

    denom = df[col_n].replace(0, np.nan)
    df[col_wr] = (df[col_w] / denom).fillna(0.0)
    df[col_pr] = (df[col_p] / denom).fillna(0.0)

    df = df.drop(columns=["_prev_win_hg", "_prev_place_hg"])
    return df


def select_final_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    学習に使う列を選ぶ。
    ここで ID / 基本特徴量 / 騎手 / 上がり系 / 前走系 / target をまとめて定義。
    """

    id_cols: List[str] = [
        "レースID",
        "レース日付",
        "競馬場コード",
        "競馬場名",
        "馬番",
        "馬名",
    ]

    target_cols: List[str] = [
        "target_win",
        "target_place",
    ]

    # 既存の basic に相当する特徴量
    base_feature_cols: List[str] = [
        "距離(m)",
        "馬齢",
        "斤量",
        "単勝",
        "人気",
        "馬体重",
        "場体重増減",
        "芝・ダート区分_芝",
        "馬場状態1_稍重",
        "馬場状態1_良",
        "馬場状態1_重",
        "競争条件",
    ]

    # 騎手（カテゴリそのまま）
    jockey_cols = ["騎手"]

    # 上がり・通過系
    agari_cols = [
        "上がり3F",
        "上がり順位",
        "通過4角",
    ]

    # 前走特徴量
    prev_cols = [
        "前走_着順",
        "前走_上がり3F",
        "前走_上がり順位",
        "前走_通過4角",
        "前走_距離(m)",
        "前走_クラス",
    ]

    jockey_cols = ["騎手"]

    # 騎手の通算成績
    jockey_stat_cols = [
        "騎手_通算騎乗数",
        "騎手_通算勝利数",
        "騎手_通算連対数",
        "騎手_通算勝率",
        "騎手_通算連対率",
        "騎手距離_通算騎乗数",
        "騎手距離_通算勝率",
        "騎手距離_通算連対率",
        "騎手場_通算騎乗数",
        "騎手場_通算勝率",
        "騎手場_通算連対率",
        "騎手芝ダ_通算騎乗数",
        "騎手芝ダ_通算勝率",
        "騎手芝ダ_通算連対率",
    ]

    horse_stat_cols = [
    "馬_通算出走数",
    "馬_通算勝率",
    "馬_通算連対率",
    "馬距離_通算出走数",
    "馬距離_通算勝率",
    "馬距離_通算連対率",
    "馬場_通算出走数",
    "馬場_通算勝率",
    "馬場_通算連対率",
    "馬芝ダ_通算出走数",
    "馬芝ダ_通算勝率",
    "馬芝ダ_通算連対率",
]


    use_cols = id_cols + base_feature_cols + jockey_cols + jockey_stat_cols + horse_stat_cols + agari_cols + prev_cols + target_cols

    # 実際に存在する列だけ残す（もし何か欠けていても落ちないように）
    use_cols = [c for c in use_cols if c in df.columns]

    df_out = df[use_cols].copy()
    print(f"[select_final_columns] total columns: {len(df_out.columns)}")

    return df_out


def main() -> None:
    print("=== build_train_race_result_basic_with_prev.py 実行開始 ===")
    print(f"[INFO] RAW_RESULT_PATH: {RAW_RESULT_PATH}")

    df = load_raw_result(RAW_RESULT_PATH)

    df = ensure_condition_column(df)

    # 必要カラムがあるか軽くチェック（無ければ警告表示）
    required = [
        "レースID",
        "レース日付",
        "競馬場コード",
        "競馬場名",
        "競争条件",
        "馬番",
        "馬名",
        "距離(m)",
        "馬齢",
        "斤量",
        "単勝",
        "人気",
        "馬体重",
        "場体重増減",
        "芝・ダート区分",
        "馬場状態1",
        "着順",
        "上り",
        "騎手",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print("[WARN] 以下の列がCSVにありません。スクリプトを調整してください:")
        for c in missing:
            print("   -", c)

    # もともとの基本列などを作ったあと
    df = build_basic_columns(df)
    df = add_agari_rank(df)
    df = extract_4th_corner(df)
    df = add_prev_race_features(df)

    # 距離帯列
    df["距離帯"] = df["距離(m)"].apply(get_distance_bin)

    # 芝ダ区分カテゴリ
    if "芝ダ区分カテゴリ" not in df.columns:
        df["芝ダ区分カテゴリ"] = np.where(df["芝・ダート区分_芝"], "芝", "ダート")

    # 騎手全体の通算
    df = add_jockey_stats(df)  # 既に実装済みのやつ

    # 距離帯ごとの騎手成績
    df = add_group_jockey_stats(df, ["騎手", "距離帯"], prefix="騎手距離")

    # 競馬場ごとの騎手成績
    df = add_group_jockey_stats(df, ["騎手", "競馬場名"], prefix="騎手場")

    # 芝ダ別の騎手成績（元の列名に合わせて）
    df = add_group_jockey_stats(df, ["騎手", "芝・ダート区分"], prefix="騎手芝ダ")

    # 馬の通算成績
    df = add_horse_stats(df)

    # 馬 × 距離帯
    df = add_group_horse_stats(df, ["馬名", "距離帯"], prefix="馬距離")

    # 馬 × 競馬場
    df = add_group_horse_stats(df, ["馬名", "競馬場名"], prefix="馬場")

    # 馬 × 芝ダ
    df = add_group_horse_stats(df, ["馬名", "芝ダ区分カテゴリ"], prefix="馬芝ダ")


    df_out = select_final_columns(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUTPUT_PATH, index=False)
    print(f"[save] 保存完了: {OUTPUT_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()