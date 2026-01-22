"""
サイドバーモジュール
検索条件と表示設定のUI構築
"""

import streamlit as st
import pandas as pd


def build_sidebar(jichitai: pd.DataFrame, catmap: pd.DataFrame) -> dict:
    """
    サイドバーUIを構築し、選択された条件を返す
    
    Args:
        jichitai: 自治体マスターデータ
        catmap: カテゴリマスターデータ
    
    Returns:
        dict: 選択された条件
            - and_words: list[str]
            - or_words: list[str]
            - not_words: list[str]
            - selected_years: list[int]
            - search_title: bool
            - sel_codes: list[str]
            - sel_categories: list[int]
            - display_unit: str
            - count_mode: str
            - result_limit: int
    """
    # ========== キーワード・年度検索 ===========
    st.sidebar.subheader("🔍 キーワード・年度絞り込み")
    
    year_options = list(range(2010, 2031))
    selected_years = st.sidebar.multiselect(
        "年度（複数選択可）",
        options=year_options,
        default=[],
        help="fiscal_year_start/fiscal_year_endで絞り込み"
    )
    
    and_input = st.sidebar.text_input(
        "AND条件（スペース区切り）",
        placeholder="例: 環境 計画",
        help="全てのキーワードを含む文書を検索"
    )
    or_input = st.sidebar.text_input(
        "OR条件（スペース区切り）",
        placeholder="例: 温暖化 気候変動",
        help="いずれかのキーワードを含む文書を検索"
    )
    not_input = st.sidebar.text_input(
        "NOT条件（スペース区切り）",
        placeholder="例: 廃止 中止",
        help="これらのキーワードを含まない文書を検索"
    )
    
    search_title = st.sidebar.checkbox(
        "資料名も検索対象に含める",
        value=False,
        help="チェックを入れるとtitleフィールドも検索対象になります"
    )
    
    st.sidebar.markdown("---")
    
    # ========== 自治体絞り込み ==========
    st.sidebar.subheader("🔍 自治体・カテゴリ絞り込み")
    pref_opts = (
        jichitai[["affiliation_code", "pref_name"]]
        .drop_duplicates()
        .assign(aff_num=lambda d: pd.to_numeric(d["affiliation_code"], errors="coerce"))
        .sort_values(["aff_num"])
    )
    sel_pref_names = st.sidebar.multiselect("都道府県", options=pref_opts["pref_name"].tolist())
    sel_aff_codes = pref_opts[pref_opts["pref_name"].isin(sel_pref_names)]["affiliation_code"].tolist()
    
    ctype_opts = sorted(jichitai["city_type"].dropna().unique().tolist())
    sel_city_types = st.sidebar.multiselect("自治体区分", options=ctype_opts)
    
    if sel_aff_codes:
        city_pool = jichitai[jichitai["affiliation_code"].isin(sel_aff_codes)]
    else:
        city_pool = jichitai.copy()
    if sel_city_types:
        city_pool = city_pool[city_pool["city_type"].isin(sel_city_types)]
    city_pool = city_pool.sort_values(["affiliation_code", "code"])
    sel_city_names = st.sidebar.multiselect("市区町村", options=city_pool["city_name"].tolist())
    sel_codes = city_pool[city_pool["city_name"].isin(sel_city_names)]["code"].tolist()
    
    cat_opts = catmap.sort_values("order")
    short_unique = cat_opts.drop_duplicates(subset=["short_name"], keep="first")
    sel_cat_short = st.sidebar.multiselect(
        "資料カテゴリ",
        options=short_unique["short_name"].tolist(),
        default=short_unique["short_name"].tolist()
    )
    sel_categories = cat_opts[cat_opts["short_name"].isin(sel_cat_short)]["category"].astype(int).tolist()
    
    # ========== 表示設定 ==========
    st.sidebar.markdown("---")
    st.sidebar.header("表示設定")
    display_unit = st.sidebar.radio(
        "表示単位",
        ["都道府県", "市区町村"],
        index=0
    )
    count_mode = st.sidebar.radio(
        "集計単位",
        ["ファイル数", "ページ数"],
        index=0,
        help="ファイル数：PDFファイル単位で集計\nページ数：PDFのページ単位で集計"
    )
    result_limit = st.sidebar.radio(
        "検索結果の表示件数",
        options=[100, 1000, 10000],
        index=0,
        help="検索結果タブでの表示件数を変更できます\n（デフォルト100件 多くなると挙動が重くなる可能性があります）"
    )
    
    # キーワード処理
    and_words = [w.strip() for w in and_input.replace("　", " ").split() if w.strip()]
    or_words = [w.strip() for w in or_input.replace("　", " ").split() if w.strip()]
    not_words = [w.strip() for w in not_input.replace("　", " ").split() if w.strip()]
    
    # 自治体コードプールを構築
    code_pool = jichitai.copy()
    if sel_aff_codes:
        code_pool = code_pool[code_pool["affiliation_code"].isin(sel_aff_codes)]
    if sel_city_types:
        code_pool = code_pool[code_pool["city_type"].isin(sel_city_types)]
    if sel_city_names:
        code_pool = code_pool[code_pool["city_name"].isin(sel_city_names)]
    codes_for_query = code_pool["code"].tolist()
    
    return {
        "and_words": and_words,
        "or_words": or_words,
        "not_words": not_words,
        "selected_years": selected_years,
        "search_title": search_title,
        "sel_codes": sel_codes,
        "sel_categories": sel_categories,
        "codes_for_query": codes_for_query,
        "display_unit": display_unit,
        "count_mode": count_mode,
        "result_limit": result_limit,
        "short_unique": short_unique,
    }