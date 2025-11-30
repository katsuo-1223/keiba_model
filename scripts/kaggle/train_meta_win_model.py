# scripts/kaggle/train_meta_win_model.py
"""
単勝1段目モデル + オッズ + 騎手・馬特徴 などを用いた
メタ学習モデル（スタッキングモデル）の訓練スクリプト。

- 入力:
    data/processed/kaggle/win_meta_train.csv
      1段目キャリブレーション結果 (lgbm_win_pred_calibrated.csv)
      + train_race_result_basic.csv の特徴量をマージしたもの

- 出力:
    models/kaggle/meta_win_model.txt
        : メタモデル (LightGBM)
    data/processed/kaggle/win_meta_pred.csv
        : 検証期間(≒2020年以降)のID + 目的変数 + オッズ + メタ予測 + EV

※ 方針
    - 1段目モデルは 〜2017 年で学習済み & 2018〜 の予測・キャリブレーション済み。
    - メタモデルは 2018〜2019 を train、2020〜 を valid として時系列分割する。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss

ROOT = Path(__file__).resolve().parents[2]

META_TRAIN_PATH = ROOT / "data" / "processed" / "kaggle" / "win_meta_train.csv"
MODEL_DIR = ROOT / "models" / "kaggle"
META_PRED_PATH = ROOT / "data" / "processed" / "kaggle" / "win_meta_pred.csv"


def load_meta_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")
    df = pd.read_csv(path)
    return df


def train_valid_split_by_date(
    df: pd.DataFrame,
    date_col: str = "レース日付",
    split_date: str = "2020-01-01",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    メタモデル用の時系列分割。
    例:
        〜2019年分 → train
        2020年以降 → valid
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    split_ts = pd.to_datetime(split_date)

    df_train = df[df[date_col] < split_ts].copy()
    df_valid = df[df[date_col] >= split_ts].copy()

    if len(df_train) == 0 or len(df_valid) == 0:
        raise ValueError(
            f"train/valid のどちらかが 0 行です。split_date={split_date} を見直してください。"
        )

    return df_train, df_valid


def build_feature_matrix(
    df: pd.DataFrame,
    id_cols: List[str],
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    ID列を除いた中で、
    ・target_win を目的変数 y
    ・その他の数値列を特徴量 X
    として返す。
    """
    if "target_win" not in df.columns:
        raise KeyError("列 'target_win' が見つかりません。win_meta_train.csv を確認してください。")

    # 目的変数
    y = df["target_win"].astype(int)

    # target_place があれば除外候補に含める
    exclude_cols = set(id_cols + ["target_win", "target_place"])

    feature_candidates = [c for c in df.columns if c not in exclude_cols]

    # 数値列だけ LightGBM に渡す
    X_all = df[feature_candidates]
    num_cols = X_all.select_dtypes(include=["number"]).columns.tolist()

    if not num_cols:
        raise ValueError("数値特徴量が見つかりません。win_meta_train.csv の中身を確認してください。")

    X = X_all[num_cols].copy()

    print(f"[build_feature_matrix] 使用する特徴量数: {len(num_cols)}")
    return X, y


def train_lgbm_meta(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
) -> lgb.Booster:
    print("[meta] Dataset 準備")
    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_valid, label=y_valid)

    params = {
        "objective": "binary",
        "metric": ["auc", "binary_logloss"],
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": -1,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "seed": 42,
    }

    print("[meta] 学習開始（LightGBM）")
    model = lgb.train(
        params=params,
        train_set=train_data,
        num_boost_round=2000,
        valid_sets=[train_data, valid_data],
        valid_names=["train", "valid"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100),
            lgb.log_evaluation(period=50),
        ],
    )

    print("[meta] 学習完了。検証データで評価")
    y_pred_valid = model.predict(X_valid, num_iteration=model.best_iteration)
    auc = roc_auc_score(y_valid, y_pred_valid)
    ll = log_loss(y_valid, y_pred_valid)

    print(f"[meta] Validation AUC:     {auc:.4f}")
    print(f"[meta] Validation logloss: {ll:.4f}")
    print(f"[meta] best_iteration:     {model.best_iteration}")

    return model, y_pred_valid


def save_model(model: lgb.Booster, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))
    print(f"[meta] モデルを保存しました: {path}")


def save_valid_prediction(
    df_valid: pd.DataFrame,
    y_pred: np.ndarray,
    id_cols: List[str],
    path: Path,
) -> None:
    """
    検証データに対するメタモデル予測を CSV 出力。
    - ID 情報
    - target_win / target_place（あれば）
    - 単勝オッズ_倍率
    - メタ予測確率 pred_win_meta
    - 期待値 expected_value_win_meta
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    base_cols = [c for c in id_cols if c in df_valid.columns]

    for c in ["target_win", "target_place", "単勝_倍率", "単勝"]:
        if c in df_valid.columns:
            base_cols.append(c)

    out_df = df_valid[base_cols].copy()

    out_df["pred_win_meta"] = y_pred

    # 単勝倍率を取得（なければ単勝を倍率とみなす）
    if "単勝_倍率" in out_df.columns:
        odds_col = "単勝_倍率"
    elif "単勝" in out_df.columns:
        odds_col = "単勝"
    else:
        raise KeyError("列 '単勝_倍率' も '単勝' も見つかりません。オッズ列が必要です。")

    out_df["expected_value_win_meta"] = out_df["pred_win_meta"] * out_df[odds_col]

    out_df.to_csv(path, index=False, encoding="utf-8")
    print(f"[meta] 検証データの予測結果を保存しました: {path}")


def main() -> None:
    print("=== train_meta_win_model.py 実行開始 ===")
    print(f"[INFO] META_TRAIN_PATH: {META_TRAIN_PATH}")

    df = load_meta_data(META_TRAIN_PATH)

    id_cols: List[str] = [
        "レースID",
        "レース日付",
        "競馬場コード",
        "競馬場名",
        "馬番",
        "馬名",
    ]

    df_train, df_valid = train_valid_split_by_date(
        df, date_col="レース日付", split_date="2020-01-01"
    )

    X_train, y_train = build_feature_matrix(df_train, id_cols=id_cols)
    X_valid, y_valid = build_feature_matrix(df_valid, id_cols=id_cols)

    print(f"[INFO] train X: {X_train.shape}, valid X: {X_valid.shape}")

    model, y_pred_valid = train_lgbm_meta(X_train, y_train, X_valid, y_valid)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "meta_win_model.txt"
    save_model(model, model_path)

    save_valid_prediction(
        df_valid=df_valid,
        y_pred=y_pred_valid,
        id_cols=id_cols,
        path=META_PRED_PATH,
    )

    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()