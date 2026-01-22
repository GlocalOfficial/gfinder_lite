"""
Elasticsearch接続モジュール
Elasticsearchクライアントの初期化と管理
"""

import streamlit as st
from elasticsearch import Elasticsearch
from config import ES_HOST, ES_USERNAME, ES_PASSWORD


@st.cache_resource(show_spinner=False)
def get_es_client() -> Elasticsearch:
    """
    Elasticsearchクライアントを取得（キャッシュ付き）
    
    Returns:
        Elasticsearch: ESクライアント
    
    Raises:
        st.stop: 接続情報が不足している場合
    """
    if not ES_HOST or not ES_USERNAME or not ES_PASSWORD:
        st.error("ES 接続情報が不足（ES_HOST / ES_USERNAME / ES_PASSWORD）")
        st.stop()
    
    return Elasticsearch(
        ES_HOST,
        basic_auth=(ES_USERNAME, ES_PASSWORD),
        verify_certs=False,
        request_timeout=90
    )