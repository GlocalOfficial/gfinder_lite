"""
クエリ構築モジュール
Elasticsearchクエリの生成ロジック（ユーザー制限対応・キーワード統合改善版）
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
    base_query: Optional[dict] = None,
    can_modify_query: bool = True
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
        can_modify_query: クエリ修正可能フラグ（Trueならベースクエリのキーワードを無視）
    
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
    
    # ===== ベースクエリの条件を分類して引き継ぐ =====
    if base_query and isinstance(base_query, dict):
        bool_base = base_query.get("bool", {})
        
        # ベースクエリのmust句を分類
        if "must" in bool_base:
            base_must = bool_base["must"]
            if not isinstance(base_must, list):
                base_must = [base_must]
            
            for clause in base_must:
                # キーワード検索条件（match_phrase）かどうか判定
                is_keyword = False
                if "match_phrase" in clause:
                    # 単一フィールドのmatch_phrase
                    field_name = list(clause["match_phrase"].keys())[0]
                    if field_name in ["content_text", "title"]:  # 検索対象フィールドかチェック
                        is_keyword = True
                elif "bool" in clause and "should" in clause["bool"]:
                    # 複数フィールドのmatch_phrase（build_field_queryの形式）
                    should_list = clause["bool"]["should"]
                    if should_list and all("match_phrase" in s for s in should_list):
                        is_keyword = True
                
                if is_keyword:
                    # キーワード条件の扱い:
                    # - can_modify_query=False: must_clausesに追加（UI入力と統合）
                    # - can_modify_query=True: 無視（UI入力のみを使用）
                    if not can_modify_query:
                        must_clauses.append(clause)
                else:
                    # その他の条件（code, categoryなど）は常にfilter_clausesに追加
                    filter_clauses.append(clause)
        
        # ベースクエリのshould句を引き継ぐ
        if "should" in bool_base:
            base_should = bool_base["should"]
            if not isinstance(base_should, list):
                base_should = [base_should]
            should_clauses.extend(base_should)
        
        # ベースクエリのmust_not句を引き継ぐ
        if "must_not" in bool_base:
            base_must_not = bool_base["must_not"]
            if not isinstance(base_must_not, list):
                base_must_not = [base_must_not]
            must_not_clauses.extend(base_must_not)
        
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
    
    # ===== AND キーワード（UI入力を追加） =====
    # ベースクエリのキーワードは既にmust_clausesに含まれているので、
    # UI入力分を追加
    for w in and_words:
        must_clauses.append(build_field_query(w))
    
    # ===== OR キーワード（UI入力を追加） =====
    for w in or_words:
        should_clauses.append(build_field_query(w))
    
    # ===== NOT キーワード（UI入力を追加） =====
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
    # UI入力で自治体が指定されている場合のみ追加
    # （ベースクエリの自治体制限は既にfilter_clausesに含まれている）
    if codes:
        # ベースクエリに自治体制限がある場合は、AND条件として追加
        # （より厳しい制限を適用）
        filter_clauses.append({"terms": {"code": codes}})
    
    # ===== カテゴリ（追加条件） =====
    # UI入力でカテゴリが指定されている場合のみ追加
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