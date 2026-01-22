"""
ユーザークエリ管理モジュール
ユーザー別のクエリファイルの読み込みと制限の適用
"""

import json
from pathlib import Path
from typing import Optional, Dict, List
import streamlit as st


def get_query_file_path(filename: str) -> Path:
    """
    クエリファイルのパスを取得
    
    Args:
        filename: クエリファイル名
    
    Returns:
        Path: クエリファイルのパス
    
    Raises:
        FileNotFoundError: ファイルが見つからない場合
    """
    # セキュリティ: パストラバーサル対策
    filename = Path(filename).name  # ディレクトリ部分を除去
    
    # queryディレクトリ内を探す
    query_dir = Path("query")
    if not query_dir.exists():
        query_dir.mkdir(parents=True)
    
    filepath = query_dir / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"クエリファイルが見つかりません: {filepath}")
    
    return filepath


def load_user_query(filename: str) -> Optional[Dict]:
    """
    ユーザーのクエリファイルを読み込み
    
    Args:
        filename: クエリファイル名
    
    Returns:
        Optional[Dict]: クエリ辞書、エラー時はNone
    """
    try:
        filepath = get_query_file_path(filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            query_data = json.load(f)
        return query_data
    except FileNotFoundError as e:
        st.error(f"クエリファイルエラー: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"クエリファイルのJSON形式が不正です: {e}")
        return None
    except Exception as e:
        st.error(f"クエリファイル読み込みエラー: {e}")
        return None


def extract_allowed_codes(query_data: Dict) -> List[str]:
    """
    クエリから許可された自治体コードリストを抽出
    
    Args:
        query_data: クエリ辞書
    
    Returns:
        List[str]: 許可された自治体コードのリスト（空の場合は制限なし）
    """
    try:
        must_clauses = query_data.get("query", {}).get("bool", {}).get("must", [])
        
        for clause in must_clauses:
            if "terms" in clause and "code" in clause["terms"]:
                return clause["terms"]["code"]
        
        return []  # 制限なし
    except Exception:
        return []


def extract_allowed_categories(query_data: Dict) -> List[int]:
    """
    クエリから許可されたカテゴリリストを抽出
    
    Args:
        query_data: クエリ辞書
    
    Returns:
        List[int]: 許可されたカテゴリIDのリスト（空の場合は制限なし）
    """
    try:
        must_clauses = query_data.get("query", {}).get("bool", {}).get("must", [])
        
        categories = []
        for clause in must_clauses:
            # term形式
            if "term" in clause and "category" in clause["term"]:
                cat_value = clause["term"]["category"]
                categories.append(int(cat_value))
            # terms形式
            elif "terms" in clause and "category" in clause["terms"]:
                categories.extend([int(c) for c in clause["terms"]["category"]])
        
        return categories
    except Exception:
        return []


def merge_queries(base_query: Dict, additional_conditions: Dict) -> Dict:
    """
    ベースクエリに追加条件をマージ
    
    Args:
        base_query: ベースクエリ（ユーザーのクエリファイル）
        additional_conditions: 追加条件（サイドバーからの入力）
    
    Returns:
        Dict: マージされたクエリ
    """
    merged = base_query.copy()
    
    # additional_conditionsがmatch_allの場合はベースクエリをそのまま返す
    if additional_conditions.get("match_all"):
        return merged
    
    # ベースクエリのmust句に追加条件をマージ
    if "query" not in merged:
        merged["query"] = {"bool": {"must": []}}
    
    if "bool" not in merged["query"]:
        merged["query"]["bool"] = {"must": []}
    
    if "must" not in merged["query"]["bool"]:
        merged["query"]["bool"]["must"] = []
    
    # additional_conditionsのbool句をマージ
    if "bool" in additional_conditions:
        add_bool = additional_conditions["bool"]
        
        # must句
        if "must" in add_bool and add_bool["must"]:
            merged["query"]["bool"]["must"].extend(add_bool["must"])
        
        # should句
        if "should" in add_bool and add_bool["should"]:
            if "should" not in merged["query"]["bool"]:
                merged["query"]["bool"]["should"] = []
            merged["query"]["bool"]["should"].extend(add_bool["should"])
            merged["query"]["bool"]["minimum_should_match"] = add_bool.get("minimum_should_match", 1)
        
        # must_not句
        if "must_not" in add_bool and add_bool["must_not"]:
            if "must_not" not in merged["query"]["bool"]:
                merged["query"]["bool"]["must_not"] = []
            merged["query"]["bool"]["must_not"].extend(add_bool["must_not"])
    
    return merged


def get_user_restrictions() -> Dict:
    """
    現在のユーザーの制限情報を取得
    
    Returns:
        Dict: ユーザー制限情報
            - has_query_file: bool (クエリファイルが設定されているか)
            - can_modify_query: bool (クエリ修正可能か)
            - allowed_codes: List[str] (許可された自治体コード、空=制限なし)
            - allowed_categories: List[int] (許可されたカテゴリ、空=制限なし)
            - base_query: Dict (ベースクエリ)
    """
    query_file = st.session_state.get("user_query_file")
    can_modify = st.session_state.get("user_can_modify_query", True)
    
    # クエリファイルが指定されていない = 無制限ユーザー
    if not query_file:
        return {
            "has_query_file": False,
            "can_modify_query": True,
            "allowed_codes": [],
            "allowed_categories": [],
            "base_query": None
        }
    
    # クエリファイルを読み込み
    query_data = load_user_query(query_file)
    if not query_data:
        # エラー時は制限なしとして扱う
        return {
            "has_query_file": False,
            "can_modify_query": True,
            "allowed_codes": [],
            "allowed_categories": [],
            "base_query": None
        }
    
    # can_modify_query=Falseの場合のみ、自治体・カテゴリを制限
    if not can_modify:
        allowed_codes = extract_allowed_codes(query_data)
        allowed_categories = extract_allowed_categories(query_data)
    else:
        allowed_codes = []
        allowed_categories = []
    
    return {
        "has_query_file": True,
        "can_modify_query": can_modify,
        "allowed_codes": allowed_codes,
        "allowed_categories": allowed_categories,
        "base_query": query_data.get("query", {})
    }