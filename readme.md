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

G-Finder Liteは、Elasticsearchに格納された自治体の公開文書データを検索・分析するためのWebアプリケーションです。キーワード検索、年度絞り込み、自治体・カテゴリ別の集計、そしてOpenAI APIによる要約機能を提供します。

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
- OpenAI APIを使った検索結果の自動要約
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
- OpenAI API（AI要約用）
- Google Cloud Storage（ユーザー管理機能用、オプション）

### Pythonパッケージ
```
streamlit
st-ant-tree
elasticsearch==8.13.0
pandas
openpyxl
openai
google-cloud-storage
google-auth
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

以下のファイルを準備してください：

#### ローカルファイル（プロジェクトルートに配置）

##### `jichitai.xlsx`（自治体マスターデータ）
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

##### `category.xlsx`（カテゴリマスターデータ）
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

#### GCSファイル（Google Cloud Storageに配置）**[オプション]**

以下のファイルはGCS（Google Cloud Storage）のバケットに配置します。

##### `auth.xlsx`（ユーザー認証・権限管理）

ユーザーごとのログイン情報と権限を管理するExcelファイル。GCS上の**バケットルート**に保存してください。以下の列が必須です：

| 列名 | 型 | 説明 | 例 |
|------|-----|------|-----|
| `username` | 文字列 | ログインID | `user_tokyo` |
| `password` | 文字列 | パスワード | `pass123` |
| `display_name` | 文字列 | 表示名 | `東京都ユーザー` |
| `query_file` | 文字列 | クエリファイル名（`query/`ディレクトリ内） | `user_tokyo.json` |
| `can_modify_query` | 文字列 | クエリ修正可否（`TRUE`/`FALSE`） | `FALSE` |
| `can_show_count` | 文字列 | 「件数」タブ表示可否（`TRUE`/`FALSE`） | `TRUE` |
| `can_show_latest` | 文字列 | 「最新収集月」タブ表示可否（`TRUE`/`FALSE`） | `TRUE` |
| `can_show_summary` | 文字列 | 「AI要約」タブ表示可否（`TRUE`/`FALSE`） | `FALSE` |
| `enabled` | 文字列 | アカウント有効/無効（`TRUE`/`FALSE`） | `TRUE` |

**サンプル（auth.xlsx）:**
```
username    | password | display_name      | query_file        | can_modify_query | can_show_count | can_show_latest | can_show_summary | enabled
------------|----------|-------------------|-------------------|------------------|----------------|-----------------|------------------|--------
admin       | admin123 | 管理者            |                   | TRUE             | TRUE           | TRUE            | TRUE             | TRUE
user_tokyo  | tokyo456 | 東京都ユーザー    | user_tokyo.json   | FALSE            | TRUE           | TRUE            | FALSE            | TRUE
user_osaka  | osaka789 | 大阪府ユーザー    | user_osaka.json   | TRUE             | TRUE           | FALSE           | TRUE             | TRUE
guest       | guest000 | ゲストユーザー    | guest.json        | FALSE            | FALSE          | FALSE           | FALSE            | FALSE
```

**GCS保存場所:**
```
gs://{your-bucket-name}/auth.xlsx
```

**列の詳細説明:**

- **username**: ログイン時に使用するユーザーID（一意である必要があります）
- **password**: 平文パスワード（⚠️ 本番環境ではハッシュ化を推奨）
- **display_name**: アプリ内で表示されるユーザー名
- **query_file**: 
  - 空欄: 制限なし（全データアクセス可能）
  - ファイル名指定: GCS上の`query/`ディレクトリ内のJSONファイルを参照（例: `user_tokyo.json`）
- **can_modify_query**:
  - `TRUE`: ベースクエリに追加してキーワード検索等が可能
  - `FALSE`: クエリ固定モード（検索条件変更不可）
- **can_show_count**:
  - `TRUE`: 「件数」タブ（自治体×カテゴリのクロス集計）を表示
  - `FALSE`: 「件数」タブを非表示
  - デフォルト値: `TRUE`
- **can_show_latest**:
  - `TRUE`: 「最新収集月」タブ（各自治体の最新データ収集時期）を表示
  - `FALSE`: 「最新収集月」タブを非表示
  - デフォルト値: `TRUE`
- **can_show_summary**:
  - `TRUE`: 「AI要約」タブ（OpenAI による自動要約）を表示
  - `FALSE`: 「AI要約」タブを非表示
  - デフォルト値: `FALSE`（API費用削減のため初期値は OFF）
- **enabled**:
  - `TRUE`: ログイン可能
  - `FALSE`: アカウント無効（ログイン不可）

#### auth.xlsx による制御フロー

ユーザーがログインすると、以下の制御が自動的に適用されます：

```
ユーザーがログイン
    ↓
