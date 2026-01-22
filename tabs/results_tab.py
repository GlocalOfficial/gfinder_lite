"""
検索結果タブの表示処理
"""

import streamlit as st
import pandas as pd
from elasticsearch import Elasticsearch
from data_fetcher import fetch_search_results


def render_results_tab(
    es: Elasticsearch,
    query: dict,
    jichitai: pd.DataFrame,
    catmap: pd.DataFrame,
    result_limit: int
):
    """
    検索結果タブの表示
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        catmap: カテゴリマスターデータ
        result_limit: 表示件数上限
    """
    if query:
        df_results = fetch_search_results(es, query, jichitai, catmap, result_limit)
        if df_results.empty:
            st.warning("該当データがありません。フィルタを見直してください。")
        else:
            st.data_editor(
                df_results,
                use_container_width=True,
                hide_index=True,
                disabled=True,
                column_config={
                    "URL(GF)": st.column_config.LinkColumn(
                        "URL(GF)",
                        display_text="📄リンク"
                    ),
                    "URL(原本)": st.column_config.LinkColumn(
                        "URL(原本)",
                        display_text="🌐リンク"
                    )
                }
            )
    else:
        st.warning("検索条件を設定してください。")