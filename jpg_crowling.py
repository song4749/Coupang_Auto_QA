import sys
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import re
import shutil
import requests
from PIL import Image
from io import BytesIO

# ✅ Windows 환경에서 UTF-8로 출력되도록 설정
sys.stdout.reconfigure(encoding="utf-8")

save_folder = "download_images"
main_image_folder = "main_image"
html_folder = "ocr_texts"
if not os.path.exists(save_folder):
    os.makedirs(save_folder)


def get_html(url):
    """Playwright를 사용해 HTML을 가져오는 함수"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--no-sandbox", "--disable-gpu"])  # 브라우저 보이게 실행 (디버깅 가능)
        context = browser.new_context()
        page = context.new_page()

        headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36"
        }
        page.set_extra_http_headers(headers)

        # ✅ 랜덤한 대기 시간 추가 (1.5 ~ 5초)
        # time.sleep(random.uniform(1.5, 5.0))

        try:
            # 페이지 이동 (HTML만 로드되면 가져오기)
            page.goto(url, timeout=60000, wait_until="load")

            if page.wait_for_selector("div.subType-IMAGE img, div.subType-TEXT img", timeout=20000):

                # ✅ JavaScript 실행 후 동적으로 생성된 HTML 가져오기
                html = page.evaluate("document.documentElement.outerHTML")
                browser.close()
                return html, True
            else:
                browser.close()
                return None, False
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            browser.close()
            return None, False


def extract_filtered_images(html):
    """HTML에서 특정 클래스 내부의 이미지 URL만 추출"""
    soup = BeautifulSoup(html, "html.parser")

    # 'subType-IMAGE','subType-TEXT' 찾기
    image_containers = soup.select("div.subType-IMAGE, div.subType-TEXT")

    image_urls = []

    # 🔹 가져올 이미지 확장자 목록 (대소문자 구분 없이 처리)
    valid_extensions = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "tiff"}

    for container in image_containers:
        # 해당 div 내의 모든 img 태그 찾기
        img_tags = container.find_all("img")

        for img in img_tags:
            img_url = img.get("src") or img.get("data-src")  # src가 없으면 data-src 체크

            if img_url:
                # 🔹 URL에서 확장자를 소문자로 변환하여 필터링
                ext = img_url.split(".")[-1].split("?")[0].lower()
                if ext in valid_extensions:
                    # 상대 URL이면 절대 URL로 변환
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    image_urls.append(img_url)

    return image_urls


def download_images(image_urls):
    """여러 개의 이미지 다운로드 후 저장"""
    for i, img_url in enumerate(image_urls, 1):
        # 저장 경로 설정 (이미지 확장자 유지)
        ext = img_url.split(".")[-1].split("?")[0]  # 확장자 추출 (jpg, png 등, URL에 ? 붙어 있는 경우 제거)
        if ext.lower() not in ["jpg", "jpeg", "png"]:  # 확장자가 이상하면 기본 jpg 사용
            ext = "jpg"
        save_path = os.path.join(save_folder, f"image_{i}.{ext}")

        try:
            # 이미지 다운로드
            response = requests.get(img_url, stream=True)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))

                # ✅ RGBA 또는 P 모드 이미지는 RGB로 변환 후 저장
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                image.save(save_path)  # 변환된 이미지 저장
                print(f"✅ {i}. 이미지 저장 완료: {save_path}")
            else:
                print(f"❌ {i}. 이미지 저장 실패: {img_url}")
        except Exception as e:
            print(f"❌ {i}. 오류 발생: {e}")


def product_image_and_name_download(html):
    soup = BeautifulSoup(html, "html.parser")
    img_tag = soup.find("img", class_="prod-image__detail")

    if img_tag:
        img_url = "https:" + img_tag["src"]  # src 값이 //로 시작하므로 https:를 붙여야 함

        img_response = requests.get(img_url)

        if img_response.status_code == 200:

            # 폴더가 존재하지 않으면 생성
            if not os.path.exists(main_image_folder):
                os.makedirs(main_image_folder)

            image_path = os.path.join(main_image_folder, "main_image.jpg")

            with open(image_path, "wb") as f:
                f.write(img_response.content)
            print("이미지 저장 완료: main_image.jpg")
        else:
            print("이미지 다운로드 실패")
    else:
        print("이미지를 찾을 수 없음")

    name = soup.find("h1", class_="prod-buy-header__title").text.strip()

    name_path = os.path.join(main_image_folder, "product_name.txt")
    if name:
        with open(name_path, "w", encoding="utf-8") as file:
            file.write(name)

    price_div = soup.find("div", class_="prod-price-onetime")
    if price_div:
        price_html = price_div.prettify()  # HTML을 보기 좋게 정리
        price_html = re.sub(r'\n\s*\n+', '\n', price_html)  # 여러 개의 연속된 줄바꿈을 하나로 줄이기
        price_html = re.sub(r'>\s+<', '><', price_html)  # 태그 사이의 불필요한 공백 제거

    price_path = os.path.join(html_folder, "price_info.html")
    with open(price_path, "w", encoding="utf-8") as file:
        file.write(price_html)


def basic_information(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="prod-delivery-return-policy-table essential-info-table")

    if table:
        if not os.path.exists(html_folder):
            os.makedirs(html_folder)
        
        file_path = os.path.join(html_folder, "basic_data.html")

        # 테이블 HTML 저장
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(table))

        print(f"테이블 HTML 저장 완료: {file_path}")
    else:
        print("테이블을 찾을 수 없음")


def delibery_data(html):
    soup = BeautifulSoup(html, "html.parser")
    li_element = soup.find_all("li", class_="product-etc tab-contents__content etc-new-style")

    if li_element:
        file_path = os.path.join(html_folder, "li_data.html")

        # 모든 <li> 태그를 하나의 HTML 파일에 저장
        with open(file_path, "w", encoding="utf-8") as f:
            for li in li_element:
                f.write(str(li) + "\n")  # HTML 그대로 저장 + 줄바꿈 추가

        print(f"<li> HTML 저장 완료: {file_path}")
    else:
        print("<li> 태그를 찾을 수 없음")


# ✅ 명령줄 인자로 URL을 받기
# if len(sys.argv) < 2:
#     print("❌ 사용법: python jpg_crowling.py <쿠팡 상품 URL>")
#     sys.exit(1)

# url = sys.argv[1]  # ✅ 명령줄에서 URL 받기

url = "https://www.coupang.com/vp/products/8338421081?itemId=24078900518&vendorItemId=83384767739&q=%EB%83%89%EC%9E%A5%EA%B3%A0&itemsCount=27&searchId=31fcffc05584302&rank=0&searchRank=0&isAddedCart="

# ✅ 쿠팡 제품 URL
html_source, S_or_F = get_html(url)

# ✅ 특정 클래스 안에 있는 jpg, png 이미지 URL 추출
filtered_image_urls = extract_filtered_images(html_source)

# ✅ 결과 출력
print("총 이미지 개수:", len(filtered_image_urls))

# ✅ 이미지 삭제(있다면) 후 다운로드 실행
if S_or_F:
    folders_to_clear = ["download_images", "main_image", "ocr_texts"]

    for folder in folders_to_clear:
        if os.path.exists(folder):  # ✅ 폴더 존재 확인
            for item in os.listdir(folder):  # ✅ 폴더 내부 파일 및 폴더 순회
                item_path = os.path.join(folder, item)
                
                if os.path.isfile(item_path):  # ✅ 파일이면 삭제
                    os.remove(item_path)
                elif os.path.isdir(item_path):  # ✅ 폴더이면 폴더 삭제 (하위 파일 포함)
                    shutil.rmtree(item_path)

    download_images(filtered_image_urls)

# 메인 이미지, 필수 표기정보, 배송/교환/반품 안내 다운로드
product_image_and_name_download(html_source)

basic_information(html_source)

delibery_data(html_source)