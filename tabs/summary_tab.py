"""
AI要約タブの表示処理（バッチ処理+ストリーミング対応版・エラー修正版）
"""

import datetime
import time
import streamlit as st
import pandas as pd
from elasticsearch import Elasticsearch
from config import get_secret
from data_fetcher import fetch_search_results
from openai_helper import get_openai_client, generate_summary, get_user_openai_api_key
from prompt import get_summary_prompt, get_custom_prompt, get_custom_batch_prompt, get_custom_integration_prompt


# ===== 定数定義 =====
MAX_DOCS_FOR_SUMMARY = 1000  # 最大文書数
BATCH_SIZE = 100  # 1バッチあたりの文書数
MAX_CHARS_PER_DOC = 800  # 本文の最大文字数


def render_summary_tab(
    es: Elasticsearch,
    query: dict,
    jichitai: pd.DataFrame,
    catmap: pd.DataFrame,
    result_limit: int
):
    """
    AI要約タブの表示（バッチ処理+ストリーミング対応）
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        catmap: カテゴリマスターデータ
        result_limit: 表示件数上限
    """
    st.subheader("🤖 GPT による要約")
    
    # APIキーの確認（ユーザー個別→デフォルトの優先順位）
    openai_api_key = get_user_openai_api_key()
    if not openai_api_key:
        st.error("OpenAI APIキーが設定されていません。ユーザー管理者に問い合わせるか、Streamlit Secretsに `OPENAI_API_KEY` を追加してください。")
        return
    
    # 検索結果の確認
    if not query:
        st.warning("まず検索条件を設定してください。")
        return
    
    df_results = fetch_search_results(es, query, jichitai, catmap, result_limit)
    
    if df_results.empty:
        st.warning("要約する検索結果がありません。検索条件を設定してください。")
        return
    
    total_docs = len(df_results)
    if total_docs > MAX_DOCS_FOR_SUMMARY:
        st.error(f"⚠️ 検索結果が{total_docs}件あります。分析対象は上限{MAX_DOCS_FOR_SUMMARY}件までです。検索条件を絞り込んでください。")
        return
    
    st.info(f"📊 要約対象: {total_docs}件のドキュメント")
    
    # モデル選択
    model_options = {
        "GPT-4o mini": "gpt-4o-mini",
    }
    
    selected_model_name = st.selectbox(
        "使用するモデル",
        options=list(model_options.keys()),
        index=0,
        help="GPT-4o miniで検証中です。"
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
    
    # ===== バッチ処理の推定値計算 =====
    total_batches = (total_docs + BATCH_SIZE - 1) // BATCH_SIZE  # 切り上げ
    
    # 推定値の計算
    estimated_time_per_batch = 60  # 秒
    estimated_total_time = total_batches * estimated_time_per_batch
    estimated_cost_per_batch = 0.10  # ドル
    estimated_total_cost = total_batches * estimated_cost_per_batch
    
    # 実行前の確認画面
    if summary_mode == "カスタムプロンプト" and custom_instruction:
        with st.expander("⚠️ 実行内容の確認", expanded=True):
            st.markdown(f"""
            **あなたの指示:**  
            {custom_instruction}
            
            **📊 処理内容:**
            - 対象文書数: {total_docs}件
            - バッチ数: {total_batches}バッチ（{BATCH_SIZE}件ずつ）
            - 推定処理時間: 約{estimated_total_time // 60}-{estimated_total_time // 60 + 3}分
            - 推定コスト: 約${estimated_total_cost:.2f}-${estimated_total_cost * 1.5:.2f}
            
            **📝 処理の流れ:**
            1. 各バッチで指示を実行（{total_batches}回）
            2. 全バッチの結果を統合（1回）
            3. 最終結果を表示
            
            **ℹ️ 注意:**  
            バッチごとの分析のため、「最も〜」「TOP3」などの指示は最終統合時に適用されます
            """)
    
    # 要約実行ボタン
    if st.button("🚀 要約を実行", type="primary", key="execute_summary_button"):
        # カスタムプロンプトモードで指示が未入力の場合
        if summary_mode == "カスタムプロンプト" and not custom_instruction:
            st.error("カスタムプロンプトを入力してください。")
            st.stop()
        
        # 中断フラグの初期化
        if "stop_processing" not in st.session_state:
            st.session_state.stop_processing = False
        
        try:
            # OpenAIクライアントを取得
            client = get_openai_client(openai_api_key)
            
            # ===== 必要な列だけを抽出 =====
            essential_columns = [
                '都道府県', 
                '市区町村', 
                '資料カテゴリ', 
                '資料名', 
                '本文', 
                '開始年度', 
                '終了年度'
            ]
            
            available_columns = [col for col in essential_columns if col in df_results.columns]
            df_essential = df_results[available_columns].copy()
            
            # ===== データをソート（まとまりのある分析のため） =====
            sort_columns = []
            if '団体コード' in df_results.columns:
                df_essential['団体コード'] = df_results['団体コード']
                sort_columns.append('団体コード')
            if '開始年度' in df_essential.columns:
                sort_columns.append('開始年度')
            if 'ファイルID' in df_results.columns:
                df_essential['ファイルID'] = df_results['ファイルID']
                sort_columns.append('ファイルID')
            
            if sort_columns:
                df_essential = df_essential.sort_values(by=sort_columns).reset_index(drop=True)
            
            # 本文を指定文字数に制限
            if '本文' in df_essential.columns:
                df_essential['本文'] = df_essential['本文'].apply(
                    lambda x: str(x)[:MAX_CHARS_PER_DOC] if pd.notna(x) else ""
                )
            
            # DataFrameを辞書のリストに変換
            all_documents = df_essential.to_dict('records')
            
            # ===== バッチ処理の実行 =====
            batch_results = []
            processing_times = []
            
            # 進捗表示用のプレースホルダー
            progress_placeholder = st.empty()
            result_placeholder = st.empty()
            
            # バッチ処理の進捗表示
            with progress_placeholder.container():
                st.markdown(f"### 🔄 {'カスタムプロンプト' if summary_mode == 'カスタムプロンプト' else '自動要約'}を実行中...")
                
                if summary_mode == "カスタムプロンプト":
                    st.info(f"**あなたの指示:** {custom_instruction}")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 中断ボタン（一意のキーを使用）
                stop_col1, stop_col2 = st.columns([1, 5])
                with stop_col1:
                    stop_button = st.button("⏹️ 中断", key=f"stop_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")
                if stop_button:
                    st.session_state.stop_processing = True
            
            # 各バッチを処理
            for batch_idx in range(total_batches):
                # 中断チェック
                if st.session_state.get("stop_processing", False):
                    progress_placeholder.empty()
                    with result_placeholder.container():
                        st.warning("⚠️ ユーザーによって処理が中断されました。")
                    st.session_state.stop_processing = False
                    break
                
                # バッチの範囲を計算
                start_idx = batch_idx * BATCH_SIZE
                end_idx = min((batch_idx + 1) * BATCH_SIZE, total_docs)
                batch_documents = all_documents[start_idx:end_idx]
                
                # 進捗更新
                progress = (batch_idx + 1) / total_batches
                progress_bar.progress(progress)
                status_text.markdown(f"**進捗: {int(progress * 100)}% ({batch_idx + 1}/{total_batches}バッチ) - バッチ{batch_idx + 1}処理中...**")
                
                # プロンプト生成
                batch_start_time = time.time()
                
                if summary_mode == "自動要約":
                    prompt = get_summary_prompt(batch_documents)
                else:
                    prompt = get_custom_batch_prompt(
                        batch_documents, 
                        custom_instruction, 
                        batch_idx + 1, 
                        total_batches
                    )
                
                # 要約生成（リトライ機能付き）
                max_retries = 3
                retry_count = 0
                batch_summary = None
                
                while retry_count < max_retries and batch_summary is None:
                    try:
                        batch_summary = generate_summary(client, prompt, model=selected_model)
                    except Exception as e:
                        error_str = str(e)
                        retry_count += 1
                        
                        # レート制限エラーの場合は60秒待機
                        if "rate_limit" in error_str.lower() or "429" in error_str:
                            if retry_count < max_retries:
                                st.warning(f"⚠️ レート制限エラー。60秒待機後にリトライします... ({retry_count}/{max_retries})")
                                time.sleep(60)
                            else:
                                st.error(f"❌ バッチ{batch_idx + 1}でレート制限エラーが継続しています。スキップします。")
                        # その他のエラー
                        else:
                            if retry_count < max_retries:
                                st.warning(f"⚠️ エラー発生。30秒待機後にリトライします... ({retry_count}/{max_retries})")
                                time.sleep(30)
                            else:
                                st.error(f"❌ バッチ{batch_idx + 1}でエラーが継続しています: {error_str}")
                
                batch_end_time = time.time()
                processing_time = batch_end_time - batch_start_time
                processing_times.append(processing_time)
                
                if batch_summary:
                    batch_results.append(batch_summary)
                else:
                    st.error(f"❌ バッチ{batch_idx + 1}の処理に失敗しました。")
            
            # 全バッチ完了 - 進捗表示を消去
            progress_placeholder.empty()
            
            # 処理完了の通知（一時的に表示）
            temp_status = st.empty()
            temp_status.success(f"✅ 全{len(batch_results)}バッチ完了")
            time.sleep(1)
            temp_status.empty()
            
            # ===== 最終統合処理 =====
            if batch_results and not st.session_state.get("stop_processing", False):
                # 統合処理の進捗表示用プレースホルダー
                integration_placeholder = st.empty()
                
                with integration_placeholder.container():
                    st.markdown("### 🔄 最終統合分析を実行中...")
                    st.info(f"""
                    {len(batch_results)}個のバッチ結果を統合して、
                    全体視点での分析を生成しています...
                    
                    ⏳ 推定残り時間: 約30-60秒
                    """)
                
                try:
                    integration_start_time = time.time()
                    
                    # 統合プロンプト生成
                    if summary_mode == "自動要約":
                        integration_prompt = f"""
以下は、全{total_docs}件の自治体文書を{len(batch_results)}バッチに分けて要約した結果です。
各バッチでは自治体ごとに分析がまとめられています。

{chr(10).join([f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{chr(10)}バッチ{i+1}の要約{chr(10)}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{chr(10)}{result}{chr(10)}" for i, result in enumerate(batch_results)])}

# 統合要約の指示
上記の各バッチ要約を統合し、全体を俯瞰した総合的な要約を作成してください。

# 統合時の重要ポイント
1. **自治体ごとの情報を統合**: 同じ自治体が複数バッチに登場する場合は情報を統合してください
2. **具体性を保持**: 根拠となる記載や具体的な施策名を保持してください
3. **重複を排除**: 同じ内容が複数回出現する場合は1回にまとめてください

# 出力形式
以下の構成で出力してください:

【全体サマリー】（200-300文字）
検索結果全体の傾向を俯瞰

【自治体別の統合分析】
各自治体の特徴を、根拠となる記載とともに整理

■ 都道府県名 市区町村名
- 特徴: ...
- 根拠となる記載: 「〇〇〇」
- 年度: ...

**重要: このバッチに含まれるすべての自治体について記載してください。省略や「以下省略」は不可。**

【主要テーマ】
最も頻出するテーマを3-5個

【地域別の傾向】
地域ごとの特徴があれば記載

【時系列の変化】
年度による変化や推移があれば記載

【頻出キーワード TOP5-10】
重要なキーワードを抽出
"""
                    else:
                        integration_prompt = get_custom_integration_prompt(
                            batch_results, 
                            custom_instruction, 
                            total_docs
                        )
                    
                    final_summary = generate_summary(client, integration_prompt, model=selected_model)
                    
                    integration_end_time = time.time()
                    integration_time = integration_end_time - integration_start_time
                    
                    if final_summary:
                        # 統合処理の進捗表示を消去
                        integration_placeholder.empty()
                        
                        # ダウンロード用コンテンツを生成（セッションステート保存前に作成）
                        download_content = f"""# {'カスタムプロンプト' if summary_mode == 'カスタムプロンプト' else '自動要約'}結果（完全版）

## 基本情報
- 実行日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 対象文書数: {total_docs}件
- バッチ数: {len(batch_results)}
- 処理時間: {(sum(processing_times) + integration_time) // 60:.0f}分{(sum(processing_times) + integration_time) % 60:.0f}秒

## 最終統合結果

{final_summary}

---

## 各バッチの詳細結果

"""
                        for i, result in enumerate(batch_results, 1):
                            start_idx = (i - 1) * BATCH_SIZE + 1
                            end_idx = min(i * BATCH_SIZE, total_docs)
                            download_content += f"""### バッチ{i}（文書{start_idx}-{end_idx}件）

{result}

---

"""
                        
                        # セッションステートに結果を保存
                        st.session_state['summary_result'] = final_summary
                        st.session_state['summary_download_content'] = download_content
                        st.session_state['summary_total_docs'] = total_docs
                        st.session_state['summary_batch_count'] = len(batch_results)
                        st.session_state['summary_processing_time'] = sum(processing_times) + integration_time
                        st.session_state['summary_mode'] = summary_mode
                        
                        # 最終結果の表示
                        with result_placeholder.container():
                            st.markdown("# 🎯 最終統合結果")
                            st.markdown(final_summary)
                            
                            # 完了情報と処理時間
                            total_processing_time = sum(processing_times) + integration_time
                            st.success(f"""
                            ✅ {'カスタムプロンプト' if summary_mode == 'カスタムプロンプト' else '自動要約'}が完了しました
                            
                            - 処理済み: {total_docs}件（{len(batch_results)}バッチ + 統合1回）
                            - 処理時間: {total_processing_time // 60:.0f}分{total_processing_time % 60:.0f}秒
                            """)
                        
                        # ページをリロードして、セッションステートから結果を再表示
                        st.rerun()
                    
                except Exception as e:
                    integration_placeholder.empty()
                    
                    # エラー時のダウンロード用コンテンツを生成
                    error_download_content = f"""# バッチ処理結果（統合失敗）

## 基本情報
- 実行日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 対象文書数: {total_docs}件
- バッチ数: {len(batch_results)}
- 処理時間: {sum(processing_times) // 60:.0f}分{sum(processing_times) % 60:.0f}秒

## エラー情報
{str(e)}

## 各バッチの結果

"""
                    for i, result in enumerate(batch_results, 1):
                        start_idx = (i - 1) * BATCH_SIZE + 1
                        end_idx = min(i * BATCH_SIZE, total_docs)
                        error_download_content += f"""### バッチ{i}（文書{start_idx}-{end_idx}件）

{result}

---

"""
                    
                    with result_placeholder.container():
                        st.error(f"⚠️ 最終統合処理でエラーが発生しました: {str(e)}")
                        
                        st.warning("""
                        各バッチの分析結果は正常に取得できています。
                        以下の対処法をお試しください:
                        
                        1. 各バッチ結果を確認する（統合なしでも有用な情報が含まれています）
                        2. カスタムプロンプトをより簡潔にして再実行
                        3. 対象文書数を減らして再実行
                        """)
                        
                        # エラー時もダウンロード機能を提供
                        st.download_button(
                            label="📥 バッチ結果をダウンロード",
                            data=error_download_content,
                            file_name=f"summary_batches_error_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain",
                            key=f"download_error_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
                        )
            
            elif not batch_results:
                progress_placeholder.empty()
                with result_placeholder.container():
                    st.error("❌ すべてのバッチ処理に失敗しました。")
            
        except Exception as e:
            if 'progress_placeholder' in locals():
                progress_placeholder.empty()
            if 'result_placeholder' in locals():
                with result_placeholder.container():
                    st.error(f"❌ 予期しないエラーが発生しました: {str(e)}")
            else:
                st.error(f"❌ 予期しないエラーが発生しました: {str(e)}")
        
        finally:
            # 中断フラグをリセット
            st.session_state.stop_processing = False
    
    # ===== セッションステートから結果を復元して表示 =====
    # ダウンロードボタンを押した後もこのセクションで結果が再表示される
    if 'summary_result' in st.session_state and 'summary_mode' in st.session_state:
        st.markdown("---")
        st.markdown("# 🎯 最終統合結果")
        st.markdown(st.session_state['summary_result'])
        
        # 完了情報
        st.success(f"""
        ✅ {st.session_state.get('summary_mode', '要約')}が完了しました
        
        - 処理済み: {st.session_state.get('summary_total_docs', 0)}件（{st.session_state.get('summary_batch_count', 0)}バッチ + 統合1回）
        - 処理時間: {st.session_state.get('summary_processing_time', 0) // 60:.0f}分{st.session_state.get('summary_processing_time', 0) % 60:.0f}秒
        """)
        
        # ダウンロードボタン
        col1, col2, col3 = st.columns([2, 2, 4])
        with col1:
            st.download_button(
                label="📥 完全版をダウンロード",
                data=st.session_state.get('summary_download_content', ''),
                file_name=f"summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="download_full_persistent"
            )
        with col2:
            st.download_button(
                label="📊 統合結果のみダウンロード",
                data=st.session_state.get('summary_result', ''),
                file_name=f"summary_final_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="download_final_persistent"
            )
    
    # 使用上の注意
    with st.expander("ℹ️ AI要約の使用上の注意"):
        st.markdown(f"""
        - AIによる要約は参考情報です。重要な決定には必ず原文を確認してください
        - **文書数制限**: 分析対象は上限{MAX_DOCS_FOR_SUMMARY}件までです
        - **バッチ処理**: {BATCH_SIZE}件ずつ処理し、最後に統合します
        - **データ並び替え**: 分析前に団体コード・年度・ファイルIDで並び替えを行います
        - 本文は最大{MAX_CHARS_PER_DOC}文字まで使用されます
        - 処理中に中断ボタンで停止できます
        - エラー時は自動リトライを行います（最大3回）
        - **トークン最適化**: 不要な列を送信から除外し、トークン数を削減しています
        - **表示**: 統合結果のみ表示されます。各バッチの詳細は完全版ダウンロードで確認できます
        - **ダウンロード後も結果表示**: ダウンロードボタンを押しても結果は消えません
        """)