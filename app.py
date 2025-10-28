import json
import datetime
from typing import Any
from pathlib import Path

import pandas as pd
import streamlit as st
from elasticsearch import Elasticsearch

# Gemini関連のインポート
from gemini_helper import get_gemini_model, generate_summary
from prompt import get_summary_prompt, get_custom_prompt

# ====== Config (Streamlit Secrets) ======
def get_secret(key: str, default: str = "") -> str:
    """Streamlit Secretsから値を取得。存在しない場合はデフォルト値を返す"""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def _check_password() -> bool:
    """APP_PASSWORD を使った超シンプルなゲート。
    - APP_PASSWORD が無い/空 → 認証オフ（そのまま入れる）
    - 合っていれば session_state に記録して以後スルー
    """
    required_pw = get_secret("APP_PASSWORD")
    if not required_pw:  # パスワード未設定なら認証OFF（開発用）
        return True

    # すでにログイン済み？
    if st.session_state.get("_authed", False):
        return True

    # 入力UI（ページの先頭に表示）
    with st.container():
        st.markdown("### 🔐 パスワードを入力してください")
        pw = st.text_input("Password", type="password", placeholder="Enter password", help="運用担当から共有されたパスワードを入力")
        col_a, col_b = st.columns([1,5])
        with col_a:
            submit = st.button("ログイン", use_container_width=True)
        if submit:
            if pw == required_pw:
                st.session_state["_authed"] = True
                st.rerun()
            else:
                st.error("パスワードが違います。")

    return False

# ここでゲート。通れなければ以降を実行しない
if not _check_password():
    st.stop()

# ====== Page & CSS ======
st.set_page_config(page_title="G-Finder データ収録状況", layout="wide")
st.markdown("""
<style>
  [data-testid="stSidebar"] {width: 360px;}
  [data-testid="stSidebar"] section {width: 360px;}
</style>
""", unsafe_allow_html=True)

# ====== Elasticsearch接続情報を取得 ======
ES_HOST = get_secret("ES_HOST")
ES_USERNAME = get_secret("ES_USERNAME")
ES_PASSWORD = get_secret("ES_PASSWORD")
ES_INDEX_yosankessan = get_secret("ES_INDEX_yosankessan")
ES_INDEX_keikakuhoshin = get_secret("ES_INDEX_keikakuhoshin")
ES_INDEX_iinkaigijiroku = get_secret("ES_INDEX_iinkaigijiroku")
ES_INDEX_kouhou = get_secret("ES_INDEX_kouhou")
INDEXES = [i for i in [ES_INDEX_yosankessan, ES_INDEX_keikakuhoshin, ES_INDEX_iinkaigijiroku, ES_INDEX_kouhou] if i]

# Gemini APIキーを取得
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

@st.cache_resource(show_spinner=False)
def es_client() -> Elasticsearch:
    if not ES_HOST or not ES_USERNAME or not ES_PASSWORD:
        st.error("ES 接続情報が不足（ES_HOST / ES_USERNAME / ES_PASSWORD）")
        st.stop()
    return Elasticsearch(ES_HOST, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=False, request_timeout=90)
es = es_client()

# ====== Masters ======
# ファイルパスを取得（カレントディレクトリまたはスクリプトのディレクトリ）
def get_data_path(filename: str) -> Path:
    """データファイルのパスを取得"""
    # まず、カレントディレクトリをチェック
    current_path = Path(filename)
    if current_path.exists():
        return current_path
    
    # 次に、スクリプトと同じディレクトリをチェック
    script_dir = Path(__file__).parent
    script_path = script_dir / filename
    if script_path.exists():
        return script_path
    
    # どちらも存在しない場合はエラー
    raise FileNotFoundError(
        f"'{filename}' が見つかりません。\n"
        f"確認したパス:\n"
        f"  - {current_path.absolute()}\n"
        f"  - {script_path.absolute()}"
    )

