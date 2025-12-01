from pathlib import Path

import pandas as pd


def load_race_result(csv_path: Path) -> pd.DataFrame:
    """Kaggle 日本語 race_result CSV を読み込む。

    エンコーディングはまず utf-8 を試し、ダメなら cp932 にフォールバック。
    """
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="cp932")
    return df


def load_horse_g1_labels(csv_path: Path) -> pd.DataFrame:
    """馬単位の G1 ラベルテーブルを読み込む。"""
    return pd.read_csv(csv_path)


def preprocess_race_df(df: pd.DataFrame) -> pd.DataFrame:
    """G1プロファイル用の前処理を行う。

    - 着順を数値化
    - 勝利フラグ / 3着以内フラグを付与
    - 距離・オッズ・人気などを数値化
    - レース日付を datetime 化
    """
    df = df.copy()

    # 着順を数値に（失格・取消などは NaN）
    df["着順_num"] = pd.to_numeric(df["着順"], errors="coerce")
    df["is_win"] = df["着順_num"] == 1
    df["is_top3"] = df["着順_num"].between(1, 3)

    # 人気・単勝オッズを数値に
    if "人気" in df.columns:
        df["人気_num"] = pd.to_numeric(df["人気"], errors="coerce")
    else:
        df["人気_num"] = pd.NA

    if "単勝" in df.columns:
        df["単勝_num"] = pd.to_numeric(df["単勝"], errors="coerce")
    else:
        df["単勝_num"] = pd.NA

    # 距離
    if "距離(m)" in df.columns:
        df["距離_num"] = pd.to_numeric(df["距離(m)"], errors="coerce")
    else:
        df["距離_num"] = pd.NA

    # レース日付
    df["レース日付_dt"] = pd.to_datetime(df["レース日付"])

    return df


def add_is_g1_race_column(df: pd.DataFrame, col_grade: str = "リステッド・重賞競走") -> pd.DataFrame:
    """レースごとに G1 レースかどうかのフラグ列 `is_g1_race` を追加する。

    すでに別スクリプトで付けていても、ここで再計算しておく。
    """
    df = df.copy()
    if col_grade not in df.columns:
        raise KeyError(f"Column '{col_grade}' not found in DataFrame columns: {df.columns.tolist()}")

    df["is_g1_race"] = df[col_grade] == "G1"
    return df


def build_basic_career_features(df: pd.DataFrame) -> pd.DataFrame:
    """馬単位の基本キャリア特徴量を作成する。

    例:
    - 出走数、勝利数、3着以内数
    - 勝率、3着以内率
    - 平均着順、最高着順
    - 平均人気、平均単勝オッズ
    - G1/G2/G3/L の出走数・勝利数
    - 障害出走フラグ（is_steeple_any）
    """
    df = df.copy()

    # 障害かどうかのフラグ（カラム名があれば）
    if "障害区分" in df.columns:
        df["is_steeple"] = df["障害区分"].notna()
    elif "障害区分/Steeplechase Category" in df.columns:
        df["is_steeple"] = df["障害区分/Steeplechase Category"].notna()
    else:
        # カラムが存在しない場合は False で埋める
        df["is_steeple"] = False

    # 基本の集計
    base_agg = (
        df.groupby("馬名")
        .agg(
            n_starts=("レースID", "count"),
            n_wins=("is_win", "sum"),
            n_top3=("is_top3", "sum"),
            avg_finish=("着順_num", "mean"),
            best_finish=("着順_num", "min"),
            avg_popularity=("人気_num", "mean"),
            avg_win_odds=("単勝_num", "mean"),
            any_steeple=("is_steeple", "max"),
        )
        .reset_index()
    )

    # 勝率・3着以内率
    base_agg["win_rate"] = base_agg["n_wins"] / base_agg["n_starts"]
    base_agg["top3_rate"] = base_agg["n_top3"] / base_agg["n_starts"]

    # 障害出走フラグを 0/1 に
    base_agg["is_steeple_any"] = base_agg["any_steeple"].astype(int)
    base_agg = base_agg.drop(columns=["any_steeple"])

    return base_agg


