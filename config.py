"""
設定・定数管理モジュール
Streamlit Secretsから設定を取得し、アプリケーション全体で使用する定数を定義
"""

import streamlit as st


# ====== Elasticsearch フィールド名 ======
FIELD_CODE = "code"
FIELD_AFFILIATION = "affiliation_code"
FIELD_CATEGORY = "category"
FIELD_FILE_ID = "file_id"
FIELD_COLLECTED_AT = "collected_at"


# ====== Secrets取得ヘルパー ======
def get_secret(key: str, default: str = "") -> str:
    """
    Streamlit Secretsから値を取得。存在しない場合はデフォルト値を返す
    
    Args:
        key: Secretsのキー名
        default: キーが存在しない場合のデフォルト値
    
    Returns:
        str: 取得した値またはデフォルト値
    """
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


# ====== Elasticsearch接続情報 ======
ES_HOST = get_secret("ES_HOST")
ES_USERNAME = get_secret("ES_USERNAME")
ES_PASSWORD = get_secret("ES_PASSWORD")
ES_INDEX_yosankessan = get_secret("ES_INDEX_yosankessan")
ES_INDEX_keikakuhoshin = get_secret("ES_INDEX_keikakuhoshin")
ES_INDEX_iinkaigijiroku = get_secret("ES_INDEX_iinkaigijiroku")
ES_INDEX_kouhou = get_secret("ES_INDEX_kouhou")

# インデックスリスト（空でないものだけ）
INDEXES = [
    i for i in [
        ES_INDEX_yosankessan,
        ES_INDEX_keikakuhoshin,
        ES_INDEX_iinkaigijiroku,
        ES_INDEX_kouhou
    ] if i
]


# ====== Gemini API設定 ======
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")


# ====== アプリケーション設定 ======
APP_PASSWORD = get_secret("APP_PASSWORD")