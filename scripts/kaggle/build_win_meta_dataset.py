"""
単勝モデルの1段目出力（calibrated_win）と
レース基本情報（馬・騎手の通算成績など）を結合して、
2段目スタッキング用のデータセットを作るスクリプト。

入力:
    - data/processed/kaggle/lgbm_win_pred_calibrated.csv
        レースID, 馬番, レース日付, target_win, 単勝, pred_win, calibrated_win ...
    - data/processed/kaggle/train_race_result_basic.csv
        レースID, 馬番, レース日付, 馬_通算勝率, 騎手_通算勝率, ...

出力:
    - data/processed/kaggle/win_meta_train.csv
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

PRED_CALIB_PATH = ROOT / "data" / "processed" / "kaggle" / "lgbm_win_pred_calibrated.csv"
BASIC_PATH      = ROOT / "data" / "processed" / "kaggle" / "train_race_result_basic.csv"
OUTPUT_PATH     = ROOT / "data" / "processed" / "kaggle" / "win_meta_train.csv"


def main() -> None:
    print("=== build_win_meta_dataset.py 開始 ===")
    print(f"[INFO] PRED_CALIB_PATH: {PRED_CALIB_PATH}")
    print(f"[INFO] BASIC_PATH     : {BASIC_PATH}")

    df_pred = pd.read_csv(PRED_CALIB_PATH)
    df_basic = pd.read_csv(BASIC_PATH)

    # キーを揃える
    for c in ["レースID"]:
        df_pred[c] = df_pred[c].astype(str)
        df_basic[c] = df_basic[c].astype(str)

    # レースID & 馬番 でマージ
    key = ["レースID", "馬番"]
    df = pd.merge(
        df_pred,
        df_basic,
        on=key,
        how="inner",
        suffixes=("", "_base"),
    )

    print(f"[merge] 結合後: {df.shape}")

    # 日付を時系列扱いできるように
    df["レース日付"] = pd.to_datetime(df["レース日付"])

    # 2段目モデルで使うカラムを選択
    # まず最低限のID/ターゲット/1段目の出力/オッズ
    base_cols = [
        "レースID",
        "レース日付",
        "競馬場コード",
        "競馬場名",
        "馬番",
        "馬名",
        "target_win",
        "単勝",              # オッズ（倍率）
        "pred_win",          # 1段目の生予測（参考）
        "calibrated_win",    # 1段目のキャリブレーション後の勝率
    ]

    # 馬・騎手の通算成績（名前は実際の列名に合わせて調整してください）
    horse_cols = [
        "馬_通算出走数",
        "馬_通算勝率",
        "馬_通算連対率",
        "馬距離_通算勝率",
        "馬場_通算勝率",
        "馬芝ダ_通算勝率",
    ]

    jockey_cols = [
        "騎手_通算騎乗数",
        "騎手_通算勝率",
        "騎手_通算連対率",
        "騎手距離_通算勝率",
        "騎手場_通算勝率",
        "騎手芝ダ_通算勝率",
    ]

    # 存在確認（なければ警告出してスキップするようにしておく）
    selected_extra_cols = []
    for c in horse_cols + jockey_cols:
        if c in df.columns:
            selected_extra_cols.append(c)
        else:
            print(f"[WARN] 列が見つかりませんでした（スキップ）: {c}")

    use_cols = base_cols + selected_extra_cols

    df_out = df[use_cols].copy()
    df_out.to_csv(OUTPUT_PATH, index=False)
    print(f"[save] win_meta_train を保存しました: {OUTPUT_PATH}")
    print("=== 正常終了 ===")


if __name__ == "__main__":
    main()