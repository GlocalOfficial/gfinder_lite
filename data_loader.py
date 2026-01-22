"""
データ読み込みモジュール
マスターデータ（jichitai.xlsx, category.xlsx）の読み込みとキャッシュ
"""

from pathlib import Path
import pandas as pd
import streamlit as st


def get_data_path(filename: str) -> Path:
    """
    データファイルのパスを取得
    
    Args:
        filename: ファイル名
    
    Returns:
        Path: ファイルパス
    
    Raises:
        FileNotFoundError: ファイルが見つからない場合
    """
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
    """
    自治体マスターデータ（jichitai.xlsx）を読み込み
    
    Returns:
        pd.DataFrame: 自治体データ（code, affiliation_code, pref_name, city_name, city_type）
    """
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
    """
    カテゴリマスターデータ（category.xlsx）を読み込み
    
    Returns:
        pd.DataFrame: カテゴリデータ（category, category_name, short_name, order, group）
    """
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


def get_pref_master(jichitai: pd.DataFrame) -> pd.DataFrame:
    """
    都道府県マスターを生成
    
    Args:
        jichitai: 自治体データ
    
    Returns:
        pd.DataFrame: 都道府県データ（affiliation_code, pref_name, aff_num）
    """
    pref_master = (
        jichitai[["affiliation_code", "pref_name"]]
        .drop_duplicates()
        .assign(aff_num=lambda d: pd.to_numeric(d["affiliation_code"], errors="coerce"))
    )
    return pref_master