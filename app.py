"""
G-Finder Lite⚡ - メインアプリケーション
自治体データの検索・集計・AI要約を提供するStreamlitアプリケーション
"""

import streamlit as st

# 認証
from auth import check_password

# ページ設定(認証前に実行)
st.set_page_config(page_title="G-Finder Lite⚡", layout="wide")
st.markdown("""
<style>
  [data-testid="stSidebar"] {width: 360px;}
  [data-testid="stSidebar"] section {width: 360px;}
</style>
""", unsafe_allow_html=True)

# 認証ゲート
if not check_password():
    st.stop()

# 認証後のインポート
from data_loader import load_jichitai, load_category, get_pref_master
from elasticsearch_client import get_es_client
from query_builder import build_search_query
from data_fetcher import fetch_kpi
from ui_components import show_page_header, show_search_info, show_kpi_metrics
from sidebar import build_sidebar
from tabs import (
    render_counts_tab,
    render_results_tab,
    render_latest_tab,
    render_summary_tab
)


# ====== データ読み込み ======
jichitai = load_jichitai()
catmap = load_category()
pref_master = get_pref_master(jichitai)

# ====== Elasticsearch接続 ======
es = get_es_client()

# ====== サイドバー構築 ======
sidebar_config = build_sidebar(jichitai, catmap)

# ====== クエリ構築 ======
query = build_search_query(
    and_words=sidebar_config["and_words"],
    or_words=sidebar_config["or_words"],
    not_words=sidebar_config["not_words"],
    years=sidebar_config["selected_years"],
    codes=sidebar_config["codes_for_query"],
    categories=sidebar_config["sel_categories"],
    search_fields=sidebar_config["search_fields"],
    base_query=sidebar_config["restrictions"]["base_query"],
    can_modify_query=sidebar_config["restrictions"]["can_modify_query"]  # 追加
)

# ====== KPI取得 ======
kpi_data = fetch_kpi(es, query)

# ====== ページヘッダー ======
show_page_header()

# ====== 検索条件表示 ======
show_search_info(
    and_words=sidebar_config["and_words"],
    or_words=sidebar_config["or_words"],
    not_words=sidebar_config["not_words"],
    selected_years=sidebar_config["selected_years"],
    search_fields=sidebar_config["search_fields"]
)

# ====== KPI表示 ======
show_kpi_metrics(kpi_data)

# ====== タブ表示 ======
tab_results, tab_counts, tab_latest, tab_summary = st.tabs([
    "検索結果", "件数", "最新収集月", "🤖 AI要約(準備中)"
])

with tab_results:
    render_results_tab(
        es=es,
        query=query,
        jichitai=jichitai,
        catmap=catmap,
        result_limit=sidebar_config["result_limit"]
    )

with tab_counts:
    render_counts_tab(
        es=es,
        query=query,
        jichitai=jichitai,
        pref_master=pref_master,
        catmap=catmap,
        short_unique=sidebar_config["short_unique"]
    )

with tab_latest:
    render_latest_tab(
        es=es,
        query=query,
        jichitai=jichitai,
        pref_master=pref_master,
        catmap=catmap,
        short_unique=sidebar_config["short_unique"]
    )

with tab_summary:
    render_summary_tab(
        es=es,
        query=query,
        jichitai=jichitai,
        catmap=catmap,
        result_limit=sidebar_config["result_limit"]
    )