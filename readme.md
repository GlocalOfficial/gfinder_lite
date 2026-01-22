# G-Finder Lite⚡

G-Finderのデータベース（ElasticSearch）を使用して簡易的に検索・件数表示・要約ができるStreamlitアプリケーション

## 📋 目次

- [概要](#概要)
- [機能](#機能)
- [必要要件](#必要要件)
- [セットアップ](#セットアップ)
- [使い方](#使い方)
- [ユーザー制限機能](#ユーザー制限機能)
- [ファイル構成](#ファイル構成)
- [トラブルシューティング](#トラブルシューティング)

---

## 概要

G-Finder Liteは、Elasticsearchに格納された自治体の公開文書データを検索・分析するためのWebアプリケーションです。キーワード検索、年度絞り込み、自治体・カテゴリ別の集計、そしてGemini AIによる要約機能を提供します。

---

## 機能

### 🔍 検索機能
- **キーワード検索**: AND/OR/NOT条件での複合検索
- **年度絞り込み**: 2010年〜2030年の年度指定
- **自治体選択**: ツリー形式で都道府県・市区町村を選択
- **カテゴリ選択**: 予算決算、計画方針、議会議事録、広報など
- **検索対象フィールド**: 本文、資料名から選択可能

### 📊 集計・可視化
- **件数タブ**: 自治体×カテゴリのクロス集計（ファイル数/ページ数）
- **最新収集月タブ**: 各自治体の最新データ収集時期を表示
- **検索結果タブ**: 詳細な検索結果一覧とPDFリンク

### 🤖 AI要約機能
- Gemini APIを使った検索結果の自動要約
- カスタムプロンプトによる柔軟な分析

### 🔐 ユーザー制限機能
- クエリファイルによるアクセス制御
- 自治体・カテゴリの閲覧制限
- 検索条件の固定モード

---

## 必要要件

### システム要件
- Python 3.8以上
- Elasticsearch 8.13.0
- Gemini API（AI要約用）

### Pythonパッケージ
```
streamlit
st-ant-tree
elasticsearch==8.13.0
pandas
openpyxl
google-generativeai
```

---

## セットアップ

### 1. リポジトリのクローン
```bash
git clone <repository-url>
cd g-finder-lite
```

### 2. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

### 3. 必須データファイルの準備

以下のファイルをプロジェクトルートに配置してください：

#### `jichitai.xlsx`（自治体マスターデータ）
全国の自治体情報を管理するExcelファイル。以下の列が必須です：

| 列名 | 型 | 説明 | 例 |
|------|-----|------|-----|
| `code` | 文字列 | 自治体コード（6桁） | `131016` |
| `affiliation_code` | 文字列 | 都道府県コード（2桁） | `13` |
| `pref_name` | 文字列 | 都道府県名 | `東京都` |
| `city_name` | 文字列 | 市区町村名 | `千代田区` |
| `city_type` | 文字列 | 自治体区分 | `特別区`, `市`, `町`, `村` |

※複数の都道府県で同名の自治体がある場合はUI上で判別しやすいようにcity_nameの末尾に「（◯◯県）」とつける

例：森町(北海道), 森町(静岡県)

**サンプル（jichitai.xlsx）:**
```
code    | affiliation_code | pref_name | city_name | city_type
--------|------------------|-----------|-----------|----------
011002  | 01               | 北海道    | 札幌市    | 市
131016  | 13               | 東京都    | 千代田区  | 特別区
271004  | 27               | 大阪府    | 大阪市    | 市
```

#### `category.xlsx`（カテゴリマスターデータ）
資料カテゴリを管理するExcelファイル。以下の列が必須です：

| 列名 | 型 | 説明 | 例 |
|------|-----|------|-----|
| `category` | 整数 | カテゴリID | `1` |
| `category_name` | 文字列 | カテゴリ名（詳細） | `予算・決算書` |
| `short_name` | 文字列 | カテゴリ名（短縮） | `予算決算` |
| `order` | 整数 | 表示順序 | `1` |
| `group` | 文字列 | グループ名（任意） | `財政` |

**サンプル（category.xlsx）:**
```
category | category_name      | short_name   | order | group
---------|-------------------|--------------|-------|-------
1        | 予算・決算書       | 予算決算     | 1     | 予算
2        | 総合計画・基本方針 | 計画方針     | 2     | 計画
3        | 議会議事録         | 議事録       | 3     | 議会議事録
```

#### `auth.xlsx`（ユーザー認証・権限管理）**[オプション]**
ユーザーごとのログイン情報と権限を管理するExcelファイル。以下の列が必須です：

| 列名 | 型 | 説明 | 例 |
|------|-----|------|-----|
| `username` | 文字列 | ログインID | `user_tokyo` |
| `password` | 文字列 | パスワード | `pass123` |
| `display_name` | 文字列 | 表示名 | `東京都ユーザー` |
| `query_file` | 文字列 | クエリファイル名（queryディレクトリ内） | `user_tokyo.json` |
| `can_modify_query` | 文字列 | クエリ修正可否（`TRUE`/`FALSE`） | `FALSE` |
| `enabled` | 文字列 | アカウント有効/無効（`TRUE`/`FALSE`） | `TRUE` |

**サンプル（auth.xlsx）:**
```
username    | password | display_name      | query_file        | can_modify_query | enabled
------------|----------|-------------------|-------------------|------------------|--------
admin       | admin123 | 管理者            |                   | TRUE             | TRUE
user_tokyo  | tokyo456 | 東京都ユーザー    | user_tokyo.json   | FALSE            | TRUE
user_osaka  | osaka789 | 大阪府ユーザー    | user_osaka.json   | TRUE             | TRUE
guest       | guest000 | ゲストユーザー    | guest.json        | FALSE            | FALSE
```

**列の詳細説明:**

- **username**: ログイン時に使用するユーザーID（一意である必要があります）
- **password**: 平文パスワード（⚠️ 本番環境ではハッシュ化を推奨）
- **display_name**: アプリ内で表示されるユーザー名
- **query_file**: 
  - 空欄: 制限なし（全データアクセス可能）
  - ファイル名指定: `query/`ディレクトリ内のJSONファイルを参照
- **can_modify_query**:
  - `TRUE`: ベースクエリに追加してキーワード検索等が可能
  - `FALSE`: クエリ固定モード（検索条件変更不可）
- **enabled**:
  - `TRUE`: ログイン可能
  - `FALSE`: アカウント無効（ログイン不可）


### 4. Streamlit Secretsの設定

`.streamlit/secrets.toml` ファイルを作成し、以下の情報を設定：

```toml
# パスワード認証（オプション）
APP_PASSWORD = "your-password"

# Elasticsearch接続情報
ES_HOST = "https://your-elasticsearch-host:9200"
ES_USERNAME = "your-username"
ES_PASSWORD = "your-password"

# Elasticsearchインデックス名
ES_INDEX_yosankessan = "index-yosankessan"
ES_INDEX_keikakuhoshin = "index-keikakuhoshin"
ES_INDEX_iinkaigijiroku = "index-iinkaigijiroku"
ES_INDEX_kouhou = "index-kouhou"

# Gemini API（AI要約用）
GEMINI_API_KEY = "your-gemini-api-key"
```

### 5. アプリケーションの起動
streamlitからgithubと連携してアプリを作成しデプロイしてください。

## 使い方

### 基本的な検索フロー

1. **サイドバーで検索条件を設定**
   - キーワード（AND/OR/NOT）を入力
   - 年度を選択
   - 自治体区分で絞り込み
   - ツリーから自治体を選択
   - カテゴリを選択

2. **タブで結果を確認**
   - **検索結果**: 詳細な一覧とPDFリンク
   - **件数**: 自治体×カテゴリのクロス集計
   - **最新収集月**: データの鮮度を確認
   - **AI要約**: Geminiによる自動要約

### 検索のコツ

- **完全一致検索**: キーワードは完全一致で検索されます（例：「環境」は「環境保全」にマッチ）
- **複数キーワード**: スペース区切りで複数指定可能
- **都道府県選択**: 都道府県を選択すると、配下の全市区町村が選択されます
- **検索フィールド**: デフォルトは「本文」のみ。「資料名」も追加可能

---

## ユーザー制限機能

特定のユーザーに対して、閲覧可能な自治体やカテゴリを制限できます。

### クエリファイルの作成

`query/` ディレクトリにユーザー別のJSONファイルを作成：

**例: `query/user_tokyo.json`（東京都のみ閲覧可能）**
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "terms": {
            "code": ["131016", "131024", "131032"]
          }
        },
        {
          "terms": {
            "category": [1, 2, 3]
          }
        }
      ]
    }
  }
}
```

### セッション状態の設定

ユーザー情報をセッション状態で管理：

```python
# app.pyまたは認証後に設定
st.session_state["user_query_file"] = "user_tokyo.json"
st.session_state["user_can_modify_query"] = False  # True=追加条件入力可, False=固定
st.session_state["user_display_name"] = "東京都ユーザー"
```

### 制限モード

| can_modify_query | 動作 |
|------------------|------|
| `True` | ベースクエリあり、追加条件の入力可能 |
| `False` | 固定クエリモード、検索条件の変更不可 |

---

## ファイル構成

```
g-finder-lite/
├── app.py                    # メインアプリケーション
├── auth.py                   # パスワード認証
├── config.py                 # 設定・定数管理
├── data_loader.py            # マスターデータ読み込み
├── data_fetcher.py           # Elasticsearchデータ取得
├── elasticsearch_client.py   # ES接続管理
├── query_builder.py          # クエリ構築ロジック
├── table_builder.py          # テーブル整形
├── ui_components.py          # UI部品
├── sidebar.py                # サイドバー構築
├── user_query.py             # ユーザー制限管理
├── gemini_helper.py          # Gemini API連携
├── prompt.py                 # AIプロンプト設定
├── tabs/                     # タブ表示モジュール
│   ├── __init__.py
│   ├── results_tab.py
│   ├── counts_tab.py
│   ├── latest_tab.py
│   └── summary_tab.py
├── query/                    # ユーザークエリファイル格納
│   └── (user_*.json)
├── .streamlit/
│   └── secrets.toml          # 機密情報（Git管理外）
├── jichitai.xlsx             # 自治体マスター（必須）
├── category.xlsx             # カテゴリマスター（必須）
├── requirements.txt          # 依存パッケージ
└── README.md                 # このファイル
```

---

## トラブルシューティング

### ❌ `jichitai.xlsx が見つかりません`

**原因**: マスターファイルが配置されていない

**解決策**:
```bash
# プロジェクトルートに jichitai.xlsx を配置
ls jichitai.xlsx  # 存在確認
```

### ❌ `ES 接続情報が不足`

**原因**: `.streamlit/secrets.toml` の設定不備

**解決策**:
```toml
# 必須項目を確認
ES_HOST = "https://..."
ES_USERNAME = "user"
ES_PASSWORD = "pass"
```

### ❌ `Gemini API エラー`

**原因**: APIキーが無効または未設定

**解決策**:
1. [Google AI Studio](https://makersuite.google.com/app/apikey)でAPIキーを取得
2. `secrets.toml` に `GEMINI_API_KEY` を設定

### ❌ 検索結果が0件

**チェックポイント**:
- Elasticsearchにデータが存在するか確認
- インデックス名が正しいか確認（`secrets.toml`）
- 自治体・カテゴリの選択範囲が狭すぎないか確認

### ❌ ツリー選択で自治体が表示されない

**原因**: 自治体区分の選択が必要

**解決策**:
1. サイドバーの「自治体区分」で市・町・村などを選択
2. ツリーが更新されて自治体が表示される

---

## ライセンス

このプロジェクトは内部利用を想定しています。

---

## サポート

問題が発生した場合は、GitHubのIssuesまたは社内チャットでお問い合わせください。