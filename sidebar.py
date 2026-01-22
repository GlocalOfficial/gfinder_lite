"""
サイドバーモジュール
検索条件と表示設定のUI構築（ユーザー制限対応）
"""

import streamlit as st
import pandas as pd
from st_ant_tree import st_ant_tree
from typing import List
from user_query import get_user_restrictions


def build_jichitai_tree(jichitai: pd.DataFrame, sel_city_types: List[str]) -> tuple[List[dict], dict]:
    """
    自治体データをツリー構造に変換(都道府県の下に市区町村をネスト)
    
    Args:
        jichitai: 自治体マスターデータ
        sel_city_types: 選択された自治体区分
    
    Returns:
        tuple: (ツリー構造のデータ, value→codeのマッピング辞書)
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
    value_to_code = {}  # value → code のマッピング
    
    for _, pref_row in pref_list.iterrows():
        aff_code = str(pref_row["affiliation_code"])
        pref_name = str(pref_row["pref_name"])
        
        # 該当都道府県の市区町村を取得
        cities = filtered_jichitai[
            filtered_jichitai["affiliation_code"] == aff_code
        ].sort_values("code")
        
        # 子ノード(市区町村)を構築
        children = []
        for _, city_row in cities.iterrows():
            city_name = str(city_row["city_name"])
            city_code = str(city_row["code"])
            
            # valueを自治体名にし、マッピングを保存
            value_to_code[city_name] = city_code
            
            children.append({
                "title": city_name,
                "value": city_name,  # 検索用に自治体名を使用
                "key": city_code,     # 内部的なキーはコードのまま
            })
        
        # 親ノード(都道府県)を構築
        pref_value = f"{pref_name}"
        pref_key = f"pref_{aff_code}"
        value_to_code[pref_value] = pref_key
        
        pref_node = {
            "title": f"{pref_name} ({len(children)}件)",
            "value": pref_value,
            "key": pref_key,
        }
        
        # 子ノードがある場合のみ追加
        if children:
            pref_node["children"] = children
        
        tree_data.append(pref_node)
    
    return tree_data, value_to_code


def build_sidebar(jichitai: pd.DataFrame, catmap: pd.DataFrame) -> dict:
    """
    サイドバーUIを構築し、選択された条件を返す（ユーザー制限対応）
    
    Args:
        jichitai: 自治体マスターデータ
        catmap: カテゴリマスターデータ
    
    Returns:
        dict: 選択された条件
    """
    # ユーザー制限情報を取得
    restrictions = get_user_restrictions()
    
    # ユーザー情報表示
    user_name = st.session_state.get("user_display_name", "ゲスト")
    st.sidebar.markdown(f"**👤 {user_name}**")
    
    if restrictions["has_query_file"]:
        if restrictions["can_modify_query"]:
            st.sidebar.caption("🔓 デフォルトクエリあり・追加条件入力可")
        else:
            st.sidebar.caption("🔒 固定クエリモード")
    
    st.sidebar.markdown("---")
    
    # ========== キーワード・年度検索 ===========
    # can_modify_query=Falseの場合は非表示
    if restrictions["can_modify_query"]:
        st.sidebar.subheader("🔍 キーワード・年度絞り込み")
        
        year_options = list(range(2010, 2031))
        selected_years = st.sidebar.multiselect(
            "年度(複数選択可)",
            options=year_options,
            default=[],
            help="fiscal_year_start/fiscal_year_endで絞り込み"
        )
        
        and_input = st.sidebar.text_input(
            "AND条件(スペース区切り)",
            placeholder="例: 環境 計画",
            help="全てのキーワードを含む文書を検索"
        )
        or_input = st.sidebar.text_input(
            "OR条件(スペース区切り)",
            placeholder="例: 温暖化 気候変動",
            help="いずれかのキーワードを含む文書を検索"
        )
        not_input = st.sidebar.text_input(
            "NOT条件(スペース区切り)",
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
    else:
        # 固定クエリモードの場合
        st.sidebar.info("🔒 検索条件は管理者により固定されています")
        selected_years = []
        and_input = ""
        or_input = ""
        not_input = ""
        search_fields = ["本文"]
    
    # ========== 自治体絞り込み(ツリー形式) ==========
    st.sidebar.subheader("🔍 自治体・カテゴリ絞り込み")
    
    # 自治体制限の適用
    allowed_codes = restrictions["allowed_codes"]
    
    # 制限がある場合、jichitaiをフィルタリング
    if allowed_codes:
        jichitai_filtered = jichitai[jichitai["code"].isin(allowed_codes)].copy()
        st.sidebar.caption(f"🔒 選択可能: {len(allowed_codes)}自治体")
    else:
        jichitai_filtered = jichitai.copy()
    
    # 自治体区分での事前フィルタリング
    ctype_opts = sorted(jichitai_filtered["city_type"].dropna().unique().tolist())
    
    # can_modify_query=Falseかつ制限ありの場合、自治体区分選択を非表示
    if not restrictions["can_modify_query"] and allowed_codes:
        sel_city_types = ctype_opts  # 全て選択状態
    else:
        sel_city_types = st.sidebar.multiselect(
            "自治体区分",
            options=ctype_opts,
            help="自治体区分で絞り込み後、ツリーから選択してください"
        )
    
    # ツリーデータの構築（フィルタ済みjichitaiを使用）
    tree_data, value_to_code = build_jichitai_tree(jichitai_filtered, sel_city_types)
    
    # ツリー選択UI
    st.sidebar.markdown("**自治体選択(都道府県→市区町村)**")
    
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
                key="jichitai_tree",
                placeholder="自治体名で検索..."
            )
    
    # デバッグ: 選択された値を表示
    if selected_values:
        st.sidebar.write("🔍 デバッグ: 選択された値", selected_values)
    
    # 選択された値(自治体名)をコードに変換
    sel_codes = []
    
    # selected_valuesが配列の場合（直接値のリスト）
    if selected_values and isinstance(selected_values, list):
        for value in selected_values:
            code = value_to_code.get(value)
            if code:
                # "pref_"で始まる場合は都道府県
                if str(code).startswith("pref_"):
                    # 都道府県コードを取得
                    pref_code = code.replace("pref_", "")
                    # 都道府県配下の全市区町村を含める
                    pref_cities = code_pool[code_pool["affiliation_code"] == pref_code]["code"].tolist()
                    sel_codes.extend(pref_cities)
                else:
                    # 市区町村コード
                    sel_codes.append(code)
        
        # 重複を除去
        sel_codes = list(set(sel_codes))
    
    # selected_valuesが辞書の場合（checkedキーを持つ）
    elif selected_values and isinstance(selected_values, dict):
        checked_items = selected_values.get("checked", [])
        for value in checked_items:
            code = value_to_code.get(value)
            if code:
                # "pref_"で始まる場合は都道府県
                if str(code).startswith("pref_"):
                    # 都道府県コードを取得
                    pref_code = code.replace("pref_", "")
                    # 都道府県配下の全市区町村を含める
                    pref_cities = code_pool[code_pool["affiliation_code"] == pref_code]["code"].tolist()
                    sel_codes.extend(pref_cities)
                else:
                    # 市区町村コード
                    sel_codes.append(code)
        
        # 重複を除去
        sel_codes = list(set(sel_codes))
        
        # デバッグ: 抽出されたコードを表示
        if sel_codes:
            st.sidebar.write(f"🔍 市区町村コード: {len(sel_codes)}件")
    
    # カテゴリ選択
    st.sidebar.markdown("---")
    cat_opts = catmap.sort_values("order")
    short_unique = cat_opts.drop_duplicates(subset=["short_name"], keep="first")
    
    # カテゴリ制限の適用
    allowed_categories = restrictions["allowed_categories"]
    
    if allowed_categories:
        # 制限がある場合、許可されたカテゴリのみ表示
        short_unique_filtered = short_unique[short_unique["category"].isin(allowed_categories)]
        default_categories = short_unique_filtered["short_name"].tolist()
        st.sidebar.caption(f"🔒 選択可能: {len(allowed_categories)}カテゴリ")
        
        # can_modify_query=Falseの場合は変更不可
        if not restrictions["can_modify_query"]:
            sel_cat_short = default_categories
            st.sidebar.multiselect(
                "資料カテゴリ",
                options=default_categories,
                default=default_categories,
                disabled=True,
                help="カテゴリは固定されています"
            )
        else:
            sel_cat_short = st.sidebar.multiselect(
                "資料カテゴリ",
                options=default_categories,
                default=default_categories
            )
    else:
        # 制限なし
        sel_cat_short = st.sidebar.multiselect(
            "資料カテゴリ",
            options=short_unique["short_name"].tolist(),
            default=short_unique["short_name"].tolist()
        )
    
    sel_categories = cat_opts[cat_opts["short_name"].isin(sel_cat_short)]["category"].astype(int).tolist()
    
    # ========== 表示設定 ==========
    st.sidebar.markdown("---")
    st.sidebar.header("表示設定")
    
    # 検索結果表示件数
    result_limit = st.sidebar.radio(
        "検索結果の表示件数",
        options=[100, 1000, 10000],
        index=0,
        help="検索結果タブでの表示件数を変更できます\n(デフォルト100件 多くなると挙動が重くなる可能性があります)"
    )
    
    # キーワード処理
    and_words = [w.strip() for w in and_input.replace("　", " ").split() if w.strip()]
    or_words = [w.strip() for w in or_input.replace("　", " ").split() if w.strip()]
    not_words = [w.strip() for w in not_input.replace("　", " ").split() if w.strip()]
    
    # クエリ用の自治体コードプールを構築（フィルタ済みを使用）
    code_pool = jichitai_filtered.copy()
    if sel_city_types:
        code_pool = code_pool[code_pool["city_type"].isin(sel_city_types)]
    
    # 都道府県全体が選択された場合の処理は上記で既に実施済み
    
    # 市区町村が選択されている場合
    if sel_codes:
        codes_for_query = sel_codes
    else:
        codes_for_query = code_pool["code"].tolist()
    
    # デバッグ: 最終的なクエリ用コード数を表示
    st.sidebar.write(f"🔍 クエリ対象: {len(codes_for_query)}自治体")
    
    return {
        "and_words": and_words,
        "or_words": or_words,
        "not_words": not_words,
        "selected_years": selected_years,
        "search_fields": search_fields,
        "sel_codes": sel_codes,
        "sel_categories": sel_categories,
        "codes_for_query": codes_for_query,
        "result_limit": result_limit,
        "short_unique": short_unique,
        "restrictions": restrictions,  # ユーザー制限情報を追加
    }