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
    short_unique: pd.DataFrame,
    include_zero: bool = False
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
        include_zero: 0件の自治体も表示するか（デフォルト：False）
    
    Returns:
        pd.DataFrame: ピボットテーブル
    """
    df = df.copy()
    df["short_name"] = df["category"].map(cat_short_map(catmap)).fillna(df["category"].astype(str))
    value_col = "file_docs" if ("ファイル数" in count_mode) else "page_docs"
    
    if display_unit == "市区町村":
        # 検索結果があるデータをマージ
        merged = df.merge(jichitai.rename(columns={"code": "g"}), on="g", how="left")
        
        if include_zero:
            # 0件の自治体も含めるため、全自治体を基準にleft merge
            # カテゴリの全組み合わせを作成
            all_codes = jichitai["code"].unique()
            all_categories = short_unique["short_name"].unique()
            
            # 全組み合わせのDataFrameを作成
            all_combinations = pd.DataFrame([
                {"code": code, "short_name": cat}
                for code in all_codes
                for cat in all_categories
            ])
            
            # 自治体情報をマージ
            all_combinations = all_combinations.merge(
                jichitai[["code", "pref_name", "city_name", "city_type"]],
                on="code",
                how="left"
            )
            
            # 集計データをマージ（ない場合は0）
            merged_with_zero = all_combinations.merge(
                merged[["g", "short_name", value_col]].rename(columns={"g": "code"}),
                on=["code", "short_name"],
                how="left"
            )
            merged_with_zero[value_col] = merged_with_zero[value_col].fillna(0).astype(int)
            
            # ピボットテーブル作成
            pvt = merged_with_zero.pivot_table(
                index=["pref_name", "city_name", "city_type", "code"],
                columns="short_name",
                values=value_col,
                aggfunc="sum",
                fill_value=0,
                observed=True
            ).reset_index().sort_values(by=["code"]).drop(columns=["code"])
        else:
            # 元の処理（検索結果があるもののみ）
            pvt = merged.pivot_table(
                index=["pref_name", "city_name", "city_type", "g"],
                columns="short_name",
                values=value_col,
                aggfunc="sum",
                fill_value=0,
                observed=True
            ).reset_index().sort_values(by=["g"]).drop(columns=["g"])
        
        pvt["合計"] = pvt.drop(columns=["pref_name", "city_name", "city_type"]).sum(axis=1).astype(int)
        pvt = pvt.rename(columns={"pref_name": "都道府県", "city_name": "市区町村", "city_type": "自治体区分"})
        ordered = [s for s in short_unique["short_name"].tolist() if s in pvt.columns]
        return pvt[["都道府県", "市区町村", "自治体区分"] + ordered + ["合計"]]
    
    else:
        # 都道府県単位の処理
        df["g"] = df["g"].astype(str).str.zfill(2)
        merged = df.merge(pref_master.rename(columns={"affiliation_code": "g"}), on="g", how="left")
        
        if include_zero:
            # 0件の都道府県も含める
            all_prefs = pref_master["affiliation_code"].unique()
            all_categories = short_unique["short_name"].unique()
            
            # 全組み合わせのDataFrameを作成
            all_combinations = pd.DataFrame([
                {"affiliation_code": pref, "short_name": cat}
                for pref in all_prefs
                for cat in all_categories
            ])
            
            # 都道府県情報をマージ
            all_combinations = all_combinations.merge(
                pref_master[["affiliation_code", "aff_num", "pref_name"]],
                on="affiliation_code",
                how="left"
            )
            
            # 集計データをマージ（ない場合は0）
            pref_agg = merged.groupby(
                ["g", "aff_num", "pref_name", "short_name"], observed=True
            )[value_col].sum().reset_index()
            
            merged_with_zero = all_combinations.merge(
                pref_agg.rename(columns={"g": "affiliation_code"}),
                on=["affiliation_code", "short_name"],
                how="left",
                suffixes=("", "_y")
            )
            
            # aff_num, pref_nameの重複列を処理
            if "aff_num_y" in merged_with_zero.columns:
                merged_with_zero["aff_num"] = merged_with_zero["aff_num"].fillna(merged_with_zero["aff_num_y"])
                merged_with_zero = merged_with_zero.drop(columns=["aff_num_y"])
            if "pref_name_y" in merged_with_zero.columns:
                merged_with_zero["pref_name"] = merged_with_zero["pref_name"].fillna(merged_with_zero["pref_name_y"])
                merged_with_zero = merged_with_zero.drop(columns=["pref_name_y"])
            
            merged_with_zero[value_col] = merged_with_zero[value_col].fillna(0).astype(int)
            
            # ピボットテーブル作成
            pvt = merged_with_zero.pivot_table(
                index=["affiliation_code", "aff_num", "pref_name"],
                columns="short_name",
                values=value_col,
                aggfunc="sum",
                fill_value=0,
                observed=True
            ).reset_index()
        else:
            # 元の処理（検索結果があるもののみ）
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
        
        pvt = pvt.sort_values(by=["aff_num"])
        pvt["合計"] = pvt.drop(columns=[col for col in ["affiliation_code", "g", "aff_num", "pref_name"] if col in pvt.columns]).sum(axis=1).astype(int)
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