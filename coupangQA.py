import streamlit as st
import os
from langchain_community.document_loaders import BSHTMLLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()


def get_api_key():
    # 환경 변수 가져오기
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None:
        st.error("🚨 OpenAI API 키가 설정되지 않았습니다! .env 파일을 확인하세요.")
    else:
        st.success("✅ OpenAI API 키가 정상적으로 로드되었습니다.")


@st.cache_resource
def load_vector_store():
    """📌 벡터 저장소를 로드하거나, 없으면 새로 생성"""
    if os.path.exists("faiss_index"):
        return FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    else:
        vectorstore = None  
        for filename in os.listdir(html_folder_path):
            if filename.endswith(".html"):
                file_path = os.path.join(html_folder_path, filename)
                try:
                    # ✅ 각 HTML 파일을 개별 문서로 로드
                    loader = BSHTMLLoader(file_path, open_encoding="utf-8", bs_kwargs={"features": "html.parser"})
                    documents = loader.load()
                    
                    # ✅ 벡터스토어 생성 및 문서 추가
                    if vectorstore is None:
                        vectorstore = FAISS.from_documents(documents, embeddings)
                    else:
                        vectorstore.add_documents(documents)

                    print(f"✅ {filename} 처리 완료! ({len(documents)}개 문서 추가됨)")
                except Exception as e:
                    print(f"❌ {filename} 처리 중 오류 발생: {e}")
                    continue  

        # ✅ 벡터 DB 저장
        if vectorstore:
            vectorstore.save_local("faiss_index")
            print("✅ 벡터 데이터베이스 저장 완료!")
            return vectorstore
        else:
            print("⚠️ 벡터스토어 생성 실패. HTML 파일을 확인하세요.")
            return None
        

# Streamlit UI
st.title("쿠팡 자동응답 시스템")
st.write("쿠팡 상품 링크와 관련 질문을 입력하시면 자동으로 답변해 드립니다!")

user_input = st.text_area("✏️ 해당 상품에 관하여 궁금한 점을 물어봐 주세요", "")

get_api_key()

# ✅ HTML 파일이 있는 폴더 경로
html_folder_path = "ocr_texts"  # 여러 개의 HTML 파일이 있는 폴더

# ✅ OpenAI Embeddings 설정
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# ✅ 벡터 데이터베이스 로드 (캐싱 적용)
vectorstore = load_vector_store()

# ✅ OpenAI LLM (GPT-4 Turbo) 설정
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.3)

# ✅ 문서 검색을 위한 Retriever 설정
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})  # 가장 관련 있는 3개 문서 검색

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

    ❌ **문서에서 답을 찾지 못한 경우**  
    - "죄송합니다. 해당 질문에 대한 정확한 정보를 찾을 수 없습니다.  
    보다 자세한 사항은 판매자에게 문의해주세요." 라고 안내하세요.  

    🌟 **추가 사항**  
    - 문서에 있는 정보라도 **불확실하거나 애매하면**, 확실한 부분만 답변하세요.  
    - 판매자 문의를 유도할 때, **연락처 정보가 있으면 함께 제공**하세요.

    문서 내용:
    {context}

    사용자 질문:
    {question}

    답변:
    """,
)

# ✅ RAG 기반 QA 시스템 생성
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=False,  # 참고한 문서도 함께 반환
    chain_type_kwargs={"prompt": prompt_template}
)

# ✅ 질문 테스트 (예제)
if st.button("질문하기"):
    response = qa_chain.invoke({"query": user_input})
    answer = response.get("result")
    st.markdown(f"📌 답변 결과: \n\n{answer}")