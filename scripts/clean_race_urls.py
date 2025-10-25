import pandas as pd
import re

# 元データの読み込み
df = pd.read_csv("data/raw/race_urls_jan2024.csv")

# 数字のみのIDを持つURLだけを残す
def is_valid_race_url(url):
    match = re.search(r"/db/race/([0-9]+)/", url)
    return bool(match)

df_cleaned = df[df["Race URL"].apply(is_valid_race_url)]

# 保存
df_cleaned.to_csv("data/raw/race_urls_jan2024_cleaned.csv", index=False)
print(f"✅ {len(df_cleaned)} 件の有効なURLを保存しました。")