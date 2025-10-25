from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import pandas as pd
import time
import os

# 入力ファイルの読み込み
input_csv = "data/raw/race_urls_jan2024_cleaned.csv"
urls_df = pd.read_csv(input_csv)
race_urls = urls_df["Race URL"].dropna().tolist()

# Seleniumの設定（ヘッドレスモード）
options = Options()
options.add_argument("--headless")

# 修正された初期化方法
service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# 出力ディレクトリの作成
output_dir = "data/raw"
os.makedirs(output_dir, exist_ok=True)

# 結果格納用リスト
all_results = []

# レース結果表の抽出関数
def extract_race_result(url):
    try:
        driver.get(url)
        time.sleep(2)  # ページ読み込み待ち

        tables = driver.find_elements(By.TAG_NAME, "table")
        for table in tables:
            html = table.get_attribute('outerHTML')
            df_list = pd.read_html(html)
            for df in df_list:
                if any(col in df.columns for col in ['Horse', '馬名']):
                    df['Source URL'] = url
                    return df
    except Exception as e:
        print(f"❌ Error processing {url}: {e}")
    return None

# 各URLを処理
for i, url in enumerate(race_urls, 1):
    print(f"🔄 Processing {i}/{len(race_urls)}: {url}")
    result_df = extract_race_result(url)
    if result_df is not None:
        all_results.append(result_df)

# 結果をCSVに保存
if all_results:
    combined_df = pd.concat(all_results, ignore_index=True)
    output_path = os.path.join(output_dir, "race_results_jan2024.csv")
    combined_df.to_csv(output_path, index=False)
    print(f"✅ Saved combined results to {output_path}")
else:
    print("⚠️ No race results were extracted.")

# ブラウザを閉じる
driver.quit()