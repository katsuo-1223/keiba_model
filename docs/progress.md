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

## 2025-11-05_2

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

以下を追記すればOKです👇
(`docs/progress.md` の末尾にコピペしてください)

---

## 2025-11-08

**Done**

* `scrape_race_results.py` を全面リファクタリング

  * **v4へ更新**：英語版Netkeiba（`https://en.netkeiba.com`）対応
  * `--site en|jp` オプションを追加し、英語・日本語いずれからもスクレイピング可能に
  * `from-list` 指定時、**JP/EN両形式のURLまたは12桁race_id**を全カラムから自動抽出
  * HTMLエンコーディング検出・正規化（UTF-8, cp932, euc-jp対応）で**文字化けを解消**
  * 出力CSVの文字コード指定（`--encoding utf-8-sig` デフォルト）に対応
  * `FP`を**馬番(3列目)**として取得し、`num_horses = max(FP)` と整合性を確保
  * 取得対象が空の場合は**自動フォールバック（JPリスト検索）**で補完
* `race_urls_2024.csv`（JP形式）からでもENサイト経由で結果取得可能に
* 将来の3年分など長期間スクレイピングにも対応（`--year-start`, `--year-end`パラメータ）

**Next**

* 2024年分全レース結果を再取得し、`data/raw/race_results.csv`を再生成

  * 入力：英語サイトURL（またはrace_id一覧）
  * 出力：`--encoding utf-8-sig` でExcel互換性を確保
* `merge_results_with_master.py` にて`race_master.csv`と結合し、
  `data/processed/race_results_with_master.csv`を作成
* 結合データを用いたEDA（人気・オッズ・距離・上り・馬体重の傾向分析）に着手

**Notes**

* `--site en`指定時は英語サイト構造（`db_h_race_results`テーブル）にも対応済み
* ENサイトURL例：`https://en.netkeiba.com/db/race/202406010107/`
* 出力ファイルはBOM付きUTF-8(`utf-8-sig`)を推奨（Excel開封時の文字化け回避）
* ENサイトとJPサイトを統一ID(`race_id`)で結合可能な設計を維持

了解！次回スムーズに再開できるように、**メモ**と**Git反映（ブランチ切り忘れ時の安全手順）**をまとめます。

---

# メモ（2025-11-09）

## 状況

* 2024年・芝1000–1700m・約50レースの**結合データ**まで整備済み
* 取得は **EN版スクレイパー v6（列ズレ対策・EN専用）**
* 事前検証・EDA用に以下を整備

  * `scripts/validate_merged_dataset.py`（品質ゲート）
  * `scripts/eda_quick_summary.py`（人気×距離・ROIなどの基礎集計）

## 次回やること（優先順）

1. `build_train_dataset.py` を作成（学習用テーブル出力: `data/processed/train_data.csv`）

   * 目的変数：`win_flag = (FP==1)`
   * 特徴量例：`distance_m, popularity, odds, last3f_num, horse_weight_kg, PP, weight(斤量), sex, age` などを整形
2. **データ分割**（レース単位：train≈70%、valid≈30%）
3. `train_lightgbm_roi.py`（勝率予測 → `win_prob` 出力）
4. `evaluate_roi.py`（`EV = win_prob × odds`、EV>1.0 の閾値別ROI集計）

## 実行順（再現手順）

```bash
# 品質チェック（OKなら前進）
python scripts/validate_merged_dataset.py

# EDA（成果物: CSV/PNG）
python scripts/eda_quick_summary.py
```

---
## 2025-11-09

**Done**

* ENスクレイパー v6（ヘッダベース・列ズレ耐性・EN専用）に刷新
* データ品質ゲート `validate_merged_dataset.py` 作成
* 基礎EDA `eda_quick_summary.py` 作成（人気×距離×ROI）

**Next**

* `build_train_dataset.py` で学習表作成（勝率モデル用）
* 2024年データを train/valid に分割（レース単位）
* `train_lightgbm_roi.py` → `evaluate_roi.py` で EV>1.0 のROI検証

**Notes**

* `roi_pct = total_ret / total_bet * 100`（単勝100円想定）
* ENサイトのみ運用。JP解析コードは削除済み（v6）

---
