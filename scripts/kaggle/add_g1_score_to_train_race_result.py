from pathlib import Path

import pandas as pd


def main():
    project_root = Path(__file__).resolve().parents[2]

    # レース結果（1頭1行）のベースデータ
    base_path = project_root / "data" / "processed" / "kaggle" / "train_race_result_basic.csv"
    # さっき作った G1スコア
    score_path = project_root / "data" / "processed" / "kaggle" / "horse_g1_score.csv"

    out_path = project_root / "data" / "processed" / "kaggle" / "train_race_result_basic_with_g1.csv"

    print(f"Loading base race result from: {base_path}")
    df_base = pd.read_csv(base_path)

    print(f"Loading horse G1 score from: {score_path}")
    df_score = pd.read_csv(score_path)

    # マージキーは「馬名」
    if "馬名" not in df_base.columns:
        raise KeyError("train_race_result_basic に '馬名' カラムがありません。")

    if "馬名" not in df_score.columns:
        raise KeyError("horse_g1_score に '馬名' カラムがありません。")

    if "g1_score" not in df_score.columns:
        raise KeyError("horse_g1_score に 'g1_score' カラムがありません。")

    # スコア側は必要な列だけに絞る（余計な重複を避ける）
    df_score_small = df_score[["馬名", "g1_score"]].drop_duplicates()

    print("Merging G1 score into race result...")
    merged = df_base.merge(df_score_small, on="馬名", how="left")

    # マージできなかった馬の件数チェック
    num_missing = merged["g1_score"].isna().sum()
    print(f"Rows with missing g1_score after merge: {num_missing} / {len(merged)}")

    # NaN は 0.0 扱いにしておく（G1プロフィール不明＝G1らしさなしとみなす）
    merged["g1_score"] = merged["g1_score"].fillna(0.0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    print(f"Saved merged dataset to: {out_path} (rows={len(merged)})")


if __name__ == "__main__":
    main()