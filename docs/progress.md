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

---

# 2025-11-09

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

## 2025-11-12

**Done**

* `add_target_encoding.py` を拡張し、`jockey`, `horse_id`, `trainer` の Target Encoding を生成
* `eda_te_analysis.py` により、TE分布・デシル別勝率・TopNカテゴリを可視化

  * 騎手TE：ごく一部の上位騎手に勝率集中（実際の競馬構造と整合）
  * 馬TE：未勝利多数のロングテール構造、少数の高勝率馬が突出
* `summarize_horse_jockey_stats.py` により、馬・騎手別の登場回数・勝率を集計

  * 複数回登場する馬・騎手を確認（例：C.ルメール勝率0.27）
* モデル方針を「勝率予測」から「ROI最大化」志向に整理

  * 1着予測から連対率・回収率ベースへの方針転換を検討
  * 「馬の成長率」や「条件適性」を考慮した拡張の方向性を整理

---

**Next**

* `build_train_dataset_v3.py`：`target_place = (FP <= 2)` を目的変数に追加
* `train_lightgbm_roi_v2.py` / `evaluate_roi_v2.py`：連対率モデルでROI再検証
* `build_horse_progress_features.py`：同馬の複数レース履歴から「成長率・パフォーマンストレンド特徴量」を生成
* 人気別・条件別のROI分析を追加し、成長型・過小評価型の馬を特定

---

**Notes**

* 騎手TE・馬TE・調教師TEはいずれも有効な特徴量。特に馬TEは成長傾向を補足できる可能性大。
* 現行データは約50レースで小規模なため、データ拡張（2023年以前など）でTEとトレンドを安定化させる。
* ROI重視分析への転換に伴い、「オッズ」「人気」「連対確率」「期待値(EV)」の統合指標を設計予定。

---


## 2025-11-20

**Done**

* Kaggle の JRA データセット（`19860105-20210731_race_result.csv`）を解析開始
* 必要カラムのみ抽出する軽量化スクリプト
  `scripts/kaggle/extract_jra_race_result_light.py` を新規作成

  * レースID／日付／距離／馬場／人気／オッズ／タイム（秒変換含む）など主要列を選定
  * 日本語カラムのまま扱い、JRA形式に最適化
* ディレクトリ構成を再整理

  * `data/raw/kaggle/`, `data/processed/kaggle/` を追加
  * 既存の Netkeiba 系コードは `netkeiba/` ディレクトリに移動
* スクリプト実行により JRA 軽量データ

  * `data/processed/kaggle/jra_race_result_light.csv`
  * `data/processed/kaggle/jra_race_result_light.parquet`
    を生成（Parquetはpyarrow未導入時はCSVのみ出力）

**Next**

* `race.csv`, `odds.csv`, `lap.csv` など Kaggle データの軽量化スクリプトを同様に作成
* Kaggle版 EDA Notebook (`notebooks/kaggle/eda_race_result.ipynb`) を作成
* Kaggle 10年分データを用いた基礎分析＆特徴量の整理
* Kaggle データ版のモデル構築（LightGBM baseline）

**Notes**

* Parquet 出力には `pyarrow` または `fastparquet` が必要
  → 未インストールでもCSVは出力されるよう例外処理済み
* 形式が Netkeiba 英語版とは異なるため、Kaggle 用の前処理・EDA・学習は**完全に独立ライン**で進める

---

## 2025-11-24

**Done**

* VS Code 上で `keiba310` 環境を Jupyter カーネルとして登録し、
  Kaggle JRA データを Notebook でも扱える開発環境を整理

* Kaggle 軽量レース結果（`train_race_result_basic.csv`）を用いた
  LightGBM 複勝ベースライン学習スクリプトを作成・実行

  * スクリプト：`scripts/kaggle/train_lgbm_place_baseline.py`
  * レース日付で時系列分割（～2017年: train / 2018年～: valid）
  * 目的変数：`target_place`（複勝的中フラグ）
  * ID列＋ target列 以外を説明変数として利用
  * LightGBM 4.x に合わせて callbacks 方式で `early_stopping` を実装
  * Validation で AUC ≒ 0.815 を確認
  * 出力：

    * モデル：`models/kaggle/lgbm_place_baseline.txt`
    * 予測結果：`data/processed/kaggle/lgbm_place_pred.csv`
      （`pred_place` 列として複勝確率を出力）

