"""
最新収集月タブの表示処理（自治体表示の優先順位対応）
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
    short_unique: pd.DataFrame,
    filtered_codes: list = None,
    restricted_codes: list = None,
    selected_city_types: list = None
):
    """
    最新収集月タブの表示（自治体表示の優先順位対応）
    
    優先順位:
    1. filtered_codes（UIで選択）が指定された場合、その自治体のみ表示
    2. filtered_codesが空でも、restricted_codes（ベースクエリ）がある場合、その自治体のみ表示
    3. どちらも該当しない場合は全自治体を表示
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        pref_master: 都道府県マスターデータ
        catmap: カテゴリマスターデータ
        short_unique: ユニークなshort_nameリスト
        filtered_codes: UIで選択された自治体コード（サイドバーから渡される）
        restricted_codes: ベースクエリで制限された自治体コード（ユーザー制限）
        selected_city_types: 選択された自治体区分（サイドバーから渡される）
    """
    # 表示設定（タブ内）
    st.markdown("### ⚙️ 表示設定")
    display_unit = st.radio(
        "表示単位",
        ["都道府県", "市区町村"],
        index=0,
        horizontal=True,
        key="latest_display_unit"
    )
    
    st.markdown("---")
    
    # 表示する自治体の決定（優先順位適用）
    display_codes = None  # None = 全自治体表示
    
    if filtered_codes:
        # 優先順位1: UIで自治体が選択されている場合
        display_codes = filtered_codes
    elif restricted_codes:
        # 優先順位2: ベースクエリで制限がある場合
        display_codes = restricted_codes
    
    # データ取得
    group_field = FIELD_CODE if display_unit == "市区町村" else FIELD_AFFILIATION
    df_latest = fetch_latest_month(es, _qkey(query), group_field)
    
    if df_latest.empty:
        st.warning("該当データがありません。フィルタを見直してください。")
    else:
        # 表示する自治体でjichitaiをフィルタリング
        if display_codes:
            jichitai_filtered = jichitai[jichitai["code"].isin(display_codes)].copy()
        else:
            jichitai_filtered = jichitai.copy()
        
        # 自治体区分でさらにフィルタリング
        if selected_city_types:
            jichitai_filtered = jichitai_filtered[jichitai_filtered["city_type"].isin(selected_city_types)].copy()
        
        table = build_latest_table(
            df_latest,
            jichitai_filtered,  # フィルタ済みのjichitaiを渡す
            pref_master,
            catmap,
            display_unit,
            short_unique
        )
        show_df(table, latest=True)