@st.cache_data(show_spinner=False)
def load_jichitai() -> pd.DataFrame:
    try:
        filepath = get_data_path("jichitai.xlsx")
        df = pd.read_excel(filepath, dtype={"code": str, "affiliation_code": str})
    except FileNotFoundError as e:
        st.error(f"ファイルエラー: {e}")
        st.stop()
    except Exception as e:
        st.error(f"jichitai.xlsx の読み込みエラー: {e}")
        st.stop()
    
    need = ["code", "affiliation_code", "pref_name", "city_name", "city_type"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        st.error(f"jichitai.xlsx に必須列が不足: {miss}")
        st.stop()
    df["code"] = df["code"].str.zfill(6)
    df["affiliation_code"] = df["affiliation_code"].str.zfill(2)  # 2桁で統一
    return df[need]

@st.cache_data(show_spinner=False)
def load_category() -> pd.DataFrame:
    try:
        filepath = get_data_path("category.xlsx")
        df = pd.read_excel(filepath)
    except FileNotFoundError as e:
        st.error(f"ファイルエラー: {e}")
        st.stop()
    except Exception as e:
        st.error(f"category.xlsx の読み込みエラー: {e}")
        st.stop()
    
    need = ["category", "category_name", "short_name", "order"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        st.error(f"category.xlsx に必須列が不足: {miss}")
        st.stop()
    if "group" not in df.columns:
        df["group"] = ""
    df = df.astype({"category": int, "order": int})
    return df

jichitai = load_jichitai()
catmap = load_category()
pref_master = (
    jichitai[["affiliation_code", "pref_name"]]
    .drop_duplicates()
    .assign(aff_num=lambda d: pd.to_numeric(d["affiliation_code"], errors="coerce"))
)

# ====== ES fields ======
FIELD_CODE = "code"
FIELD_AFFILIATION = "affiliation_code"
FIELD_CATEGORY = "category"
FIELD_FILE_ID = "file_id"
FIELD_COLLECTED_AT = "collected_at"  # datetime

# ====== Sidebar ======

# ========== キーワード・年度検索 ===========
st.sidebar.subheader("🔍 キーワード・年度絞り込み")

year_options = list(range(2010, 2031))
selected_years = st.sidebar.multiselect(
    "年度（複数選択可）",
    options=year_options,
    default=[],
    help="fiscal_year_start/fiscal_year_endで絞り込み"
)

and_input = st.sidebar.text_input(
    "AND条件（スペース区切り）",
    placeholder="例: 環境 計画",
    help="全てのキーワードを含む文書を検索"
)
or_input = st.sidebar.text_input(
    "OR条件（スペース区切り）",
    placeholder="例: 温暖化 気候変動",
    help="いずれかのキーワードを含む文書を検索"
)
not_input = st.sidebar.text_input(
    "NOT条件（スペース区切り）",
    placeholder="例: 廃止 中止",
    help="これらのキーワードを含まない文書を検索"
)

search_title = st.sidebar.checkbox(
    "資料名も検索対象に含める",
    value=False,
    help="チェックを入れるとtitleフィールドも検索対象になります"
)

st.sidebar.markdown("---")

# ========== 自治体絞り込み ==========
st.sidebar.subheader("🔍 自治体・カテゴリ絞り込み")
pref_opts = (
    jichitai[["affiliation_code", "pref_name"]]
    .drop_duplicates().assign(aff_num=lambda d: pd.to_numeric(d["affiliation_code"], errors="coerce"))
    .sort_values(["aff_num"])
)
sel_pref_names = st.sidebar.multiselect("都道府県", options=pref_opts["pref_name"].tolist())
sel_aff_codes = pref_opts[pref_opts["pref_name"].isin(sel_pref_names)]["affiliation_code"].tolist()

ctype_opts = sorted(jichitai["city_type"].dropna().unique().tolist())
sel_city_types = st.sidebar.multiselect("自治体区分", options=ctype_opts)

if sel_aff_codes:
    city_pool = jichitai[jichitai["affiliation_code"].isin(sel_aff_codes)]
else:
    city_pool = jichitai.copy()
if sel_city_types:
    city_pool = city_pool[city_pool["city_type"].isin(sel_city_types)]
city_pool = city_pool.sort_values(["affiliation_code", "code"])
sel_city_names = st.sidebar.multiselect("市区町村", options=city_pool["city_name"].tolist())
sel_codes = city_pool[city_pool["city_name"].isin(sel_city_names)]["code"].tolist()

cat_opts = catmap.sort_values("order")
short_unique = cat_opts.drop_duplicates(subset=["short_name"], keep="first")
sel_cat_short = st.sidebar.multiselect("資料カテゴリ", options=short_unique["short_name"].tolist(), default=short_unique["short_name"].tolist())
sel_categories = cat_opts[cat_opts["short_name"].isin(sel_cat_short)]["category"].astype(int).tolist()


# ========== 表示設定 ==========
st.sidebar.markdown("---")
st.sidebar.header("表示設定")
display_unit = st.sidebar.radio(
    "表示単位", 
    ["都道府県", "市区町村"],
    index=0)
count_mode = st.sidebar.radio(
    "集計単位", 
    ["ファイル数", "ページ数"], 
    index=0,
    help="ファイル数：PDFファイル単位で集計\nページ数：PDFのページ単位で集計")
result_limit = st.sidebar.radio(
    "検索結果の表示件数",
    options=[100, 1000, 10000],
    index=0,
    help="検索結果タブでの表示件数を変更できます\n（デフォルト100件 多くなると挙動が重くなる可能性があります）"
)

# ====== Query Builder ======
def build_search_query(and_words, or_words, not_words, years, codes, categories, include_title=False):
    """キーワード・年度・自治体・カテゴリを組み合わせたクエリを構築"""
    must_clauses = []
    should_clauses = []
    must_not_clauses = []
    filter_clauses = []
    
    # キーワード検索
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
    
    # 年度検索
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
    
    # 自治体コード
    if codes:
        filter_clauses.append({"terms": {FIELD_CODE: codes}})
    
    # カテゴリ
    if categories:
        filter_clauses.append({"terms": {FIELD_CATEGORY: categories}})
    
    # クエリ組み立て
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

# ====== Query (common) ======
code_pool = jichitai.copy()
if sel_aff_codes:
    code_pool = code_pool[code_pool["affiliation_code"].isin(sel_aff_codes)]
if sel_city_types:
    code_pool = code_pool[code_pool["city_type"].isin(sel_city_types)]
if sel_city_names:
    code_pool = code_pool[code_pool["city_name"].isin(sel_city_names)]
codes_for_query = code_pool["code"].tolist()

# キーワード処理
and_words = [w.strip() for w in and_input.replace("　", " ").split() if w.strip()]
or_words = [w.strip() for w in or_input.replace("　", " ").split() if w.strip()]
not_words = [w.strip() for w in not_input.replace("　", " ").split() if w.strip()]

# クエリ構築
query = build_search_query(
    and_words=and_words,
    or_words=or_words,
    not_words=not_words,
    years=selected_years,
    codes=codes_for_query,
    categories=sel_categories,
    include_title=search_title
)

# ====== KPI（全体） ======
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
kpi_total_pages = kpi_res.get("hits", {}).get("total", {}).get("value", 0)
kpi_total_files = kpi_res.get("aggregations", {}).get("uniq_files", {}).get("value", 0)
max_collected_value = kpi_res.get("aggregations", {}).get("max_collected", {}).get("value")

def fmt_month_from_epoch(v):
    if v is None: return "―"
    try:
        dt = datetime.datetime.utcfromtimestamp(v/1000.0) + datetime.timedelta(hours=9)
        return f"{dt.year}年{dt.month}月"
    except Exception:
        return "―"

latest_collected_label = fmt_month_from_epoch(max_collected_value)

# ====== Title + KPI ======
st.markdown("""
# G-Finder Lite⚡ 
・各列のヘッダをクリックすると並び替えできます。  
・最新収集月は収集者が最後に収集した日付から算出しているため、必ずしも当月の資料が収録されているということではありません。  
・キーワードは完全一致検索です（""は不要です）
""", unsafe_allow_html=True)

# 検索条件の表示
search_info_parts = []
if and_words:
    search_info_parts.append(f"**AND**: {', '.join(and_words)}")
if or_words:
    search_info_parts.append(f"**OR**: {', '.join(or_words)}")
if not_words:
    search_info_parts.append(f"**NOT**: {', '.join(not_words)}")
if selected_years:
    search_info_parts.append(f"**年度**: {', '.join(map(str, sorted(selected_years)))}")
if search_title:
    search_info_parts.append("**検索対象**: 本文 + 資料名")

if search_info_parts:
    st.info("🔍 **検索条件**: " + " | ".join(search_info_parts))

k1, k2, _sp = st.columns([2, 2, 6])
with k1: st.metric("総ファイル数", f"{kpi_total_files:,}")
with k2: st.metric("総データ（ページ）数", f"{kpi_total_pages:,}")

# ====== Helpers ======
def _qkey(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)

@st.cache_data(show_spinner=False, ttl=300)
def fetch_counts(query_key: str, group_field: str, include_file: bool) -> pd.DataFrame:
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
                            {"category": {"terms": {"field": FIELD_CATEGORY}}},
                        ],
                        **({"after": after} if after else {}),
                    },
                    "aggs": ({ "file_count": {"cardinality": {"field": FIELD_FILE_ID}} } if include_file else {}),
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
        if not after: break
    return pd.DataFrame.from_records(recs)

