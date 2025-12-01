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


def add_is_g1_race_column(df: pd.DataFrame, col_grade: str = "リステッド・重賞競走") -> pd.DataFrame:
    """レースごとに G1 レースかどうかのフラグ列 `is_g1_race` を追加する。

    Args:
        df: 元のレース結果 DataFrame（1行=1頭）
        col_grade: G1/G2/G3/L などが入っているカラム名

    Returns:
        `is_g1_race` 列を追加した DataFrame
    """
    if col_grade not in df.columns:
        raise KeyError(f"Column '{col_grade}' not found in DataFrame columns: {df.columns.tolist()}")

    df = df.copy()
    df["is_g1_race"] = df[col_grade] == "G1"
    return df


def build_race_is_g1_table(df: pd.DataFrame) -> pd.DataFrame:
    """レースID単位で G1 フラグをまとめたテーブルを作る。

    - 1レースIDにつき1行
    - カラム: レースID, レース日付, 競馬場名, レース名, is_g1_race
    """
    cols = ["レースID", "レース日付", "競馬場名", "レース名", "is_g1_race"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Required columns not found: {missing}")

    race_df = (
        df[cols]
        .drop_duplicates(subset=["レースID"])
        .reset_index(drop=True)
    )
    return race_df


def build_horse_g1_label_table(df: pd.DataFrame) -> pd.DataFrame:
    """馬単位の G1勝ちフラグと初G1勝ち日などの情報を作る。

    ルール:
    - G1レース (is_g1_race=True) かつ 着順==1 のレコードを「G1勝利」とみなす
    - 馬名ごとに
        - G1勝利回数 (num_g1_wins)
        - G1を1回でも勝っていれば horse_is_g1_winner=1, なければ0
        - 初G1勝ち日 (first_g1_win_date, YYYY-MM-DD) を付与
    """
    required_cols = ["レースID", "レース日付", "馬名", "着順", "is_g1_race"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Required columns not found: {missing}")

    df = df.copy()

    # 着順を数値にして、1着だけを勝ちと判定（失格・取消などは NaN になっている前提）
    df["着順_num"] = pd.to_numeric(df["着順"], errors="coerce")

    # G1勝利レコードだけ抽出
    g1_win = df[(df["is_g1_race"]) & (df["着順_num"] == 1)].copy()

    # 日付を datetime に
    g1_win["レース日付_dt"] = pd.to_datetime(g1_win["レース日付"])

    # 馬ごとの G1 勝利回数
    g1_win_count = (
        g1_win.groupby("馬名")
        .agg(
            num_g1_wins=("レースID", "nunique"),
            first_g1_win_date=("レース日付_dt", "min"),
        )
        .reset_index()
    )

    # 馬名ごとに最初の出走日を取得
    first_dates = (
        df.groupby("馬名")["レース日付"]
        .min()
        .reset_index()
        .rename(columns={"レース日付": "first_race_date"})
    )

    first_dates["first_race_date"] = pd.to_datetime(first_dates["first_race_date"])

    # 1986年に初出走 → 過去にレースがある可能性が高い
    first_dates["is_left_truncated"] = (
        first_dates["first_race_date"].dt.year == 1986
    ).astype(int)

    # 馬名の全リスト（G1勝ち経験のない馬も含めるため）
    all_horses = df[["馬名"]].drop_duplicates().copy()

    # 左結合して、G1勝ちがない馬は NaN → 0 / NaT に埋める
    horse_tbl = all_horses.merge(g1_win_count, on="馬名", how="left")

    horse_tbl["num_g1_wins"] = horse_tbl["num_g1_wins"].fillna(0).astype(int)
    horse_tbl["horse_is_g1_winner"] = (horse_tbl["num_g1_wins"] > 0).astype(int)
    # 日付は文字列として保存しておく（NaT は空文字に）
    horse_tbl["first_g1_win_date"] = horse_tbl["first_g1_win_date"].dt.strftime("%Y-%m-%d")
    horse_tbl["first_g1_win_date"] = horse_tbl["first_g1_win_date"].fillna("")

    # 馬ラベルテーブルにマージ
    horse_tbl = horse_tbl.merge(first_dates, on="馬名", how="left")

    # カラム順を整理
    horse_tbl = horse_tbl[
        ["馬名", "horse_is_g1_winner", "num_g1_wins", "first_g1_win_date", "is_left_truncated"]
    ].sort_values(["horse_is_g1_winner", "num_g1_wins"], ascending=[False, False])

    return horse_tbl


def main():
    project_root = Path(__file__).resolve().parents[2]  # scripts/kaggle/ から見てプロジェクトルートを想定
    raw_csv_path = project_root / "data" / "raw" / "kaggle" / "19860105-20210731_race_result.csv"
    processed_dir = project_root / "data" / "processed" / "kaggle"
    processed_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading race_result from: {raw_csv_path}")
    df = load_race_result(raw_csv_path)

    # G1フラグ追加
    df = add_is_g1_race_column(df, col_grade="リステッド・重賞競走")

    # レース単位 G1テーブル
    race_is_g1 = build_race_is_g1_table(df)
    race_out_path = processed_dir / "race_is_g1_flag.csv"
    race_is_g1.to_csv(race_out_path, index=False)
    print(f"Saved race_is_g1_flag to: {race_out_path} (rows={len(race_is_g1)})")

    # 馬単位 G1ラベルテーブル
    horse_g1_tbl = build_horse_g1_label_table(df)
    horse_out_path = processed_dir / "horse_g1_label.csv"
    horse_g1_tbl.to_csv(horse_out_path, index=False)
    print(f"Saved horse_g1_label to: {horse_out_path} (rows={len(horse_g1_tbl)})")


if __name__ == "__main__":
    main()