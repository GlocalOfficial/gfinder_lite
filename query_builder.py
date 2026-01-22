"""
クエリ構築モジュール
Elasticsearchクエリの生成ロジック
"""

from typing import List


def build_search_query(
    and_words: List[str],
    or_words: List[str],
    not_words: List[str],
    years: List[int],
    codes: List[str],
    categories: List[int],
    search_fields: List[str] = None
) -> dict:
    """
    キーワード・年度・自治体・カテゴリを組み合わせたクエリを構築
    
    Args:
        and_words: AND検索キーワードリスト
        or_words: OR検索キーワードリスト
        not_words: NOT検索キーワードリスト
        years: 検索対象年度リスト
        codes: 自治体コードリスト
        categories: カテゴリIDリスト
        search_fields: 検索対象フィールドリスト（["本文", "資料名"]）
    
    Returns:
        dict: Elasticsearchクエリ
    """
    if search_fields is None:
        search_fields = ["本文"]
    
    # フィールド名のマッピング
    field_mapping = {
        "本文": "content_text",
        "資料名": "title"
    }
    target_fields = [field_mapping[f] for f in search_fields if f in field_mapping]
    
    # 検索対象フィールドがない場合はデフォルトで本文のみ
    if not target_fields:
        target_fields = ["content_text"]
    
    must_clauses = []
    should_clauses = []
    must_not_clauses = []
    filter_clauses = []
    
    # ===== キーワード検索用ヘルパー関数 =====
    def build_field_query(word):
        """複数フィールドに対するクエリを構築"""
        if len(target_fields) == 1:
            return {"match_phrase": {target_fields[0]: word}}
        else:
            return {
                "bool": {
                    "should": [{"match_phrase": {field: word}} for field in target_fields],
                    "minimum_should_match": 1
                }
            }
    
    # ===== AND キーワード =====
    for w in and_words:
        must_clauses.append(build_field_query(w))
    
    # ===== OR キーワード =====
    for w in or_words:
        should_clauses.append(build_field_query(w))
    
    # ===== NOT キーワード =====
    for w in not_words:
        must_not_clauses.append(build_field_query(w))
    
    # ===== 年度検索 =====
    if years:
        year_should = []
        for y in years:
            # fiscal_year_start <= y <= fiscal_year_end
            cond_between = {
                "bool": {
                    "must": [
                        {"range": {"fiscal_year_start": {"lte": y}}},
                        {"range": {"fiscal_year_end": {"gte": y}}}
                    ]
                }
            }
            # fiscal_year_start == y かつ fiscal_year_end が存在しない
            cond_start_eq_when_no_end = {
                "bool": {
                    "must": [
                        {"term": {"fiscal_year_start": y}}
                    ],
                    "must_not": [
                        {"exists": {"field": "fiscal_year_end"}}
                    ]
                }
            }
            year_should.append(cond_between)
            year_should.append(cond_start_eq_when_no_end)
        
        filter_clauses.append({
            "bool": {
                "should": year_should,
                "minimum_should_match": 1
            }
        })
    
    # ===== 自治体コード =====
    if codes:
        filter_clauses.append({"terms": {"code": codes}})
    
    # ===== カテゴリ =====
    if categories:
        filter_clauses.append({"terms": {"category": categories}})
    
    # ===== クエリ組み立て =====
    query = {"bool": {}}
    if must_clauses:
        query["bool"]["must"] = must_clauses
    if should_clauses:
        query["bool"]["should"] = should_clauses
        query["bool"]["minimum_should_match"] = 1
    if must_not_clauses:
        query["bool"]["must_not"] = must_not_clauses
    if filter_clauses:
        query["bool"]["filter"] = filter_clauses
    
    # 何も条件がない場合
    if not query["bool"]:
        return {"match_all": {}}
    
    return query