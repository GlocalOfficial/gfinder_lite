"""
AI要約タブの表示処理
"""

import datetime
import streamlit as st
import pandas as pd
from elasticsearch import Elasticsearch
from config import get_secret
from data_fetcher import fetch_search_results
from gemini_helper import get_gemini_model, generate_summary
from prompt import get_summary_prompt, get_custom_prompt


def render_summary_tab(
    es: Elasticsearch,
    query: dict,
    jichitai: pd.DataFrame,
    catmap: pd.DataFrame,
    result_limit: int
):
    """
    AI要約タブの表示
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        catmap: カテゴリマスターデータ
        result_limit: 表示件数上限
    """
    st.subheader("🤖 Gemini AIによる要約")
    
    # APIキーの確認
    gemini_api_key = get_secret("GEMINI_API_KEY")
    if not gemini_api_key:
        st.error("Gemini APIキーが設定されていません。Streamlit Secretsに `GEMINI_API_KEY` を追加してください。")
        return
    
    # 検索結果の確認
    if not query:
        st.warning("まず検索条件を設定してください。")
        return
    
    df_results = fetch_search_results(es, query, jichitai, catmap, result_limit)
    
    if df_results.empty:
        st.warning("要約する検索結果がありません。検索条件を設定してください。")
        return
    
    st.info(f"📊 検索結果: {len(df_results)}件のドキュメント")
    
    # 要約モード選択
    summary_mode = st.radio(
        "要約モード",
        ["自動要約", "カスタムプロンプト"],
        horizontal=True
    )
    
    # カスタムプロンプトの入力
    custom_instruction = ""
    if summary_mode == "カスタムプロンプト":
        custom_instruction = st.text_area(
            "AIへの指示を入力してください",
            placeholder="例: これらの文書から環境政策に関する共通の課題を3つ抽出してください",
            height=100
        )
    
    # 要約実行ボタン
    if st.button("🚀 要約を実行", type="primary"):
        with st.spinner("AIが要約を生成中..."):
            try:
                # Geminiモデルを取得
                model = get_gemini_model(gemini_api_key)
                
                # DataFrameを辞書のリストに変換
                documents = df_results.to_dict('records')
                
                # プロンプト生成
                if summary_mode == "自動要約":
                    prompt = get_summary_prompt(documents)
                else:
                    if not custom_instruction:
                        st.error("カスタムプロンプトを入力してください。")
                        st.stop()
                    prompt = get_custom_prompt(documents, custom_instruction)
                
                # 要約生成
                summary = generate_summary(model, prompt)
                
                if summary:
                    st.success("✅ 要約が完成しました")
                    
                    # 要約結果の表示
                    st.markdown("### 📝 要約結果")
                    st.markdown(summary)
                    
                    # ダウンロードボタン
                    st.download_button(
                        label="📥 要約をダウンロード",
                        data=summary,
                        file_name=f"summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                else:
                    st.error("要約の生成に失敗しました。")
                    
            except Exception as e:
                st.error(f"エラーが発生しました: {str(e)}")
    
    # 使用上の注意
    with st.expander("ℹ️ AI要約の使用上の注意"):
        st.markdown("""
        - AIによる要約は参考情報です。重要な決定には必ず原文を確認してください
        - 検索結果が多い場合、処理に時間がかかることがあります
        - 本文は最大2000文字まで使用されます
        - Gemini APIの利用制限に応じて、一度に処理できる件数に制限があります
        """)