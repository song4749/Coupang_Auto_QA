import os
import cv2
import numpy as np
import requests
import openai
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# .env 파일에서 환경 변수 로드
load_dotenv()

# ✅ 폴더 경로 설정
save_folder = "download_images"
cropped_folder = "cropped_images"
text_folder = "ocr_texts"

# Upstage Console API 설정
API_KEY = os.getenv("API_KEY")
UPLOAD_URL = os.getenv("UPLOAD_URL")

# 환경 변수 가져오기
client = openai.OpenAI(api_key = os.getenv("OPENAI_API_KEY"))
if client is None:
    print("🚨 OpenAI API 키가 설정되지 않았습니다! .env 파일을 확인하세요.")
else:
    print("✅ OpenAI API 키가 정상적으로 로드되었습니다.")


def split_vertical_with_overlap(image_path, output_folder, crop_height=5000, overlap=500):
    """
    긴 이미지를 일정한 높이로 나누되, 일정 부분을 겹쳐서 자르는 함수
    - image_path: 원본 이미지 경로
    - output_folder: 저장할 폴더
    - crop_height: 자를 높이 크기 (기본값: 800px)
    - overlap: 다음 이미지와 겹치는 부분 (기본값: 100px)
    """
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ 이미지 로드 실패: {image_path}")
        return []

    # 이미지 크기 가져오기
    height, width, _ = image.shape

    # 저장할 폴더 생성 (없으면 생성)
    os.makedirs(output_folder, exist_ok=True)

    count = 0
    y = 0  # 자를 위치
    base_name = os.path.splitext(os.path.basename(image_path))[0]  # 파일명 추출
    cropped_image_paths = []

    while y < height:
        # 만약 남은 높이가 crop_height보다 작다면 남은 부분만 자름
        if y + crop_height > height:
            cropped = image[y:height, 0:width]  # 남은 부분만 저장
        else:
            cropped = image[y:y+crop_height, 0:width]  # 일반적인 크롭

        # 크롭된 이미지 저장 경로
        save_path = os.path.join(output_folder, f"{base_name}_crop_{count}.jpg")
        cv2.imwrite(save_path, cropped)
        print(f"✅ 분할된 이미지 저장 완료: {save_path}")

        cropped_image_paths.append(save_path)  # OCR 수행을 위해 리스트에 추가
        count += 1

        # 다음 자를 위치를 조정 (겹치는 부분을 빼고 이동)
        y += crop_height - overlap

    print(f"📌 총 {count}개의 이미지로 분할 완료!")

    os.remove(image_path)
    
    return cropped_image_paths  # 분할된 이미지 경로 리스트 반환


def preprocess_image(image_path):
    """OCR 전처리를 위한 이미지 변환 및 노이즈 제거"""
    # 이미지 불러오기 (Grayscale 변환)
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # 선명하게 하기 (Sharpening)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])  # 샤프닝 필터
    img = cv2.filter2D(img, -1, kernel)

    # 전처리된 이미지 저장 (디버깅용)
    preprocessed_path = image_path.replace(".jpg", "_processed.jpg").replace(".png", "_processed.png")
    cv2.imwrite(preprocessed_path, img)

    os.remove(image_path)

    return preprocessed_path


def process_ocr_to_html(image_path):
    """이미지를 OCR하여 HTML로 변환 후 저장 (중복 저장 문제 해결)"""

    # 1️⃣ OCR 수행 (파일 업로드)
    with open(image_path, "rb") as image_file:
        files = {"document": image_file}  # ✅ 'document' 키로 전송
        headers = {"Authorization": f"Bearer {API_KEY}"}
        data = {"ocr": "force", "model": "document-parse"}

        response = requests.post(UPLOAD_URL, headers=headers, files=files, data=data)

        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}, {response.text}")
            return False

        ocr_data = response.json()

    # 2️⃣ HTML 변환
    html_content = ocr_data.get("content", {}).get("html", "")

    if not html_content:
        print("⚠ OCR 결과가 없습니다! API 응답을 확인하세요.")
        return False

    # 📂 저장 폴더 생성 (없으면 만들기)
    os.makedirs(text_folder, exist_ok=True)

    # 🔥 중복 방지를 위해 타임스탬프 기반 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"ocr_text_{timestamp}.html"
    output_path = os.path.join(text_folder, file_name)

    # 3️⃣ HTML 저장
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    print(f"✅ HTML 파일이 성공적으로 저장되었습니다: {output_path}")

    os.remove(image_path)
    
    return True


