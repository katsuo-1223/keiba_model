from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.model_selection import StratifiedKFold


def load_g1_profile_dataset(path: Path) -> pd.DataFrame:
    """G1プロファイル学習用データセットを読み込む。"""
    df = pd.read_csv(path)
    return df


def build_feature_matrix(df: pd.DataFrame):
    """特徴量行列 X と目的変数 y、メタ情報を作成する。

    - 目的変数: horse_is_g1_winner (0/1)
    - 除外するカラム:
        - 馬名: ID 的役割なので除外
        - horse_is_g1_winner: 目的変数
        - num_g1_wins, n_G1_wins: ラベルリーク防止のため除外
        - first_g1_win_date: そもそも G1 勝ってからしか分からないので除外
        - first_race_date: 文字列なので、今回は単純化のため除外
    """
    df = df.copy()

    if "horse_is_g1_winner" not in df.columns:
        raise KeyError("Column 'horse_is_g1_winner' not found in dataset.")

    y = df["horse_is_g1_winner"].astype(int).values

    # 数値カラムのみを候補に
    numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

    # 除外する数値カラム
    drop_numeric = []
    for col in ["horse_is_g1_winner", "num_g1_wins", "n_G1_wins"]:
        if col in numeric_cols:
            drop_numeric.append(col)

    feature_cols = [c for c in numeric_cols if c not in drop_numeric]

    X = df[feature_cols].values

    meta = {
        "feature_cols": feature_cols,
        "horse_name": df["馬名"].values if "馬名" in df.columns else None,
    }

    return X, y, meta


def train_lgbm_with_cv(X, y, feature_names, n_splits: int = 5, random_state: int = 42):
    """Stratified K-Fold で LightGBM の CV 学習を行い、スコアを表示する。

    戻り値:
        best_params: 最終的に使用するパラメータ dict
    """
    skf = StratifiedKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=random_state,
    )

    # クラス不均衡が激しいので scale_pos_weight を設定
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    params = {
        "objective": "binary",
        "metric": ["auc", "binary_logloss"],
        "learning_rate": 0.05,
        "num_leaves": 63,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "min_data_in_leaf": 50,
        "verbosity": -1,
        "seed": random_state,
        "feature_pre_filter": False,
        "scale_pos_weight": scale_pos_weight,
    }

    print(f"n_pos={int(n_pos)}, n_neg={int(n_neg)}, scale_pos_weight={scale_pos_weight:.1f}")

    oof_pred = np.zeros(len(y), dtype=float)
    auc_list = []
    logloss_list = []

    for fold, (trn_idx, val_idx) in enumerate(skf.split(X, y), start=1):
        X_trn, X_val = X[trn_idx], X[val_idx]
        y_trn, y_val = y[trn_idx], y[val_idx]

        train_set = lgb.Dataset(X_trn, label=y_trn, feature_name=feature_names)
        valid_set = lgb.Dataset(X_val, label=y_val, feature_name=feature_names)

        model = lgb.train(
            params=params,
            train_set=train_set,
            num_boost_round=2000,
            valid_sets=[train_set, valid_set],
            valid_names=["train", "valid"],
            callbacks=[
                lgb.early_stopping(stopping_rounds=100, verbose=False),
                lgb.log_evaluation(period=100),
            ],
        )

        best_iter = model.best_iteration
        print(f"[Fold {fold}] best_iteration={best_iter}")

        pred_val = model.predict(X_val, num_iteration=best_iter)
        oof_pred[val_idx] = pred_val

        auc = roc_auc_score(y_val, pred_val)
        ll = log_loss(y_val, pred_val)

        auc_list.append(auc)
        logloss_list.append(ll)

        print(f"[Fold {fold}] AUC={auc:.4f}, logloss={ll:.4f}")

    oof_auc = roc_auc_score(y, oof_pred)
    oof_ll = log_loss(y, oof_pred)

    print("====== CV Result ======")
    print(f"AUC (fold mean ± std): {np.mean(auc_list):.4f} ± {np.std(auc_list):.4f}")
    print(f"logloss (fold mean ± std): {np.mean(logloss_list):.4f} ± {np.std(logloss_list):.4f}")
    print(f"OOF AUC: {oof_auc:.4f}")
    print(f"OOF logloss: {oof_ll:.4f}")
    print("=======================")

    return params


def train_final_model(X, y, feature_names, params, model_path: Path):
    """全データで最終モデルを学習して保存する。"""
    train_set = lgb.Dataset(X, label=y, feature_name=feature_names)

    model = lgb.train(
        params=params,
        train_set=train_set,
        num_boost_round=2000,
        valid_sets=[train_set],
        valid_names=["train"],
        callbacks=[
            lgb.log_evaluation(period=200),
        ],
    )

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    print(f"Saved final model to: {model_path}")

    return model


def save_g1_scores(
    model,
    X,
    df_profile: pd.DataFrame,
    feature_names,
    out_path: Path,
):
    """学習済みモデルで全馬の G1スコアを推論して保存する。

    出力カラム例:
        馬名, g1_score, horse_is_g1_winner, num_g1_wins, n_G1_starts, ...
    """
    proba = model.predict(X)
    df_out = df_profile.copy()
    df_out["g1_score"] = proba

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_path, index=False)
    print(f"Saved horse_g1_score to: {out_path} (rows={len(df_out)})")


def main():
    project_root = Path(__file__).resolve().parents[2]
    profile_path = project_root / "data" / "processed" / "kaggle" / "g1_profile_train.csv"
    model_path = project_root / "models" / "kaggle" / "g1_profile_lgbm.txt"
    score_path = project_root / "data" / "processed" / "kaggle" / "horse_g1_score.csv"

    print(f"Loading G1 profile dataset from: {profile_path}")
    df_profile = load_g1_profile_dataset(profile_path)

    X, y, meta = build_feature_matrix(df_profile)
    feature_names = meta["feature_cols"]

    print(f"Dataset shape: X={X.shape}, y_pos={int(y.sum())}, y_neg={len(y) - int(y.sum())}")
    print(f"Num features: {len(feature_names)}")

    # CV でざっくり性能を確認
    params = train_lgbm_with_cv(X, y, feature_names, n_splits=5, random_state=42)

    # 全データで最終モデル学習
    final_model = train_final_model(X, y, feature_names, params, model_path=model_path)

    # 全馬に対して G1スコアを推論・保存
    save_g1_scores(final_model, X, df_profile, feature_names, out_path=score_path)


if __name__ == "__main__":
    main()