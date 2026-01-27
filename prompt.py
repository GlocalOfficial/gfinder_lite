"""
Gemini/OpenAI API用のプロンプト設定（バッチ処理対応版）
"""

def get_summary_prompt(documents: list[dict]) -> str:
    """
    検索結果を要約するためのプロンプトを生成（バッチ処理用）
    
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
        str: APIに送信するプロンプト
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
    
    # プロンプト本体
    prompt = f"""
以下の自治体文書の検索結果を分析し、要約してください。

# 検索結果
{docs_text}

# 要約の指示
1. **全体の傾向**：検索結果全体から読み取れる主要なテーマや傾向を説明してください
2. **自治体ごとの特徴**：各自治体の特徴的な取り組みや政策について、具体的な記載内容を引用しながら分析してください
3. **時期的な変化**：年度による変化や推移が見られる場合は指摘してください
4. **キーワード**：頻出する重要なキーワードを3-5個抽出してください

# 出力形式
以下の形式で出力してください：

【全体の傾向】
...

【自治体別の分析】
■ 都道府県名 市区町村名
- 特徴: ...
- 根拠となる記載: 「〇〇〇」（資料名より）
- 年度: ...

■ 都道府県名 市区町村名
- 特徴: ...
- 根拠となる記載: 「〇〇〇」（資料名より）
- 年度: ...

【時期的な変化】
...

【重要キーワード】
...
"""
    
    return prompt


def get_custom_prompt(documents: list[dict], user_instruction: str) -> str:
    """
    ユーザーが指定したカスタムプロンプトを生成
    
    Args:
        documents: 検索結果のリスト
        user_instruction: ユーザーからの追加指示
    
    Returns:
        str: APIに送信するプロンプト
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


def get_custom_batch_prompt(documents: list[dict], user_instruction: str, batch_num: int, total_batches: int) -> str:
    """
    カスタムプロンプト用のバッチプロンプトを生成
    
    Args:
        documents: 検索結果のリスト（バッチ分）
        user_instruction: ユーザーからの指示
        batch_num: 現在のバッチ番号（1から開始）
        total_batches: 総バッチ数
    
    Returns:
        str: バッチ処理用プロンプト
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
{doc.get('本文', '')[:800]}

---
"""
    
    prompt = f"""
# バッチ処理情報
これは全{total_batches}バッチ中の第{batch_num}バッチです。
このバッチには{len(documents)}件の文書が含まれています。

# 自治体文書データ
{docs_text}

# あなたへの指示
以下のユーザー指示に従って、上記の文書を分析してください：

{user_instruction}

# 出力形式
- このバッチ（{len(documents)}件）の範囲内での分析結果を出力してください
- **必ず自治体ごとに分析結果をまとめてください**
- 各自治体について、具体的な記載内容（根拠となる文言）を引用してください
- 後で全バッチの結果を統合するため、以下の構造化された形式で出力してください：

【バッチ{batch_num}の分析結果】

■ 都道府県名 市区町村名
- 分析内容: ...
- 根拠となる記載: 「〇〇〇」（資料名より）
- 年度: ...

■ 都道府県名 市区町村名
- 分析内容: ...
- 根拠となる記載: 「〇〇〇」（資料名より）
- 年度: ...

（このバッチ内の全自治体について記載）
"""
    
    return prompt


def get_custom_integration_prompt(batch_results: list[str], user_instruction: str, total_docs: int) -> str:
    """
    カスタムプロンプト用の統合プロンプトを生成
    
    Args:
        batch_results: 各バッチの分析結果リスト
        user_instruction: ユーザーからの指示
        total_docs: 総文書数
    
    Returns:
        str: 統合処理用プロンプト
    """
    
    all_batch_results = ""
    for i, result in enumerate(batch_results, 1):
        all_batch_results += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
バッチ{i}の分析結果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{result}

"""
    
    prompt = f"""
# 統合分析タスク

以下は、全{total_docs}件の自治体文書を{len(batch_results)}バッチに分けて分析した結果です。
各バッチでは自治体ごとに分析がまとめられています。

{all_batch_results}

# あなたへの指示
上記の各バッチの分析結果を統合し、全体視点で以下の指示を実行してください：

{user_instruction}

# 出力要件
1. **自治体ごとの統合分析**
   - 各バッチの結果から同じ自治体の情報をまとめてください
   - 各自治体について、特徴・根拠となる記載・年度を整理してください
   
2. **全体の傾向分析**
   - 自治体間の共通点・相違点を明らかにしてください
   - 地域的な特徴があれば指摘してください
   
3. **重要度の高い情報を優先**
   - 重複を排除し、最も重要な情報を優先してください
   - 「TOP3」「ランキング」などの指示があれば、全バッチから選出してください

# 出力形式
以下の構造で出力してください：

【全体サマリー】
...

【自治体別の統合分析】
■ 都道府県名 市区町村名
- 特徴: ...
- 根拠: ...
- 年度: ...

■ 都道府県名 市区町村名
- 特徴: ...
- 根拠: ...
- 年度: ...

**重要: 対象となるすべての自治体について記載してください。省略や「以下省略」「その他の自治体」などは不可。自治体が多い場合でも、すべて列挙してください。**

【地域別・カテゴリ別の傾向】
...

【重要な発見事項】
...
"""
    
    return prompt