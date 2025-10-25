from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import csv
import os

# Selenium設定
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)

# 対象のレース一覧ページ（2024年1月分）
url = "https://en.netkeiba.com/db/race/race_list.html?pid=race_list&word=&track[]=1&start_mon=1&start_year=2024&end_mon=1&end_year=2024&jyo[]=01&jyo[]=02&jyo[]=03&jyo[]=04&jyo[]=05&jyo[]=06&jyo[]=07&jyo[]=08&jyo[]=09&jyo[]=10&barei[]=11&barei[]=12&grade[]=6&grade[]=7&kyori_min=1000&kyori_max=1700&sort=date"

# ページを開く
driver.get(url)

# ページをスクロールして読み込みを促進
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(5)  # 読み込み待ち時間を延長

# ページのHTMLを保存して確認（デバッグ用）
with open("page_source.html", "w") as f:
    f.write(driver.page_source)

# レースリンクを抽出（より広い範囲で検索）
elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/db/race/')]")
race_urls = sorted(set([e.get_attribute("href") for e in elements]))

# 保存先ディレクトリを作成
os.makedirs("data/raw", exist_ok=True)

# CSVに保存
with open("data/raw/race_urls_jan2024.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Race URL"])
    for u in race_urls:
        writer.writerow([u])

print