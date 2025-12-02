# scripts/kaggle/train_g1_profile_model_splitA.py

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss

ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "g1_profile_train_splitA.csv"
MODEL_PATH = ROOT / "models" / "kaggle" / "g1_profile_lgbm_splitA.txt"
SCORE_PATH = ROOT / "data" / "processed" / "kaggle" / "horse_g1_score_splitA.csv"


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")
    df = pd.read_csv(path)
    return df


def build_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    g1_profile_train_splitA.csv から特徴量 X と目的変数 y を作る。

    - 馬名 は ID 扱いなので「必ず」特徴量から除外
    - horse_is_g1_winner を目的変数にする
    - LightGBM に渡すのは int / float / bool のみ
    """
    target_col = "horse_is_g1_winner"

    if target_col not in df.columns:
        raise KeyError(f"目的変数 {target_col} が見つかりません")

    # ▼ まず、ID的なカラムを全部 drop してから
    drop_cols = [c for c in ["馬名", target_col] if c in df.columns]
    df_feat = df.drop(columns=drop_cols)

    # ▼ 数値と bool だけを特徴量として採用
    X = df_feat.select_dtypes(include=["number", "bool"]).copy()

    # 念のためログを出しておくと安心
    print(f"[g1] feature columns: {list(X.columns)[:10]} ... (total {X.shape[1]})")
    print(f"[g1] samples: {X.shape[0]}")

    y = df[target_col].astype(int)

    return X, y


def train_g1_profile_model(X: pd.DataFrame, y: pd.Series) -> lgb.Booster:
    train_data = lgb.Dataset(X, label=y)

    params = {
        "objective": "binary",
        "metric": ["auc", "binary_logloss"],
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": -1,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "seed": 42,
        "verbose": -1,
    }

    print("[g1] 学習開始")
    model = lgb.train(
        params=params,
        train_set=train_data,
        num_boost_round=1000,
        valid_sets=[train_data],
        valid_names=["train"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100),
            lgb.log_evaluation(period=100),
        ],
    )

    y_pred = model.predict(X, num_iteration=model.best_iteration)
    auc = roc_auc_score(y, y_pred)
    ll = log_loss(y, y_pred)
    print(f"[g1] train AUC: {auc:.4f}, logloss: {ll:.4f}")
    print(f"[g1] best_iteration: {model.best_iteration}")

    return model


def main() -> None:
    print("=== train_g1_profile_model_splitA 開始 ===")
    print(f"[INFO] INPUT_PATH: {INPUT_PATH}")

    df = load_data(INPUT_PATH)
    X, y = build_feature_matrix(df)

    model = train_g1_profile_model(X, y)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_PATH))
    print(f"[g1] モデルを保存しました: {MODEL_PATH}")

    # 馬名 と g1_score_splitA を保存
    id_col = "馬名"
    horse_ids = df[id_col].values
    g1_score = model.predict(X, num_iteration=model.best_iteration)

    out_df = pd.DataFrame(
        {
            "馬名": horse_ids,
            "g1_score_splitA": g1_score,
        }
    )
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(SCORE_PATH, index=False)
    print(f"[g1] horse_g1_score_splitA.csv を保存しました: {SCORE_PATH}")

    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()