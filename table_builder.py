"""
テーブル構築モジュール
DataFrameの整形とピボットテーブルの生成
"""

import datetime
import pandas as pd


def fmt_month_from_epoch(v) -> str:
    """
    エポックミリ秒を 'YYYY年M月' 形式に変換
    
    Args:
        v: エポックミリ秒（int or None）
    
    Returns:
        str: 'YYYY年M月' または '―'
    """
    if v is None:
        return "―"
    try:
        dt = datetime.datetime.utcfromtimestamp(v / 1000.0) + datetime.timedelta(hours=9)
        return f"{dt.year}年{dt.month}月"
    except Exception:
        return "―"


def cat_short_map(catmap: pd.DataFrame) -> dict:
    """
    カテゴリID→short_nameのマッピング辞書を作成
    
    Args:
        catmap: カテゴリマスターデータ
    
    Returns:
        dict: {category: short_name}
    """
    return catmap.set_index("category")["short_name"].to_dict()


def build_counts_table(
    df: pd.DataFrame,
    jichitai: pd.DataFrame,
    pref_master: pd.DataFrame,
    catmap: pd.DataFrame,
    display_unit: str,
    count_mode: str,
    short_unique: pd.DataFrame
) -> pd.DataFrame:
    """
    件数集計テーブルを構築
    
    Args:
        df: 集計元データ（fetch_countsの結果）
        jichitai: 自治体マスターデータ
        pref_master: 都道府県マスターデータ
        catmap: カテゴリマスターデータ
        display_unit: 表示単位（'都道府県' or '市区町村'）
        count_mode: 集計単位（'ファイル数' or 'ページ数'）
        short_unique: ユニークなshort_nameリスト
    
    Returns:
        pd.DataFrame: ピボットテーブル
    """
    df = df.copy()
    df["short_name"] = df["category"].map(cat_short_map(catmap)).fillna(df["category"].astype(str))
    value_col = "file_docs" if ("ファイル数" in count_mode) else "page_docs"
    
    if display_unit == "市区町村":
        merged = df.merge(jichitai.rename(columns={"code": "g"}), on="g", how="left")
        pvt = merged.pivot_table(
            index=["pref_name", "city_name", "city_type", "g"],
            columns="short_name",
            values=value_col,
            aggfunc="sum",
            fill_value=0,
            observed=True
        ).reset_index().sort_values(by=["g"]).drop(columns=["g"])
        pvt["合計"] = pvt.drop(columns=["pref_name", "city_name", "city_type"]).sum(axis=1)
        pvt = pvt.rename(columns={"pref_name": "都道府県", "city_name": "市区町村", "city_type": "自治体区分"})
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        return pvt[["都道府県", "市区町村", "自治体区分"] + ordered + ["合計"]]
    else:
        df["g"] = df["g"].astype(str).str.zfill(2)
        merged = df.merge(pref_master.rename(columns={"affiliation_code": "g"}), on="g", how="left")
        pref_agg = merged.groupby(
            ["g", "aff_num", "pref_name", "short_name"], observed=True
        )[value_col].sum().reset_index()
        pvt = pref_agg.pivot_table(
            index=["g", "aff_num", "pref_name"],
            columns="short_name",
            values=value_col,
            aggfunc="sum",
            fill_value=0,
            observed=True
        ).reset_index()
        pvt = pvt.sort_values(by=["aff_num", "g"])
        pvt["合計"] = pvt.drop(columns=["g", "aff_num", "pref_name"]).sum(axis=1)
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        pvt = pvt[["pref_name"] + ordered + ["合計"]].rename(columns={"pref_name": "都道府県"})
        return pvt


def build_latest_table(
    df: pd.DataFrame,
    jichitai: pd.DataFrame,
    pref_master: pd.DataFrame,
    catmap: pd.DataFrame,
    display_unit: str,
    short_unique: pd.DataFrame
) -> pd.DataFrame:
    """
    最新収集月テーブルを構築
    
    Args:
        df: 集計元データ（fetch_latest_monthの結果）
        jichitai: 自治体マスターデータ
        pref_master: 都道府県マスターデータ
        catmap: カテゴリマスターデータ
        display_unit: 表示単位（'都道府県' or '市区町村'）
        short_unique: ユニークなshort_nameリスト
    
    Returns:
        pd.DataFrame: ピボットテーブル
    """
    df = df.copy()
    df["short_name"] = df["category"].map(cat_short_map(catmap)).fillna(df["category"].astype(str))
    # epoch → 'YYYY年M月'
    df["latest"] = df["latest_epoch"].apply(lambda v: fmt_month_from_epoch(v))
    
    if display_unit == "市区町村":
        merged = df.merge(jichitai.rename(columns={"code": "g"}), on="g", how="left")
        pvt = merged.pivot_table(
            index=["pref_name", "city_name", "city_type", "g"],
            columns="short_name",
            values="latest",
            aggfunc="max",
            fill_value="―",
            observed=True
        ).reset_index().sort_values(by=["g"]).drop(columns=["g"])
        pvt = pvt.rename(columns={"pref_name": "都道府県", "city_name": "市区町村", "city_type": "自治体区分"})
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        return pvt[["都道府県", "市区町村", "自治体区分"] + ordered]
    else:
        df["g"] = df["g"].astype(str).str.zfill(2)
        merged = df.merge(pref_master.rename(columns={"affiliation_code": "g"}), on="g", how="left")
        pref_agg = merged.groupby(
            ["g", "aff_num", "pref_name", "short_name"], observed=True
        )["latest"].max().reset_index()
        pvt = pref_agg.pivot_table(
            index=["g", "aff_num", "pref_name"],
            columns="short_name",
            values="latest",
            aggfunc="max",
            fill_value="―",
            observed=True
        ).reset_index()
        pvt = pvt.sort_values(by=["aff_num", "g"])
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        pvt = pvt[["pref_name"] + ordered].rename(columns={"pref_name": "都道府県"})
        return pvt