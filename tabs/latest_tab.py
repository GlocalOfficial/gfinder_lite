"""
最新収集月タブの表示処理
"""

import streamlit as st
import pandas as pd
from elasticsearch import Elasticsearch
from config import FIELD_CODE, FIELD_AFFILIATION
from data_fetcher import fetch_latest_month, _qkey
from table_builder import build_latest_table
from ui_components import show_df


def render_latest_tab(
    es: Elasticsearch,
    query: dict,
    jichitai: pd.DataFrame,
    pref_master: pd.DataFrame,
    catmap: pd.DataFrame,
    display_unit: str,
    short_unique: pd.DataFrame
):
    """
    最新収集月タブの表示
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        pref_master: 都道府県マスターデータ
        catmap: カテゴリマスターデータ
        display_unit: 表示単位
        short_unique: ユニークなshort_nameリスト
    """
    group_field = FIELD_CODE if display_unit == "市区町村" else FIELD_AFFILIATION
    df_latest = fetch_latest_month(es, _qkey(query), group_field)
    
    if df_latest.empty:
        st.warning("該当データがありません。フィルタを見直してください。")
    else:
        table = build_latest_table(
            df_latest,
            jichitai,
            pref_master,
            catmap,
            display_unit,
            short_unique
        )
        show_df(table, latest=True)