auth.py が auth.xlsx を読み込み
    ↓
1️⃣ enabled = FALSE の場合
    → ログイン拒否、エラーメッセージ表示
    ↓
2️⃣ query_file が空の場合
    → セッション状態に「全データアクセス可能」を設定
    → サイドバーで全自治体・全カテゴリ選択可能
    ↓
3️⃣ query_file にファイル名が指定されている場合
    → GCS から該当JSONファイルを取得
    → セッション状態に制限クエリを設定
    ↓
4️⃣ can_modify_query = FALSE の場合
    → UI上で検索条件の入力欄を非表示/無効化
    → 固定クエリのみで検索実行
    ↓
5️⃣ can_modify_query = TRUE の場合
    → UI上で検索条件の入力が可能
    → ベースクエリ ＋ ユーザー入力で複合検索
    ↓
検索実行時にベースクエリをElasticsearchに送信
    ↓
ユーザーの権限内のみデータが返却される
```

#### auth.xlsx 設定パターン例

**パターン1: 管理者（全アクセス・全機能可能）**
```
username         | password   | display_name | query_file | can_modify_query | can_show_count | can_show_latest | can_show_summary | enabled
-----------------|-----------|--------------|------------|------------------|----------------|-----------------|------------------|--------
admin            | admin_pw   | 管理者       | (空)       | TRUE             | TRUE           | TRUE            | TRUE             | TRUE
```
→ 全自治体・全カテゴリにアクセス可能。検索条件の自由な変更も可能。全タブが表示される。

**パターン2: 東京都専用ユーザー（固定クエリ・限定タブ）**
```
username         | password   | display_name | query_file          | can_modify_query | can_show_count | can_show_latest | can_show_summary | enabled
-----------------|-----------|--------------|---------------------|------------------|----------------|-----------------|------------------|--------
user_tokyo       | tokyo_pw   | 東京都職員   | user_tokyo.json     | FALSE            | TRUE           | TRUE            | FALSE            | TRUE
```
→ 東京都のみ表示。キーワード検索などの条件変更は不可。「件数」「最新収集月」タブは表示。「AI要約」タブは非表示（API費用削減）。

**パターン3: 大阪府専用ユーザー（カスタマイズ可能）**
```
username         | password   | display_name | query_file          | can_modify_query | can_show_count | can_show_latest | can_show_summary | enabled
-----------------|-----------|--------------|---------------------|------------------|----------------|-----------------|------------------|--------
user_osaka       | osaka_pw   | 大阪府職員   | user_osaka.json     | TRUE             | TRUE           | FALSE           | TRUE             | TRUE
```
→ 大阪府がベース。キーワード検索での絞り込みは可能。「最新収集月」は非表示。「AI要約」は表示。

**パターン4: ゲストユーザー（期間限定・最小限の機能）**
```
username         | password   | display_name | query_file          | can_modify_query | can_show_count | can_show_latest | can_show_summary | enabled
-----------------|-----------|--------------|---------------------|------------------|----------------|-----------------|------------------|--------
guest_user       | guest_pw   | 外部コンサル | guest.json          | FALSE            | FALSE          | FALSE           | FALSE            | TRUE
```
→ 限定的なデータのみアクセス可能。検索条件は固定。タブは「検索結果」のみ表示。

**パターン5: 無効ユーザー（ログイン不可）**
```
username         | password   | display_name | query_file          | can_modify_query | can_show_count | can_show_latest | can_show_summary | enabled
-----------------|-----------|--------------|---------------------|------------------|----------------|-----------------|------------------|--------
former_user      | (任意)     | 前任者       | (任意)               | (任意)           | (任意)         | (任意)          | (任意)           | FALSE
```
→ ログイン試行時に「アカウントが無効です」エラーが表示される。その他の設定値は参照されない。
user_osaka       | osaka_pw   | 大阪府職員   | user_osaka.json     | TRUE             | TRUE
```
→ `user_osaka.json` で定義された大阪府がベース。キーワード検索での絞り込みは可能。