@st.cache_data(show_spinner=False, ttl=300)
def fetch_latest_month(query_key: str, group_field: str) -> pd.DataFrame:
    """g×categoryごとの collected_at 最大（epoch millis）"""
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
                            {"category": {"terms": {"field": FIELD_CATEGORY}}},
                        ],
                        **({"after": after} if after else {}),
                    },
                    "aggs": { "max_collected": { "max": { "field": FIELD_COLLECTED_AT } } }
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
        if not after: break
    return pd.DataFrame.from_records(recs)

def cat_short_map():
    return catmap.set_index("category")["short_name"].to_dict()

def build_counts_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["short_name"] = df["category"].map(cat_short_map()).fillna(df["category"].astype(str))
    value_col = "file_docs" if ("ファイル数" in count_mode) else "page_docs"
    if display_unit == "市区町村":
        merged = df.merge(jichitai.rename(columns={"code": "g"}), on="g", how="left")
        pvt = merged.pivot_table(index=["pref_name","city_name","city_type","g"],
                                 columns="short_name", values=value_col, aggfunc="sum",
                                 fill_value=0, observed=True
                                 ).reset_index().sort_values(by=["g"]).drop(columns=["g"])
        pvt["合計"] = pvt.drop(columns=["pref_name","city_name","city_type"]).sum(axis=1)
        pvt = pvt.rename(columns={"pref_name":"都道府県","city_name":"市区町村","city_type":"自治体区分"})
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        return pvt[["都道府県","市区町村","自治体区分"] + ordered + ["合計"]]
    else:
        df["g"] = df["g"].astype(str).str.zfill(2)
        merged = df.merge(pref_master.rename(columns={"affiliation_code":"g"}), on="g", how="left")
        pref_agg = merged.groupby(["g","aff_num","pref_name","short_name"], observed=True)[value_col].sum().reset_index()
        pvt = pref_agg.pivot_table(index=["g","aff_num","pref_name"],
                                   columns="short_name", values=value_col, aggfunc="sum",
                                   fill_value=0, observed=True).reset_index()
        pvt = pvt.sort_values(by=["aff_num","g"])
        pvt["合計"] = pvt.drop(columns=["g","aff_num","pref_name"]).sum(axis=1)
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        pvt = pvt[["pref_name"] + ordered + ["合計"]].rename(columns={"pref_name":"都道府県"})
        return pvt

