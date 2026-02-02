"""
OpenAI API連携用のヘルパー関数
"""

from openai import OpenAI
from typing import Optional
import streamlit as st
from config import get_secret


def init_openai(api_key: str) -> OpenAI:
    """
    OpenAI APIクライアントを初期化
    
    Args:
        api_key: OpenAI APIキー
    
    Returns:
        OpenAI: 初期化されたOpenAIクライアント
    """
    return OpenAI(api_key=api_key)


def get_user_openai_api_key() -> Optional[str]:
    """
    ユーザーのOpenAI APIキーを取得
    優先順位：
    1. ユーザー個別のAPIキー（auth.xlsx）
    2. secrets.tomlのOPENAI_API_KEY
    3. None
    
    Returns:
        Optional[str]: OpenAI APIキー、未設定時はNone
    """
    # ユーザー個別のAPIキーを確認
    user_api_key = st.session_state.get("user_openai_api_key")
    if user_api_key:
        return user_api_key
    
    # フォールバック：secrets.tomlから取得
    default_api_key = get_secret("OPENAI_API_KEY")
    if default_api_key:
        return default_api_key
    
    return None


def generate_summary(client: OpenAI, prompt: str, model: str = "gpt-4o") -> Optional[str]:
    """
    OpenAI APIを使って要約を生成
    
    Args:
        client: 初期化されたOpenAIクライアント
        prompt: 送信するプロンプト
        model: 使用するモデル（デフォルト: gpt-4o）
    
    Returns:
        Optional[str]: 生成されたテキスト、エラー時はNone
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "あなたは自治体の公開文書を分析する専門家です。検索結果を分かりやすく要約し、重要なポイントを抽出してください。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2048
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"OpenAI API エラー: {str(e)}")
        return None


@st.cache_resource
def get_openai_client(api_key: str) -> OpenAI:
    """
    キャッシュ付きでOpenAIクライアントを取得
    
    Args:
        api_key: OpenAI APIキー
    
    Returns:
        OpenAI: 初期化されたOpenAIクライアント
    """
    return init_openai(api_key)