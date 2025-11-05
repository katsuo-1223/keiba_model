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

## 2025-11-05_1
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

以下のように、今回の進捗を追記できます👇
`docs/progress.md` の末尾にコピペしてください。

---

## 2025-11-06_2

**Done**
* `build_race_master_from_jp.py` を大幅改修

  * **年・月単位のバッチ実行 (`run_batch`)** に対応（例: 2022〜2024年）
  * **厳密フィルタ**（芝／距離1000〜1700m／2〜3歳／1〜2勝クラス）を一覧・詳細の両方で適用
  * **フォールバック処理**：一覧0件時にJP詳細ページからrace_id単位で再取得
  * **resume機能**：既存 `race_master_jp_YYYYMM.csv` をスキップ再利用
  * **write_master_eachオプション**：月ごとの逐次upsert or 最後に一括upsertを選択可能
* `build_race_master.py` を刷新

  * 年範囲（例: 2022〜2024）×月範囲でJPマスターを集約
  * JP→EN整形（列名ゆらぎ対応）と`--strict`フィルタを追加
* 2024年1〜12月の `race_master_jp_YYYYMM.csv` を自動生成
* 1年分のレース情報と結果データを統合

  * 出力: `data/raw/race_master.csv`
  * 出力: `data/processed/race_results_with_master.csv`
* ブランチ `feature/jp_master_batch` を作成し、PR準備完了

**Next**

* PRレビュー後、`main` ブランチへマージ
* 結合済みデータ (`race_results_with_master.csv`) を元にEDA開始

  * 距離・年齢・人気・オッズ・上り・馬体重などの分析基盤構築

**Notes**

* `run_batch()` により途中停止しても再開可能
* Netkeiba側DOM変更時も詳細フォールバックで取得継続
* `data/raw/` は `.gitignore` 対象のまま維持（軽量リポジトリ運用）

