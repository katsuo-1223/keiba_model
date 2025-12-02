# scripts/kaggle/timeseries_backtest_win.py
"""
Kaggle JRA 単勝モデルの「時系列バックテスト」スクリプト。

- 入力:
    data/processed/kaggle/train_race_result_with_g1_splitA.csv

- 処理:
    Split A:
        train: ～2010-12-31
        test : 2011-01-01 ～ 2015-12-31
    Split B:
        train: ～2015-12-31
        test : 2016-01-01 ～ 2021-07-31

    各 split について
        1. 1段目 LightGBM を train 期間のみで学習
        2. train で Isotonic Regression によるキャリブレーション
        3. test に対して
            - p_raw, p_win_calib を算出
            - EV = p_win_calib * 単勝 で EV>=threshold の ROI を評価
        4. メタモデル（簡易版）を学習し、EV_meta>=threshold の ROI も評価

- 出力:
    outputs/kaggle/roi_timeseries_summary.csv
        split, model, roi, hit_rate, bets, returns
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, log_loss

from utils_time_split import add_race_date, split_by_date

# プロジェクトルートを推定
ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_with_g1_splitA.csv"
OUTPUT_DIR_DEFAULT = ROOT / "outputs" / "kaggle"


# ===============================
# データロード & 特徴量マトリクス
# ===============================
def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {path}")
    df = pd.read_csv(path)
    return df


def build_feature_matrix(
    df: pd.DataFrame,
    id_cols: List[str],
    target_cols: List[str],
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    train_lgbm_win_baseline.py と同じ思想で特徴量行列を作る。

    - ID 列と目的変数列を除く
    - レース後の結果情報（リーク列）は除外
    """
    missing = [c for c in id_cols + target_cols if c not in df.columns]
    if missing:
        raise KeyError(f"必要な列が見つかりません: {missing}")

    leak_cols = [
        "上がり3F",      # レースのラスト3Fタイム（結果）
        "上がり順位",    # そのレース内での上がり順位（結果）
        "通過4角",       # 4コーナー通過順（結果）
        "g1_score",  # ★ 元の生涯版 g1_score はリーク扱いとして除外
    ]

    feature_cols = [
        c for c in df.columns
        if c not in id_cols + target_cols + leak_cols
    ]

    X = df[feature_cols].copy()
    y = df["target_win"].astype(int)

    return X, y


# ===============================
# 1段目 LightGBM
# ===============================
def train_lgbm_first_stage(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_valid: pd.DataFrame,
    y_valid: pd.Series,
) -> lgb.Booster:
    # baseline と同じカテゴリ列設定
    categorical_cols = [c for c in ["騎手", "前走_クラス", "競争条件"] if c in X_train.columns]

    for c in categorical_cols:
        X_train[c] = X_train[c].astype("category")
        X_valid[c] = X_valid[c].astype("category")

    print("[1st] Dataset 準備")
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

    print("[1st] 学習開始")
    model = lgb.train(
        params=params,
        train_set=train_data,
        num_boost_round=2000,
        valid_sets=[train_data, valid_data],
        valid_names=["train", "valid"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100),
            lgb.log_evaluation(period=100),
        ],
    )

    print("[1st] 学習完了。train/test の logloss を確認用に計算")
    y_pred_valid = model.predict(X_valid, num_iteration=model.best_iteration)
    ll = log_loss(y_valid, y_pred_valid)
    auc = roc_auc_score(y_valid, y_pred_valid)
    print(f"[1st] Valid logloss: {ll:.4f}, AUC: {auc:.4f}")

    return model


# ===============================
# メタモデル LightGBM
# ===============================
def train_meta_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> lgb.Booster:

    print("[meta] Dataset 準備")
    train_data = lgb.Dataset(X_train, label=y_train)

    params = {
        "objective": "binary",
        "metric": ["binary_logloss"],
        "learning_rate": 0.05,
        "num_leaves": 15,
        "max_depth": -1,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "seed": 42,
    }

    print("[meta] 学習開始")
    model = lgb.train(
        params=params,
        train_set=train_data,
        num_boost_round=500,
        valid_sets=[train_data],
        valid_names=["train"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100),
            lgb.log_evaluation(period=100),
        ],
    )

    print("[meta] 学習完了")
    return model


# ===============================
# ROI 計算ユーティリティ
# ===============================
def compute_roi_ev_threshold(
    df: pd.DataFrame,
    prob_col: str,
    odds_col: str = "単勝",
    hit_col: str = "target_win",
    threshold: float = 2.0,
) -> tuple[float, float, int, float]:
    """
    EV = prob * odds
    EV >= threshold の馬に 1 単位ずつベットすると仮定したときの ROI を計算。
    """
    df = df.copy()
    df["ev"] = df[prob_col] * df[odds_col]

    bet_df = df[df["ev"] >= threshold]
    if len(bet_df) == 0:
        return 0.0, 0.0, 0, 0.0

    bets = len(bet_df)
    # 的中時はオッズ分の払い戻し（100円単位はここではスケーリングしない）
    returns = bet_df.apply(lambda r: r[odds_col] if r[hit_col] == 1 else 0.0, axis=1).sum()

    roi = (returns - bets) / bets
    hit_rate = bet_df[hit_col].mean()

    return float(roi), float(hit_rate), int(bets), float(returns)


