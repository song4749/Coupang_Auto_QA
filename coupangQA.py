import streamlit as st
from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx
import shutil
import os
import json
import time
from langchain_community.document_loaders import BSHTMLLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import sys
import subprocess
import jpg2text_run

sys.stdout.reconfigure(encoding='utf-8')

# .env 파일에서 환경 변수 로드
load_dotenv()

# ✅ HTML 파일이 있는 폴더 경로
html_folder_path = "ocr_texts"  # 여러 개의 HTML 파일이 있는 폴더

# ✅ OpenAI Embeddings 설정
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 🚨 크롤링 제한 설정
MAX_CRAWL_ATTEMPTS = 3  # 최대 3번
RESET_TIME = 2 * 60 * 60  # 2시간 (초 단위)
CRAWL_LOG_FILE = "user_ip_data.json"  # 사용자 크롤링 기록을 저장할 JSON 파일


def get_api_key():
    # 환경 변수 가져오기
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None:
        st.error("🚨 OpenAI API 키가 설정되지 않았습니다! .env 파일을 확인하세요.")
    else:
        st.toast("✅ OpenAI API 키가 정상적으로 로드되었습니다.")


# @st.cache_resource
def load_vector_store():
    vectorstore = None  

    # ✅ HTML 폴더 내 모든 파일을 벡터 DB로 저장
    for filename in os.listdir(html_folder_path):
        if filename.endswith(".html"):
            file_path = os.path.join(html_folder_path, filename)
            try:
                # ✅ 각 HTML 파일을 개별 문서로 로드
                loader = BSHTMLLoader(file_path, open_encoding="utf-8", bs_kwargs={"features": "html.parser"})
                documents = loader.load()

                # ✅ 벡터스토어 생성 (첫 번째 문서)
                if vectorstore is None:
                    vectorstore = FAISS.from_documents(documents, embeddings)
                else:
                    vectorstore.add_documents(documents)  # 기존 DB에 추가

                print(f"✅ {filename} 처리 완료! ({len(documents)}개 문서 추가됨)")

                # ✅ HTML 파일 삭제
                os.remove(file_path)

            except Exception as e:
                print(f"❌ {filename} 처리 중 오류 발생: {e}")
                continue  

    # ✅ 새로운 벡터 DB 저장
    if vectorstore:
        vectorstore.save_local("faiss_index")
        print("✅ 새로운 벡터 데이터베이스 저장 완료!")
        return vectorstore
    else:
        print("⚠️ 벡터스토어 생성 실패. HTML 파일을 확인하세요.")
        return None
        

# ✅ 벡터 DB 삭제 함수
def delete_vector_db():
    """벡터 DB 삭제 함수"""
    if os.path.exists("faiss_index"):
        shutil.rmtree("faiss_index")
        print("🗑 벡터 DB 삭제 완료!")


# ✅ JSON 파일이 없으면 자동 생성
def initialize_crawl_data():
    if not os.path.exists(CRAWL_LOG_FILE):
        with open(CRAWL_LOG_FILE, "w") as file:
            json.dump({}, file)  # 빈 JSON 객체 생성
        print(f"📂 {CRAWL_LOG_FILE} 파일이 생성되었습니다.")


# ✅ JSON 파일에서 크롤링 데이터 로드
def load_crawl_data():
    initialize_crawl_data()  # 파일이 없으면 생성
    try:
        with open(CRAWL_LOG_FILE, "r") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print("⚠️ JSON 파일이 손상되었습니다. 초기화합니다.")
        save_crawl_data({})  # 손상된 경우 초기화
        return {}


# ✅ JSON 파일에 크롤링 데이터 저장
def save_crawl_data(data):
    with open(CRAWL_LOG_FILE, "w") as file:
        json.dump(data, file, indent=4)


def get_user_ip() -> str:
    """클라이언트(사용자)의 실제 IP 가져오기"""
    try:
        ctx = get_script_run_ctx()
        if ctx is None:
            return "세션 없음"

        session_info = runtime.get_instance().get_client(ctx.session_id)
        if session_info is None:
            return "클라이언트 정보 없음"
        
        # ✅ 프록시 서버(Nginx, Caddy) 뒤에서 실행될 경우
        user_ip = session_info.request.headers.get("X-Forwarded-For")
        if user_ip:
            return user_ip.split(",")[0]  # 가장 앞의 IP가 실제 클라이언트 IP
        
        # ✅ 직접 실행 중인 경우
        return session_info.request.remote_ip
    
    except Exception as e:
        return f"오류 발생: {e}"


