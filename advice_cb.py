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
st.markdown(
    "<h5 style='text-align: center; font-weight: 100'>고민을 입력해 주시면 상담을 진행하고, 충분한 대화 맥락이 형성되면 적절한 쿠팡 제품을 추천해 드립니다.</h5>",
    unsafe_allow_html=True,
)

# 좌우 여백을 위해 전체 UI를 세 열로 분할 (왼쪽, 중앙, 오른쪽)
left_col, center_col, right_col = st.columns([2, 5, 2])

with center_col:
    # 대화 기록 초기화
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "안녕하세요! 먼저 당신의 고민을 자유롭게 말씀해 주세요."}
        ]
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    # OpenAI 모델 설정
    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)

    # 사용자 맞춤형 프롬프트 템플릿
    custom_prompt = PromptTemplate(
        input_variables=["history", "input"],
        template="""
        당신은 친절하고 섬세한 상담 챗봇입니다.
        사용자가 고민을 이야기하면 먼저 공감하고 추가 질문을 통해 상담을 진행하십시오.
        충분한 상담이 이루어졌다고 판단되면, 적절한 제품이 있을 경우 하나만 추천하십시오.
        단, 무리하게 제품을 추천하지 말고 대화 맥락이 충분하다고 판단될 때만 추천하세요.

        **출력 형식 예시**:
        - 고민 요약:
        - 해결 방법:
        - 추천 제품: (제품 추천이 필요하다고 판단될 경우만 표시)
        - 쿠팡 검색 키워드: (제품 추천이 필요할 경우만 제공)

        **입력 정보**:
        - 사용자 고민: {input}
        - 이전 대화 내용: {history}
        """
    )

    conversation_chain = ConversationChain(
        llm=llm,
        memory=st.session_state.memory,
        prompt=custom_prompt
    )

    # 기존 대화 내역 출력 (채팅 말풍선 스타일)
    for message in st.session_state.chat_history:
        with st.chat_message("user" if message["role"] == "user" else "assistant"):
            st.write(message["content"])

# 사용자 입력 받기 (입력창은 st.chat_input() 사용)
if prompt := st.chat_input("💬 고민을 입력하세요..."):
    # 사용자 메시지 추가
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    # 메모리에서 대화 기록 불러오기 (없으면 빈 문자열)
    chat_history_data = st.session_state.memory.load_memory_variables({})
    history = chat_history_data.get("history", "")
    
    # GPT 호출: 모델이 자율적으로 상담 후 제품 추천 여부를 결정
    response = conversation_chain.run({"history": history, "input": prompt})
    
    # 만약 GPT 응답에 "쿠팡 검색 키워드:"가 포함되어 있다면 제품 추천으로 판단하여 링크 생성
    match = re.search(r"쿠팡 검색 키워드:\s*(.+)", response)
    if match:
        recommended_product = match.group(1).strip()
        coupang_link = f"https://www.coupang.com/np/search?q={recommended_product.replace(' ', '+')}"
        response += f"\n\n🔗 [쿠팡에서 '{recommended_product}' 검색하기]({coupang_link})"
    
    # GPT 응답을 대화 내역에 추가
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.write(response)
    
    st.rerun()