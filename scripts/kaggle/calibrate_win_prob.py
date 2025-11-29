"""
Isotonic Regression による勝率キャリブレーション

入力:
    data/processed/kaggle/lgbm_win_pred.csv
    - pred_win : LightGBMの生予測
    - target_win : 正解
    - 単勝 : 倍率

出力:
    data/processed/kaggle/lgbm_win_pred_calibrated.csv
    - calibrated_win : 補正済み勝率
    - calibrated_ev  : 補正後の期待値
"""

from pathlib import Path
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "kaggle" / "lgbm_win_pred.csv"
OUTPUT = ROOT / "data" / "processed" / "kaggle" / "lgbm_win_pred_calibrated.csv"


def main():
    print("=== Isotonic Calibration Start ===")

    df = pd.read_csv(INPUT)

    # 予測値と正解
    pred = df["pred_win"].values
    y = df["target_win"].values

    print(f"[INFO] Input rows: {len(df)}")

    # Isotonic Regression 訓練
    ir = IsotonicRegression(out_of_bounds="clip")  # 範囲外も補正
    calibrated = ir.fit_transform(pred, y)

    # 保存
    df["calibrated_win"] = calibrated
    df["calibrated_ev"] = df["calibrated_win"] * df["単勝"]

    df.to_csv(OUTPUT, index=False)
    print(f"[DONE] 保存しました: {OUTPUT}")


if __name__ == "__main__":
    main()