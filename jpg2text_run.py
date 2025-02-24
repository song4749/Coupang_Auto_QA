import os
import cv2
import numpy as np
import openai
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import aiofiles
import asyncio
import aiohttp
import sys

sys.stdout.reconfigure(encoding='utf-8')

# .env 파일에서 환경 변수 로드
load_dotenv()

# ✅ 폴더 경로 설정
save_folder = "download_images"
cropped_folder = "cropped_images"
text_folder = "ocr_texts"

# Upstage Console API 설정
API_KEY = os.getenv("UPSTAGE_API_KEY")
UPLOAD_URL = os.getenv("UPSTAGE_UPLOAD_URL")

# 환경 변수 가져오기
client = openai.OpenAI(api_key = os.getenv("OPENAI_API_KEY"))
if client is None:
    print("🚨 OpenAI API 키가 설정되지 않았습니다! .env 파일을 확인하세요.")
else:
    print("✅ OpenAI API 키가 정상적으로 로드되었습니다.")


async def split_vertical_with_overlap_async(image_path, output_folder, crop_height=5000, overlap=500):
    """
    📌 긴 이미지를 일정한 높이로 나누되, 일정 부분을 겹쳐서 비동기적으로 저장
    """
    image = await asyncio.to_thread(cv2.imread, image_path)
    if image is None:
        print(f"❌ 이미지 로드 실패: {image_path}")
        return []

    height, width, _ = image.shape
    os.makedirs(output_folder, exist_ok=True)

    count = 0
    y = 0  
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    cropped_image_paths = []
    tasks = []  

    while y < height:
        cropped = image[y:height, 0:width] if y + crop_height > height else image[y:y+crop_height, 0:width]
        save_path = os.path.join(output_folder, f"{base_name}_crop_{count}.jpg")

        task = asyncio.to_thread(cv2.imwrite, save_path, cropped)
        tasks.append(task)
        cropped_image_paths.append(save_path)  
        count += 1
        y += crop_height - overlap  

    await asyncio.gather(*tasks)  # ✅ 모든 이미지 저장 후 OCR 시작
    await asyncio.to_thread(os.remove, image_path)  

    return cropped_image_paths  # ✅ OCR을 위해 리스트 반환


async def preprocess_image_async(image_path):
    """📌 비동기 OCR 전처리 (Grayscale 변환 + 샤프닝)"""
    img = await asyncio.to_thread(cv2.imread, image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"❌ 이미지 전처리 실패: {image_path}")
        return None

    # 샤프닝 필터 적용
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    img = await asyncio.to_thread(cv2.filter2D, img, -1, kernel)

    # 새로운 파일 경로 설정
    preprocessed_path = image_path.replace(".jpg", "_processed.jpg").replace(".png", "_processed.png")

    # 비동기적으로 이미지 저장
    await asyncio.to_thread(cv2.imwrite, preprocessed_path, img)
    await asyncio.to_thread(os.remove, image_path)  # 원본 삭제

    return preprocessed_path  # 전처리된 이미지 경로 반환


async def process_ocr_to_html_async(image_path, session):   # upstage ocr
    """📌 비동기 OCR 수행 및 HTML 저장"""
    async with aiofiles.open(image_path, "rb") as image_file:
        image_data = await image_file.read()
    
    # 🔹 Multipart FormData 생성
    form_data = aiohttp.FormData()
    form_data.add_field("ocr", "force")  # OCR 강제 수행 옵션
    form_data.add_field("model", "document-parse")  # 모델 선택
    form_data.add_field("document", 
                        image_data, 
                        filename=os.path.basename(image_path), 
                        content_type="image/jpeg"
                        )

    headers = {"Authorization": f"Bearer {API_KEY}"}  # Content-Type은 자동 설정됨

    try:
        async with session.post(UPLOAD_URL, headers=headers, data=form_data) as response:
            if response.status != 200:
                print(f"❌ OCR 오류: {response.status}, {await response.text()}")
                await asyncio.to_thread(os.remove, image_path)  # ✅ OCR 실패해도 이미지 삭제
                return None

            ocr_data = await response.json()

    except Exception as e:
        print(f"❌ 비동기 OCR 요청 실패: {e}")
        await asyncio.to_thread(os.remove, image_path)  # ✅ 예외 발생 시에도 이미지 삭제
        return None

    # 🔹 OCR 결과 확인 및 HTML 파일 저장
    html_content = ocr_data.get("content", {}).get("html", "")
    if not html_content:
        print(f"⚠ OCR 결과가 없습니다! API 응답 확인 필요.")
        await asyncio.to_thread(os.remove, image_path)  # ✅ OCR 결과가 없어도 이미지 삭제
        return None

    os.makedirs(text_folder, exist_ok=True)

    # ✅ 파일명 생성: 원본 이미지 이름 + 타임스탬프 (마이크로초 포함)
    base_name = os.path.splitext(os.path.basename(image_path))[0]  # 확장자 제거
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # 마이크로초까지 포함
    file_name = f"{base_name}_{timestamp}.html"
    
    output_path = os.path.join(text_folder, file_name)

    async with aiofiles.open(output_path, "w", encoding="utf-8") as file:
        await file.write(html_content)

    await asyncio.to_thread(os.remove, image_path)

    print(f"✅ OCR 저장 완료: {output_path}")

    return output_path


