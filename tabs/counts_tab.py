"""
件数タブの表示処理
"""

import streamlit as st
import pandas as pd
from elasticsearch import Elasticsearch
from config import FIELD_CODE, FIELD_AFFILIATION
from data_fetcher import fetch_counts, _qkey
from table_builder import build_counts_table
from ui_components import show_df


def render_counts_tab(
    es: Elasticsearch,
    query: dict,
    jichitai: pd.DataFrame,
    pref_master: pd.DataFrame,
    catmap: pd.DataFrame,
    display_unit: str,
    count_mode: str,
    short_unique: pd.DataFrame
):
    """
    件数タブの表示
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        pref_master: 都道府県マスターデータ
        catmap: カテゴリマスターデータ
        display_unit: 表示単位
        count_mode: 集計単位
        short_unique: ユニークなshort_nameリスト
    """
    group_field = FIELD_CODE if display_unit == "市区町村" else FIELD_AFFILIATION
    df_counts = fetch_counts(
        es,
        _qkey(query),
        group_field,
        include_file=("ファイル数" in count_mode)
    )
    
    if df_counts.empty:
        st.warning("該当データがありません。フィルタを見直してください。")
    else:
        table = build_counts_table(
            df_counts,
            jichitai,
            pref_master,
            catmap,
            display_unit,
            count_mode,
            short_unique
        )
        show_df(table)