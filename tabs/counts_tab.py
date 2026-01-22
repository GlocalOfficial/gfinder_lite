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
        short_unique: ユニークなshort_nameリスト
    """
    # 表示設定（タブ内）
    st.markdown("### ⚙️ 表示設定")
    col1, col2 = st.columns(2)
    
    with col1:
        display_unit = st.radio(
            "表示単位",
            ["都道府県", "市区町村"],
            index=0,
            horizontal=True,
            key="counts_display_unit"
        )
    
    with col2:
        count_mode = st.radio(
            "集計単位",
            ["ファイル数", "ページ数"],
            index=0,
            help="ファイル数：PDFファイル単位で集計\nページ数：PDFのページ単位で集計",
            horizontal=True,
            key="counts_count_mode"
        )
    
    st.markdown("---")
    
    # データ取得と表示
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