**パターン4: ゲストユーザー（期間限定）**
```
username         | password   | display_name | query_file          | can_modify_query | enabled
-----------------|-----------|--------------|---------------------|------------------|--------
guest_user       | guest_pw   | 外部コンサル | guest.json          | FALSE            | TRUE
```
→ 限定的なデータのみアクセス可能。検索条件は固定。

**パターン5: 無効ユーザー（ログイン不可）**
```
username         | password   | display_name | query_file          | can_modify_query | enabled
-----------------|-----------|--------------|---------------------|------------------|--------
former_user      | (任意)     | 前任者       | (任意)               | (任意)           | FALSE
```
→ ログイン試行時に「アカウントが無効です」エラーが表示される。

#### セッション状態への反映

ユーザーログイン時、以下の値が自動的に `st.session_state` に設定されます：

```python
# auth.py により自動設定（コード記述不要）
st.session_state["authenticated"] = True
st.session_state["username"] = "user_tokyo"              # auth.xlsx の username
st.session_state["user_display_name"] = "東京都ユーザー"  # auth.xlsx の display_name
st.session_state["user_query_file"] = "user_tokyo.json"  # auth.xlsx の query_file
st.session_state["user_can_modify_query"] = False        # auth.xlsx の can_modify_query
st.session_state["user_base_query"] = {...}              # GCS から取得したJSON
```

#### user_query.py での利用

ユーザー制限機能は `user_query.py` で以下のように実装されます：

```python
# ユーザー権限に基づくクエリの動的構築
def build_user_constrained_query(user_base_query, user_input_query):
    if not user_can_modify_query:
        # 固定クエリモード: ユーザー入力は無視し、ベースクエリのみ使用
        return user_base_query
    else:
        # カスタマイズ可能モード: ベースクエリとユーザー入力を結合
        return combine_queries(user_base_query, user_input_query)
```

このように、`auth.xlsx` の設定により、各ユーザーのアクセス権と操作範囲が動的に制御されます。

##### クエリファイル（`query/*.json`）

ユーザーごとのアクセス制限を定義するJSONファイル。GCS上の**`query/`ディレクトリ**に保存してください。

**GCS保存場所:**
```
gs://{your-bucket-name}/query/user_tokyo.json
gs://{your-bucket-name}/query/user_osaka.json
gs://{your-bucket-name}/query/guest.json
```

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

**注意:**
- `auth.xlsx`で指定した`query_file`のファイル名と一致させてください
- JSONファイルはElasticsearchのクエリ形式で記述します


### 4. GCS（Google Cloud Storage）の設定

ユーザー認証機能を使用する場合は、GCSの設定が必要です。

#### 4-1. GCSバケットの準備

1. Google Cloud Consoleでバケットを作成
2. 以下のファイル構造でアップロード：
   ```
   {your-bucket-name}/
   ├── auth.xlsx          # ユーザー認証ファイル
   └── query/             # クエリディレクトリ
       ├── user_tokyo.json
       ├── user_osaka.json
       └── guest.json
   ```

#### 4-2. サービスアカウントの作成

