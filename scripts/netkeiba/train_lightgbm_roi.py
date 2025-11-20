#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import pandas as pd
import lightgbm as lgb
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/processed")
    ap.add_argument("--model-out", default="models/lgbm_win_prob.txt")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-leaves", type=int, default=63)
    ap.add_argument("--n-estimators", type=int, default=800)
    ap.add_argument("--lr", type=float, default=0.03)
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    Path("models").mkdir(exist_ok=True)

    train = pd.read_csv(data_dir / "train_dataset.csv")
    valid = pd.read_csv(data_dir / "valid_dataset.csv")

    meta = json.loads(Path(data_dir / "train_meta.json").read_text())
    feature_cols = meta["feature_cols"]
    target_col = meta["target_col"]

    train_x, train_y = train[feature_cols], train[target_col]
    valid_x, valid_y = valid[feature_cols], valid[target_col]

    lgb_train = lgb.Dataset(train_x, label=train_y)
    lgb_valid = lgb.Dataset(valid_x, label=valid_y)

    params = dict(
        objective="binary",
        metric=["auc", "binary_logloss"],
        learning_rate=args.lr,
        num_leaves=args.num_leaves,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=1,
        random_state=args.seed,
        verbose=-1,
    )

    model = lgb.train(
        params,
        lgb_train,
        num_boost_round=args.n_estimators,
        valid_sets=[lgb_train, lgb_valid],
        valid_names=["train", "valid"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100, verbose=True),
            lgb.log_evaluation(period=50),
        ],
    )

    model.save_model(str(Path(args.model_out)))

    # 検証データに確率を付与
    valid_out = valid.copy()
    valid_out["p_win"] = model.predict(valid_x, num_iteration=model.best_iteration)
    valid_out.to_csv(data_dir / "valid_with_pred.csv", index=False)

    print("Saved model:", args.model_out)
    print("Saved preds:", data_dir / "valid_with_pred.csv")


if __name__ == "__main__":
    main()