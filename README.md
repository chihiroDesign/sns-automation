# SNS Content Auto-Generator

毎週月曜朝9時(JST)に GitHub Actions が自動実行し、
**チンアナゴ人生相談** と **POPPY GUMMY BEARS** の2週間分(14件)の投稿ネタを
Google スプレッドシートに追記します。

---

## スプレッドシートの列構成

| 列 | 内容 |
|---|---|
| Date | 投稿予定日 (YYYY-MM-DD) |
| Series | チンアナゴ人生相談 / POPPY GUMMY BEARS |
| Topic or Scene | 相談テーマ(チンアナゴ) / シーン概要(POPPY) |
| EN Script | 英語セリフ(10秒以内) |
| JA Subtitle | 日本語字幕 |
| Image Prompt | 画像生成プロンプト(POPPY のみ) |
| Shooting Note | 撮影メモ(チンアナゴ のみ) |
| EN Caption | 英語キャプション |
| JA Caption | 日本語キャプション |
| Hashtags | ハッシュタグ |
| Status | Draft / Approved / Posted |

---

## 必要な GitHub Secrets

| Secret 名 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API キー |
| `GOOGLE_CREDENTIALS_JSON` | Google Service Account の JSON キー（文字列） |
| `SPREADSHEET_ID` | 対象スプレッドシートの ID |

---

## Google Sheets API セットアップ手順

### 1. Google Cloud プロジェクトを作成

1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. 上部のプロジェクト選択 → **新しいプロジェクト** → プロジェクト名を入力して作成

### 2. Google Sheets API を有効化

1. 左メニュー → **API とサービス** → **ライブラリ**
2. 検索欄に `Google Sheets API` と入力
3. **Google Sheets API** を選択 → **有効にする**

### 3. Service Account を作成

1. 左メニュー → **API とサービス** → **認証情報**
2. **認証情報を作成** → **サービス アカウント**
3. 任意の名前(例: `sns-automation`)を入力 → **作成して続行**
4. ロールは **編集者** を選択 → **完了**

### 4. JSON キーを発行

1. 作成したサービスアカウントをクリック → **キー** タブ
2. **鍵を追加** → **新しい鍵を作成** → **JSON** → **作成**
3. JSON ファイルがダウンロードされる（大切に保管）

### 5. スプレッドシートを作成・共有

1. [Google スプレッドシート](https://sheets.google.com/) で新規シートを作成
2. URL から ID をコピー:
   `https://docs.google.com/spreadsheets/d/【ここがSPREADSHEET_ID】/edit`
3. シートの **共有** ボタン → サービスアカウントのメールアドレス
   (例: `sns-automation@your-project.iam.gserviceaccount.com`) を **編集者** として追加

### 6. GitHub Secrets に登録

リポジトリの **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `GOOGLE_CREDENTIALS_JSON` | JSON ファイルの内容をそのまま貼り付け |
| `SPREADSHEET_ID` | スプレッドシートの ID 文字列 |

> `GOOGLE_CREDENTIALS_JSON` は JSON ファイルをテキストエディタで開き、
> 内容を丸ごとコピーして貼り付けてください。

---

## ローカルでのテスト実行

```bash
# 依存パッケージをインストール
pip install anthropic gspread google-auth

# 環境変数をセット
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_CREDENTIALS_JSON='{ "type": "service_account", ... }'
export SPREADSHEET_ID="your-spreadsheet-id"

# 実行
python scripts/generate_content.py
```

---

## ワークフロー手動実行

GitHub Actions の **Actions** タブ → **Generate Weekly SNS Content** →
**Run workflow** ボタンで任意のタイミングで実行できます。

---

## ファイル構成

```
sns-automation/
├── .github/
│   └── workflows/
│       └── generate.yml    # GitHub Actions ワークフロー
├── scripts/
│   └── generate_content.py # メインスクリプト
└── README.md
```
