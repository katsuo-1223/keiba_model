import pandas as pd
import matplotlib.pyplot as plt

def main():
    df = pd.read_csv("data/processed/kaggle/lgbm_win_pred_calibrated.csv")

    df["EV"] = df["calibrated_win"] * df["単勝_倍率"]

    print(df["EV"].describe())

    # EVヒストグラム
    plt.hist(df["EV"], bins=100)
    plt.xlabel("EV")
    plt.ylabel("count")
    plt.title("Expected Value Distribution (Win)")
    plt.show()

    # EV>=1 の割合
    ev_ratio = (df["EV"] >= 1).mean()
    print(f"EV>=1 ratio: {ev_ratio:.3f}")

if __name__ == "__main__":
    main()