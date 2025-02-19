import sys
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import requests
from PIL import Image
from io import BytesIO

# ✅ Windows 환경에서 UTF-8로 출력되도록 설정
sys.stdout.reconfigure(encoding="utf-8")

save_folder = "download_images"

def get_html(url):
    """Playwright를 사용해 개발자 도구(F12)의 Elements와 같은 HTML을 가져오는 함수"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 브라우저 보이게 실행 (디버깅 가능)
        context = browser.new_context()
        page = context.new_page()

        # 사용자 에이전트 추가 (403 방지)
        page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.0.0 Safari/537.36'
        })

        # 페이지 이동 (HTML만 로드되면 가져오기)
        page.goto(url, timeout=60000, wait_until="domcontentloaded")

        # ✅ 모든 리소스 로드될 때까지 대기
        page.wait_for_load_state("load")

        # ✅ 특정 요소가 나올 때까지 대기 (상품 이미지가 있는 div)
        page.wait_for_selector("div.subType-IMAGE", timeout=10000)

        # ✅ JavaScript 실행 후 동적으로 생성된 HTML 가져오기
        html = page.evaluate("document.documentElement.outerHTML")

        browser.close()
        return html


def extract_filtered_images(html):
    """HTML에서 'subType-IMAGE' 클래스 내부의 jpg, png 이미지 URL만 추출"""
    soup = BeautifulSoup(html, "html.parser")

    # 'type-IMAGE_NO_SPACE' 내의 'subType-IMAGE' 찾기
    image_containers = soup.select("div.subType-IMAGE")

    image_urls = []

    for container in image_containers:
        # 해당 div 내의 모든 img 태그 찾기
        img_tags = container.find_all("img")

        for img in img_tags:
            img_url = img.get("src") or img.get("data-src")  # src가 없으면 data-src 체크

            if img_url and (".jpg" in img_url or ".png" in img_url):  # jpg 또는 png 파일만 필터링
                # 상대 URL이면 절대 URL로 변환
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                image_urls.append(img_url)

    return image_urls


def download_images(image_urls):
    """여러 개의 이미지 다운로드 후 저장"""
    for i, img_url in enumerate(image_urls, 1):
        # 저장 경로 설정 (이미지 확장자 유지)
        ext = img_url.split(".")[-1]  # 확장자 추출 (jpg, png 등)
        save_path = os.path.join(save_folder, f"image_{i}.{ext}")

        try:
            # 이미지 다운로드
            response = requests.get(img_url, stream=True)
            if response.status_code == 200:
                image = Image.open(BytesIO(response.content))
                image.save(save_path)
                print(f"✅ {i}. 이미지 저장 완료")
            else:
                print(f"❌ {i}. 이미지 저장 실패")
        except Exception as e:
            print(f"❌ {i}. 오류 발생: {e}")


# ✅ 테스트할 쿠팡 제품 URL
url = "https://www.coupang.com/vp/products/7245496425?itemId=18419322860&vendorItemId=85573616196&q=%EB%A1%9C%EB%B3%B4%EB%9D%BD&itemsCount=36&searchId=1172c9662582230&rank=13&searchRank=13&isAddedCart="
html_source = get_html(url)

# ✅ 특정 클래스 안에 있는 jpg, png 이미지 URL 추출
filtered_image_urls = extract_filtered_images(html_source)

# ✅ 결과 출력
print("총 이미지 개수:", len(filtered_image_urls))

# ✅ 이미지 다운로드 실행
download_images(filtered_image_urls)