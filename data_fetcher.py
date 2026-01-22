"""
データ取得モジュール
Elasticsearchからのデータ取得と集計処理
"""

import json
from typing import Any
import pandas as pd
import streamlit as st
from elasticsearch import Elasticsearch
from config import INDEXES, FIELD_FILE_ID, FIELD_COLLECTED_AT


def _qkey(obj: Any) -> str:
    """オブジェクトをJSON文字列化してキャッシュキーとして使用"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


@st.cache_data(show_spinner=False, ttl=300)
def fetch_counts(
    es: Elasticsearch,
    query_key: str,
    group_field: str,
    include_file: bool
) -> pd.DataFrame:
    """
    グループ×カテゴリごとの件数を取得
    
    Args:
        es: Elasticsearchクライアント
        query_key: クエリのJSON文字列
        group_field: グループ化するフィールド名
        include_file: ファイル数をカウントするか
    
    Returns:
        pd.DataFrame: 集計結果（g, category, page_docs, file_docs）
    """
    after, recs = None, []
    while True:
        body = {
            "size": 0,
            "query": json.loads(query_key) if query_key else {"match_all": {}},
            "aggs": {
                "by_pair": {
                    "composite": {
                        "size": 500,
                        "sources": [
                            {"g": {"terms": {"field": group_field}}},
                            {"category": {"terms": {"field": "category"}}},
                        ],
                        **({"after": after} if after else {}),
                    },
                    "aggs": (
                        {"file_count": {"cardinality": {"field": FIELD_FILE_ID}}}
                        if include_file else {}
                    ),
                }
            },
        }
        res = es.search(index=INDEXES, body=body)
        for b in res["aggregations"]["by_pair"]["buckets"]:
            recs.append({
                "g": str(b["key"]["g"]),
                "category": int(b["key"]["category"]) if b["key"].get("category") is not None else None,
                "page_docs": b["doc_count"],
                "file_docs": b.get("file_count", {}).get("value", 0),
            })
        after = res["aggregations"]["by_pair"].get("after_key")
        if not after:
            break
    return pd.DataFrame.from_records(recs)


@st.cache_data(show_spinner=False, ttl=300)
def fetch_latest_month(
    es: Elasticsearch,
    query_key: str,
    group_field: str
) -> pd.DataFrame:
    """
    グループ×カテゴリごとの最新収集月（epoch millis）を取得
    
    Args:
        es: Elasticsearchクライアント
        query_key: クエリのJSON文字列
        group_field: グループ化するフィールド名
    
    Returns:
        pd.DataFrame: 最新収集月データ（g, category, latest_epoch）
    """
    after, recs = None, []
    while True:
        body = {
            "size": 0,
            "query": json.loads(query_key) if query_key else {"match_all": {}},
            "aggs": {
                "by_pair": {
                    "composite": {
                        "size": 500,
                        "sources": [
                            {"g": {"terms": {"field": group_field}}},
                            {"category": {"terms": {"field": "category"}}},
                        ],
                        **({"after": after} if after else {}),
                    },
                    "aggs": {"max_collected": {"max": {"field": FIELD_COLLECTED_AT}}}
                }
            },
        }
        res = es.search(index=INDEXES, body=body)
        for b in res["aggregations"]["by_pair"]["buckets"]:
            recs.append({
                "g": str(b["key"]["g"]),
                "category": int(b["key"]["category"]) if b["key"].get("category") is not None else None,
                "latest_epoch": b.get("max_collected", {}).get("value"),
            })
        after = res["aggregations"]["by_pair"].get("after_key")
        if not after:
            break
    return pd.DataFrame.from_records(recs)


def fetch_search_results(
    es: Elasticsearch,
    query: dict,
    jichitai: pd.DataFrame,
    catmap: pd.DataFrame,
    result_limit: int
) -> pd.DataFrame:
    """
    検索結果を取得してDataFrame形式で返す
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
        jichitai: 自治体マスターデータ
        catmap: カテゴリマスターデータ
        result_limit: 取得件数上限
    
    Returns:
        pd.DataFrame: 検索結果
    """
    body = {
        "size": result_limit,
        "query": query,
    }
    res = es.search(index=INDEXES, body=body)
    hits = res.get("hits", {}).get("hits", [])
    
    # 必要な情報を抽出
    data = []
    for hit in hits:
        source = hit["_source"]
        
        # jichitai.xlsxのcodeを6桁にゼロ埋めして照合
        code_str = str(source.get("code")).zfill(6)
        todofuken = jichitai.loc[
            jichitai["code"] == code_str, "pref_name"
        ].values
        shikuchoson = jichitai.loc[
            jichitai["code"] == code_str, "city_name"
        ].values
        
        # category.xlsxからカテゴリ名を取得
        category_name = catmap.loc[
            catmap["category"] == source.get("category"), "short_name"
        ].values
        
        data.append({
            "団体コード": code_str,
            "都道府県": todofuken[0] if len(todofuken) > 0 else "",
            "市区町村": shikuchoson[0] if len(shikuchoson) > 0 else "",
            "資料カテゴリ": category_name[0] if len(category_name) > 0 else "",
            "資料名": source.get("title", ""),
            "URL": source.get("source_url", "") + "#page=" + str(source.get("file_page", "")),
            "ページ": str(source.get("file_page", "")) + "／" + str(source.get("number_of_pages", "")),
            "本文": source.get("content_text", ""),
            "開始年度": source.get("fiscal_year_start", ""),
            "終了年度": source.get("fiscal_year_end", ""),
        })
    
    return pd.DataFrame(data)


def fetch_kpi(es: Elasticsearch, query: dict) -> dict:
    """
    KPI（全体統計）を取得
    
    Args:
        es: Elasticsearchクライアント
        query: 検索クエリ
    
    Returns:
        dict: KPIデータ（total_pages, total_files, max_collected_value）
    """
    kpi_body = {
        "size": 0,
        "track_total_hits": True,
        "query": query,
        "aggs": {
            "uniq_files": {"cardinality": {"field": FIELD_FILE_ID, "precision_threshold": 40000}},
            "max_collected": {"max": {"field": FIELD_COLLECTED_AT}},
        },
    }
    kpi_res = es.search(index=INDEXES, body=kpi_body)
    
    return {
        "total_pages": kpi_res.get("hits", {}).get("total", {}).get("value", 0),
        "total_files": kpi_res.get("aggregations", {}).get("uniq_files", {}).get("value", 0),
        "max_collected_value": kpi_res.get("aggregations", {}).get("max_collected", {}).get("value"),
    }