async def process_images_and_ocr_async():
    """📌 다운로드된 모든 이미지를 비동기 처리 (분할 → 전처리 → OCR)"""
    image_files = [
        os.path.join(save_folder, img) 
        for img in os.listdir(save_folder) 
        if img.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".JPG"))
    ]

    async with aiohttp.ClientSession() as session:
        async def process_single_image(image_path):

            # 1️⃣ [이미지 분할] → 반드시 모든 분할이 완료될 때까지 대기
            cropped_images = await split_vertical_with_overlap_async(image_path, cropped_folder)
            if not cropped_images:
                print(f"⚠ 분할 실패: {image_path}")
                return  

            print(f"✅ 분할 완료: {image_path} → {len(cropped_images)}개 이미지 생성")

            # 2️⃣ [이미지 전처리] → 모든 분할된 이미지의 전처리 완료 대기
            preprocessed_images = []
            for cropped in cropped_images:
                processed = await preprocess_image_async(cropped)  # 개별 이미지 전처리
                if processed:
                    preprocessed_images.append(processed)

            if not preprocessed_images:
                print(f"⚠ 전처리 실패: {image_path}")
                return  

            print(f"✅ 전처리 완료: {image_path} → {len(preprocessed_images)}개 이미지 전처리됨")

            # 3️⃣ [OCR 실행] → 모든 전처리된 이미지에 대해 OCR 실행
            ocr_results = []
            for preprocessed in preprocessed_images:
                ocr_output = await process_ocr_to_html_async(preprocessed, session)
                if ocr_output:
                    ocr_results.append(ocr_output)

            if not ocr_results:
                print(f"⚠ OCR 결과 없음: {image_path}")
                return

            print(f"✅ OCR 완료: {image_path} → {len(ocr_results)}개 HTML 파일 생성됨")

        # ✅ 모든 이미지에 대해 순차적으로 처리 (각각의 이미지에 대해 `process_single_image` 실행)
        await asyncio.gather(*[process_single_image(img) for img in image_files])

    print(f"🎉 모든 이미지 OCR 완료!")

 
def clean_html_to_markdown_table(html_content):
    """HTML에서 표를 Markdown 형식으로 변환하고, 태그 속성을 제거하여 순수 텍스트만 추출하는 함수"""
    
    # BeautifulSoup으로 HTML 파싱
    soup = BeautifulSoup(html_content, "html.parser")

    # ✅ <img> 태그의 alt 속성을 텍스트로 변환
    for img in soup.find_all("img"):
        if img.has_attr("alt"):
            img.replace_with(img["alt"])  # 이미지 태그를 alt 속성값으로 대체

    # ✅ 모든 태그 속성 제거 (태그 자체는 유지)
    for tag in soup.find_all(True):
        tag.attrs = {}  # 속성 제거

    # ✅ <table> 태그를 Markdown 표로 변환
    for table in soup.find_all("table"):
        rows = []
        headers = table.find_all("th")  # 테이블 헤더 가져오기
        if headers:
            headers_text = [th.get_text(strip=True) for th in headers]
            rows.append("| " + " | ".join(headers_text) + " |")  # Markdown 헤더 추가
            rows.append("|" + "|".join(["-" * len(h) for h in headers_text]) + "|")  # 구분선 추가

        # 본문 데이터 처리
        for tr in table.find_all("tr"):
            cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cols:  # 빈 행이 아니면 추가
                rows.append("| " + " | ".join(cols) + " |")

        table_text = "\n".join(rows)  # Markdown 형식으로 변환
        table.replace_with(table_text)  # <table> 태그를 변환된 Markdown 텍스트로 대체

    # ✅ 최종적으로 순수 텍스트만 추출
    clean_text = soup.get_text(separator="\n", strip=True)

    return clean_text