def build_latest_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["short_name"] = df["category"].map(cat_short_map()).fillna(df["category"].astype(str))
    # epoch → 'YYYY年M月'
    df["latest"] = df["latest_epoch"].apply(lambda v: fmt_month_from_epoch(v))
    if display_unit == "市区町村":
        merged = df.merge(jichitai.rename(columns={"code":"g"}), on="g", how="left")
        pvt = merged.pivot_table(index=["pref_name","city_name","city_type","g"],
                                 columns="short_name", values="latest", aggfunc="max",
                                 fill_value="―", observed=True
                                 ).reset_index().sort_values(by=["g"]).drop(columns=["g"])
        pvt = pvt.rename(columns={"pref_name":"都道府県","city_name":"市区町村","city_type":"自治体区分"})
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        return pvt[["都道府県","市区町村","自治体区分"] + ordered]
    else:
        df["g"] = df["g"].astype(str).str.zfill(2)
        merged = df.merge(pref_master.rename(columns={"affiliation_code":"g"}), on="g", how="left")
        pref_agg = merged.groupby(["g","aff_num","pref_name","short_name"], observed=True)["latest"].max().reset_index()
        pvt = pref_agg.pivot_table(index=["g","aff_num","pref_name"],
                                   columns="short_name", values="latest", aggfunc="max",
                                   fill_value="―", observed=True).reset_index()
        pvt = pvt.sort_values(by=["aff_num","g"])
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        pvt = pvt[["pref_name"] + ordered].rename(columns={"pref_name":"都道府県"})
        return pvt

def show_df(df: pd.DataFrame, latest: bool = False):
    disp = df.copy()
    # 数値列は文字列化してカンマ区切り
    for c in disp.columns:
        if not latest and pd.api.types.is_numeric_dtype(disp[c]):
            disp[c] = disp[c].apply(lambda v: f"{v:,}" if pd.notnull(v) else "")
    st.dataframe(disp, use_container_width=True, hide_index=True)

