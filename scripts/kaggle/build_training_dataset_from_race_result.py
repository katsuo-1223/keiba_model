# scripts/kaggle/build_training_dataset_from_race_result.py
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "jra_race_result_light.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "kaggle" / "train_race_result_basic.csv"

def main():
    df = pd.read_csv(INPUT_PATH)

    # 1. 基本フィルタ：芝・ダートのみ
    df = df[df["芝・ダート区分"].isin(["芝", "ダート"])].copy()

    # 2. 目的変数を作成
    df["target_win"] = (df["着順"] == 1).astype(int)
    df["target_place"] = (df["着順"] <= 3).astype(int)

    # 3. 特徴量候補（まずはシンプルに数値中心）
    feature_cols = [
        "距離(m)",
        "馬齢",
        "斤量",
        "単勝",      # オッズ
        "人気",
        "馬体重",
        "場体重増減",
    ]

    # カテゴリ変数（最初は one-hot しても次元が爆発しないものだけ）
    cat_cols = [
        "芝・ダート区分",
        "馬場状態1",   # 良 / 稍重 / 重 など
        # 必要なら 天候, 競馬場名 なども後で
    ]

    # 4. リークになる列はここで除外（学習用に渡さない）
    leak_cols = [
        "着順", "着順注記",
        "タイム", "上り",
        "賞金(万円)", "タイム_秒",
    ]

    # 5. one-hot エンコード
    df_features = df[feature_cols + cat_cols].copy()
    df_features = pd.get_dummies(df_features, columns=cat_cols, drop_first=True)

    # 6. 目的変数も付けて保存
    df_out = pd.concat(
        [
            df[["レースID", "レース日付", "競馬場コード", "競馬場名", "馬番", "馬名"]],
            df_features,
            df[["target_win", "target_place"]],
        ],
        axis=1,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved training dataset to: {OUTPUT_PATH}")

    # 余力があれば parquet 保存
    try:
        df_out.to_parquet(OUTPUT_PATH.with_suffix(".parquet"), index=False)
        print(f"Saved Parquet to: {OUTPUT_PATH.with_suffix('.parquet')}")
    except Exception as e:
        print(f"Parquet 保存はスキップしました: {e}")

if __name__ == "__main__":
    main()