* 複勝オッズとの結合＆期待値計算スクリプトを作成・実行

  * オッズ元データ：`data/raw/kaggle/19860105-20210731_odds.csv`
    （レース単位の横持ち：`複勝1_馬番`／`複勝1_オッズ` …）
  * スクリプト：`scripts/kaggle/attach_place_odds_and_value.py`

    * 予測に含まれるレースID（2018年以降）のみをフィルタ
    * 横持ちの複勝オッズを縦持ちに変換
      → `レースID, 馬番, 複勝オッズ`
    * `lgbm_place_pred.csv` と `レースID + 馬番` で結合
    * 複勝オッズ（100円払戻）を倍率に変換：

      * `複勝オッズ_倍率 = 複勝オッズ / 100`
    * 期待値（Value）を計算：

      * `expected_value = pred_place * 複勝オッズ_倍率`
    * 出力：

      * `data/processed/kaggle/lgbm_place_with_odds.csv`
        （`pred_place`・`複勝オッズ_倍率`・`expected_value` 付き）

**Next**

* `lgbm_place_with_odds.csv` を用いて、期待値しきい値別（`expected_value >= 1.0, 1.05, 1.1` など）の
  ベット件数・的中率・回収率（ROI）を集計するスクリプトを実装・実行

  * まずは「しきい値で機械的に全頭ベット」のシンプルな戦略で検証
* 期待値しきい値ごとの結果を見て、

  * 回収率が 1.0 を超えるゾーンがあるか
  * ベット件数とのトレードオフ（絞りすぎ vs 広げすぎ）
    を確認し、戦略の方向性を整理
* その後の拡張案：

  * 1レースあたり最大ベット頭数の制約（例：1頭のみ、2頭まで など）
  * 特徴量追加（馬体重増減・距離・馬場・競馬場ごとの効果をモデルに反映）
  * LightGBM のハイパーパラメータ調整による精度向上

**Notes**

* LightGBM は 4.x 系のため、`early_stopping_rounds` ではなく
  `lgb.early_stopping()`＋`lgb.log_evaluation()` の callbacks 方式で対応。
* 期待値 `expected_value` は **「倍率ベース」**（= プラスマイナスの基準が 1.0）で定義：

  * `expected_value = pred_place × 複勝オッズ_倍率`
  * `expected_value > 1.0` なら理論上プラスの期待値。
* オッズ CSV は 1986〜2021年分だが、予測は 2018年以降のみのため、
  結合前に **予測側のレースIDでフィルタ** することが重要。

  ---

## **2025-11-29**

### **Done**

* 複勝モデルから単勝モデルへ方向転換

  * 複勝オッズがレース上位 5 頭しか存在せず、学習データ欠損が多過ぎるため
  * Kaggle の単勝オッズは全頭揃っており、期待値分析に適していると判断
* 競馬モデル開発用の **AI 向けプロジェクト憲法（spec）** を整備

  * プロジェクト目的、使用データ、パイプライン仕様、制約を体系化
  * 今後の会話が高速かつ一貫性を持って進められる状態を整備
* **騎手・馬の履歴特徴量（過去レースの強さ指標）を大幅追加**

  * 騎手：通算・距離帯別・競馬場別・芝ダ別での勝率 / 連対率
  * 馬：通算・距離帯別・競馬場別・芝ダ別での勝率 / 連対率
  * 過去レースに基づき “未来情報のリークなし” の累積特徴量を構築
* `build_train_race_result_basic_with_prev.py` を全面拡張し再生成
* `select_final_columns()` に新しい特徴量を追加しモデルに取り込める状態に更新
* 2段階モデル（スタッキング）の準備として
  `build_win_meta_dataset.py` の雛形を作成

---

### **Next**

* 拡張済み特徴量を使って **単勝 LightGBM モデルを再学習**
* `calibrate_win_prob.py` を走らせて再度キャリブレーション
* `eval_win_value_calibrated.py` により、ROI の改善を検証
* メタモデル（オッズ × AI）用の学習スクリプト作成

  * ロジスティック回帰 or 小型 LightGBM
* 最終的に「BET対象を自動抽出する勝負パターン」識別モデルへ拡張

---

### **Notes**

* 特色のある特徴量（騎手距離、馬距離、馬場適性など）が追加され、
  モデルが「それぞれの距離・競馬場・芝/ダートに強い騎手/馬」を学習可能に。
* 期待値分析の精度を上げるため、キャリブレーション（Isotonic Regression）を正式導入。
* 次のステップ（スタッキング）が収益化の核心部分。

---

