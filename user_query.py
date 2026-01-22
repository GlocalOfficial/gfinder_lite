"""
ユーザークエリ管理モジュール（GCS対応版）
GCSからユーザー別のクエリファイルを読み込み、制限を適用
"""

from typing import Optional, Dict, List
import streamlit as st
from gcs_loader import load_query_from_gcs


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


def get_user_restrictions() -> Dict:
    """
    現在のユーザーの制限情報を取得（GCSから読み込み）
    
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
    
    # GCSからクエリファイルを読み込み
    query_data = load_query_from_gcs(query_file)
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