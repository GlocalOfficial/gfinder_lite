"""
Elasticsearch接続モジュール
Elasticsearchクライアントの初期化と管理
"""

import streamlit as st
from elasticsearch import Elasticsearch
from config import get_secret


@st.cache_resource(show_spinner=False)
def get_es_client() -> Elasticsearch:
    """
    Elasticsearchクライアントを取得（キャッシュ付き）
    
    Returns:
        Elasticsearch: ESクライアント
    
    Raises:
        st.stop: 接続情報が不足している場合
    """
    es_host = get_secret("ES_HOST")
    es_username = get_secret("ES_USERNAME")
    es_password = get_secret("ES_PASSWORD")
    
    if not es_host or not es_username or not es_password:
        st.error("ES 接続情報が不足（ES_HOST / ES_USERNAME / ES_PASSWORD）")
        st.stop()
    
    return Elasticsearch(
        es_host,
        basic_auth=(es_username, es_password),
        verify_certs=False,
        request_timeout=90
    )