# ✅ IP별 크롤링 횟수 관리
def can_crawl(user_ip):
    crawl_data = load_crawl_data()
    now = time.time()

    # IP별 데이터가 없으면 초기화
    user_data = crawl_data.get(user_ip, {"count": 0, "last_time": now})

    # 2시간 경과 여부 확인
    if now - user_data["last_time"] > RESET_TIME:
        user_data["count"] = 0  # 크롤링 횟수 초기화
        user_data["last_time"] = now  # 시간 갱신
        crawl_data[user_ip] = user_data
        save_crawl_data(crawl_data)

    remaining_attempts = MAX_CRAWL_ATTEMPTS - user_data["count"]
    return user_data["count"] < MAX_CRAWL_ATTEMPTS, remaining_attempts  # 크롤링 가능 여부 반환
    

# ✅ 버튼 클릭 시 크롤링 횟수 증가하는 함수
def update_crawl_count(user_ip):
    crawl_data = load_crawl_data()
    now = time.time()

    if user_ip in crawl_data:
        crawl_data[user_ip]["count"] += 1  # ✅ 버튼 클릭 시에만 크롤링 횟수 증가
        crawl_data[user_ip]["last_time"] = now  # 마지막 크롤링 시간 업데이트
    else:
        crawl_data[user_ip] = {"count": 1, "last_time": now}  # 새 사용자 추가

    save_crawl_data(crawl_data)  # JSON 파일 저장


def copy_files(src_folder, dst_folder="."):
    """주어진 폴더의 모든 파일 및 하위 폴더를 복사"""
    folders_to_clear = ["download_images", "main_image", "ocr_texts"]
    for folder in folders_to_clear:
        if os.path.exists(folder):  # ✅ 폴더 존재 확인
            shutil.rmtree(folder)   # ✅ 폴더와 내부 모든 파일 삭제

    if not os.path.exists(src_folder):  # ✅ 원본 폴더가 존재하는지 확인
        st.error(f"❌ 원본 폴더 '{src_folder}'이(가) 존재하지 않습니다!")
        return False

    for item in os.listdir(src_folder):
        src_path = os.path.join(src_folder, item)
        dst_path = os.path.join(dst_folder, item)

        if os.path.isdir(src_path):  # ✅ 폴더 복사
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:  # ✅ 파일 복사
            shutil.copy2(src_path, dst_path)

    return True


