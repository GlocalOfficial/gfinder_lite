"""
サイドバーモジュール
検索条件と表示設定のUI構築
"""

import streamlit as st
import pandas as pd
from st_ant_tree import st_ant_tree
from typing import List


def build_jichitai_tree(jichitai: pd.DataFrame, sel_city_types: List[str]) -> List[dict]:
    """
    自治体データをツリー構造に変換（都道府県の下に市区町村をネスト）
    
    Args:
        jichitai: 自治体マスターデータ
        sel_city_types: 選択された自治体区分
    
    Returns:
        list: ツリー構造のデータ
    """
    # 自治体区分でフィルタリング
    filtered_jichitai = jichitai.copy()
    if sel_city_types:
        filtered_jichitai = filtered_jichitai[filtered_jichitai["city_type"].isin(sel_city_types)]
    
    # 都道府県リストを取得
    pref_list = (
        filtered_jichitai[["affiliation_code", "pref_name"]]
        .drop_duplicates()
        .assign(aff_num=lambda d: pd.to_numeric(d["affiliation_code"], errors="coerce"))
        .sort_values(["aff_num"])
    )
    
    tree_data = []
    
    for _, pref_row in pref_list.iterrows():
        aff_code = str(pref_row["affiliation_code"])
        pref_name = str(pref_row["pref_name"])
        
        # 該当都道府県の市区町村を取得
        cities = filtered_jichitai[
            filtered_jichitai["affiliation_code"] == aff_code
        ].sort_values("code")
        
        # 子ノード（市区町村）を構築
        children = []
        for _, city_row in cities.iterrows():
            children.append({
                "title": str(f"{city_row['city_name']}"),
                "value": str(city_row["code"]),
                "key": str(city_row["code"]),
            })
        
        # 親ノード（都道府県）を構築
        pref_node = {
            "title": str(f"{pref_name} ({len(children)}件)"),
            "value": str(f"pref_{aff_code}"),
            "key": str(f"pref_{aff_code}"),
        }
        
        # 子ノードがある場合のみ追加
        if children:
            pref_node["children"] = children
        
        tree_data.append(pref_node)
    
    return tree_data


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
            - search_fields: list[str]
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
    
    search_fields = st.sidebar.multiselect(
        "検索対象フィールド",
        options=["本文", "資料名"],
        default=["本文"],
        help="キーワード検索の対象とするフィールドを選択"
    )
    
    st.sidebar.markdown("---")
    
    # ========== 自治体絞り込み（ツリー形式） ==========
    st.sidebar.subheader("🔍 自治体・カテゴリ絞り込み")
    
    # 自治体区分での事前フィルタリング
    ctype_opts = sorted(jichitai["city_type"].dropna().unique().tolist())
    sel_city_types = st.sidebar.multiselect(
        "自治体区分",
        options=ctype_opts,
        help="自治体区分で絞り込み後、ツリーから選択してください"
    )
    
    # ツリーデータの構築
    tree_data = build_jichitai_tree(jichitai, sel_city_types)
    
    # ツリー選択UI（st.sidebarを使わず、直接コンポーネント内で指定）
    st.sidebar.markdown("**自治体選択（都道府県→市区町村）**")
    
    if not tree_data:
        st.sidebar.warning("⚠️ 表示する自治体がありません。")
        selected_values = None
    else:
        # サイドバー内にコンテナを作成
        with st.sidebar:
            selected_values = st_ant_tree(
                treeData=tree_data,
                treeCheckable=True,
                allowClear=True,
                showSearch=True,
                key="jichitai_tree"
            )
    # 選択された値から自治体コードを抽出
    sel_codes = []
    if selected_values and isinstance(selected_values, dict):
        checked_items = selected_values.get("checked", [])
        # "pref_" プレフィックスがないもの（市区町村）のみを抽出
        sel_codes = [code for code in checked_items if not str(code).startswith("pref_")]
    
    # カテゴリ選択
    st.sidebar.markdown("---")
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
    
    # クエリ用の自治体コードプールを構築
    code_pool = jichitai.copy()
    if sel_city_types:
        code_pool = code_pool[code_pool["city_type"].isin(sel_city_types)]
    
    # 都道府県全体が選択された場合の処理
    if selected_values and isinstance(selected_values, dict):
        checked_items = selected_values.get("checked", [])
        
        # "pref_" プレフィックス付きのもの（都道府県）を取得
        pref_keys = [key for key in checked_items if str(key).startswith("pref_")]
        if pref_keys:
            # プレフィックスを除去して都道府県コードを取得
            pref_codes = [key.replace("pref_", "") for key in pref_keys]
            # 都道府県配下の全市区町村を含める
            pref_cities = code_pool[code_pool["affiliation_code"].isin(pref_codes)]["code"].tolist()
            sel_codes.extend(pref_cities)
            # 重複を除去
            sel_codes = list(set(sel_codes))
    
    # 市区町村が選択されている場合
    if sel_codes:
        codes_for_query = sel_codes
    else:
        codes_for_query = code_pool["code"].tolist()
    
    return {
        "and_words": and_words,
        "or_words": or_words,
        "not_words": not_words,
        "selected_years": selected_years,
        "search_fields": search_fields,
        "sel_codes": sel_codes,
        "sel_categories": sel_categories,
        "codes_for_query": codes_for_query,
        "display_unit": display_unit,
        "count_mode": count_mode,
        "result_limit": result_limit,
        "short_unique": short_unique,
    }