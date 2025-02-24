import sys
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
import time
import random
from PIL import Image
from io import BytesIO

# ✅ Windows 환경에서 UTF-8로 출력되도록 설정
sys.stdout.reconfigure(encoding="utf-8")

save_folder = "download_images"
if not os.path.exists(save_folder):
    os.makedirs(save_folder)

# # ✅ 명령줄 인자로 URL을 받기
# if len(sys.argv) < 2:
#     print("❌ 사용법: python jpg_crowling.py <쿠팡 상품 URL>")
#     sys.exit(1)

# url = sys.argv[1]  # ✅ 명령줄에서 URL 받기


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

        # 페이지 이동 (HTML만 로드되면 가져오기)
        page.goto(url, timeout=60000, wait_until="load")

        page.wait_for_selector("div.subType-IMAGE img, div.subType-TEXT img", timeout=20000)

        # # ✅ 특정 요소가 나올 때까지 대기 (상품 이미지가 있는 div)
        # page.wait_for_selector("div.subType-IMAGE", timeout=10000)

        # ✅ JavaScript 실행 후 동적으로 생성된 HTML 가져오기
        html = page.evaluate("document.documentElement.outerHTML")

        browser.close()
        return html


def extract_filtered_images(html):
    """HTML에서 'subType-IMAGE' 클래스 내부의 jpg, png 이미지 URL만 추출"""
    soup = BeautifulSoup(html, "html.parser")

    # 'type-IMAGE_NO_SPACE' 내의 'subType-IMAGE' 찾기
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


# ✅ 쿠팡 제품 URL
url = "https://www.coupang.com/vp/products/8338421081?itemId=24078900518&vendorItemId=83384767739&q=%EB%83%89%EC%9E%A5%EA%B3%A0&itemsCount=27&searchId=31fcffc05584302&rank=0&searchRank=0&isAddedCart="
html_source = get_html(url)

# ✅ 특정 클래스 안에 있는 jpg, png 이미지 URL 추출
filtered_image_urls = extract_filtered_images(html_source)

# ✅ 결과 출력
print("총 이미지 개수:", len(filtered_image_urls))

# ✅ 이미지 다운로드 실행
download_images(filtered_image_urls)