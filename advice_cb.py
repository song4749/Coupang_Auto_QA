import streamlit as st
import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate
from langchain.chains import ConversationChain

# OpenAI API 키 불러오기
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

st.markdown("<h1 style='text-align: center;'>고민에 따른 제품 추천 시스템</h1>", unsafe_allow_html=True)
st.markdown("<h5 style='text-align: center; font-weight: 100'>고민을 입력해 주세요! 당신의 상황을 고려해 지금 가장 필요한 쿠팡 아이템을 추천해 드립니다.<br><br><br></h5>", unsafe_allow_html=True)

# ✅ 레이아웃 설정 (왼쪽/오른쪽 공백 추가)
left_space, chat_area, right_space = st.columns([2, 5, 2])

with chat_area:
    # OpenAI 모델 설정
    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)

    # ✅ 대화 내용을 기억하는 메모리 추가 (기본: 최근 10개 메시지 저장)
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    # ✅ 채팅 기록 저장 공간 초기화
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ✅ 사용자 맞춤형 프롬프트 템플릿 추가
    custom_prompt = PromptTemplate(
        input_variables=["history", "input"],
        template="""
        당신은 친절한 상담 챗봇입니다. 사용자가 고민을 이야기하면 공감해주고, 현실적인 해결책을 제안해야 합니다.
        고민을 듣고 그 상황에 필요한 제품을 추천해 주세요. 사용자가 학생인지, 직장인인지, 어느정도의 예산을 가지고 있는지 고려하세요.

        - 사용자 고민: {input}
        - 이전 대화 내용: {history}

        💡 출력 형식:
        - 고민 요약: 
        - 해결 방법:
        - 추천 제품: (한 개만 추천)
        - 쿠팡 검색 키워드: (추천 제품의 핵심 키워드, 짧게)
        """
    )

    # ✅ 대화형 체인 생성 (Retrieval 기능 추가 가능)
    conversation_chain = ConversationChain(
        llm=llm,
        memory=st.session_state.memory,
        prompt=custom_prompt
    )

    # 채팅 메시지 표시 (채팅 말풍선 스타일)
    for role, text in st.session_state.chat_history:
        with st.chat_message("user" if role == "👤 당신" else "assistant"):
            st.write(text)

# 고정된 입력창 영역 생성
user_input = st.chat_input("💬 고민을 입력하세요...")

# ✅ 응답 처리
if user_input:
    # ✅ chat_history 예외 처리 (없을 경우 빈 문자열 반환)
    chat_history_data = st.session_state.memory.load_memory_variables({})
    history = chat_history_data.get("history", "")

    # ✅ GPT에 요청하여 제품 추천 받기
    response = conversation_chain.run({"history": history, "input": user_input})

    # ✅ 추천 제품 추출 (GPT가 생성한 응답에서 제품명 찾기 - 정규식 사용)
    match = re.search(r"쿠팡 검색 키워드:\s*(.+)", response)
    recommended_product = match.group(1).strip() if match else None

    # ✅ 쿠팡 검색 링크 생성 (GPT가 추천한 제품으로)
    if recommended_product:
        coupang_link = f"https://www.coupang.com/np/search?q={recommended_product.replace(' ', '+')}"
        response += f"\n\n🔗 [쿠팡에서 '{recommended_product}' 검색하기]({coupang_link})"

    # ✅ 채팅 기록 저장
    st.session_state.chat_history.append(("👤 당신", user_input))
    st.session_state.chat_history.append(("🤖 챗봇", response))

    # ✅ 새 메시지 바로 표시 (입력 후 자동 스크롤)
    st.rerun()