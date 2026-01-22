"""
UI部品モジュール
再利用可能なUI要素とデータ表示機能
"""

import pandas as pd
import streamlit as st
from table_builder import fmt_month_from_epoch


def show_df(df: pd.DataFrame, latest: bool = False):
    """
    DataFrameを整形して表示
    
    Args:
        df: 表示するDataFrame
        latest: 最新収集月テーブルかどうか
    """
    disp = df.copy()
    # 数値列は文字列化してカンマ区切り
    for c in disp.columns:
        if not latest and pd.api.types.is_numeric_dtype(disp[c]):
            disp[c] = disp[c].apply(lambda v: f"{v:,}" if pd.notnull(v) else "")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def show_kpi_metrics(kpi_data: dict):
    """
    KPI指標を表示
    
    Args:
        kpi_data: KPIデータ（total_files, total_pages, max_collected_value）
    """
    k1, k2, _sp = st.columns([2, 2, 6])
    with k1:
        st.metric("総ファイル数", f"{kpi_data['total_files']:,}")
    with k2:
        st.metric("総データ（ページ）数", f"{kpi_data['total_pages']:,}")


def show_search_info(
    and_words: list,
    or_words: list,
    not_words: list,
    selected_years: list,
    search_fields: list
):
    """
    検索条件を表示
    
    Args:
        and_words: AND検索キーワード
        or_words: OR検索キーワード
        not_words: NOT検索キーワード
        selected_years: 選択年度
        search_fields: 検索対象フィールド
    """
    search_info_parts = []
    if and_words:
        search_info_parts.append(f"**AND**: {', '.join(and_words)}")
    if or_words:
        search_info_parts.append(f"**OR**: {', '.join(or_words)}")
    if not_words:
        search_info_parts.append(f"**NOT**: {', '.join(not_words)}")
    if selected_years:
        search_info_parts.append(f"**年度**: {', '.join(map(str, sorted(selected_years)))}")
    if search_fields:
        search_info_parts.append(f"**検索対象**: {', '.join(search_fields)}")
    
    if search_info_parts:
        st.info("🔍 **検索条件**: " + " | ".join(search_info_parts))


def show_page_header():
    """
    ページヘッダーを表示
    """
    st.markdown("""
# G-Finder Lite⚡ 
・各列のヘッダをクリックすると並び替えできます。  
・最新収集月は収集者が最後に収集した日付から算出しているため、必ずしも当月の資料が収録されているということではありません。  
・キーワードは完全一致検索です（""は不要です）
""", unsafe_allow_html=True)