1. Google Cloud Consoleで「IAM と管理」→「サービスアカウント」
2. 新しいサービスアカウントを作成
3. 権限：「Storage オブジェクト閲覧者」を付与
4. JSONキーを作成してダウンロード

#### 4-3. Streamlit Secretsへの設定

`.streamlit/secrets.toml`に以下を追加：

```toml
# GCS認証情報（方法1: JSON全体を設定）
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/..."

# または方法2: 個別の値として設定
# GCS_PROJECT_ID = "your-project-id"
# GCS_PRIVATE_KEY_ID = "your-private-key-id"
# GCS_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
# GCS_CLIENT_EMAIL = "your-service-account@your-project.iam.gserviceaccount.com"
# GCS_CLIENT_ID = "123456789"

# GCSバケット名
GCS_BUCKET_NAME = "your-bucket-name"
```

**注意:**
- `private_key`の改行は`\n`で表現してください
- Streamlit Cloudにデプロイする場合は、Webコンソールから同じ内容を設定してください


### 5. Streamlit Secretsの設定（全体）

`.streamlit/secrets.toml` ファイルを作成し、以下の情報を設定：

```toml
# パスワード認証（オプション: auth.xlsxが無い場合の簡易認証）
APP_PASSWORD = "your-password"

# GCS認証情報（方法1推奨: JSON全体）
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/..."

# GCSバケット名
GCS_BUCKET_NAME = "your-bucket-name"

# Elasticsearch接続情報
ES_HOST = "https://your-elasticsearch-host:9200"
ES_USERNAME = "your-username"
ES_PASSWORD = "your-password"

# Elasticsearchインデックス名
ES_INDEX_yosankessan = "index-yosankessan"
ES_INDEX_keikakuhoshin = "index-keikakuhoshin"
ES_INDEX_iinkaigijiroku = "index-iinkaigijiroku"
ES_INDEX_kouhou = "index-kouhou"

# OpenAI API（AI要約用）
OPENAI_API_KEY = "your-openai-api-key"
```

**認証モードについて:**
- **GCS + auth.xlsx**: GCS上に`auth.xlsx`がある場合、ユーザー管理モードで起動
- **APP_PASSWORD**: `auth.xlsx`が無い場合、簡易パスワード認証で起動
- **認証なし**: `APP_PASSWORD`も未設定の場合、認証なしで起動（開発用）


### 6. アプリケーションの起動
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
   - **AI要約**: OpenAI APIによる自動要約

### 検索のコツ

- **完全一致検索**: キーワードは完全一致で検索されます（例：「環境」は「環境保全」にマッチ）
- **複数キーワード**: スペース区切りで複数指定可能
- **都道府県選択**: 都道府県を選択すると、配下の全市区町村が選択されます
- **検索フィールド**: デフォルトは「本文」のみ。「資料名」も追加可能

---

## ユーザー制限機能（GCS版）

特定のユーザーに対して、閲覧可能な自治体やカテゴリを制限できます。

### クエリファイルの管理

#### GCS上での配置
```
gs://{your-bucket-name}/
├── auth.xlsx                 # ユーザー認証ファイル
└── query/                    # クエリディレクトリ
    ├── user_tokyo.json       # 東京都専用クエリ
    ├── user_osaka.json       # 大阪府専用クエリ
    └── guest.json            # ゲスト用クエリ
```

#### クエリファイルの作成

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

#### ファイルのアップロード方法

**方法1: Google Cloud Consoleから**
1. Google Cloud Console → Storage → バケットを選択
2. `query/`フォルダを作成（なければ）
3. JSONファイルをアップロード

**方法2: gsutilコマンド**
```bash
# ローカルで作成したファイルをアップロード
gsutil cp user_tokyo.json gs://{your-bucket-name}/query/

# 複数ファイルを一括アップロード
gsutil cp query/*.json gs://{your-bucket-name}/query/
```

**方法3: Pythonスクリプト（gcs_loader.pyの関数を利用）**
```python
from gcs_loader import upload_query_to_gcs

query_data = {
    "query": {
        "bool": {
            "must": [{"terms": {"code": ["131016"]}}]
        }
    }
}

upload_query_to_gcs("user_tokyo.json", query_data)
```