def get_link_content(file_path):
    """📌 링크 파일 (link.txt)의 내용을 읽어 반환하는 함수"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()  # ✅ 공백 제거 후 반환
    except FileNotFoundError:
        return "🚨 링크 파일을 찾을 수 없습니다."
    except Exception as e:
        return f"❌ 오류 발생: {e}"
    

# # ✅ Streamlit 세션 상태 확인 및 벡터 DB 삭제 로직 적용
# if "session_active" not in st.session_state:
#     # 🚀 세션이 새로 시작됨 (즉, 새로고침 또는 페이지 닫기 후 다시 접속한 경우)
#     st.cache_resource.clear()
#     delete_vector_db()  # ✅ 벡터 DB 삭제 실행
    

# # ✅ 세션 상태에서 크롤링 횟수 관리 (최초 실행 시 초기화)
# if "crawl_count" not in st.session_state:
#     st.session_state.crawl_count = 0

# Streamlit UI
st.markdown("<h1 style='text-align: center;'>쿠팡 상품문의 자동응답 시스템</h1>", unsafe_allow_html=True)
st.markdown("<h5 style='text-align: center; font-weight: 100'>쿠팡 상품 링크와 관련 문의를 입력하시면 자동으로 답변해 드립니다!<br><br><br></h5>", unsafe_allow_html=True)
left, right = st.columns([0.7, 0.3])

if "product_name" not in st.session_state:
    st.session_state.product_name = None
if "product_image" not in st.session_state:
    st.session_state.product_image = None
if "image_displayed" not in st.session_state:
    st.session_state.image_displayed = False

# ✅ 오른쪽에 이미지 표시할 공간 미리 생성
right_display_text = right.container()
right_display_image = right.container()

with right_display_text:
    st.markdown("<span style='font-size: 18px; font-weight: bold;'>검색하신 상품:</span>", unsafe_allow_html=True)

with left:
    st.warning(
        """
        ⚠️ **주의:**  
        쿠팡에서는 **동일 IP로 반복적인 요청이 발생할 경우**, 접속이 **제한될 수 있습니다**.  

        🔹 **검색 가능 횟수:**  
        - 현재 ip당 최대 **3번까지 가능**  
        - 이후에는 **2시간 후 다시 이용**해야 합니다.  
        - 질문은 무제한 입니다.

        🚨 **만약 서버 IP가 차단되어 검색이 불가능한 경우**  
        아래 **"Test" 버튼** 중 하나를 눌러 **미리 저장된 정보를 가져올 수 있습니다.**

        **-- 현재 쿠팡이 서버 ip차단중: Test 데이터만 이용 가능 --**
        """
    )
    
    if "selected_link" not in st.session_state:
        st.session_state.selected_link = None
    if "link_content" not in st.session_state:
        st.session_state.link_content = None

    col1, col2, col3, col4 = st.columns([0.15, 0.15, 0.15, 0.55])
    copy_success = False

    with col1:
        if st.button("Test - 냉장고"):
            copy_success = copy_files("test/case1")
            st.session_state.selected_link = "test/case1/main_image/link.txt"
            st.session_state.link_content = get_link_content(st.session_state.selected_link)

            with open("main_image/product_name.txt", "r", encoding="utf-8") as file:
                st.session_state.product_name = file.read().strip()
            st.session_state.product_image = "main_image/main_image.jpg"
            st.session_state.image_displayed = True

    with col2:
        if st.button("Test - 세탁기"):
            copy_success = copy_files("test/case2")
            st.session_state.selected_link = "test/case2/main_image/link.txt"
            st.session_state.link_content = get_link_content(st.session_state.selected_link)

            with open("main_image/product_name.txt", "r", encoding="utf-8") as file:
                st.session_state.product_name = file.read().strip()
            st.session_state.product_image = "main_image/main_image.jpg"
            st.session_state.image_displayed = True


    with col3:
        if st.button("Test - 청소기"):
            copy_success = copy_files("test/case3")
            st.session_state.selected_link = "test/case3/main_image/link.txt"
            st.session_state.link_content = get_link_content(st.session_state.selected_link)

            with open("main_image/product_name.txt", "r", encoding="utf-8") as file:
                st.session_state.product_name = file.read().strip()
            st.session_state.product_image = "main_image/main_image.jpg"
            st.session_state.image_displayed = True

    
    if copy_success:
        st.success("✅ 테스트 데이터 준비 완료! 이미지 크롤링 실행 버튼을 눌러 주세요.")

    with col4:
        if st.session_state.link_content:  # 버튼을 눌러서 값이 설정된 경우만 표시
            st.info(f"선택된 파일 링크: `{st.session_state.link_content}`")

    initialize_crawl_data()

    # 사용자 IP 가져오기
    user_ip = get_user_ip()

    st.info(f"📌 현재 당신의 IP: `{user_ip}`")

    link = st.text_area("🔗 상품 판매링크를 입력하세요:", placeholder="https://www.coupang.com/vp/products/123456...")

    # 크롤링 가능 여부 확인
    can_crawl_now, remaining_attempts = can_crawl(user_ip)

    # ✅ UI에 남은 크롤링 횟수를 표시할 공간 만들기
    remaining_attempts_display = st.empty()
    remaining_attempts_display.write(f"🔹 남은 크롤링 횟수: {remaining_attempts}회")

with left:
    if can_crawl_now:
        if st.button("🖼 이미지 크롤링 실행"):
            if link:
                # ✅ 버튼을 클릭했을 때만 크롤링 횟수 증가
                update_crawl_count(user_ip)

                # ✅ 남은 크롤링 횟수를 즉시 업데이트
                can_crawl_now, remaining_attempts = can_crawl(user_ip)

                # ✅ 기존 `st.write()`를 지우고 새로운 값 출력
                remaining_attempts_display.empty()  # 기존 UI 삭제
                remaining_attempts_display.write(f"🔹 남은 크롤링 횟수: {remaining_attempts}회")

                if remaining_attempts == 0:
                    st.error("🚨 크롤링 허용 횟수를 초과했습니다! 2시간 후 다시 시도해주세요.")

                # ✅ 기존 벡터 DB 삭제 후 초기화
                delete_vector_db()
                st.session_state.vectorstore = None  # 벡터 DB 캐시 제거

                # ✅ jpg_crowling.py 실행 (이미지 크롤링)
                with st.spinner("🔄 이미지 가져오는 중..."):
                    subprocess.run(["python", "jpg_crowling.py", link])     # 이것도 import 를 하면 playwright 와 asyncio 가 충돌한다. 따라서 크롤링 코드는 별도의 프로세스로 실행

                st.toast("✅ 이미지 크롤링 완료!")

                # 메인 사진, 이름 표시
                with open("main_image/product_name.txt", "r", encoding="utf-8") as file:
                    st.session_state.product_name = file.read().strip()
                st.session_state.product_image = "main_image/main_image.jpg"
                st.session_state.image_displayed = True

                # ✅ jpg2text_run.py 실행 (이미지 → 텍스트 변환)
                with st.spinner("🔄 이미지 변환 중..."):
                    jpg2text_run.main()

                st.toast("✅ 변환 완료! 데이터가 저장되었습니다.")

                with st.spinner("🔄 정보 저장 중..."):
                    # ✅ OCR 변환된 HTML 파일을 벡터 DB에 추가
                    vectorstore = load_vector_store()

                if vectorstore:
                    st.session_state.vectorstore = vectorstore
                else:
                    st.error("⚠️ 데이터 생성 실패: 링크가 올바른지 확인해 주세요.")
                
                # ✅ 벡터 DB가 필요할 경우 세션 상태 업데이트
                st.session_state.data_ready = True

                st.toast("✅ 저장 완료! 질문받을 준비가 되었습니다.")

            else:
                st.error("❌ 링크를 입력하세요! (Test 파일의 경우 아무거나 입력)")
    else:
        # 🚨 크롤링 횟수 초과 시 경고 메시지 표시
        st.error("🚨 크롤링 허용 횟수를 초과했습니다! 2시간 후 다시 시도해주세요.")

if "data_ready" not in st.session_state:
    st.stop()  # 🚀 사용자가 링크 입력 후 실행되도록 중단

if st.session_state.image_displayed and st.session_state.product_name and st.session_state.product_image:
    with right:
        st.markdown(f"<span style='font-size: 18px;'>{st.session_state.product_name}</span>", unsafe_allow_html=True)
        st.image(st.session_state.product_image, caption="검색된 상품 이미지", use_container_width=True)

if "api_key_checked" not in st.session_state:
    with left:
        get_api_key()
    st.session_state.api_key_checked = True


# ✅ 벡터 데이터베이스 로드
vectorstore = st.session_state.vectorstore if "vectorstore" in st.session_state else load_vector_store()

# ✅ OpenAI LLM (GPT-4 Turbo) 설정
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.5)

# ✅ 문서 검색을 위한 Retriever 설정
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})  # 가장 관련 있는 3개 문서 검색

# ✅ Prompt 템플릿 설정 (검색된 문서를 포함한 질의 응답)
prompt_template = PromptTemplate(
    input_variables=["context", "question"],
    template="""
    당신은 고객 지원 챗봇입니다.  
    사용자의 질문에 대해 제공된 문서를 기반으로 정확하고 친절하게 답변하세요.  
    
    ✅ **답변 방식**  
    - 문서에서 관련 정보를 찾으면, 이를 바탕으로 **쉽고 명확하게 설명**하세요.  
    - 사용자가 이해하기 쉽게, **필요하면 추가 설명을 덧붙이세요**.  
    - 너무 짧거나 딱딱한 답변 대신, **친절하고 부드러운 톤으로 응답**하세요.  

    ❗ **문서에서 정확한 답을 찾지 못한 경우**  
    - 관련 정보가 있다면 **논리적으로 유추하여 답변**하세요.  
    - 예를 들어, 제품의 크기, 기능, 일반적인 사용 방법을 고려하여 **가장 적절한 답을 제공**하세요.  
    - 정확한 정보는 없지만 비슷한 사례가 있다면 이를 참고하여 **최대한 유용한 답을 제시**하세요.  

    ❌ **완전히 알 수 없는 경우**  
    - 그래도 확실한 정보가 없을 경우, "죄송합니다. 해당 질문에 대한 정확한 정보를 찾을 수 없습니다.  
      하지만 일반적으로 [유추된 정보]를 참고하시면 도움이 될 수 있습니다."라고 안내하세요.  
    - 보다 자세한 사항은 판매자에게 문의하도록 유도하세요.  

    🌟 **추가 사항**  
    - 문서에 있는 정보라도 **불확실하거나 애매하면**, 확실한 부분만 답변하세요.  
    - 판매자 문의를 유도할 때, **연락처 정보가 있으면 함께 제공**하세요.

    문서 내용:
    {context}

    사용자 질문:
    {question}

    답변:
    """
)

# ✅ RAG 기반 QA 시스템 생성
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=False,  # 참고한 문서도 함께 반환
    chain_type_kwargs={"prompt": prompt_template}
) if retriever else None

with left:
    user_input = st.text_area("✏️ 해당 상품에 관하여 궁금한 점을 물어봐 주세요", placeholder="ex) 배송이 얼마나 걸려?")

if "answer" not in st.session_state:
    st.session_state.answer = None  # 처음에는 답변 없음

with left:
    if st.button("질문하기") and qa_chain:
        if user_input:
            with st.spinner("🔄 질문 처리 중..."):
                response = qa_chain.invoke({"query": user_input})
                st.session_state.answer = response.get("result")
                
            if st.session_state.answer:
                st.markdown(f"📌 **답변:** \n\n{st.session_state.answer}")
        
        else:
            st.error("❌ 질문을 입력하세요!")