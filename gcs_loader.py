"""
GCS（Google Cloud Storage）からファイルを読み込むモジュール
auth.xlsx、queryファイルをGCSから取得
"""

import io
import json
import pandas as pd
import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
from typing import Optional, Dict
from pathlib import Path


@st.cache_resource(show_spinner=False)
def get_gcs_client():
    """
    GCSクライアントを取得（キャッシュ付き）
    
    Returns:
        storage.Client: GCSクライアント
    """
    # Streamlit Secretsからサービスアカウント情報を取得
    try:
        # JSONキー全体がsecretsに保存されている場合
        if "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return storage.Client(credentials=credentials)
        
        # 個別の値として保存されている場合
        elif "GCS_PROJECT_ID" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info({
                "type": "service_account",
                "project_id": st.secrets["GCS_PROJECT_ID"],
                "private_key_id": st.secrets["GCS_PRIVATE_KEY_ID"],
                "private_key": st.secrets["GCS_PRIVATE_KEY"],
                "client_email": st.secrets["GCS_CLIENT_EMAIL"],
                "client_id": st.secrets["GCS_CLIENT_ID"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": st.secrets.get("GCS_CLIENT_CERT_URL", "")
            })
            return storage.Client(credentials=credentials)
        
        else:
            st.error("GCS認証情報が見つかりません。Streamlit Secretsに設定してください。")
            st.stop()
    
    except Exception as e:
        st.error(f"GCSクライアント初期化エラー: {e}")
        st.stop()


def get_gcs_bucket_name() -> str:
    """
    GCSバケット名を取得
    
    Returns:
        str: バケット名
    """
    bucket_name = st.secrets.get("GCS_BUCKET_NAME", "")
    if not bucket_name:
        st.error("GCS_BUCKET_NAME が設定されていません。")
        st.stop()
    return bucket_name


@st.cache_data(show_spinner=False, ttl=300)
def load_auth_from_gcs() -> Optional[pd.DataFrame]:
    """
    GCSからauth.xlsxを読み込み
    
    Returns:
        Optional[pd.DataFrame]: 認証データ、エラー時はNone
    """
    try:
        client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        bucket = client.bucket(bucket_name)
        
        # auth.xlsxのパス
        blob = bucket.blob("auth.xlsx")
        
        if not blob.exists():
            st.warning("auth.xlsx がGCSに存在しません。簡易認証モードで起動します。")
            return None
        
        # ファイルをダウンロード
        content = blob.download_as_bytes()
        
        # BytesIOを使ってpandasで読み込み
        df = pd.read_excel(io.BytesIO(content))
        
        # 必須列のチェック
        required_cols = [
            "username", "password", "display_name", "query_file", 
            "can_modify_query", "enabled",
            "can_show_count", "can_show_latest", "can_show_summary"
        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"auth.xlsx に必須列が不足: {missing_cols}")
            return None
        
        # データ型の変換（空欄を適切に処理）
        # can_modify_queryの処理（空欄の場合はNoneのまま保持）
        def parse_bool(val):
            """ブール値を安全にパース（空欄はNoneのまま返す）"""
            if pd.isna(val) or val == '' or str(val).strip() == '':
                return None
            return str(val).upper() in ['TRUE', '1', 'YES']
        
        df["can_modify_query"] = df["can_modify_query"].apply(parse_bool)
        
        # タブ表示権限の処理（空欄の場合はNoneのまま保持）
        df["can_show_count"] = df["can_show_count"].apply(parse_bool)
        df["can_show_latest"] = df["can_show_latest"].apply(parse_bool)
        df["can_show_summary"] = df["can_show_summary"].apply(parse_bool)
        
        # enabledの処理（デフォルトはTrue）
        df["enabled"] = df["enabled"].apply(lambda x: parse_bool(x) if parse_bool(x) is not None else True)
        
        # query_fileの処理（空欄はNoneに変換）
        df["query_file"] = df["query_file"].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() and str(x).lower() != 'nan' else None
        )
        
        return df
    
    except Exception as e:
        st.error(f"GCSからauth.xlsxの読み込みエラー: {e}")
        return None


@st.cache_data(show_spinner=False, ttl=300)
def load_query_from_gcs(filename: str) -> Optional[Dict]:
    """
    GCSからクエリJSONファイルを読み込み
    
    Args:
        filename: クエリファイル名（例: user_tokyo.json）
    
    Returns:
        Optional[Dict]: クエリデータ、エラー時はNone
    """
    if not filename:
        return None
    
    try:
        client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        bucket = client.bucket(bucket_name)
        
        # queryディレクトリ内のファイルパス
        blob_path = f"query/{filename}"
        blob = bucket.blob(blob_path)
        
        if not blob.exists():
            st.error(f"クエリファイルがGCSに存在しません: {blob_path}")
            return None
        
        # ファイルをダウンロード
        content = blob.download_as_string()
        
        # JSONとしてパース
        query_data = json.loads(content)
        
        return query_data
    
    except json.JSONDecodeError as e:
        st.error(f"クエリファイルのJSON形式が不正です: {e}")
        return None
    except Exception as e:
        st.error(f"GCSからクエリファイルの読み込みエラー: {e}")
        return None


def upload_auth_to_gcs(df: pd.DataFrame) -> bool:
    """
    auth.xlsxをGCSにアップロード（管理用）
    
    Args:
        df: アップロードするDataFrame
    
    Returns:
        bool: 成功時True
    """
    try:
        client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob("auth.xlsx")
        
        # DataFrameをExcelに変換
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='auth')
        
        # GCSにアップロード
        blob.upload_from_string(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        return True
    
    except Exception as e:
        st.error(f"GCSへのアップロードエラー: {e}")
        return False


def upload_query_to_gcs(filename: str, query_data: Dict) -> bool:
    """
    クエリJSONファイルをGCSにアップロード（管理用）
    
    Args:
        filename: ファイル名（例: user_tokyo.json）
        query_data: クエリデータ
    
    Returns:
        bool: 成功時True
    """
    try:
        client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        bucket = client.bucket(bucket_name)
        
        blob_path = f"query/{filename}"
        blob = bucket.blob(blob_path)
        
        # JSONとしてアップロード
        content = json.dumps(query_data, ensure_ascii=False, indent=2)
        blob.upload_from_string(content, content_type='application/json')
        
        return True
    
    except Exception as e:
        st.error(f"GCSへのアップロードエラー: {e}")
        return False


def list_query_files_in_gcs() -> list:
    """
    GCS上のqueryディレクトリ内のファイル一覧を取得
    
    Returns:
        list: ファイル名のリスト
    """
    try:
        client = get_gcs_client()
        bucket_name = get_gcs_bucket_name()
        bucket = client.bucket(bucket_name)
        
        # queryディレクトリ内のファイルを取得
        blobs = bucket.list_blobs(prefix="query/")
        
        files = []
        for blob in blobs:
            # ディレクトリ自体は除外
            if blob.name != "query/" and blob.name.endswith('.json'):
                filename = Path(blob.name).name
                files.append(filename)
        
        return files
    
    except Exception as e:
        st.error(f"GCSファイル一覧取得エラー: {e}")
        return []