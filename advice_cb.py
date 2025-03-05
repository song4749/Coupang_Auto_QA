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
    "<h5 style='text-align: center; font-weight: 100'>고민을 입력해 주시면 상담을 진행하고, 상황에 맞는 적절한 쿠팡 제품을 추천해 드립니다.</h5>",
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
    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=OPENAI_API_KEY, temperature=0.8)

    # 사용자 맞춤형 프롬프트 템플릿
    custom_prompt = PromptTemplate(
        input_variables=["history", "input"],
        template="""
        당신은 친절하고 자연스럽게 상담하는 AI 챗봇입니다.  
        사용자의 고민을 듣고, 먼저 공감한 뒤 적절한 해결 방법을 제안하세요.  
        꼭 제품이 아니더라도 현실적인 해결 방법을 함께 제시하세요.  
        대화가 충분히 이루어졌다고 판단되면, 적절한 제품을 추천하세요.

        **제품 추천이 필요한 경우**:
        - 사용자가 **"추천", "구매", "살까", "뭐 사야 돼?", "어떤 게 좋아?"** 등의 말을 하면 즉시 제품을 추천하세요.
        - 사용자의 고민을 해결할 수 있는 제품이 있을 경우, 바로 제품을 추천하세요.
        - 단, 제품 추천 말고도 적절한 해결 방법이 있다면 그것도 함께 제시하세요.
        - 사용자가 명확한 제품을 원하면, 바로 추천하고 구매할 수 있도록 제품 추천과 쿠팡 검색 키워드를 제공합니다.

        **💡 쿠팡 검색 키워드 포맷:**
        - 추천 제품이 있을 경우, **한 줄 띄운 후** 아래와 같은 형식으로 표시하세요.
        쿠팡 검색 키워드: [제품명]

        **📝 출력 예시 1 (제품 추천이 필요 없는 경우):**
        출퇴근이 너무 힘드시군요. 매일 이동하는 게 피곤하고 지칠 수 있죠.
        혹시 대중교통 대신 자전거나 전동 킥보드를 고려해 보신 적 있나요?
        더 편리한 출퇴근 방법을 찾으면 시간이 절약될 수도 있어요!

        **📝 출력 예시 2 (자연스럽게 제품 추천이 이어지는 경우):**
        출퇴근이 너무 힘드시군요. 매일 이동하는 게 피곤하고 지칠 수 있죠.
        만약 이동 거리가 길다면 전동 킥보드 같은 이동수단을 고려해 보시는 것도 방법이에요.
        요즘은 가볍고 접이식 모델도 많아서 보관이 편리하답니다!
        쿠팡 검색 키워드: 전동 킥보드

        **📝 출력 예시 3 (사용자가 직접 제품 추천을 요청하는 경우):**
        전동 킥보드를 찾고 계시군요! 이동 거리에 따라 다양한 모델이 있어요.
        가성비 좋은 모델부터, 장거리 주행이 가능한 고급 모델까지 비교해 보세요.
        쿠팡 검색 키워드: 전동 킥보드

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