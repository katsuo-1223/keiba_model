# scripts/kaggle/train_lgbm_win_baseline.py
"""
Kaggle JRA データを用いた LightGBM ベースライン（単勝予測）学習スクリプト。

- 入力: data/processed/kaggle/train_race_result_basic.csv
    - 先頭に ID 情報:
        レースID, レース日付, 競馬場コード, 競馬場名, 馬番, 馬名
    - 末尾に目的変数:
        target_win, target_place
    - それ以外の列を特徴量として使用（数値＋one-hot 済み列を想定）

- 出力:
    - models/kaggle/lgbm_win_baseline.txt      : 学習済みモデル
    - data/processed/kaggle/lgbm_win_pred.csv : 検証期間での予測結果＋ID＋目的変数
    - 学習・検証の AUC / logloss を標準出力

※ 事前に以下をインストールしておくこと:
    pip install lightgbm scikit-learn
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss

# プロジェクトルートを推定（このファイルから2つ上のディレクトリ）
ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_basic.csv"
MODEL_DIR = ROOT / "models" / "kaggle"
PRED_PATH = ROOT / "data" / "processed" / "kaggle" / "lgbm_win_pred.csv"


def load_data(path: Path) -> pd.DataFrame:
    """学習用データを読み込む。"""
    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")
    df = pd.read_csv(path)
    return df


def train_valid_split_by_date(
    df: pd.DataFrame,
    date_col: str = "レース日付",
    split_date: str = "2018-01-01",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    レース日付で時系列分割する。

    例:
        ～2017年分      → train
        2018年以降分    → valid
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    split_ts = pd.to_datetime(split_date)

    df_train = df[df[date_col] < split_ts].copy()
    df_valid = df[df[date_col] >= split_ts].copy()

    if len(df_train) == 0 or len(df_valid) == 0:
        raise ValueError(
            f"train/valid のいずれかが 0 行です。split_date={split_date} を見直してください。"
        )

    return df_train, df_valid


def build_feature_matrix(
    df: pd.DataFrame,
    id_cols: List[str],
    target_cols: List[str],
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    ID 列と目的変数列を除いたものを特徴量行列 X として返す。
    target_win を目的変数 y に使用。

    ※ レース後にしか分からない情報（リーク列）は除外する。
    """
    missing = [c for c in id_cols + target_cols if c not in df.columns]
    if missing:
        raise KeyError(f"必要な列が見つかりません: {missing}")

    # ★ レース後にしか分からない当該レース情報 → 学習から除外
    leak_cols = [
        "上がり3F",      # レースのラスト3Fタイム（結果）
        "上がり順位",    # そのレース内での上がり順位（結果）
        "通過4角",       # 4コーナー通過順（結果）
        # 必要があれば今後、他の結果系列もここに足す
    ]

    feature_cols = [
        c for c in df.columns
        if c not in id_cols + target_cols + leak_cols
    ]

    X = df[feature_cols].copy()
    y = df["target_win"].astype(int)

    return X, y


def train_lightgbm_baseline(
    X_train,
    y_train,
    X_valid,
    y_valid,
) -> lgb.Booster:
    # ▼ ここを追加 ▼
    categorical_cols = [c for c in ["騎手", "前走_クラス"] if c in X_train.columns]

    for c in categorical_cols:
        X_train[c] = X_train[c].astype("category")
        X_valid[c] = X_valid[c].astype("category")

    print("[lgbm] Dataset 準備")
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

    print("[lgbm] 学習開始（LightGBM 4.x callbacks版）")

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

    print("[lgbm] 学習完了。検証データで評価")
    y_pred_valid = model.predict(X_valid, num_iteration=model.best_iteration)
    auc = roc_auc_score(y_valid, y_pred_valid)
    ll = log_loss(y_valid, y_pred_valid)

    print(f"[lgbm] Validation AUC:     {auc:.4f}")
    print(f"[lgbm] Validation logloss: {ll:.4f}")
    print(f"[lgbm] best_iteration:     {model.best_iteration}")

    return model, y_pred_valid


def save_model(model: lgb.Booster, path: Path) -> None:
    """モデルをテキスト形式で保存。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))
    print(f"モデルを保存しました: {path}")


def save_valid_prediction(
    df_valid: pd.DataFrame,
    y_pred: np.ndarray,
    id_cols: List[str],
    target_cols: List[str],
    path: Path,
) -> None:
    """
    検証データに対する予測値を CSV 出力。
    - ID 情報
    - 目的変数 (target_win, target_place)
    - 単勝オッズ（倍率）
    - 予測確率 pred_win
    - 期待値 expected_value_win
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    base_cols = id_cols + target_cols + ["単勝"]

    out_df = df_valid[base_cols].copy()

    # 予測確率
    out_df["pred_win"] = y_pred

    # ★ train_race_result_basic.csv の「単勝」はすでに倍率なので、そのまま使う
    out_df["単勝_倍率"] = out_df["単勝"]

    # 期待値（1点100円購入時の期待回収倍率）
    out_df["expected_value_win"] = out_df["pred_win"] * out_df["単勝_倍率"]

    out_df.to_csv(path, index=False)
    print(f"検証データの予測結果を保存しました: {path}")

def main() -> None:
    print("=== train_lgbm_win_baseline.py 実行開始 ===")
    print(f"[INFO] ROOT:       {ROOT}")
    print(f"[INFO] INPUT_PATH: {INPUT_PATH}")

    df = load_data(INPUT_PATH)

    id_cols = ["レースID", "レース日付", "競馬場コード", "競馬場名", "馬番", "馬名"]
    target_cols = ["target_win", "target_place"]

    df_train, df_valid = train_valid_split_by_date(
        df, date_col="レース日付", split_date="2018-01-01"
    )

    X_train, y_train = build_feature_matrix(
        df_train, id_cols=id_cols, target_cols=target_cols
    )
    X_valid, y_valid = build_feature_matrix(
        df_valid, id_cols=id_cols, target_cols=target_cols
    )

    print(f"[INFO] train X: {X_train.shape}, valid X: {X_valid.shape}")

    model, y_pred_valid = train_lightgbm_baseline(X_train, y_train, X_valid, y_valid)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "lgbm_win_baseline.txt"
    save_model(model, model_path)

    save_valid_prediction(
        df_valid=df_valid,
        y_pred=y_pred_valid,
        id_cols=id_cols,
        target_cols=target_cols,
        path=PRED_PATH,
    )

    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()