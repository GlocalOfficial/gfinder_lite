"""
クエリ構築モジュール
Elasticsearchクエリの生成ロジック（ユーザー制限対応）
"""

from typing import List, Optional


def build_search_query(
    and_words: List[str],
    or_words: List[str],
    not_words: List[str],
    years: List[int],
    codes: List[str],
    categories: List[int],
    search_fields: List[str] = None,
    base_query: Optional[dict] = None
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
        base_query: ベースクエリ（ユーザー制限用、user_query.pyから渡される）
    
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
    
    # ===== ベースクエリがある場合は、そこから条件を引き継ぐ =====
    if base_query and isinstance(base_query, dict):
        bool_base = base_query.get("bool", {})
        
        # ベースクエリのmust句を引き継ぐ
        if "must" in bool_base:
            must_clauses.extend(bool_base["must"])
        
        # ベースクエリのshould句を引き継ぐ
        if "should" in bool_base:
            should_clauses.extend(bool_base["should"])
        
        # ベースクエリのmust_not句を引き継ぐ
        if "must_not" in bool_base:
            must_not_clauses.extend(bool_base["must_not"])
        
        # ベースクエリのfilter句を引き継ぐ
        if "filter" in bool_base:
            if isinstance(bool_base["filter"], list):
                filter_clauses.extend(bool_base["filter"])
            else:
                filter_clauses.append(bool_base["filter"])
    
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
    
    # ===== AND キーワード（追加条件） =====
    for w in and_words:
        must_clauses.append(build_field_query(w))
    
    # ===== OR キーワード（追加条件） =====
    for w in or_words:
        should_clauses.append(build_field_query(w))
    
    # ===== NOT キーワード（追加条件） =====
    for w in not_words:
        must_not_clauses.append(build_field_query(w))
    
    # ===== 年度検索（追加条件） =====
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
    
    # ===== 自治体コード（追加条件） =====
    # ベースクエリで既に制限されている可能性があるので、
    # codesが指定されている場合のみ追加
    if codes:
        # 既存のcode制限と重複しないように、新しいtermsクエリとして追加
        # （ベースクエリのcode制限は既にmust_clausesに含まれている）
        filter_clauses.append({"terms": {"code": codes}})
    
    # ===== カテゴリ（追加条件） =====
    # 同様に、categoriesが指定されている場合のみ追加
    if categories:
        filter_clauses.append({"terms": {"category": categories}})
    
    # ===== クエリ組み立て =====
    query = {"bool": {}}
    
    if must_clauses:
        query["bool"]["must"] = must_clauses
    
    if should_clauses:
        query["bool"]["should"] = should_clauses
        # ベースクエリでminimum_should_matchが設定されていた場合は保持
        if base_query and "bool" in base_query and "minimum_should_match" in base_query["bool"]:
            query["bool"]["minimum_should_match"] = base_query["bool"]["minimum_should_match"]
        else:
            query["bool"]["minimum_should_match"] = 1
    
    if must_not_clauses:
        query["bool"]["must_not"] = must_not_clauses
    
    if filter_clauses:
        query["bool"]["filter"] = filter_clauses
    
    # 何も条件がない場合
    if not query["bool"]:
        return {"match_all": {}}
    
    return query