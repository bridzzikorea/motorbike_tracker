import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from secure_login_app import SecureLoginApp

BASE_DIR = Path(__file__).resolve().parents[2]  # Bridzzi 폴더
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from util.data_load.google_sheet import get_now_datetime
from util.data_load.google_sheet import GoogleSheet


KAKAO_JAVASCRIPT_KEY = st.secrets["KAKAO_JAVASCRIPT_KEY"]

st.set_page_config(
    page_title="오토바이 트래커", 
    page_icon="🏍️",
    layout="wide"
)

# ✅ 세션당 한 번만 SecureLoginApp 인스턴스를 만들고 재사용
@st.cache_resource
def get_app() -> SecureLoginApp:
    return SecureLoginApp()


# 스크립트로 실행될 때
if __name__ == "__main__":
    app = get_app()  # 여기서 __init__은 세션당 한 번만 실행
    app.run()