def build_grade_features(df: pd.DataFrame, col_grade: str = "リステッド・重賞競走") -> pd.DataFrame:
    """G1/G2/G3/L ごとの出走数・勝利数を馬単位で集計する。"""
    df = df.copy()
    if col_grade not in df.columns:
        raise KeyError(f"Column '{col_grade}' not found in DataFrame columns: {df.columns.tolist()}")

    grades = ["G1", "G2", "G3", "L"]

    grade_features = pd.DataFrame({"馬名": df["馬名"].drop_duplicates()})

    for g in grades:
        tmp = df[df[col_grade] == g]

        if tmp.empty:
            # そのグレードのレースが存在しない場合は 0 で埋める
            counts = pd.DataFrame({"馬名": [], f"n_{g}_starts": [], f"n_{g}_wins": []})
        else:
            tmp_agg = (
                tmp.groupby("馬名")
                .agg(
                    **{
                        f"n_{g}_starts": ("レースID", "count"),
                        f"n_{g}_wins": ("is_win", "sum"),
                    }
                )
                .reset_index()
            )
            counts = tmp_agg

        grade_features = grade_features.merge(counts, on="馬名", how="left")

    # NaN を 0 で埋める
    for g in grades:
        for col in [f"n_{g}_starts", f"n_{g}_wins"]:
            if col in grade_features.columns:
                grade_features[col] = grade_features[col].fillna(0).astype(int)

    return grade_features


def build_g1_profile_dataset(
    race_df: pd.DataFrame,
    horse_labels: pd.DataFrame,
    col_grade: str = "リステッド・重賞競走",
) -> pd.DataFrame:
    """G1プロファイル学習用の馬単位データセットを構築する。

    出力イメージ:
    - 馬名
    - 基本キャリア特徴量
    - G1/G2/G3/L 出走・勝利数
    - ラベル情報 (horse_is_g1_winner, num_g1_wins, first_g1_win_date, first_race_date, is_left_truncated)
    """
    df = preprocess_race_df(race_df)
    df = add_is_g1_race_column(df, col_grade=col_grade)

    basic_feat = build_basic_career_features(df)
    grade_feat = build_grade_features(df, col_grade=col_grade)

    # 馬名をキーに特徴量を結合
    profile = basic_feat.merge(grade_feat, on="馬名", how="left")

    # G1ラベルをマージ
    # horse_labels の想定カラム:
    #   馬名, horse_is_g1_winner, num_g1_wins, first_g1_win_date, first_race_date, is_left_truncated
    profile = profile.merge(horse_labels, on="馬名", how="left")

    # NaN を必要に応じて埋める
    # （G1未勝利馬は num_g1_wins=0, horse_is_g1_winner=0 になっている想定）
    if "horse_is_g1_winner" in profile.columns:
        profile["horse_is_g1_winner"] = profile["horse_is_g1_winner"].fillna(0).astype(int)
    if "num_g1_wins" in profile.columns:
        profile["num_g1_wins"] = profile["num_g1_wins"].fillna(0).astype(int)
    if "is_left_truncated" in profile.columns:
        profile["is_left_truncated"] = profile["is_left_truncated"].fillna(0).astype(int)

    return profile


def main():
    project_root = Path(__file__).resolve().parents[2]  # scripts/kaggle/ から見てプロジェクトルートを想定

    raw_csv_path = project_root / "data" / "raw" / "kaggle" / "19860105-20210731_race_result.csv"
    horse_label_path = project_root / "data" / "processed" / "kaggle" / "horse_g1_label.csv"
    out_path = project_root / "data" / "processed" / "kaggle" / "g1_profile_train.csv"

    print(f"Loading race_result from: {raw_csv_path}")
    race_df = load_race_result(raw_csv_path)

    print(f"Loading horse_g1_label from: {horse_label_path}")
    horse_labels = load_horse_g1_labels(horse_label_path)

    print("Building G1 profile dataset...")
    profile_df = build_g1_profile_dataset(race_df, horse_labels, col_grade="リステッド・重賞競走")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    profile_df.to_csv(out_path, index=False)
    print(f"Saved G1 profile dataset to: {out_path} (rows={len(profile_df)})")


if __name__ == "__main__":
    main()