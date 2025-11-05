from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time, csv, os

def build_en_list_url(year:int, mon:int, page:int=1)->str:
    # list=100 で1ページ100件、page=でページ送り
    return (
        "https://en.netkeiba.com/db/race/race_list.html"
        "?pid=race_list&word="
        "&track[]=1"
        f"&start_mon={mon}&start_year={year}"
        f"&end_mon={mon}&end_year={year}"
        "&jyo[]=01&jyo[]=02&jyo[]=03&jyo[]=04&jyo[]=05&jyo[]=06&jyo[]=07&jyo[]=08&jyo[]=09&jyo[]=10"
        "&barei[]=11&barei[]=12"
        "&grade[]=6&grade[]=7"
        "&kyori_min=1000&kyori_max=1700"
        "&sort=date"
        "&list=100"
        f"&page={page}"
    )

options = Options()
options.add_argument("--headless=new")

# ✅ 自動でChromeに合うドライバを取得
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

all_urls = set()
try:
    for mon in range(1, 13):
        page = 1
        while True:
            url = build_en_list_url(2024, mon, page)
            driver.get(url)
            # 読み込み待ち（必要に応じ延長）
            time.sleep(2.0)

            # レースリンク抽出
            elems = driver.find_elements(By.XPATH, "//a[contains(@href, '/db/race/') and contains(@href, '/db/race/')]")
            urls = {e.get_attribute("href") for e in elems if e.get_attribute("href")}
            # race詳細のみ（listページ内の他リンク混入対策）
            urls = {u for u in urls if "/db/race/" in u and u.rstrip("/").split("/")[-1].isdigit()}

            before = len(all_urls)
            all_urls |= urls
            added = len(all_urls) - before

            # 次ページが無いときは break（新規に何も増えなければ最後のページと判断）
            if added == 0:
                break
            page += 1

    # 保存
    os.makedirs("data/raw", exist_ok=True)
    out_csv = "data/raw/race_urls_2024.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["race_url"])
        for u in sorted(all_urls):
            w.writerow([u])
    print(f"✅ collected {len(all_urls)} urls → {out_csv}")

finally:
    driver.quit()