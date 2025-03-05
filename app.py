import streamlit as st
import runpy

st.set_page_config(layout="wide")

# ✅ 세션 상태 초기화
if "selected_page" not in st.session_state:
    st.session_state.selected_page = None  # 선택된 페이지를 저장할 변수

# ✅ 메인 화면 표시
if st.session_state.selected_page is None:
    st.title("쿠팡 상담챗봇 및 답글생성 개발 프로젝트")
    st.write("쿠팡 사용자들인 판매자와 구매자들에게 편의성을 제공하기 위한 프로젝트입니다.")

# 홈 버튼
if st.sidebar.button("홈"):
    st.session_state.selected_page = None
    st.rerun()
    
# ✅ 사이드바 메뉴 (항상 유지됨)
st.sidebar.title("판매자용 메뉴")

# 🔽 모든 버튼을 개별적으로 실행하여 유지
if st.sidebar.button("상품문의 자동응답 시스템"):
    st.session_state.selected_page = "coupangQA"
    st.rerun()

if st.sidebar.button("1-2"):
    st.session_state.selected_page = "1-2"
    st.rerun()
if st.sidebar.button("1-3"):
    st.session_state.selected_page = "1-3"
    st.rerun()

st.sidebar.title("구매자용 메뉴")

if st.sidebar.button("리뷰 자동 정리 시스템"):
    st.session_state.selected_page = "auto_review"
    st.rerun()
if st.sidebar.button("고민에 따른 제품 추천 시스템"):
    st.session_state.selected_page = "advice_cb"
    st.rerun()
if st.sidebar.button("2-3"):
    st.session_state.selected_page = "2-3"
    st.rerun()

# ✅ 선택된 페이지에 따라 실행 (사이드바는 그대로 유지됨)
if st.session_state.selected_page == "coupangQA":
    runpy.run_path("coupangQA.py")
elif st.session_state.selected_page == "auto_review":
    runpy.run_path("auto_review.py")
elif st.session_state.selected_page == "advice_cb":
    runpy.run_path("advice_cb.py")
elif st.session_state.selected_page == "1-3":
    st.write("ℹ️ 정보 화면입니다.")
elif st.session_state.selected_page == "2-2":
    st.write("⚙️ 설정 화면입니다.")
elif st.session_state.selected_page == "2-3":
    st.write("ℹ️ 정보 화면입니다.")
else:
    st.write("❗ <<--- 페이지를 선택하세요.")