def fetch_search_results(query: dict) -> pd.DataFrame:
    """Elastic Searchからデータを取得してDataFrame形式で返す"""
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
        todofuken = jichitai.loc[jichitai["code"].astype(str).str.zfill(6) == str(source.get("code")).zfill(6), "pref_name"].values
        shikuchoson = jichitai.loc[jichitai["code"].astype(str).str.zfill(6) == str(source.get("code")).zfill(6), "city_name"].values
        
        # category.xlsxからカテゴリ名を取得
        category_name = catmap.loc[catmap["category"] == source.get("category"), "short_name"].values
        
        data.append({
            "団体コード": str(source.get("code")).zfill(6),  
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


# ====== Tabs：件数 / 検索結果 / 最新収集月 / AI要約 ======
tab_counts, tab_results, tab_latest, tab_summary = st.tabs(["件数", "検索結果", "最新収集月", "🤖 AI要約"])

with tab_counts:
    group_field = FIELD_CODE if display_unit == "市区町村" else FIELD_AFFILIATION
    df_counts = fetch_counts(_qkey(query), group_field, include_file=("ファイル数" in count_mode))
    if df_counts.empty:
        st.warning("該当データがありません。フィルタを見直してください。")
    else:
        table = build_counts_table(df_counts)
        show_df(table)

with tab_results:
    if query:
        df_results = fetch_search_results(query)
        if df_results.empty:
            st.warning("該当データがありません。フィルタを見直してください。")
        else:
            st.dataframe(df_results, use_container_width=True, hide_index=True)
    else:
        st.warning("検索条件を設定してください。")

with tab_latest:
    group_field = FIELD_CODE if display_unit == "市区町村" else FIELD_AFFILIATION
    df_latest = fetch_latest_month(_qkey(query), group_field)
    if df_latest.empty:
        st.warning("該当データがありません。フィルタを見直してください。")
    else:
        table = build_latest_table(df_latest)
        show_df(table, latest=True)

with tab_summary:
    st.subheader("🤖 Gemini AIによる要約")
    
    # APIキーの確認
    if not GEMINI_API_KEY:
        st.error("Gemini APIキーが設定されていません。Streamlit Secretsに `GEMINI_API_KEY` を追加してください。")
    else:
        # 検索結果の確認
        if query:
            df_results = fetch_search_results(query)
            
            if df_results.empty:
                st.warning("要約する検索結果がありません。検索条件を設定してください。")
            else:
                st.info(f"📊 検索結果: {len(df_results)}件のドキュメント")
                
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
                
                # 要約実行ボタン
                if st.button("🚀 要約を実行", type="primary"):
                    with st.spinner("AIが要約を生成中..."):
                        try:
                            # Geminiモデルを取得
                            model = get_gemini_model(GEMINI_API_KEY)
                            
                            # DataFrameを辞書のリストに変換
                            documents = df_results.to_dict('records')
                            
                            # プロンプト生成
                            if summary_mode == "自動要約":
                                prompt = get_summary_prompt(documents)
                            else:
                                if not custom_instruction:
                                    st.error("カスタムプロンプトを入力してください。")
                                    st.stop()
                                prompt = get_custom_prompt(documents, custom_instruction)
                            
                            # 要約生成
                            summary = generate_summary(model, prompt)
                            
                            if summary:
                                st.success("✅ 要約が完成しました")
                                
                                # 要約結果の表示
                                st.markdown("### 📝 要約結果")
                                st.markdown(summary)
                                
                                # ダウンロードボタン
                                st.download_button(
                                    label="📥 要約をダウンロード",
                                    data=summary,
                                    file_name=f"summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                    mime="text/plain"
                                )
                            else:
                                st.error("要約の生成に失敗しました。")
                                
                        except Exception as e:
                            st.error(f"エラーが発生しました: {str(e)}")
                
                # 使用上の注意
                with st.expander("ℹ️ AI要約の使用上の注意"):
                    st.markdown("""
                    - AIによる要約は参考情報です。重要な決定には必ず原文を確認してください
                    - 検索結果が多い場合、処理に時間がかかることがあります
                    - 本文は最大2000文字まで使用されます
                    - Gemini APIの利用制限に応じて、一度に処理できる件数に制限があります
                    """)
        else:
            st.warning("まず検索条件を設定してください。")