# ===============================
# メイン処理
# ===============================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-path",
        type=str,
        default=str(INPUT_PATH),
        help="train_race_result_basic_with_g1.csv のパス",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_DIR_DEFAULT),
        help="結果 CSV を保存するディレクトリ",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=2.0,
        help="EV のしきい値 (例: 2.0)",
    )
    args = parser.parse_args()

    data_path = Path(args.data_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== 時系列バックテスト開始 ===")
    print(f"[INFO] data_path : {data_path}")
    print(f"[INFO] output_dir: {output_dir}")

    df_all = load_data(data_path)
    df_all = add_race_date(df_all, date_col="レース日付")

    id_cols = ["レースID", "レース日付", "競馬場コード", "競馬場名", "馬番", "馬名"]
    target_cols = ["target_win", "target_place"]

    # Split 定義
    splits = {
        "splitA": {
            "train_end": "2010-12-31",
            "test_start": "2011-01-01",
            "test_end": "2015-12-31",
        },
        "splitB": {
            "train_end": "2015-12-31",
            "test_start": "2016-01-01",
            "test_end": "2021-07-31",
        },
    }

    results = []

    for split_name, cfg in splits.items():
        print(f"\n===== {split_name} =====")
        train_df, test_df = split_by_date(
            df_all,
            date_col="レース日付",
            train_end=cfg["train_end"],
            test_start=cfg["test_start"],
            test_end=cfg["test_end"],
        )

        print(f"[INFO] train_df: {len(train_df)} 行, test_df: {len(test_df)} 行")

        # ---------- 1段目 LightGBM ----------
        X_train, y_train = build_feature_matrix(train_df, id_cols=id_cols, target_cols=target_cols)
        X_test, y_test = build_feature_matrix(test_df, id_cols=id_cols, target_cols=target_cols)

        model_1st = train_lgbm_first_stage(X_train, y_train, X_test, y_test)

        # train 用の raw 予測（Isotonic 学習用）
        print("[1st] Isotonic calibration...")
        p_raw_train = model_1st.predict(X_train, num_iteration=model_1st.best_iteration)
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(p_raw_train, y_train)

        # test での予測＋キャリブレーション
        p_raw_test = model_1st.predict(X_test, num_iteration=model_1st.best_iteration)
        p_calib_test = iso.predict(p_raw_test)

        test_df = test_df.copy()
        test_df["p_raw"] = p_raw_test
        test_df["p_win_calib"] = p_calib_test

        # ---------- ROI（1段目のみ） ----------
        roi1, hit1, bet1, ret1 = compute_roi_ev_threshold(
            test_df,
            prob_col="p_win_calib",
            odds_col="単勝",
            hit_col="target_win",
            threshold=args.threshold,
        )
        print(f"[1st] ROI={roi1:.3f}, hit_rate={hit1:.3f}, bets={bet1}, returns={ret1:.1f}")
        results.append([split_name, "1st_stage", roi1, hit1, bet1, ret1])

        # ---------- メタモデル用データセット ----------
        print("[meta] データセット構築")
        train_meta = train_df.copy()
        train_meta["p_raw"] = p_raw_train
        train_meta["p_win_calib"] = iso.predict(p_raw_train)
        train_meta["hit"] = train_meta["target_win"]

        test_meta = test_df.copy()
        test_meta["hit"] = test_meta["target_win"]

        # メタモデルに使う特徴量（シンプル版）
        meta_feature_candidates = [
            "p_raw",
            "p_win_calib",
            "単勝",
            "人気",
            "距離(m)",
            "g1_score",
            # "競争条件",
            # "騎手",
        ]
        meta_features = [c for c in meta_feature_candidates if c in train_meta.columns]

        X_meta_train = train_meta[meta_features].copy()
        y_meta_train = train_meta["hit"].astype(int)

        X_meta_test = test_meta[meta_features].copy()
        y_meta_test = test_meta["hit"].astype(int)

        # ★ ここで train / test 両方のカテゴリ列を揃える
        # categorical_cols = [c for c in ["騎手", "前走_クラス", "競争条件"] if c in X_meta_train.columns]
        # for c in categorical_cols:
        #     X_meta_train[c] = X_meta_train[c].astype("category")
        #     X_meta_test[c] = X_meta_test[c].astype("category")

        meta_model = train_meta_model(X_meta_train, y_meta_train)

        # test に対する meta スコア（確率扱い）
        test_meta["meta_prob"] = meta_model.predict(
            X_meta_test,
            num_iteration=meta_model.best_iteration
        )

        # ROI（メタモデル）
        roi2, hit2, bet2, ret2 = compute_roi_ev_threshold(
            test_meta,
            prob_col="meta_prob",
            odds_col="単勝",
            hit_col="hit",
            threshold=args.threshold,
        )
        print(f"[meta] ROI={roi2:.3f}, hit_rate={hit2:.3f}, bets={bet2}, returns={ret2:.1f}")
        results.append([split_name, "meta", roi2, hit2, bet2, ret2])

    # 結果を CSV に保存
    result_df = pd.DataFrame(
        results,
        columns=["split", "model", "roi", "hit_rate", "bets", "returns"],
    )

    save_path = output_dir / "roi_timeseries_summary.csv"
    result_df.to_csv(save_path, index=False)

    print("\n=== Backtest Finished ===")
    print(result_df)
    print(f"\nSaved to {save_path}")


if __name__ == "__main__":
    main()