def merge_and_delete_html_files(html_folder, output_file):
    """여러 개의 HTML 파일을 하나로 합친 후 기존 파일 삭제"""
    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write("<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n<title>Merged HTML</title>\n</head>\n<body>\n")
        
        for file_name in sorted(os.listdir(html_folder)):  # 정렬된 순서로 파일 읽기
            if file_name.endswith('.html'):  # .html 파일만 처리
                file_path = os.path.join(html_folder, file_name)
                with open(file_path, 'r', encoding='utf-8') as infile:
                    outfile.write(infile.read())  # HTML 내용 추가
                    outfile.write("\n")  # 파일 구분을 위한 줄바꿈 추가
                print(f"✅ 합침: {file_name}")

        outfile.write("\n</body>\n</html>")  # HTML 태그 닫기

    print(f"🎉 모든 HTML 파일이 '{output_file}'로 합쳐졌습니다!")

    # ✅ 기존 HTML 파일 삭제
    for file_name in os.listdir(html_folder):
        if file_name.endswith('.html') and file_name != os.path.basename(output_file):
            file_path = os.path.join(html_folder, file_name)
            os.remove(file_path)  # 파일 삭제
            print(f"🗑 삭제 완료: {file_name}")

    print("🚀 기존 HTML 파일 삭제 완료!")


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


def correct_text_with_openai(input_text):
    """📌 OpenAI API (최신 버전)로 RAG 기반 검색 최적화 문서 정리"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", 
                 "content": 
                 """
                 이 문서는 RAG 기반 검색 데이터로 사용할 것입니다.
                 따라서 검색 최적화를 위해 다음과 같이 정리해 주세요.

                 1. **문서의 원래 의미를 유지하면서 문장을 다듬어 가독성을 높이세요.**  
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


def process_text_file(input_folder, output_folder):
    """OCR 결과 파일을 읽고 OpenAI로 수정한 후 별도 저장"""
    for filename in os.listdir(input_folder):
        if filename.endswith(".html"):  # HTML 파일만 처리
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            try:
                with open(input_path, "r", encoding="utf-8") as f:
                    ocr_text = f.read()

                print(f"🚀 OpenAI에 텍스트 전달 중... (파일: {input_path})")
                corrected_text = correct_text_with_openai(ocr_text)

                if corrected_text:
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(corrected_text)
                    print(f"✅ 수정된 텍스트 저장 완료: {output_path}")
                else:
                    print(f"⚠️ {filename} 처리 실패: OpenAI 응답 없음")
                    
            except FileNotFoundError:
                print(f"❌ 파일을 찾을 수 없습니다: {input_path}")


# ✅ OCR 실행할 이미지 리스트 (이미 다운로드된 이미지 목록 가져오기)
image_files = [os.path.join(save_folder, img) for img in os.listdir(save_folder) if img.endswith((".jpg", ".png", ".jpeg"))]

for image_path in image_files:
    print(f"🚀 처리 중: {image_path}")

    # 1️⃣ 이미지 전처리
    processed_image = preprocess_image(image_path)
    if processed_image is None:
        continue  # 전처리 실패 시 건너뜀

    # 2️⃣ 전처리된 이미지 분할
    cropped_images = split_vertical_with_overlap(processed_image, cropped_folder)

    # 3️⃣ OCR 수행
    for cropped_image in cropped_images:
        # perform_ocr_and_save(cropped_image)
        process_ocr_to_html(cropped_image)

print("🎉 모든 이미지 처리 완료!")

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

process_text_file(text_folder, text_folder)