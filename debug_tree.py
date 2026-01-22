"""
ツリー生成デバッグ用スクリプト
"""

import streamlit as st
import pandas as pd
from st_ant_tree import st_ant_tree
from typing import List
import json

st.set_page_config(page_title="ツリーデバッグ", layout="wide")

# jichitai.xlsxの読み込み
@st.cache_data
def load_jichitai():
    df = pd.read_excel("jichitai.xlsx", dtype={"code": str, "affiliation_code": str})
    df["code"] = df["code"].str.zfill(6)
    df["affiliation_code"] = df["affiliation_code"].str.zfill(2)
    return df

# メイン処理
st.title("🌳 自治体ツリー デバッグ")

# まず最小限のテストデータで試す
st.markdown("## ステップ1: 最小限のテストデータ")

test_tree = [
    {
        "title": "テスト親ノード",
        "value": "parent_01",
        "key": "parent_01",
        "children": [
            {"title": "子ノード1", "value": "child_01", "key": "child_01"},
            {"title": "子ノード2", "value": "child_02", "key": "child_02"},
        ]
    }
]

st.write("テストデータ:")
st.json(test_tree)

st.write("テストツリー表示:")
test_result = st_ant_tree(
    treeData=test_tree,
    treeCheckable=True,
    allowClear=True,
    showSearch=True,
     key="test_tree_1"
)

st.write("選択結果:")
st.write(test_result)

st.markdown("---")
st.markdown("## ステップ2: 実データでの生成")

# データ読み込み
try:
    jichitai = load_jichitai()
    st.success(f"✅ jichitai.xlsx 読み込み成功: {len(jichitai)}件")
    
    # 最初の数行を表示
    st.write("データサンプル:")
    st.dataframe(jichitai.head())
    
    # 都道府県を1つだけ使って簡単なツリーを作る
    st.markdown("### 北海道のみのツリー")
    
    hokkaido = jichitai[jichitai["affiliation_code"] == "01"].head(5)  # 最初の5市区町村のみ
    
    children = []
    for _, city in hokkaido.iterrows():
        children.append({
            "title": f"{city['city_name']} ({city['city_type']})",
            "value": city["code"],
            "key": city["code"],
        })
    
    simple_tree = [
        {
            "title": f"北海道 ({len(children)}件)",
            "value": "pref_01",
            "key": "pref_01",
            "children": children
        }
    ]
    
    st.write("生成されたツリーデータ:")
    st.json(simple_tree)
    
    # JSON として有効か確認
    try:
        json_str = json.dumps(simple_tree, ensure_ascii=False)
        st.success("✅ JSON形式として有効です")
    except Exception as e:
        st.error(f"❌ JSON変換エラー: {e}")
    
    st.write("ツリー表示:")
    simple_result = st_ant_tree(
        treeData=simple_tree,
        treeCheckable=True,
        allowClear=True,
        showSearch=True,
        key="simple_tree_2"
    )
    
    st.write("選択結果:")
    st.write(simple_result)
    
except FileNotFoundError:
    st.error("❌ jichitai.xlsx が見つかりません")
except Exception as e:
    st.error(f"❌ エラー: {e}")
    import traceback
    st.code(traceback.format_exc())