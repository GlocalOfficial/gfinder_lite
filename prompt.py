"""
Gemini API用のプロンプト設定
"""

def get_summary_prompt(documents: list[dict]) -> str:
    """
    検索結果を要約するためのプロンプトを生成
    
    Args:
        documents: 検索結果のリスト。各要素は以下のキーを含む辞書：
            - 都道府県: str
            - 市区町村: str
            - 資料カテゴリ: str
            - 資料名: str
            - 本文: str
            - 開始年度: int
            - 終了年度: int
    
    Returns:
        str: Gemini APIに送信するプロンプト
    """
    
    # 検索結果を整形
    docs_text = ""
    for i, doc in enumerate(documents, 1):
        docs_text += f"""
【文書{i}】
自治体: {doc.get('都道府県', '')} {doc.get('市区町村', '')}
資料カテゴリ: {doc.get('資料カテゴリ', '')}
資料名: {doc.get('資料名', '')}
年度: {doc.get('開始年度', '')}年度"""
        
        if doc.get('終了年度'):
            docs_text += f"～{doc.get('終了年度', '')}年度"
        
        docs_text += f"""
本文:
{doc.get('本文', '')[:2000]}  # 本文は最大2000文字まで

---
"""
    
    # プロンプト本体
    prompt = f"""
以下の自治体文書の検索結果を分析し、要約してください。

# 検索結果
{docs_text}

# 要約の指示
1. **全体の傾向**：検索結果全体から読み取れる主要なテーマや傾向を説明してください
2. **自治体別の特徴**：特徴的な取り組みや政策がある自治体について言及してください
3. **時期的な変化**：年度による変化や推移が見られる場合は指摘してください
4. **キーワード**：頻出する重要なキーワードを3-5個抽出してください

# 出力形式
簡潔かつ分かりやすく、箇条書きを活用して要約してください。
"""
    
    return prompt


def get_custom_prompt(documents: list[dict], user_instruction: str) -> str:
    """
    ユーザーが指定したカスタムプロンプトを生成
    
    Args:
        documents: 検索結果のリスト
        user_instruction: ユーザーからの追加指示
    
    Returns:
        str: Gemini APIに送信するプロンプト
    """
    
    # 検索結果を整形
    docs_text = ""
    for i, doc in enumerate(documents, 1):
        docs_text += f"""
【文書{i}】
自治体: {doc.get('都道府県', '')} {doc.get('市区町村', '')}
資料カテゴリ: {doc.get('資料カテゴリ', '')}
資料名: {doc.get('資料名', '')}
年度: {doc.get('開始年度', '')}年度"""
        
        if doc.get('終了年度'):
            docs_text += f"～{doc.get('終了年度', '')}年度"
        
        docs_text += f"""
本文:
{doc.get('本文', '')[:2000]}

---
"""
    
    prompt = f"""
以下の自治体文書の検索結果について、指示に従って分析してください。

# 検索結果
{docs_text}

# 指示
{user_instruction}

# 出力
簡潔かつ分かりやすく回答してください。
"""
    
    return prompt