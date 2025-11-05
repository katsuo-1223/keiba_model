# Progress Log

## 2025-10-25
**Done**
- GitHub SSH連携成功
- 初期リポジトリpush完了

**Next**
- race_resultsスクレイピング部分の実装
- DataFrame結合設計

**Notes**
- SSHキーは id_ed25519 を使用中。Keychain登録済。

## 2025-11-05
**Done**
- Selenium＋webdriver-manager を用いて 2024年分（芝1000〜1700m・2〜3歳・1〜2勝クラス）のレースURLを自動抽出  
  - 出力: `data/raw/race_urls_2024.csv`（不要データなし・URLのみ）  
- `fetch_race_results_from_list.py` を修正し、英語版Netkeibaからレース結果を1年分取得  
  - 出力: `data/raw/race_results.csv`（約50レース）  
- 日本語マスター英語整形スクリプト `build_race_master.py` を刷新  
  - `surface_jp`, `track_condition_jp` → 英語化 (`TURF`, `DIRT`, `Gd`, `Yld` etc.)  
  - スクレイピング依存を排除し、高速・再現性を確保  
- `.gitignore` 整備、`.DS_Store` などの不要ファイルを追跡除外  
- GitHub上にスクリプトを反映（feat/build-race-master-simple → main に統合）

**Next** 
- `build_race_master_from_jp.py` により 2024年1〜12月の日本語マスターを自動収集  
  - 出力: `data/raw/race_master_jp_2024MM.csv`（12ファイル）  
- 英語整形スクリプトで統合し、`data/raw/race_master.csv` を作成  
- `race_results.csv` と `race_master.csv` を結合  
  - 出力: `data/processed/race_results_with_master.csv`  
- 初期EDAおよび特徴量設計（距離・馬齢・人気・オッズ等）

**Notes** 
- 約50レース分（2024年対象条件）の結果データを取得済み  
- リモートのmainブランチを最新化済み  
- `.gitignore` により `.DS_Store`, `__pycache__`, `data/raw/` などを除外  
