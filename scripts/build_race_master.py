import pandas as pd
from pathlib import Path

IN_CSV  = Path("data/raw/race_master_jp_202401.csv")
OUT_CSV = Path("data/raw/race_master.csv")

VENUE_MAP = {
    "札幌": "SAPPORO","函館": "HAKODATE","福島": "FUKUSHIMA","新潟": "NIIGATA",
    "東京": "TOKYO","中山": "NAKAYAMA","中京": "CHUKYO","京都": "KYOTO",
    "阪神": "HANSHIN","小倉": "KOKURA",
}
SURFACE_MAP = {"芝": "TURF", "ダート": "DIRT"}
TRACK_COND_MAP = {"良": "Gd", "稍重": "Yld", "重": "Sft", "不良": "Hvy"}
WEATHER_MAP = {
    "晴": "Sunny", "曇": "Cloudy", "小雨": "LightRain",
    "雨": "Rain", "小雪": "LightSnow", "雪": "Snow"
}

def translate_master(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 列名の標準化
    rename_map = {
        "場所": "venue",
        "venue_jp": "venue",
        "surface_jp": "surface_type",
        "track_condition_jp": "track_condition",
        "track_condision_jp": "track_condition",  # タイポ対策
        "天候": "weather",
        "weather_jp": "weather",
    }
    df.rename(columns=rename_map, inplace=True)

    # venue
    if "venue" in df.columns:
        df["venue"] = df["venue"].map(VENUE_MAP).fillna(df["venue"])

    # surface_type
    if "surface_type" in df.columns:
        df["surface_type"] = df["surface_type"].map(SURFACE_MAP).fillna(df["surface_type"])

    # track_condition（←ここを明示的に変換）
    if "track_condition" in df.columns:
        df["track_condition"] = df["track_condition"].map(TRACK_COND_MAP).fillna(df["track_condition"])

    # weather
    if "weather" in df.columns:
        df["weather"] = df["weather"].replace(WEATHER_MAP)

    return df

def main():
    df = pd.read_csv(IN_CSV, dtype={"race_id": str})
    print("📄 読み込んだ列:", df.columns.tolist())

    df_out = translate_master(df)
    df_out.to_csv(OUT_CSV, index=False)
    print(f"✅ wrote {OUT_CSV}, rows={len(df_out)}")

if __name__ == "__main__":
    main()