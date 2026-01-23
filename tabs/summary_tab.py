"""
AI要約タブの表示処理
"""

import datetime
import streamlit as st
import pandas as pd
from elasticsearch import Elasticsearch
from config import get_secret
from data_fetcher import fetch_search_results
from openai_helper import get_openai_client, generate_summary
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
    st.subheader("🤖 GPT による要約")
    
    # APIキーの確認
    openai_api_key = get_secret("OPENAI_API_KEY")
    if not openai_api_key:
        st.error("OpenAI APIキーが設定されていません。Streamlit Secretsに `OPENAI_API_KEY` を追加してください。")
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
    
    # モデル選択
    model_options = {
        "GPT-4o": "gpt-4o",
        "GPT-4o mini": "gpt-4o-mini",
        "GPT-4 Turbo": "gpt-4-turbo-preview",
        "GPT-3.5 Turbo": "gpt-3.5-turbo"
    }
    
    selected_model_name = st.selectbox(
        "使用するモデル",
        options=list(model_options.keys()),
        index=0,
        help="GPT-4oが最新で高性能です。コストを抑えたい場合はGPT-4o miniまたはGPT-3.5 Turboを選択してください。"
    )
    selected_model = model_options[selected_model_name]
    
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
                # OpenAIクライアントを取得
                client = get_openai_client(openai_api_key)
                
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
                summary = generate_summary(client, prompt, model=selected_model)
                
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
        - OpenAI APIの利用制限に応じて、一度に処理できる件数に制限があります
        - モデルによってコストが異なります：
          - **GPT-4o**: 最新で高性能（やや高コスト）
          - **GPT-4o mini**: GPT-4oの軽量版（バランス型）
          - **GPT-4 Turbo**: 高性能（高コスト）
          - **GPT-3.5 Turbo**: 高速で低コスト
        """)