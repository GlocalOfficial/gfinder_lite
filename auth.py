"""
認証モジュール
パスワード認証によるアクセス制御を提供
"""

import streamlit as st
from config import get_secret


def check_password() -> bool:
    """
    APP_PASSWORD を使った超シンプルなゲート
    
    - APP_PASSWORD が無い/空 → 認証オフ（そのまま入れる）
    - 合っていれば session_state に記録して以後スルー
    
    Returns:
        bool: 認証成功ならTrue、失敗ならFalse
    """
    required_pw = get_secret("APP_PASSWORD")
    if not required_pw:  # パスワード未設定なら認証OFF（開発用）
        return True

    # すでにログイン済み？
    if st.session_state.get("_authed", False):
        return True

    # 入力UI（ページの先頭に表示）
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
                st.rerun()
            else:
                st.error("パスワードが違います。")

    return False