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


def get_indexes() -> list:
    """
    Elasticsearchインデックスのリストを取得
    
    Returns:
        list: インデックス名のリスト（空でないものだけ）
    """
    indexes = [
        get_secret("ES_INDEX_yosankessan"),
        get_secret("ES_INDEX_keikakuhoshin"),
        get_secret("ES_INDEX_iinkaigijiroku"),
        get_secret("ES_INDEX_kouhou")
    ]
    return [i for i in indexes if i]