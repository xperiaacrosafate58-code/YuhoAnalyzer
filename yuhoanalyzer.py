import os
import time
import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
from google.api_core.exceptions import ResourceExhausted

# ページのレイアウト設定（ワイド画面で綺麗に表示）
st.set_page_config(page_title="銘柄検討インターフェイス", layout="wide")

st.title("銘柄検討インターフェイス")

# APIキーの設定
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    api_key = st.text_input("Gemini APIキーを入力してください", type="password")

if api_key:
    genai.configure(api_key=api_key)
    # エラーメッセージが指定している最新モデル名に変更
    model_name = 'gemini-3.8-flash'
else:
    st.warning("APIキーを入力してください。")

# 分析対象の企業名・銘柄コード入力
company_name = st.text_input("分析対象の企業名または銘柄コード（例: トヨタ自動車、7203 等）")

# PDFファイルのアップロード
uploaded_file = st.file_uploader("有価証券報告書PDFファイルを選択（任意）", type=["pdf"])

pdf_text = ""
if uploaded_file is not None:
    with st.spinner("PDFからテキストを抽出中..."):
        reader = PdfReader(uploaded_file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n"
    st.success(f"PDFの読み込みが完了しました（総ページ数: {len(reader.pages)}ページ）")

if api_key:
    col1, col2 = st.columns(2)
    
    run_with_pdf = False
    run_with_ai_only = False
    
    with col1:
        if st.button("分析を実行する"):
            if not company_name and not uploaded_file:
                st.warning("企業名を入力するか、PDFをアップロードしてください。")
            else:
                run_with_pdf = True
                
    with col2:
        if st.button("分析を実行する(PDF無)"):
            if not company_name:
                st.warning("企業名を入力してください。")
            else:
                run_with_ai_only = True

    if run_with_pdf or run_with_ai_only:
        with st.spinner("AIがデータを解析・抽出しています..."):
            try:
                model = genai.GenerativeModel(model_name)
                
                target_info = f"対象企業名: {company_name}\n" if company_name else ""
                
                if run_with_pdf and pdf_text:
                    target_info += f"\n【有価証券報告書データ】\n{pdf_text[:100000]}"
                else:
                    target_info += "\n※PDFが提供されていないため、AIの持つ知識に基づいて分析を行ってください。"

                prompt = f"""
以下の情報をもとに必要な情報を抽出し、以下の【出力フォーマット】に厳密に従ってMarkdown形式で出力してください。
有報のPDFデータがある場合はそれを優先し、情報が無い項目やPDFが無い場合は、AIの視点から推測・補足して埋めてください。

【出力フォーマット】
以下の3つのブロック（2つの表と1つの文章ブロック）に明確に分けて出力してください。余計な挨拶などは省き、構造化された出力のみを行ってください。

### 1. 業績推移
直近数年分（可能であれば過去4〜5年分および会社予想）の売上高・営業利益・経常利益とその前年同期比を以下のテーブルで出力してください。
| 決算期 | 売上高 | 前年同期比 | 営業利益 | 前年同期比 | 経常利益 | 前年同期比 |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| (例: 2022年10月期) | (数値) | (数値%) | (数値) | (数値%) | (数値) | (数値%) |

### 2. 投資指標・財務安全性
PERから有利子負債までの項目を、独立した以下のテーブルで出力してください。
| 項目 | 数値・内容 |
|:---|:---|
| PER | |
| PBR | |
| 配当利回り | |
| 信用倍率 | |
| 総資産額 | |
| 純資産額 | |
| 自己資本 | |
| 自己資本比率 | |
| 資本金 | |
| 利益剰余金 | |
| 有利子負債 | |

### 3. 定性分析（国内シェア・解散価値・中国依存度）
表には収めず、それぞれの項目について文章形式（各800文字以内）で詳細に記載してください。有報に記載がない場合やPDFが無い場合はAIの視点から補足してください。

- **国内シェア**: 
- **解散価値**: 
- **中国依存度**: 

---
{target_info}
"""
                
                # --- レート制限（429）発生時の自動リトライ処理 ---
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = model.generate_content(prompt)
                        result_text = response.text
                        break
                    except ResourceExhausted:
                        if attempt < max_retries - 1:
                            st.warning("APIの利用制限に達したため、15秒待機して自動再試行します...")
                            time.sleep(15)
                        else:
                            raise
                
                st.subheader("【分析・抽出結果】")
                st.markdown(result_text)
                
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")