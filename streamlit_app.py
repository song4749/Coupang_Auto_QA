import streamlit as st
import subprocess


# ✅ 크롤링 실행 함수
def run_crawler(link):
    """📌 `jpg_crowling.py` 실행 (상품 링크에서 이미지 크롤링)"""
    try:
        subprocess.run(["python", "jpg_crowling.py", link], check=True)

    except Exception as e:
        st.error(f"❌ 크롤링 오류 발생: {e}")


# ✅ OCR 실행 함수
def run_ocr():
    """📌 `jpg2text.ipynb` 실행 (이미지 → HTML 변환)"""
    try:
        subprocess.run(["jupyter", "nbconvert", "--execute", "jpg2text.ipynb"], check=True)

    except Exception as e:
        st.error(f"❌ OCR 오류 발생: {e}")


# ✅ 질의응답 실행 함수
def run_qa(question):
    """📌 `coupangQA.py` 실행 (RAG 기반 질의응답)"""
    try:
        result = subprocess.run(["python", "coupangQA.py", question], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        st.error(f"❌ 질의응답 오류 발생: {e}")
    

@st.cache_resource
def load_vector_store():
    vectorstore = None  

    # ✅ HTML 폴더 내 모든 파일을 다시 벡터 DB로 저장
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
    """세션이 종료될 때 벡터 DB 삭제"""
    if os.path.exists("faiss_index"):
        shutil.rmtree("faiss_index")
        print("🗑 세션 종료 감지 - 벡터 DB 삭제 완료!")


# ✅ Streamlit 세션 상태 확인 및 벡터 DB 삭제 로직 적용
if "session_active" not in st.session_state:
    # 🚀 세션이 새로 시작됨 (즉, 새로고침 또는 페이지 닫기 후 다시 접속한 경우)
    st.cache_resource.clear()
    delete_vector_db()  # ✅ 벡터 DB 삭제 실행


# ✅ Streamlit UI 실행
st.title("쿠팡 자동응답 시스템")
st.write("쿠팡 상품 판매링크를 입력하시고 관련 질문을 물어보시면 자동으로 답변해 드립니다!")

# 🔹 **크롤링, ocr 실행**
link = st.text_input("🔗 상품 판매링크를 입력하세요:")

if st.button("🖼 이미지 크롤링 실행"):
    if link:
        with st.spinner("🔄 이미지 가져오는 중..."):
            run_crawler(link)
        st.success("✅ 이미지 크롤링 완료!")

        with st.spinner("🔄 이미지 변환 중..."):
            run_ocr()
        st.success("✅ 변환 완료! 데이터가 저장되었습니다.")
    else:
        st.error("❌ 링크를 입력하세요!")



# 🔹 **질의응답 실행**
user_input = st.text_area("✏️ 해당 상품에 관하여 궁금한 점을 물어봐 주세요", "ex)배송이 얼마나 걸려?")
if st.button("질문하기"):
    if user_input:
        with st.spinner("🔄 질문 처리 중..."):
            answer = run_qa(user_input)
        st.markdown(f"📌 **답변:** \n\n{answer}")

    else:
        st.error("❌ 질문을 입력하세요!")