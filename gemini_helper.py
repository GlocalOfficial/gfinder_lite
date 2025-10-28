"""
Gemini API連携用のヘルパー関数
"""

import google.generativeai as genai
from typing import Optional
import streamlit as st


def init_gemini(api_key: str) -> genai.GenerativeModel:
    """
    Gemini APIを初期化
    
    Args:
        api_key: Gemini APIキー
    
    Returns:
        GenerativeModel: 初期化されたGeminiモデル
    """
    genai.configure(api_key=api_key)
    
    # モデル設定
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 2048,
    }
    
    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
    ]
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",  # または "gemini-1.5-pro"
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    
    return model


def generate_summary(model: genai.GenerativeModel, prompt: str) -> Optional[str]:
    """
    Gemini APIを使って要約を生成
    
    Args:
        model: 初期化されたGeminiモデル
        prompt: 送信するプロンプト
    
    Returns:
        Optional[str]: 生成されたテキスト、エラー時はNone
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Gemini API エラー: {str(e)}")
        return None


@st.cache_resource
def get_gemini_model(api_key: str) -> genai.GenerativeModel:
    """
    キャッシュ付きでGeminiモデルを取得
    
    Args:
        api_key: Gemini APIキー
    
    Returns:
        GenerativeModel: 初期化されたGeminiモデル
    """
    return init_gemini(api_key)