"""
認証モジュール（GCS対応版）
GCSからauth.xlsxを読み込んでユーザー認証を実施
"""

import streamlit as st
from config import get_secret
from gcs_loader import load_auth_from_gcs


def check_password() -> bool:
    """
    ユーザー認証を実施
    
    優先順位:
    1. GCSのauth.xlsx（存在する場合）
    2. APP_PASSWORD（auth.xlsxが無い場合）
    
    Returns:
        bool: 認証成功ならTrue、失敗ならFalse
    """
    # すでにログイン済み？
    if st.session_state.get("_authed", False):
        return True
    
    # GCSからauth.xlsxを読み込み
    auth_df = load_auth_from_gcs()
    
    # auth.xlsxが存在する場合 → ユーザー管理モード
    if auth_df is not None and not auth_df.empty:
        return _auth_with_user_db(auth_df)
    
    # auth.xlsxが無い場合 → 簡易認証モード
    else:
        return _auth_with_simple_password()


def _auth_with_user_db(auth_df) -> bool:
    """
    auth.xlsxを使ったユーザー認証
    
    Args:
        auth_df: 認証データベース（DataFrame）
    
    Returns:
        bool: 認証成功ならTrue
    """
    with st.container():
        st.markdown("### 🔐 ログイン")
        
        username = st.text_input(
            "ユーザー名",
            placeholder="username"
        )
        password = st.text_input(
            "パスワード",
            type="password",
            placeholder="password"
        )
        
        col_a, col_b = st.columns([1, 5])
        with col_a:
            submit = st.button("ログイン", use_container_width=True)
        
        if submit:
            # ユーザー検索
            user_row = auth_df[
                (auth_df["username"] == username) &
                (auth_df["password"] == password) &
                (auth_df["enabled"] == True)
            ]
            
            if not user_row.empty:
                # 認証成功
                user_info = user_row.iloc[0]
                
                st.session_state["_authed"] = True
                st.session_state["user_display_name"] = user_info["display_name"]
                
                # query_fileが空欄（NaN, None, 空文字列）の場合はNoneを設定
                query_file_value = user_info["query_file"]
                if query_file_value and str(query_file_value).strip() and str(query_file_value).lower() != 'nan':
                    st.session_state["user_query_file"] = str(query_file_value).strip()
                else:
                    st.session_state["user_query_file"] = None
                
                # can_modify_queryが空欄の場合はTrueとして扱う（デフォルト：制限なし）
                can_modify_value = user_info["can_modify_query"]
                if can_modify_value is None or str(can_modify_value).strip() == '' or str(can_modify_value).lower() == 'nan':
                    st.session_state["user_can_modify_query"] = True
                else:
                    st.session_state["user_can_modify_query"] = bool(can_modify_value)
                
                st.success(f"ようこそ、{user_info['display_name']}さん")
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが正しくありません。")
    
    return False


def _auth_with_simple_password() -> bool:
    """
    APP_PASSWORDを使った簡易認証
    
    Returns:
        bool: 認証成功ならTrue
    """
    required_pw = get_secret("APP_PASSWORD")
    if not required_pw:  # パスワード未設定なら認証OFF（開発用）
        return True
    
    # 入力UI
    with st.container():
        st.markdown("### 🔐 パスワードを入力してください")
        pw = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password"
        )
        col_a, col_b = st.columns([1, 5])
        with col_a:
            submit = st.button("ログイン", use_container_width=True)
        
        if submit:
            if pw == required_pw:
                st.session_state["_authed"] = True
                st.session_state["user_display_name"] = "ゲスト"
                st.session_state["user_query_file"] = None
                st.session_state["user_can_modify_query"] = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
    
    return False