async def correct_text_with_openai(input_text):
    """📌 OpenAI API (최신 버전)로 RAG 기반 검색 최적화 문서 정리"""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", 
                 "content": 
                 """
                 이 문서는 RAG 기반 검색 데이터로 사용할 것입니다.
                 따라서 검색 최적화를 위해 다음과 같이 정리해 주세요.

                 1. **문장을 최대한 변형시키지 말고 다듬어서 가독성을 높이세요.**  
                 2. **표(Table) 데이터는 원본 그대로 유지하세요.** (Markdown 표 `|` 형식 유지)  
                 3. **불필요한 중복 문장 및 공백을 제거하세요.**  
                 4. **문서의 계층 구조(제목, 소제목)를 유지하여 쉽게 검색할 수 있도록 하세요.**   
                 5. **필요한 경우, 목록(Bullet Point)을 활용하여 가독성을 높이세요.**  
                 6. **의미를 바꾸지 않도록 주의하고, 정보가 빠지지 않도록 유지하세요.**  
                 """
                },
                {"role": "user", "content": input_text}
            ]
        )

        # ✅ 최신 OpenAI SDK에서는 응답 데이터 접근 방식 변경됨
        corrected_text = response.choices[0].message.content

        return corrected_text

    except Exception as e:
        print(f"❌ OpenAI API 오류 발생: {e}")
        return None


async def process_text_file_async(input_folder, output_folder):
    """📌 OCR 결과 파일을 읽고 OpenAI로 수정한 후 비동기 처리하여 저장"""

    async def process_single_file(file_path, output_path):
        """개별 파일을 비동기적으로 처리하는 내부 함수"""
        try:
            # ✅ 비동기 파일 읽기
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                ocr_text = await f.read()

            print(f"🚀 OpenAI에 텍스트 전달 중... (파일: {file_path})")

            # ✅ 비동기 OpenAI API 호출
            corrected_text = await correct_text_with_openai(ocr_text)

            if corrected_text:
                # ✅ 비동기 파일 쓰기
                async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
                    await f.write(corrected_text)
                print(f"✅ 수정된 텍스트 저장 완료: {output_path}")
            else:
                print(f"⚠️ {file_path} 처리 실패: OpenAI 응답 없음")

        except FileNotFoundError:
            print(f"❌ 파일을 찾을 수 없습니다: {file_path}")

    # ✅ 모든 파일을 비동기적으로 처리
    tasks = []
    for filename in os.listdir(input_folder):
        if filename.endswith(".html"):  # HTML 파일만 처리
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            tasks.append(process_single_file(input_path, output_path))

    await asyncio.gather(*tasks)  # 모든 파일을 동시에 처리


asyncio.run(process_images_and_ocr_async())

for filename in os.listdir(text_folder):
        if filename.endswith(".html"):  # HTML 파일만 처리
            input_path = os.path.join(text_folder, filename)
            output_path = os.path.join(text_folder, filename)

            try:
                # ✅ 원본 HTML 파일 읽기
                with open(input_path, "r", encoding="utf-8") as file:
                    html_data = file.read()

                # ✅ HTML 정리 함수 실행
                cleaned_html = clean_html_to_markdown_table(html_data)

                # ✅ 정리된 HTML 저장
                with open(output_path, "w", encoding="utf-8") as file:
                    file.write(cleaned_html)

                print(f"✅ 정리된 HTML 저장 완료: {output_path}")

            except FileNotFoundError:
                print(f"❌ 파일을 찾을 수 없습니다: {input_path}")

asyncio.run(process_text_file_async(text_folder, text_folder))