### auth.xlsxでの設定

`auth.xlsx`の`query_file`列に、GCS上のファイル名を指定：

```
username    | query_file
------------|-------------------
user_tokyo  | user_tokyo.json
user_osaka  | user_osaka.json
guest       | guest.json
```

### セッション状態の動作

ログイン後、以下の情報が自動的にセッション状態に設定されます：

```python
# 自動設定される（コード記述不要）
st.session_state["user_query_file"] = "user_tokyo.json"  # auth.xlsxから
st.session_state["user_can_modify_query"] = False        # auth.xlsxから
st.session_state["user_display_name"] = "東京都ユーザー"  # auth.xlsxから
```

これらの値は`auth.py`により自動的に設定されるため、手動での設定は不要です。

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
├── auth.py                   # パスワード認証（GCS対応）
├── config.py                 # 設定・定数管理
├── data_loader.py            # マスターデータ読み込み
├── data_fetcher.py           # Elasticsearchデータ取得
├── elasticsearch_client.py   # ES接続管理
├── gcs_loader.py             # GCSファイル読み込み
├── openai_helper.py          # OpenAI/AIプロンプト連携
├── prompt.py                 # AIプロンプト設定
├── query_builder.py          # クエリ構築ロジック
├── sidebar.py                # サイドバー構築
├── table_builder.py          # テーブル整形
├── ui_components.py          # UI部品
├── user_query.py             # ユーザー制限管理（GCS対応）
├── tabs/                     # タブ表示モジュール
│   ├── __init__.py
│   ├── counts_tab.py
│   ├── latest_tab.py
│   ├── results_tab.py
│   └── summary_tab.py
├── query/                    # ※ローカル開発用（本番はGCS）
│   └── (user_*.json)
├── .streamlit/
│   └── secrets.toml          # 機密情報（Git管理外）
├── jichitai.xlsx             # 自治体マスター（必須）
├── category.xlsx             # カテゴリマスター（必須）
├── requirements.txt          # 依存パッケージ
└── README.md                 # このファイル
```

**GCS上のファイル構造:**
```
gs://{your-bucket-name}/
├── auth.xlsx                 # ユーザー認証ファイル
└── query/                    # クエリディレクトリ
    ├── user_tokyo.json
    ├── user_osaka.json
    └── guest.json
```

---

## トラブルシューティング

### ❌ `auth.xlsx がGCSに存在しません`

**原因**: GCSバケットに`auth.xlsx`が配置されていない、またはGCS認証情報が不正

**解決策**:
```bash
# ファイルの存在確認
gsutil ls gs://{your-bucket-name}/auth.xlsx

# ファイルをアップロード
gsutil cp auth.xlsx gs://{your-bucket-name}/

# 認証情報を確認
# .streamlit/secrets.toml のGCS設定を確認
```

### ❌ `クエリファイルがGCSに存在しません`

**原因**: 指定されたクエリファイルがGCS上に存在しない

**解決策**:
```bash
# queryディレクトリの確認
gsutil ls gs://{your-bucket-name}/query/

# クエリファイルをアップロード
gsutil cp user_tokyo.json gs://{your-bucket-name}/query/

# auth.xlsxのquery_file列の値を確認
```

### ❌ `GCSクライアント初期化エラー`

**原因**: GCS認証情報が不正または不足

**解決策**:
1. `.streamlit/secrets.toml`のGCS設定を確認
2. サービスアカウントのJSONキーが正しいか確認
3. `GCS_BUCKET_NAME`が設定されているか確認
4. サービスアカウントに適切な権限があるか確認（Storage オブジェクト閲覧者）

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

### ❌ `OpenAI API エラー`

**原因**: APIキーが無効または未設定

**解決策**:
1. [OpenAI API](https://platform.openai.com/api-keys)でAPIキーを取得
2. `secrets.toml` に `OPENAI_API_KEY` を設定

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