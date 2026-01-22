"""
認証モジュール
ユーザー認証とクエリファイルの管理
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from config import get_secret


def load_auth_data() -> pd.DataFrame:
    """
    auth.xlsxから認証データを読み込み
    
    Returns:
        pd.DataFrame: 認証データ
    """
    try:
        filepath = Path("auth.xlsx")
        if not filepath.exists():
            return None
        
        df = pd.read_excel(filepath, dtype=str)
        
        # 必須列の確認
        required_cols = ["user_id", "password"]
        if not all(col in df.columns for col in required_cols):
            st.error(f"auth.xlsxに必須列が不足しています: {required_cols}")
            return None
        
        # オプション列のデフォルト値設定
        if "query_file" not in df.columns:
            df["query_file"] = None
        if "display_name" not in df.columns:
            df["display_name"] = df["user_id"]
        if "can_modify_query" not in df.columns:
            df["can_modify_query"] = True
        
        # can_modify_queryをboolに変換
        df["can_modify_query"] = df["can_modify_query"].fillna(True).astype(str).str.lower().isin(['true', '1', 'yes'])
        
        return df
    
    except Exception as e:
        st.error(f"auth.xlsx読み込みエラー: {e}")
        return None


def authenticate_user(user_id: str, password: str, auth_df: pd.DataFrame) -> dict:
    """
    ユーザー認証を実行
    
    Args:
        user_id: ユーザーID
        password: パスワード
        auth_df: 認証データ
    
    Returns:
        dict: 認証成功時はユーザー情報、失敗時はNone
    """
    user_row = auth_df[auth_df["user_id"] == user_id]
    
    if user_row.empty:
        return None
    
    user_data = user_row.iloc[0]
    
    if user_data["password"] == password:
        return {
            "user_id": user_data["user_id"],
            "display_name": user_data["display_name"],
            "query_file": user_data["query_file"] if pd.notna(user_data["query_file"]) else None,
            "can_modify_query": user_data["can_modify_query"]
        }
    
    return None


def check_password() -> bool:
    """
    認証ゲート
    
    - APP_PASSWORDが設定されている場合は簡易認証
    - auth.xlsxが存在する場合はユーザー認証
    
    Returns:
        bool: 認証成功ならTrue、失敗ならFalse
    """
    # すでにログイン済み？
    if st.session_state.get("_authed", False):
        return True
    
    # auth.xlsxの存在確認
    auth_df = load_auth_data()
    
    # auth.xlsxが存在しない場合はAPP_PASSWORDで簡易認証
    if auth_df is None:
        required_pw = get_secret("APP_PASSWORD")
        if not required_pw:
            # パスワード設定なし = 認証OFF
            st.session_state["_authed"] = True
            st.session_state["user_id"] = "guest"
            st.session_state["user_display_name"] = "ゲスト"
            st.session_state["user_query_file"] = None
            st.session_state["user_can_modify_query"] = True
            return True
        
        # 簡易パスワード認証
        with st.container():
            st.markdown("### 🔐 パスワードを入力してください")
            pw = st.text_input("Password", type="password", placeholder="Enter password")
            col_a, col_b = st.columns([1, 5])
            with col_a:
                submit = st.button("ログイン", use_container_width=True)
            if submit:
                if pw == required_pw:
                    st.session_state["_authed"] = True
                    st.session_state["user_id"] = "guest"
                    st.session_state["user_display_name"] = "ゲスト"
                    st.session_state["user_query_file"] = None
                    st.session_state["user_can_modify_query"] = True
                    st.rerun()
                else:
                    st.error("パスワードが違います。")
        return False
    
    # auth.xlsxによるユーザー認証
    with st.container():
        st.markdown("### 🔐 ログイン")
        
        user_id = st.text_input("ユーザーID", placeholder="User ID")
        password = st.text_input("パスワード", type="password", placeholder="Password")
        
        col_a, col_b = st.columns([1, 5])
        with col_a:
            submit = st.button("ログイン", use_container_width=True)
        
        if submit:
            if not user_id or not password:
                st.error("ユーザーIDとパスワードを入力してください。")
                return False
            
            user_info = authenticate_user(user_id, password, auth_df)
            
            if user_info:
                # 認証成功
                st.session_state["_authed"] = True
                st.session_state["user_id"] = user_info["user_id"]
                st.session_state["user_display_name"] = user_info["display_name"]
                st.session_state["user_query_file"] = user_info["query_file"]
                st.session_state["user_can_modify_query"] = user_info["can_modify_query"]
                st.success(f"ようこそ、{user_info['display_name']}さん！")
                st.rerun()
            else:
                st.error("ユーザーIDまたはパスワードが違います。")
    
    return False