# Keiba Baseline (Step 1: 梅)

目的: CSVを読み込むと、各馬の「複勝確率 P(top3)」を出力する最小構成を動かす。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 使い方

入力CSV（例: `sample_data.csv`）の列仕様はファイル冒頭のコメント参照。
学習・予測は同じスクリプトで動作します。`finish_position` が入っていれば学習、
無ければ学習済みモデルがあれば予測のみ行います（サンプルでは学習→即時予測）。

```bash
python train_and_predict.py --csv sample_data.csv --out outputs/preds.csv
```

出力: `race_id, horse_id, p_place`（3着以内確率）ほか補助列。

## 対象レースのフィルタ（仕様）
- 芝 1600〜2000m
- 良馬場
- 1勝クラス以上（['1Win', '2Win', '3Win', 'Open', 'G3', 'G2', 'G1']）
- 出走取消・乗り替わり多数・±20kg超増減は除外（サンプルでは個別馬の除外）

## 注意（リーク対策）
- 時系列分割（例: 2023年まで学習、2024年以降を検証）を行うこと。
- GroupKFoldを`race_id`で行い、同一レースがtrain/validにまたがらないようにする。
- 特徴量は「発走前に入手可能なもの」に限定する（確定払戻などはNG）。

## 次の拡張
- 前走×コース補正のスピード指標、脚質、滞在競馬フラグ
- 校正（温度スケーリング）
- ROIベースのベット戦略（EV>0のフィルタ）