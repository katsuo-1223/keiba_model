import argparse
import os
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.metrics import brier_score_loss, log_loss
import lightgbm as lgb


SPEC_COLUMNS = [
    # race-level
    'race_id','date','course_id','surface','distance','going','class_','field_size',
    'cancel_flag','jockey_change_flag',
    # entry-level
    'horse_id','horse_name','draw','frame_no','jockey','trainer',
    'win_odds','rank_pop','prev_rank','last3f','interval_days',
    'body_weight','body_diff',
    # target (train only)
    'finish_position'  # may be missing at prediction time
]

def filter_scope(df: pd.DataFrame) -> pd.DataFrame:
    # Scope per spec
    cond = (
        (df["surface"] == "芝") &
        (df["distance"].between(1600, 2000)) &
        (df["going"] == "良") &
        (df["class_"].isin(['1Win','2Win','3Win','Open','G3','G2','G1'])) &
        (~df["cancel_flag"]) &
        (~df["jockey_change_flag"]) &
        (df["body_diff"].abs() <= 20)  # remove extreme body weight change
    )
    return df.loc[cond].copy()

def add_target(df: pd.DataFrame) -> pd.DataFrame:
    if "finish_position" in df.columns and df["finish_position"].notna().any():
        df["y_place"] = (df["finish_position"] <= 3).astype(int)
    else:
        df["y_place"] = np.nan
    return df

def build_features(df: pd.DataFrame):
    # Basic numeric
    num_cols = [
        "win_odds", "rank_pop", "distance", "field_size",
        "prev_rank", "last3f", "interval_days", "body_weight", "body_diff", "frame_no", "draw"
    ]
    # Categorical (let LightGBM handle)
    cat_cols = ["course_id","class_","jockey","trainer","going","surface"]

    # Ensure dtypes
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in cat_cols:
        df[c] = df[c].astype("category")

    X = df[num_cols + cat_cols]
    cats_idx = [X.columns.get_loc(c) for c in cat_cols]
    return X, cats_idx

def train_and_eval(train_df: pd.DataFrame, cats_idx):
    X = train_df["X"]
    y = train_df["y_place"]
    groups = train_df["race_id"]

    gkf = GroupKFold(n_splits=5)
    oof = np.zeros(len(train_df))
    models = []
    folds = []

    for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups=groups)):
        X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]

        lgb_train = lgb.Dataset(X_tr, label=y_tr, categorical_feature=cats_idx, free_raw_data=False)
        lgb_valid = lgb.Dataset(X_va, label=y_va, categorical_feature=cats_idx, free_raw_data=False)

        params = {
            "objective": "binary",
            "metric": ["binary_logloss"],
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_data_in_leaf": 30,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.9,
            "bagging_freq": 1,
            "verbose": -1,
            "seed": 42,
        }

        model = lgb.train(
            params,
            lgb_train,
            valid_sets=[lgb_train, lgb_valid],
            num_boost_round=2000,
            early_stopping_rounds=100,
            verbose_eval=False,
        )
        models.append(model)
        folds.append((tr_idx, va_idx))
        oof[va_idx] = model.predict(X_va, num_iteration=model.best_iteration)

    # Basic metrics
    brier = brier_score_loss(y, oof)
    try:
        ll = log_loss(y, np.clip(oof, 1e-6, 1-1e-6))
    except ValueError:
        ll = np.nan

    return models, oof, {"brier": brier, "logloss": ll}

def predict_ensemble(models, X):
    preds = np.zeros(len(X))
    for m in models:
        preds += m.predict(X, num_iteration=m.best_iteration)
    preds /= len(models)
    return preds

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="input CSV path")
    ap.add_argument("--out", required=True, help="output predictions CSV path")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df = filter_scope(df)
    df = add_target(df)

    # Build features
    X, cats_idx = build_features(df)
    df["X"] = list(X.values)  # temporary container to keep alignment (not used)
    # Better: keep X separately but align by index
    features_pack = {"X": X, "cats_idx": cats_idx}

    # Split train/predict
    has_label = df["y_place"].notna().all()

    if has_label:
        # Train with GroupKFold by race_id
        train_pack = {
            "X": X,
            "y_place": df["y_place"],
            "race_id": df["race_id"],
        }
        train_df = pd.concat([
            train_pack["X"],
            train_pack["y_place"],
            df["race_id"]
        ], axis=1)
        models, oof, metrics = train_and_eval(train_df, cats_idx)
        print(f"[Metrics] Brier: {metrics['brier']:.4f}, LogLoss: {metrics['logloss']:.4f}")

        # In this minimal example, we also predict on the same filtered set
        p_place = predict_ensemble(models, X)
    else:
        # In a real flow, we would load pre-trained models and predict.
        raise SystemExit("No labels found. Provide a labeled CSV for initial training.")

    out = df[["race_id","horse_id","horse_name","win_odds","rank_pop"]].copy()
    out["p_place"] = p_place
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"Saved predictions to {args.out}")

if __name__ == "__main__":
    main()