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
    include_title: bool = False
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
        include_title: 資料名も検索対象に含めるか
    
    Returns:
        dict: Elasticsearchクエリ
    """
    must_clauses = []
    should_clauses = []
    must_not_clauses = []
    filter_clauses = []
    
    # ===== キーワード検索 =====
    for w in and_words:
        if include_title:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"content_text": w}},
                        {"match_phrase": {"title": w}}
                    ],
                    "minimum_should_match": 1
                }
            })
        else:
            must_clauses.append({"match_phrase": {"content_text": w}})
    
    for w in or_words:
        if include_title:
            should_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"content_text": w}},
                        {"match_phrase": {"title": w}}
                    ],
                    "minimum_should_match": 1
                }
            })
        else:
            should_clauses.append({"match_phrase": {"content_text": w}})
    
    for w in not_words:
        if include_title:
            must_not_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"content_text": w}},
                        {"match_phrase": {"title": w}}
                    ],
                    "minimum_should_match": 1
                }
            })
        else:
            must_not_clauses.append({"match_phrase": {"content_text": w}})
    
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